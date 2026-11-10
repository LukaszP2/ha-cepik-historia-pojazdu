"""Unit tests for CEPiK domain models and parsers (AUD-003)."""
from datetime import date
from unittest.mock import MagicMock

import pytest

from custom_components.cepik_historia_pojazdu.const import DOMAIN
from custom_components.cepik_historia_pojazdu.models import (
    CepikVehicleData,
    device_info_obj,
    extract_api_data,
)


def test_vehicle_data_full_payload_parsing():
    """Verify parsing of full CEPiK API payload into CepikVehicleData."""
    raw_api = {
        "registrationNumber": "WA12345",
        "VINNumber": "WVWZZZ1JZXW000000",
        "firstRegistrationDate": "2015-05-20",
        "insuranceExpiryDate": "2025-11-30",
        "technicalData": {
            "basicData": {
                "make": "VOLKSWAGEN",
                "model": "GOLF",
                "productionYear": 2015,
                "hasCurrentOCPolicy": "tak",
                "technicalInspectionStatus": "aktualne",
                "odometerReadings": "180 500 km",
                "isStolen": False,
            }
        },
        "timelineData": {
            "reportGenerationDate": "2024-06-01",
            "odometerReadings": [
                {"value": 150000, "date": "2023-05-10"},
                {"value": 180500, "date": "2024-05-12"},
            ],
            "events": [
                {
                    "eventDate": "2024-05-12",
                    "description": "Okresowe badanie techniczne ważne do 12.05.2025",
                }
            ],
        },
    }

    model = CepikVehicleData.from_dict(
        data={"api": raw_api, "http_status": 200, "last_update": "2024-06-01T12:00:00Z"}
    )

    assert model.registration == "WA12345"
    assert model.vin == "WVWZZZ1JZXW000000"
    assert model.first_registration_date == "2015-05-20"
    assert model.make == "VOLKSWAGEN"
    assert model.model == "GOLF"
    assert model.production_year == 2015

    # Odometer
    assert model.odometer_km == 180500
    assert model.odometer_date == date(2024, 5, 12)
    assert model.odometer_source == "timelineData.odometerReadings"

    # Inspection
    assert model.inspection_event_date == date(2024, 5, 12)
    assert model.inspection_expiry_date == date(2025, 5, 12)
    assert model.technical_inspection_status == "aktualne"
    assert model.is_inspection_valid is True

    # Insurance
    assert model.has_current_oc is True
    assert model.has_current_oc_raw == "tak"
    assert model.oc_expiry_date == date(2025, 11, 30)
    assert model.api_insurance_expiry_date == "2025-11-30"

    # Stolen status
    assert model.is_stolen is False

    # Report & Timeline
    assert model.report_generation_date == date(2024, 6, 1)
    assert model.timeline_events_count == 1
    assert model.http_status == 200
    assert model.last_update == "2024-06-01T12:00:00Z"
    assert model.raw == raw_api


def test_vehicle_data_dict_compatibility():
    """Verify dict-like compatibility interface (__getitem__, get, __contains__)."""
    raw_api = {"registrationNumber": "KR99999"}
    model = CepikVehicleData.from_dict(
        data={"api": raw_api, "http_status": 200, "last_update": "2024-01-01T00:00:00Z"}
    )

    assert "api" in model
    assert "http_status" in model
    assert "last_update" in model
    assert "other_key" not in model

    assert model["api"] == raw_api
    assert model["http_status"] == 200
    assert model["last_update"] == "2024-01-01T00:00:00Z"

    assert model.get("api") == raw_api
    assert model.get("missing", "default_val") == "default_val"

    with pytest.raises(KeyError):
        _ = model["invalid_key"]


def test_vehicle_data_minimal_empty_payload():
    """Verify empty/minimal payload creates safe defaults without raising exceptions."""
    model = CepikVehicleData.from_dict({})

    assert model.registration is None
    assert model.vin is None
    assert model.make is None
    assert model.model is None
    assert model.odometer_km is None
    assert model.odometer_date is None
    assert model.inspection_expiry_date is None
    assert model.is_inspection_valid is None
    assert model.has_current_oc is None
    assert model.is_stolen is False
    assert model.report_generation_date is None
    assert model.timeline_events_count == 0
    assert model.raw == {}


def test_extract_api_data():
    """Verify extract_api_data unwraps both CepikVehicleData and legacy dicts."""
    raw_api = {"vin": "123"}
    model = CepikVehicleData(raw=raw_api)

    # Directly from model
    assert extract_api_data(model) == raw_api

    # From coordinator mock holding model
    coord_model = MagicMock()
    coord_model.data = model
    assert extract_api_data(coord_model) == raw_api

    # From coordinator mock holding dict
    coord_dict = MagicMock()
    coord_dict.data = {"api": raw_api}
    assert extract_api_data(coord_dict) == raw_api

    # From direct dict
    assert extract_api_data({"api": raw_api}) == raw_api

    # Fallbacks for empty/None
    assert extract_api_data(None) == {}
    assert extract_api_data("invalid") == {}


def test_device_info_obj():
    """Verify device_info_obj constructs HA DeviceInfo with CepikVehicleData and fallback."""
    coord = MagicMock()
    coord.vehicle_id = "VIN123"
    coord.registration = "WA12345"
    coord.vin = "VIN123"

    # With CepikVehicleData
    coord.data = CepikVehicleData(make="TOYOTA", model="YARIS")
    dev_info = device_info_obj(coord)
    assert dev_info["identifiers"] == {(DOMAIN, "VIN123")}
    assert dev_info["name"] == "CEPiK WA12345"
    assert dev_info["manufacturer"] == "TOYOTA"
    assert dev_info["model"] == "YARIS"
    assert dev_info["serial_number"] == "VIN123"

    # With raw dict
    coord.data = {
        "api": {
            "technicalData": {
                "basicData": {"brand": "SKODA", "model": "OCTAVIA"}
            }
        }
    }
    dev_info_dict = device_info_obj(coord)
    assert dev_info_dict["manufacturer"] == "SKODA"
    assert dev_info_dict["model"] == "OCTAVIA"

    # With None
    coord.data = None
    dev_info_none = device_info_obj(coord)
    assert dev_info_none["manufacturer"] == "CEPiK"
    assert dev_info_none["model"] is None
