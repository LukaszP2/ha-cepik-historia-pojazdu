from __future__ import annotations

import asyncio
import logging
import ssl
import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError, ClientTimeout, CookieJar
from homeassistant.core import HomeAssistant
if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_UPDATE_INTERVAL_HOURS,
    DOMAIN,
    ENGINE_URL,
    TIMELINE_URL,
    VEHICLE_URL,
)
from .models import CepikVehicleData

_LOGGER = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 30


class CepikCoordinator(DataUpdateCoordinator[CepikVehicleData]):
    def __init__(
        self,
        hass: HomeAssistant,
        registration: str,
        vin: str,
        first_registration_date: str,
        vehicle_id: str | None = None,
        update_interval_hours: int = DEFAULT_UPDATE_INTERVAL_HOURS,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        self.registration = registration
        self.vin = vin
        self.first_registration_date = first_registration_date
        self.vehicle_id = vehicle_id or vin
        self._ssl_ctx: ssl.SSLContext | None = None

        try:
            super().__init__(
                hass,
                _LOGGER,
                name=f"CEPiK {registration}",
                update_interval=timedelta(hours=update_interval_hours),
                config_entry=config_entry,
            )
        except TypeError:
            super().__init__(
                hass,
                _LOGGER,
                name=f"CEPiK {registration}",
                update_interval=timedelta(hours=update_interval_hours),
            )

    @staticmethod
    def _create_ssl_context() -> ssl.SSLContext:
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        return ctx

    async def _async_get_ssl_context(self) -> ssl.SSLContext:
        if self._ssl_ctx is None:
            self._ssl_ctx = await self.hass.async_add_executor_job(self._create_ssl_context)
        assert isinstance(self._ssl_ctx, ssl.SSLContext)
        return self._ssl_ctx

    async def async_validate(self) -> CepikVehicleData:
        return await self._async_update_data()

    async def _async_update_data(self) -> dict[str, Any]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept-Language": "pl,en-US;q=0.9,en;q=0.8",
        }
        nf_wid = f"HistoriaPojazdu:{int(time.time() * 1000)}"

        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                ssl_context = await self._async_get_ssl_context()
                session = async_create_clientsession(
                    self.hass,
                    cookie_jar=CookieJar(),
                    timeout=ClientTimeout(total=REQUEST_TIMEOUT),
                )

                # Inicjalizacja sesji
                async with session.get(
                    ENGINE_URL, headers=headers, allow_redirects=True, ssl=ssl_context
                ) as response:
                    await response.read()

                init_headers = {
                    **headers,
                    "Accept": "*/*",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "null",
                    "Referer": ENGINE_URL,
                }
                async with session.post(
                    ENGINE_URL,
                    data={"NF_WID": nf_wid},
                    headers=init_headers,
                    allow_redirects=True,
                    ssl=ssl_context,
                ) as response:
                    await response.read()

                xsrf_token = None
                for cookie in session.cookie_jar:
                    if cookie.key.upper() == "XSRF-TOKEN":
                        xsrf_token = cookie.value
                        break

                if not xsrf_token:
                    raise UpdateFailed("Nie udało się uzyskać tokenu XSRF.")

                api_headers = {
                    **headers,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Origin": "https://moj.gov.pl",
                    "Referer": ENGINE_URL,
                    "NF_WID": nf_wid,
                    "X-XSRF-TOKEN": xsrf_token,
                }
                payload = {
                    "registrationNumber": self.registration,
                    "VINNumber": self.vin,
                    "firstRegistrationDate": self.first_registration_date,
                }

                # 1. POBRANIE DANYCH GŁÓWNYCH (vehicle-data)
                async with session.post(
                    VEHICLE_URL,
                    json=payload,
                    headers=api_headers,
                    ssl=ssl_context,
                ) as response:
                    status = response.status
                    try:
                        data = await response.json(content_type=None)
                    except (ValueError, ClientError):
                        data = {"raw_response": await response.text()}

                if status != 200:
                    if isinstance(data, dict):
                        message = data.get("VALIDATION_ERROR_MSG")
                        if message:
                            raise UpdateFailed(message)
                    if status == 404:
                        raise UpdateFailed("Nie znaleziono pojazdu o podanych danych.")
                    if status == 406:
                        async_create_issue(
                            self.hass,
                            DOMAIN,
                            f"invalid_vehicle_{self.vehicle_id}",
                            is_fixable=False,
                            severity=IssueSeverity.WARNING,
                            translation_key="invalid_vehicle_credentials",
                            translation_placeholders={
                                "registration": self.registration,
                                "vin": self.vin,
                            },
                        )
                        raise UpdateFailed(
                            "API odrzuciło żądanie (HTTP 406). Sprawdź numer rejestracyjny, VIN i datę pierwszej rejestracji."
                        )
                    if status == 429:
                        retry_after = response.headers.get("Retry-After", "3600")
                        raise UpdateFailed(
                            f"Przekroczono limit zapytań do API (HTTP 429). Ponów za {retry_after}s."
                        )
                    raise UpdateFailed(f"API Historia Pojazdu zwróciło HTTP {status}.")

                async_delete_issue(self.hass, DOMAIN, f"invalid_vehicle_{self.vehicle_id}")

                if not isinstance(data, dict):
                    raise UpdateFailed("API zwróciło nieoczekiwany format danych.")

                # 2. POBRANIE OSI CZASU (timeline-data)
                async with session.post(
                    TIMELINE_URL,
                    json=payload,
                    headers=api_headers,
                    ssl=ssl_context,
                ) as tl_response:
                    if tl_response.status == 200:
                        try:
                            tl_data = await tl_response.json(content_type=None)
                            if isinstance(tl_data, dict):
                                # Zrzucamy oś czasu bezpośrednio do głównego obiektu, tak jak by była od początku
                                if "timelineData" in tl_data:
                                    data["timelineData"] = tl_data["timelineData"]
                                else:
                                    data["timelineData"] = tl_data
                        except (ValueError, ClientError) as e:
                            _LOGGER.warning("Nie udało się sparsować osi czasu z CEPiK: %s", e)
                    else:
                        _LOGGER.warning("Endpoint timeline zwrócił status: %s", tl_response.status)

            now_iso = datetime.now().astimezone().isoformat()
            return CepikVehicleData.from_dict(
                data={
                    "api": data,
                    "http_status": status,
                    "last_update": now_iso,
                },
                http_status=status,
                last_update=now_iso,
            )

        except UpdateFailed:
            raise
        except TimeoutError as err:
            raise UpdateFailed(f"Przekroczono limit czasu połączenia z CEPiK: {err}") from err
        except (ClientError, OSError, ssl.SSLError) as err:
            raise UpdateFailed(f"Błąd połączenia z CEPiK: {err}") from err
        except Exception as err:
            _LOGGER.exception("Nieoczekiwany błąd CEPiK")
            raise UpdateFailed(f"Nieoczekiwany błąd: {err}") from err
