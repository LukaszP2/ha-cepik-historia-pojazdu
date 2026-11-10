"""Test CEPiK sensor parsers and logic."""
from datetime import date

from custom_components.cepik_historia_pojazdu.sensor import (
    _extract_km,
    _latest_inspection,
    _latest_odometer,
    _oc_expiry,
    _parse_date_any,
)


def test_extract_km_ignores_dates():
    """Verify that calendar dates are not parsed as kilometers."""
    text_with_date = "Badanie techniczne po wymianie drogomierza w dniu 12.05.2023"
    assert _extract_km(text_with_date) is None

    text_with_km_and_date = "Badanie w dniu 12.05.2023 - stan drogomierza 154 200 km"
    assert _extract_km(text_with_km_and_date) == 154200

    text_simple = "Stan drogomierza: 215000 km"
    assert _extract_km(text_simple) == 215000


def test_parse_date_any_invalid_values():
    """Verify that malformed or out-of-range dates do not crash with ValueError."""
    assert _parse_date_any("15-88-2024") is None
    assert _parse_date_any("99.99.2023") is None
    assert _parse_date_any("") is None
    assert _parse_date_any(None) is None
    assert _parse_date_any("2024-05-15") == date(2024, 5, 15)
    assert _parse_date_any("15.05.2024") == date(2024, 5, 15)


def test_latest_odometer_structured_precedence():
    """Verify structured odometerReadings are properly parsed and dated."""
    api = {
        "timelineData": {
            "odometerReadings": [
                {"value": 120000, "date": "2023-01-10"},
                {"value": 135000, "date": "2024-01-10"},
            ],
            "events": [
                {
                    "eventDate": "2022-01-10",
                    "description": "Stan drogomierza: 100000 km",
                }
            ],
        }
    }
    km, dt, source = _latest_odometer(api)
    assert km == 135000
    assert dt == date(2024, 1, 10)
    assert source == "timelineData.odometerReadings"


def test_latest_inspection_basic_data_and_timeline():
    """Verify latest inspection date from basicData and timeline."""
    api_basic = {
        "technicalData": {
            "basicData": {
                "technicalInspectionExpiryDate": "2025-06-20",
            }
        }
    }
    _, expiry, _ = _latest_inspection(api_basic)
    assert expiry == date(2025, 6, 20)

    api_timeline = {
        "timelineData": {
            "events": [
                {
                    "eventDate": "2024-05-10",
                    "description": "Okresowe badanie techniczne (pozytywne) ważne do 10.05.2025",
                }
            ]
        }
    }
    _, expiry_tl, _ = _latest_inspection(api_timeline)
    assert expiry_tl == date(2025, 5, 10)


def test_oc_expiry():
    """Verify OC insurance expiration parsing."""
    api = {
        "timelineData": {
            "insuranceExpiryDate": "2025-11-30",
        }
    }
    assert _oc_expiry(api) == date(2025, 11, 30)


def test_sensor_entity_metadata():
    """Verify sensor categories, units, and device info."""
    from unittest.mock import MagicMock

    from homeassistant.const import EntityCategory, UnitOfLength

    from custom_components.cepik_historia_pojazdu.sensor import (
        CepikMainSensor,
        CepikOdometerSensor,
        CepikUpdateDateSensor,
    )

    coordinator = MagicMock()
    coordinator.vehicle_id = "VIN123"
    coordinator.registration = "WA12345"
    coordinator.vin = "VIN123"
    coordinator.last_update_success = True
    coordinator.data = {"api": {}}

    main_sensor = CepikMainSensor(coordinator)
    assert main_sensor.entity_category == EntityCategory.DIAGNOSTIC
    assert main_sensor.entity_registry_enabled_default is False
    assert main_sensor.device_info["serial_number"] == "VIN123"

    odometer = CepikOdometerSensor(coordinator)
    assert odometer.native_unit_of_measurement == UnitOfLength.KILOMETERS

    update_date = CepikUpdateDateSensor(coordinator)
    assert update_date.entity_category == EntityCategory.DIAGNOSTIC
