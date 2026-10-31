from __future__ import annotations

import logging
from datetime import date

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    CONF_REGISTRATION,
    CONF_VIN,
    CONF_FIRST_REGISTRATION,
    CONF_VEHICLE_ID,
    PLATFORMS,
)
from .coordinator import CepikCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = CepikCoordinator(
        hass=hass,
        registration=entry.data[CONF_REGISTRATION],
        vin=entry.data[CONF_VIN],
        first_registration_date=entry.data[CONF_FIRST_REGISTRATION],
        vehicle_id=entry.data.get(CONF_VEHICLE_ID, entry.data[CONF_VIN]),
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old CEPiK config entries to the current data format."""
    version = config_entry.version
    data = dict(config_entry.data)

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
        data[CONF_VEHICLE_ID] = str(vin).strip().upper()
    if first_date:
        try:
            data[CONF_FIRST_REGISTRATION] = date.fromisoformat(str(first_date)).isoformat()
        except ValueError:
            data[CONF_FIRST_REGISTRATION] = str(first_date)

    if version < 3:
        _LOGGER.info(
            "Migracja wpisu CEPiK %s: %s -> 3", config_entry.title, version
        )
        hass.config_entries.async_update_entry(
            config_entry, data=data, version=3
        )

    return True
