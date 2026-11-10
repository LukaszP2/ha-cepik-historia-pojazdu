from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

import voluptuous as vol
from aiohttp import ClientError
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FIRST_REGISTRATION,
    CONF_REGISTRATION,
    CONF_SCAN_INTERVAL,
    CONF_VEHICLE_ID,
    CONF_VIN,
    DEFAULT_UPDATE_INTERVAL_HOURS,
    DOMAIN,
)
from .coordinator import CepikCoordinator

_LOGGER = logging.getLogger(__name__)


def _date_schema(default_date: str | None = None) -> dict[vol.Marker, Any]:
    """Return a native HA date selector."""
    default = default_date or dt_util.now().date().isoformat()
    return {
        vol.Required(
            CONF_FIRST_REGISTRATION,
            default=default,
        ): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.DATE))
    }


class CepikConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # pyright: ignore[reportCallIssue, reportGeneralTypeIssues]  # type: ignore[call-arg]
    """Config flow for CEPiK Historia Pojazdu."""

    VERSION = 3

    async def async_step_user(self, user_input=None):
        """Handle adding a vehicle."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}

        if user_input is not None:
            registration = re.sub(r"\s+", "", user_input[CONF_REGISTRATION]).upper()
            vin = re.sub(r"\s+", "", user_input[CONF_VIN]).upper()
            first_date = user_input[CONF_FIRST_REGISTRATION]

            if not registration:
                errors[CONF_REGISTRATION] = "required"
            elif not vin:
                errors[CONF_VIN] = "required"
            else:
                try:
                    date.fromisoformat(first_date)
                except (TypeError, ValueError):
                    errors[CONF_FIRST_REGISTRATION] = "invalid_date"
                else:
                    await self.async_set_unique_id(vin)
                    self._abort_if_unique_id_configured()

                    try:
                        coordinator = CepikCoordinator(
                            self.hass,
                            registration,
                            vin,
                            first_date,
                        )
                        await coordinator.async_validate()
                    except (UpdateFailed, ClientError, TimeoutError, OSError) as err:
                        _LOGGER.warning(
                            "Nie udało się zweryfikować pojazdu %s: %s",
                            registration,
                            err,
                        )
                        errors["base"] = "invalid_vehicle"
                        placeholders["error"] = str(err)
                    except Exception as err:
                        _LOGGER.exception(
                            "Nieoczekiwany błąd podczas weryfikacji pojazdu %s",
                            registration,
                        )
                        errors["base"] = "invalid_vehicle"
                        placeholders["error"] = str(err)
                    else:
                        return self.async_create_entry(
                            title=f"CEPiK {registration}",
                            data={
                                CONF_REGISTRATION: registration,
                                CONF_VIN: vin,
                                CONF_FIRST_REGISTRATION: first_date,
                                CONF_VEHICLE_ID: vin,
                            },
                        )

        schema = vol.Schema(
            {
                vol.Required(CONF_REGISTRATION): selector.TextSelector(),
                vol.Required(CONF_VIN): selector.TextSelector(),
                **_date_schema(),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reconfigure(self, user_input=None):
        """Allow editing an existing vehicle from HA's Configure action."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry is None:
            return self.async_abort(reason="unknown")

        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        current = entry.data

        if user_input is not None:
            registration = re.sub(r"\s+", "", user_input[CONF_REGISTRATION]).upper()
            vin = re.sub(r"\s+", "", user_input[CONF_VIN]).upper()
            first_date = user_input[CONF_FIRST_REGISTRATION]

            if not registration:
                errors[CONF_REGISTRATION] = "required"
            elif not vin:
                errors[CONF_VIN] = "required"
            else:
                try:
                    date.fromisoformat(first_date)
                except (TypeError, ValueError):
                    errors[CONF_FIRST_REGISTRATION] = "invalid_date"
                else:
                    if vin != entry.unique_id:
                        await self.async_set_unique_id(vin)
                        self._abort_if_unique_id_configured()

                    try:
                        coordinator = CepikCoordinator(
                            self.hass,
                            registration,
                            vin,
                            first_date,
                            vehicle_id=vin,
                        )
                        await coordinator.async_validate()
                    except (UpdateFailed, ClientError, TimeoutError, OSError) as err:
                        _LOGGER.warning(
                            "Nie udało się zweryfikować zmienionego pojazdu %s: %s",
                            registration,
                            err,
                        )
                        errors["base"] = "invalid_vehicle"
                        placeholders["error"] = str(err)
                    except Exception as err:
                        _LOGGER.exception(
                            "Nieoczekiwany błąd podczas weryfikacji pojazdu %s",
                            registration,
                        )
                        errors["base"] = "invalid_vehicle"
                        placeholders["error"] = str(err)
                    else:
                        return self.async_update_reload_and_abort(
                            entry,
                            title=f"CEPiK {registration}",
                            data={
                                CONF_REGISTRATION: registration,
                                CONF_VIN: vin,
                                CONF_FIRST_REGISTRATION: first_date,
                                CONF_VEHICLE_ID: vin,
                            },
                            reason="reconfigure_successful",
                        )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_REGISTRATION, default=current.get(CONF_REGISTRATION, "")
                ): selector.TextSelector(),
                vol.Required(
                    CONF_VIN, default=current.get(CONF_VIN, "")
                ): selector.TextSelector(),
                **_date_schema(current.get(CONF_FIRST_REGISTRATION)),
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get options flow handler."""
        return CepikOptionsFlowHandler(config_entry)


class CepikOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle CEPiK options."""

    def __init__(self, config_entry: config_entries.ConfigEntry | None = None) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    @property
    def config_entry(self) -> config_entries.ConfigEntry:
        """Return config entry."""
        if self._config_entry is not None:
            return self._config_entry
        return super().config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL_HOURS
        )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=current_interval,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=6,
                        max=72,
                        step=1,
                        unit_of_measurement="h",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
