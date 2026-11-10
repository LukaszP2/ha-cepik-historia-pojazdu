"""Unit tests for CEPiK integration lifecycle and migrations (AUD-004)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.cepik_historia_pojazdu import (
    async_migrate_entry,
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.cepik_historia_pojazdu.const import (
    CONF_FIRST_REGISTRATION,
    CONF_REGISTRATION,
    CONF_SCAN_INTERVAL,
    CONF_VEHICLE_ID,
    CONF_VIN,
    DOMAIN,
    PLATFORMS,
)
from custom_components.cepik_historia_pojazdu.coordinator import CepikCoordinator


@pytest.mark.asyncio
async def test_async_setup_entry():
    """Verify entry setup initializes coordinator and forwards platform setup."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

    entry = MagicMock()
    entry.entry_id = "test_entry_123"
    entry.data = {
        CONF_REGISTRATION: "WA12345",
        CONF_VIN: "WVWZZZ1JZXW000000",
        CONF_FIRST_REGISTRATION: "2015-05-20",
        CONF_VEHICLE_ID: "WVWZZZ1JZXW000000",
    }
    entry.options = {CONF_SCAN_INTERVAL: 12}
    entry.add_update_listener = MagicMock(return_value=MagicMock())
    entry.async_on_unload = MagicMock()

    with patch.object(
        CepikCoordinator, "async_config_entry_first_refresh", new=AsyncMock()
    ) as mock_refresh:
        result = await async_setup_entry(hass, entry)

    assert result is True
    assert mock_refresh.await_count == 1
    assert isinstance(entry.runtime_data, CepikCoordinator)
    assert hass.data[DOMAIN][entry.entry_id] is entry.runtime_data
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(
        entry, PLATFORMS
    )
    assert entry.async_on_unload.call_count >= 1


@pytest.mark.asyncio
async def test_async_reload_entry():
    """Verify config entry reload triggers HA reload."""
    hass = MagicMock()
    hass.config_entries.async_reload = AsyncMock()

    entry = MagicMock()
    entry.entry_id = "test_entry_123"

    await async_reload_entry(hass, entry)
    hass.config_entries.async_reload.assert_awaited_once_with("test_entry_123")


@pytest.mark.asyncio
async def test_async_unload_entry_success():
    """Verify successful unload removes coordinator from hass.data."""
    hass = MagicMock()
    coordinator = MagicMock()
    hass.data = {DOMAIN: {"test_entry_123": coordinator}}
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    entry = MagicMock()
    entry.entry_id = "test_entry_123"

    result = await async_unload_entry(hass, entry)
    assert result is True
    hass.config_entries.async_unload_platforms.assert_awaited_once_with(
        entry, PLATFORMS
    )
    assert "test_entry_123" not in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_async_unload_entry_failure():
    """Verify failed unload preserves coordinator in hass.data."""
    hass = MagicMock()
    coordinator = MagicMock()
    hass.data = {DOMAIN: {"test_entry_123": coordinator}}
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

    entry = MagicMock()
    entry.entry_id = "test_entry_123"

    result = await async_unload_entry(hass, entry)
    assert result is False
    assert hass.data[DOMAIN]["test_entry_123"] is coordinator


@pytest.mark.asyncio
async def test_async_migrate_entry_v1_to_v3():
    """Verify migration of v1 entry with legacy Polish keys to v3 schema."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()

    entry = MagicMock()
    entry.version = 1
    entry.title = "CEPiK WA12345"
    entry.data = {
        "numer_rejestracyjny": "wa12345",
        "VIN": "wvwzzz1jz9w123456",
        "data_pierwszej_rejestracji": "2015-06-15",
    }

    result = await async_migrate_entry(hass, entry)
    assert result is True

    hass.config_entries.async_update_entry.assert_called_once()
    _, kwargs = hass.config_entries.async_update_entry.call_args
    assert kwargs["version"] == 3
    data = kwargs["data"]
    assert data[CONF_REGISTRATION] == "WA12345"
    assert data[CONF_VIN] == "WVWZZZ1JZ9W123456"
    assert data[CONF_VEHICLE_ID] == "WVWZZZ1JZ9W123456"
    assert data[CONF_FIRST_REGISTRATION] == "2015-06-15"


@pytest.mark.asyncio
async def test_async_migrate_entry_v2_to_v3():
    """Verify migration of v2 entry to v3 schema."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()

    entry = MagicMock()
    entry.version = 2
    entry.title = "CEPiK KR54321"
    entry.data = {
        "registration": "kr54321",
        "vin": "vin789",
        "first_registration_date": "2018-03-01",
    }

    result = await async_migrate_entry(hass, entry)
    assert result is True

    hass.config_entries.async_update_entry.assert_called_once()
    _, kwargs = hass.config_entries.async_update_entry.call_args
    assert kwargs["version"] == 3
    data = kwargs["data"]
    assert data[CONF_REGISTRATION] == "KR54321"
    assert data[CONF_VIN] == "VIN789"
    assert data[CONF_VEHICLE_ID] == "VIN789"
    assert data[CONF_FIRST_REGISTRATION] == "2018-03-01"


@pytest.mark.asyncio
async def test_async_migrate_entry_already_v3():
    """Verify that v3 entries are untouched by migration."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()

    entry = MagicMock()
    entry.version = 3
    entry.title = "CEPiK WA12345"
    entry.data = {
        CONF_REGISTRATION: "WA12345",
        CONF_VIN: "WVWZZZ1JZXW000000",
        CONF_FIRST_REGISTRATION: "2015-05-20",
        CONF_VEHICLE_ID: "WVWZZZ1JZXW000000",
    }

    result = await async_migrate_entry(hass, entry)
    assert result is True
    hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_async_migrate_entry_invalid_date_fallback():
    """Verify invalid date string does not crash migration and is retained."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()

    entry = MagicMock()
    entry.version = 1
    entry.title = "CEPiK WA12345"
    entry.data = {
        CONF_REGISTRATION: "WA12345",
        CONF_VIN: "VIN123",
        CONF_FIRST_REGISTRATION: "invalid-date-string",
    }

    result = await async_migrate_entry(hass, entry)
    assert result is True
    hass.config_entries.async_update_entry.assert_called_once()
    _, kwargs = hass.config_entries.async_update_entry.call_args
    assert kwargs["data"][CONF_FIRST_REGISTRATION] == "invalid-date-string"
