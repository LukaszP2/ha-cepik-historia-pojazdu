from __future__ import annotations

from datetime import date
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_REGISTRATION,
    CONF_VIN,
    CONF_FIRST_REGISTRATION,
)
from .coordinator import CepikCoordinator

_LOGGER = logging.getLogger(__name__)


def _date_schema(default_date: str | None = None) -> dict:
    """Return a native HA date selector."""
    default = default_date or date.today().isoformat()
    return {
        vol.Required(
            CONF_FIRST_REGISTRATION,
            default=default,
        ): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.DATE))
    }


class CepikConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for CEPiK Historia Pojazdu."""

    VERSION = 3

    async def async_step_user(self, user_input=None):
        """Handle adding a vehicle."""
        errors = {}
        placeholders = {}

        if user_input is not None:
            registration = user_input[CONF_REGISTRATION].strip().upper()
            vin = user_input[CONF_VIN].strip().upper()
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
                    except Exception as err:
                        _LOGGER.warning(
                            "Nie udało się zweryfikować pojazdu %s: %s",
                            registration,
                            err,
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

        errors = {}
        placeholders = {}
        current = entry.data

        if user_input is not None:
            registration = user_input[CONF_REGISTRATION].strip().upper()
            vin = user_input[CONF_VIN].strip().upper()
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
                    try:
                        coordinator = CepikCoordinator(
                            self.hass, registration, vin, first_date,
                            vehicle_id=vin,
                        )
                        await coordinator.async_validate()
                    except Exception as err:
                        _LOGGER.warning(
                            "Nie udało się zweryfikować zmienionego pojazdu %s: %s",
                            registration, err,
                        )
                        errors["base"] = "invalid_vehicle"
                        placeholders["error"] = str(err)
                    else:
                        self.hass.config_entries.async_update_entry(
                            entry,
                            title=f"CEPiK {registration}",
                            data={
                                CONF_REGISTRATION: registration,
                                CONF_VIN: vin,
                                CONF_FIRST_REGISTRATION: first_date,
                                CONF_VEHICLE_ID: vin,
                            },
                        )
                        await self.hass.config_entries.async_reload(entry.entry_id)
                        return self.async_abort(reason="reconfigure_successful")

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
    async def async_migrate_entry(hass, config_entry):
        """Migrate older config entries without losing vehicle data."""
        version = config_entry.version
        data = dict(config_entry.data)

        # 0.1.x / 0.2.x used the same three pieces of vehicle data.
        # Normalize possible legacy field names.
        registration = (
            data.get(CONF_REGISTRATION)
            or data.get("numer_rejestracyjny")
            or data.get("registration")
        )
        vin = data.get(CONF_VIN) or data.get("VIN") or data.get("vin")
        first_date = (
            data.get(CONF_FIRST_REGISTRATION)
            or data.get("data_pierwszej_rejestracji")
            or data.get("first_registration_date")
        )

        if registration:
            data[CONF_REGISTRATION] = str(registration).strip().upper()
        if vin:
            data[CONF_VIN] = str(vin).strip().upper()
        if first_date:
            try:
                data[CONF_FIRST_REGISTRATION] = date.fromisoformat(
                    str(first_date)
                ).isoformat()
            except ValueError:
                # Keep the original value rather than destroying a user's
                # configuration. The edit flow will allow correction.
                data[CONF_FIRST_REGISTRATION] = str(first_date)

        if version < 3:
            _LOGGER.info(
                "Migracja wpisu CEPiK %s: %s -> 3",
                config_entry.title,
                version,
            )
            hass.config_entries.async_update_entry(
                config_entry,
                data=data,
                version=3,
            )

        return True
