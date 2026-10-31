"""Diagnostics support for CEPiK Historia Pojazdu."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_FIRST_REGISTRATION, CONF_REGISTRATION, CONF_VEHICLE_ID, CONF_VIN, DOMAIN
from .coordinator import CepikCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry | None = None
) -> dict[str, Any]:
    """Return CEPiK API data and parser diagnostics for HA's Diagnostics UI."""
    coordinator: CepikCoordinator | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    config = {
        CONF_REGISTRATION: entry.data.get(CONF_REGISTRATION),
        CONF_VIN: entry.data.get(CONF_VIN),
        CONF_FIRST_REGISTRATION: entry.data.get(CONF_FIRST_REGISTRATION),
        CONF_VEHICLE_ID: entry.data.get(CONF_VEHICLE_ID),
    }

    result: dict[str, Any] = {
        "integration_version": "0.3.5",
        "config_entry": config,
        "coordinator_available": coordinator is not None,
    }

    if coordinator is None:
        return result

    result.update({
        "coordinator": {
            "vehicle_id": coordinator.vehicle_id,
            "registration": coordinator.registration,
            "vin": coordinator.vin,
            "first_registration_date": coordinator.first_registration_date,
            "last_update_success": coordinator.last_update_success,
            "last_update_success_time": getattr(coordinator, "last_update_success_time", None),
        },
        # Pełna odpowiedź API jest celowo dostępna w diagnostyce tej wersji.
        # HA Diagnostics może redagować dane identyfikujące, jeśli będzie to wymagane.
        "api_response": coordinator.data.get("api") if isinstance(coordinator.data, dict) else coordinator.data,
    })

    return result
