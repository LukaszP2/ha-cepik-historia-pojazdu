"""Test CEPiK coordinator error handling and Repairs integration."""
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.issue_registry import IssueSeverity
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.cepik_historia_pojazdu.const import DOMAIN
from custom_components.cepik_historia_pojazdu.coordinator import CepikCoordinator


def test_coordinator_custom_update_interval():
    """Verify custom update_interval_hours configures coordinator interval."""
    hass = MagicMock()
    coord = CepikCoordinator(
        hass,
        registration="WA12345",
        vin="VIN123",
        first_registration_date="2020-01-01",
        update_interval_hours=48,
    )
    assert coord.update_interval == timedelta(hours=48)


@pytest.mark.asyncio
async def test_coordinator_http_406_creates_repairs_issue():
    """Verify HTTP 406 triggers Repairs issue creation and raises UpdateFailed."""
    hass = MagicMock()
    coord = CepikCoordinator(
        hass,
        registration="WA12345",
        vin="VIN123",
        first_registration_date="2020-01-01",
    )

    mock_cookie = MagicMock()
    mock_cookie.key = "XSRF-TOKEN"
    mock_cookie.value = "token123"

    mock_session = MagicMock()
    mock_session.cookie_jar = [mock_cookie]

    # Mock responses
    resp_init = AsyncMock()
    resp_init.read = AsyncMock()
    mock_session.get.return_value.__aenter__.return_value = resp_init

    resp_post_init = AsyncMock()
    resp_post_init.read = AsyncMock()
    mock_session.post.return_value.__aenter__.return_value = resp_post_init

    # Vehicle response 406
    resp_vehicle = AsyncMock()
    resp_vehicle.status = 406
    resp_vehicle.json = AsyncMock(return_value={})

    mock_session.post.return_value.__aenter__.side_effect = [
        resp_post_init,
        resp_vehicle,
    ]

    with (
        patch(
            "custom_components.cepik_historia_pojazdu.coordinator.async_create_clientsession",
            return_value=mock_session,
        ),
        patch(
            "custom_components.cepik_historia_pojazdu.coordinator.async_create_issue"
        ) as mock_create_issue,
        patch(
            "custom_components.cepik_historia_pojazdu.coordinator.CepikCoordinator._async_get_ssl_context",
            new=AsyncMock(),
        ),
    ):
        with pytest.raises(UpdateFailed) as exc_info:
            await coord._async_update_data()

        assert "HTTP 406" in str(exc_info.value)
        mock_create_issue.assert_called_once_with(
            hass,
            DOMAIN,
            "invalid_vehicle_VIN123",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="invalid_vehicle_credentials",
            translation_placeholders={
                "registration": "WA12345",
                "vin": "VIN123",
            },
        )


@pytest.mark.asyncio
async def test_coordinator_http_429_retry_after():
    """Verify HTTP 429 reads Retry-After header and formats error message."""
    hass = MagicMock()
    coord = CepikCoordinator(
        hass,
        registration="WA12345",
        vin="VIN123",
        first_registration_date="2020-01-01",
    )

    mock_cookie = MagicMock()
    mock_cookie.key = "XSRF-TOKEN"
    mock_cookie.value = "token123"

    mock_session = MagicMock()
    mock_session.cookie_jar = [mock_cookie]

    resp_init = AsyncMock()
    resp_init.read = AsyncMock()
    mock_session.get.return_value.__aenter__.return_value = resp_init

    resp_post_init = AsyncMock()
    resp_post_init.read = AsyncMock()

    resp_vehicle = AsyncMock()
    resp_vehicle.status = 429
    resp_vehicle.headers = {"Retry-After": "7200"}
    resp_vehicle.json = AsyncMock(return_value={})

    mock_session.post.return_value.__aenter__.side_effect = [
        resp_post_init,
        resp_vehicle,
    ]

    with (
        patch(
            "custom_components.cepik_historia_pojazdu.coordinator.async_create_clientsession",
            return_value=mock_session,
        ),
        patch(
            "custom_components.cepik_historia_pojazdu.coordinator.CepikCoordinator._async_get_ssl_context",
            new=AsyncMock(),
        ),
    ):
        with pytest.raises(UpdateFailed) as exc_info:
            await coord._async_update_data()

        assert "429" in str(exc_info.value)
        assert "7200s" in str(exc_info.value)


@pytest.mark.asyncio
async def test_coordinator_success_deletes_issue():
    """Verify successful update deletes any existing invalid_vehicle issue."""
    hass = MagicMock()
    coord = CepikCoordinator(
        hass,
        registration="WA12345",
        vin="VIN123",
        first_registration_date="2020-01-01",
    )

    mock_cookie = MagicMock()
    mock_cookie.key = "XSRF-TOKEN"
    mock_cookie.value = "token123"

    mock_session = MagicMock()
    mock_session.cookie_jar = [mock_cookie]

    resp_init = AsyncMock()
    resp_init.read = AsyncMock()
    mock_session.get.return_value.__aenter__.return_value = resp_init

    resp_post_init = AsyncMock()
    resp_post_init.read = AsyncMock()

    resp_vehicle = AsyncMock()
    resp_vehicle.status = 200
    resp_vehicle.json = AsyncMock(return_value={"technicalData": {}})

    resp_tl = AsyncMock()
    resp_tl.status = 200
    resp_tl.json = AsyncMock(return_value={"timelineData": {}})

    mock_session.post.return_value.__aenter__.side_effect = [
        resp_post_init,
        resp_vehicle,
        resp_tl,
    ]

    with (
        patch(
            "custom_components.cepik_historia_pojazdu.coordinator.async_create_clientsession",
            return_value=mock_session,
        ),
        patch(
            "custom_components.cepik_historia_pojazdu.coordinator.async_delete_issue"
        ) as mock_delete_issue,
        patch(
            "custom_components.cepik_historia_pojazdu.coordinator.CepikCoordinator._async_get_ssl_context",
            new=AsyncMock(),
        ),
    ):
        data = await coord._async_update_data()
        assert "technicalData" in data["api"]
        mock_delete_issue.assert_called_once_with(hass, DOMAIN, "invalid_vehicle_VIN123")
