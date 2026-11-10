"""Diagnostics support for CEPiK Historia Pojazdu."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.loader import async_get_integration

from .const import (
    CONF_FIRST_REGISTRATION,
    CONF_REGISTRATION,
    CONF_VEHICLE_ID,
    CONF_VIN,
    DOMAIN,
)
from .coordinator import CepikCoordinator
from .models import CepikVehicleData

TO_REDACT = {
    CONF_REGISTRATION,
    CONF_VIN,
    CONF_FIRST_REGISTRATION,
    CONF_VEHICLE_ID,
    "registrationNumber",
    "VINNumber",
    "firstRegistrationDate",
    "vin",
    "registration",
    "policyNumber",
    "numerPolisy",
}


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

    integration_version: str | None = None
    try:
        integration = await async_get_integration(hass, DOMAIN)
        integration_version = str(integration.version) if integration.version else None
    except Exception:
        integration_version = None

    if not integration_version:
        try:
            manifest_path = Path(__file__).parent / "manifest.json"
            if manifest_path.is_file():
                with manifest_path.open(encoding="utf-8") as fp:
                    integration_version = json.load(fp).get("version")
        except Exception:
            integration_version = None

    result: dict[str, Any] = {
        "integration_version": integration_version,
        "config_entry": config,
        "coordinator_available": coordinator is not None,
    }

    if coordinator is None:
        return async_redact_data(result, TO_REDACT)

    result.update({
        "coordinator": {
            "vehicle_id": coordinator.vehicle_id,
            "registration": coordinator.registration,
            "vin": coordinator.vin,
            "first_registration_date": coordinator.first_registration_date,
            "last_update_success": coordinator.last_update_success,
            "last_update_success_time": getattr(coordinator, "last_update_success_time", None),
        },
        "api_response": (
            coordinator.data.raw
            if isinstance(coordinator.data, CepikVehicleData)
            else (coordinator.data.get("api") if isinstance(coordinator.data, dict) else coordinator.data)
        ),
    })

    return async_redact_data(result, TO_REDACT)
