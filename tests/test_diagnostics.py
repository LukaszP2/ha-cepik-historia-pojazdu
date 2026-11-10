"""Test diagnostics redaction for CEPiK."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.cepik_historia_pojazdu.const import (
    CONF_FIRST_REGISTRATION,
    CONF_REGISTRATION,
    CONF_VEHICLE_ID,
    CONF_VIN,
    DOMAIN,
)
from custom_components.cepik_historia_pojazdu.diagnostics import (
    async_get_config_entry_diagnostics,
)


@pytest.mark.asyncio
async def test_diagnostics_redacts_sensitive_data():
    """Verify VIN and registration numbers are redacted in diagnostics."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        CONF_REGISTRATION: "WA12345",
        CONF_VIN: "WVWZZZ1JZXW000000",
        CONF_FIRST_REGISTRATION: "2015-05-20",
        CONF_VEHICLE_ID: "WVWZZZ1JZXW000000",
    }

    coordinator = MagicMock()
    coordinator.vehicle_id = "WVWZZZ1JZXW000000"
    coordinator.registration = "WA12345"
    coordinator.vin = "WVWZZZ1JZXW000000"
    coordinator.first_registration_date = "2015-05-20"
    coordinator.last_update_success = True
    coordinator.data = {
        "api": {
            "registrationNumber": "WA12345",
            "VINNumber": "WVWZZZ1JZXW000000",
            "firstRegistrationDate": "2015-05-20",
            "policyNumber": "POL-99999",
        }
    }

    hass.data = {DOMAIN: {entry.entry_id: coordinator}}

    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["integration_version"] == "0.3.5"
    assert diag["config_entry"][CONF_REGISTRATION] == "**REDACTED**"
    assert diag["config_entry"][CONF_VIN] == "**REDACTED**"
    assert diag["coordinator"]["vin"] == "**REDACTED**"
    assert diag["api_response"]["VINNumber"] == "**REDACTED**"
    assert diag["api_response"]["registrationNumber"] == "**REDACTED**"
    assert diag["api_response"]["policyNumber"] == "**REDACTED**"


@pytest.mark.asyncio
async def test_diagnostics_integration_version_from_integration():
    """Verify version is dynamically obtained from async_get_integration."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {}
    hass.data = {DOMAIN: {}}

    mock_integration = MagicMock()
    mock_integration.version = "1.2.3"

    with patch(
        "custom_components.cepik_historia_pojazdu.diagnostics.async_get_integration",
        new=AsyncMock(return_value=mock_integration),
    ):
        diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["integration_version"] == "1.2.3"
