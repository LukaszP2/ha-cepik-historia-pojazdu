"""Test CEPiK data extraction and parsing helpers."""
from datetime import date

from custom_components.cepik_historia_pojazdu.binary_sensor import _is_stolen
from custom_components.cepik_historia_pojazdu.sensor import (
    _extract_km,
    _latest_inspection,
    _latest_odometer,
    _parse_date_any,
)


def test_extract_km():
    """Verify odometer kilometer extraction logic."""
    # Standard formats
    assert _extract_km("Stan drogomierza: 154 200 km") == 154200
    assert _extract_km("Przebieg 85000 km") == 85000
    assert _extract_km("120000 kilometrów") == 120000
    assert _extract_km("Odczyt drogomierza: 215000") == 215000

    # Critical edge case: date in event description must not be treated as odometer
    assert _extract_km("Badanie techniczne po wymianie drogomierza w dniu 12.05.2023") is None
    assert _extract_km("Wymiana drogomierza w dniu 2023-05-12") is None

    # Date followed by actual odometer reading
    assert _extract_km("Wymiana drogomierza w dniu 12.05.2023, nowy stan: 12500 km") == 12500


def test_parse_date_any():
    """Verify robust date parsing and invalid date handling."""
    assert _parse_date_any("2024-05-12") == date(2024, 5, 12)
    assert _parse_date_any("12.05.2024") == date(2024, 5, 12)
    assert _parse_date_any("12-05-2024") == date(2024, 5, 12)
    assert _parse_date_any("2024/05/12") == date(2024, 5, 12)

    # Invalid dates that previously caused ValueError crashes
    assert _parse_date_any("Kod: 15-88-2024") is None
    assert _parse_date_any("Numer 99.99.2024") is None
    assert _parse_date_any("") is None
    assert _parse_date_any(None) is None


def test_latest_odometer_structured():
    """Verify structured odometer readings are prioritized."""
    api = {
        "timelineData": {
            "odometerReadings": [
                {"value": 110000, "date": "2023-01-15"},
                {"value": 135000, "date": "2024-03-20"},
            ]
        }
    }
    km, reading_date, source = _latest_odometer(api)
    assert km == 135000
    assert reading_date == date(2024, 3, 20)
    assert source == "timelineData.odometerReadings"


def test_latest_inspection_new_vehicle():
    """Verify inspection expiry for new vehicles from basicData."""
    api = {
        "technicalData": {
            "basicData": {
                "technicalInspectionExpiryDate": "2027-04-10"
            }
        }
    }
    _, expiry, _ = _latest_inspection(api)
    assert expiry == date(2027, 4, 10)


def test_latest_inspection_timeline():
    """Verify inspection expiry from timeline events."""
    api = {
        "timelineData": {
            "events": [
                {
                    "eventDate": "2024-05-10",
                    "description": "Okresowe badanie techniczne, ważne do 10.05.2025",
                }
            ]
        }
    }
    event_d, expiry, _ = _latest_inspection(api)
    assert event_d == date(2024, 5, 10)
    assert expiry == date(2025, 5, 10)


def test_is_stolen():
    """Verify theft detection logic."""
    assert not _is_stolen({})
    assert not _is_stolen({"technicalData": {"basicData": {"isStolen": False}}})

    # Basic data boolean
    assert _is_stolen({"technicalData": {"basicData": {"isStolen": True}}})
    # Basic data string
    assert _is_stolen({"technicalData": {"basicData": {"stolen": "tak"}}})
    # Timeline event
    assert _is_stolen({
        "timelineData": {
            "events": [
                {"eventType": "Kradzież pojazdu", "description": "Zgłoszono kradzież"}
            ]
        }
    })
