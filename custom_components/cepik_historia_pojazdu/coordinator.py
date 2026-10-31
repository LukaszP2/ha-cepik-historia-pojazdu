from __future__ import annotations

from datetime import datetime, timedelta
import logging
import ssl
import time
from typing import Any

from aiohttp import ClientError, ClientSession, CookieJar
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ENGINE_URL, VEHICLE_URL, TIMELINE_URL, UPDATE_INTERVAL_HOURS

_LOGGER = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36"
)


class CepikCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self,
        hass: HomeAssistant,
        registration: str,
        vin: str,
        first_registration_date: str,
        vehicle_id: str | None = None,
    ) -> None:
        self.registration = registration
        self.vin = vin
        self.first_registration_date = first_registration_date
        self.vehicle_id = vehicle_id or vin
        self._nf_wid = f"HistoriaPojazdu:{int(time.time() * 1000)}"

        super().__init__(
            hass,
            _LOGGER,
            name=f"CEPiK {registration}",
            update_interval=timedelta(hours=UPDATE_INTERVAL_HOURS),
        )

    @staticmethod
    def _ssl_context() -> ssl.SSLContext:
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        return ctx

    async def async_validate(self) -> dict[str, Any]:
        return await self._async_update_data()

    async def _async_update_data(self) -> dict[str, Any]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept-Language": "pl,en-US;q=0.9,en;q=0.8",
        }

        try:
            ssl_context = await self.hass.async_add_executor_job(self._ssl_context)
            async with ClientSession(cookie_jar=CookieJar()) as session:
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
                    data={"NF_WID": self._nf_wid},
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
                    "NF_WID": self._nf_wid,
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
                    except Exception:
                        data = {"raw_response": await response.text()}

                if status != 200:
                    if isinstance(data, dict):
                        message = data.get("VALIDATION_ERROR_MSG")
                        if message:
                            raise UpdateFailed(message)
                    if status == 404:
                        raise UpdateFailed("Nie znaleziono pojazdu o podanych danych.")
                    if status == 406:
                        raise UpdateFailed(
                            "API odrzuciło żądanie (HTTP 406). Sprawdź numer rejestracyjny, VIN i datę pierwszej rejestracji."
                        )
                    raise UpdateFailed(f"API Historia Pojazdu zwróciło HTTP {status}.")

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
                        except Exception as e:
                            _LOGGER.warning("Nie udało się sparsować osi czasu z CEPiK: %s", e)
                    else:
                        _LOGGER.warning("Endpoint timeline zwrócił status: %s", tl_response.status)

            return {
                "api": data,
                "http_status": status,
                "last_update": datetime.now().astimezone().isoformat(),
            }

        except UpdateFailed:
            raise
        except (ClientError, OSError, ssl.SSLError) as err:
            raise UpdateFailed(f"Błąd połączenia z CEPiK: {err}") from err
        except Exception as err:
            _LOGGER.exception("Nieoczekiwany błąd CEPiK")
            raise UpdateFailed(f"Nieoczekiwany błąd: {err}") from err