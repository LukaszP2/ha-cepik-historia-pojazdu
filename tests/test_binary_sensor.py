"""Test CEPiK binary sensors."""
from unittest.mock import MagicMock

from custom_components.cepik_historia_pojazdu.binary_sensor import (
    CepikInspectionBinarySensor,
    CepikOcBinarySensor,
    CepikStolenBinarySensor,
    _is_stolen,
)


def test_is_stolen_detection():
    """Verify theft detection logic."""
    assert not _is_stolen({})
    assert _is_stolen({"technicalData": {"basicData": {"isStolen": True}}})
    assert _is_stolen({"technicalData": {"basicData": {"stolen": "tak"}}})
    assert _is_stolen({"timelineData": {"events": [{"description": "Zgłoszenie kradzieży pojazdu"}]}})
    assert not _is_stolen({"technicalData": {"basicData": {"isStolen": False}}})


def test_binary_sensors_state():
    """Test state property of binary sensors."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.vehicle_id = "WA12345"
    coordinator.registration = "WA12345"
    coordinator.vin = "VIN12345678901234"
    coordinator.data = {
        "api": {
            "technicalData": {
                "basicData": {
                    "hasCurrentOCPolicy": True,
                    "technicalInspectionStatus": "aktualne",
                    "isStolen": False,
                }
            }
        }
    }

    oc_sensor = CepikOcBinarySensor(coordinator)
    assert oc_sensor.is_on is True

    inspection_sensor = CepikInspectionBinarySensor(coordinator)
    assert inspection_sensor.is_on is True

    stolen_sensor = CepikStolenBinarySensor(coordinator)
    assert stolen_sensor.is_on is False
    assert stolen_sensor.device_info["serial_number"] == "VIN12345678901234"
