"""Test CEPiK Historia Pojazdu config flow."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.cepik_historia_pojazdu.const import (
    CONF_FIRST_REGISTRATION,
    CONF_REGISTRATION,
    CONF_SCAN_INTERVAL,
    CONF_VEHICLE_ID,
    CONF_VIN,
)


@pytest.mark.asyncio
async def test_config_flow_user_success():
    """Test successful user step configuration."""
    from custom_components.cepik_historia_pojazdu.config_flow import CepikConfigFlow

    flow = CepikConfigFlow()
    flow.hass = MagicMock()
    flow.context = {}
    flow.hass.config_entries.flow.async_progress_by_handler = MagicMock(return_value=[])
    flow.hass.config_entries.async_entry_for_domain_unique_id = MagicMock(return_value=None)

    with patch(
        "custom_components.cepik_historia_pojazdu.coordinator.CepikCoordinator.async_validate",
        new=AsyncMock(return_value={"http_status": 200}),
    ):
        result = await flow.async_step_user(
            user_input={
                CONF_REGISTRATION: "wa 12345 ",
                CONF_VIN: "wvwzzz1kz9w123456",
                CONF_FIRST_REGISTRATION: "2015-06-15",
            }
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "CEPiK WA12345"
    assert result["data"] == {
        CONF_REGISTRATION: "WA12345",
        CONF_VIN: "WVWZZZ1KZ9W123456",
        CONF_FIRST_REGISTRATION: "2015-06-15",
        CONF_VEHICLE_ID: "WVWZZZ1KZ9W123456",
    }


@pytest.mark.asyncio
async def test_config_flow_reconfigure_success():
    """Test reconfigure step does not raise NameError and succeeds."""
    from custom_components.cepik_historia_pojazdu.config_flow import CepikConfigFlow

    flow = CepikConfigFlow()
    flow.hass = MagicMock()
    flow.context = {"entry_id": "test_entry"}
    flow.hass.config_entries.flow.async_progress_by_handler = MagicMock(return_value=[])
    flow.hass.config_entries.async_entry_for_domain_unique_id = MagicMock(return_value=None)

    entry = MagicMock()
    entry.version = 3
    entry.unique_id = "VIN123"
    entry.entry_id = "test_entry"
    entry.update_listeners = []
    entry.data = {
        CONF_REGISTRATION: "OLD123",
        CONF_VIN: "VIN123",
        CONF_FIRST_REGISTRATION: "2010-01-01",
        CONF_VEHICLE_ID: "VIN123",
    }
    flow.hass.config_entries.async_get_entry = MagicMock(return_value=entry)

    with patch(
        "custom_components.cepik_historia_pojazdu.coordinator.CepikCoordinator.async_validate",
        new=AsyncMock(return_value={"http_status": 200}),
    ):
        result = await flow.async_step_reconfigure(
            user_input={
                CONF_REGISTRATION: "NEW456",
                CONF_VIN: "VIN123",
                CONF_FIRST_REGISTRATION: "2010-01-01",
            }
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert flow.hass.config_entries.async_update_entry.call_count == 1
    call_kwargs = flow.hass.config_entries.async_update_entry.call_args.kwargs
    assert call_kwargs["title"] == "CEPiK NEW456"
    assert call_kwargs["data"] == {
        CONF_REGISTRATION: "NEW456",
        CONF_VIN: "VIN123",
        CONF_FIRST_REGISTRATION: "2010-01-01",
        CONF_VEHICLE_ID: "VIN123",
    }


@pytest.mark.asyncio
async def test_options_flow():
    """Test options flow configuration of scan_interval."""
    from custom_components.cepik_historia_pojazdu.config_flow import (
        CepikConfigFlow,
        CepikOptionsFlowHandler,
    )

    entry = MagicMock()
    entry.options = {CONF_SCAN_INTERVAL: 12}
    handler = CepikConfigFlow.async_get_options_flow(entry)
    assert isinstance(handler, CepikOptionsFlowHandler)

    # Initial step without input shows form
    result_form = await handler.async_step_init()
    assert result_form["type"] == FlowResultType.FORM
    assert result_form["step_id"] == "init"

    # Step with input creates entry
    result_save = await handler.async_step_init(user_input={CONF_SCAN_INTERVAL: 48})
    assert result_save["type"] == FlowResultType.CREATE_ENTRY
    assert result_save["data"] == {CONF_SCAN_INTERVAL: 48}
