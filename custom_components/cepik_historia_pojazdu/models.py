"""Domain models and parsers for CEPiK Historia Pojazdu."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


def _flatten(obj: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten dictionaries/lists into (path, value) pairs."""
    out: list[tuple[str, Any]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            out.extend(_flatten(value, path))
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            path = f"{prefix}[{idx}]"
            out.extend(_flatten(value, path))
    else:
        out.append((prefix, obj))
    return out


def _find_values(obj: Any, names: set[str]) -> list[tuple[str, Any]]:
    wanted = {n.lower() for n in names}
    return [
        (path, value)
        for path, value in _flatten(obj)
        if path.rsplit(".", 1)[-1].split("[", 1)[0].lower() in wanted
    ]


def _to_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if value is None:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            pass
    return None


def _parse_date_any(value: Any) -> date | None:
    d = _to_date(value)
    if d:
        return d
    text = str(value or "")
    m = re.search(r"(?<!\d)(\d{2})[./-](\d{2})[./-](\d{4})(?!\d)", text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    m = re.search(r"(?<!\d)(20\d{2})[-/](\d{2})[-/](\d{2})(?!\d)", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def _timeline_events(api: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        api.get("timelineData"),
        api.get("timeline_data"),
    ]
    events: list[dict[str, Any]] = []
    for candidate in candidates:
        if isinstance(candidate, dict):
            value = candidate.get("events") or candidate.get("event") or []
            if isinstance(value, list):
                events.extend(x for x in value if isinstance(x, dict))
    if events:
        return events
    return []


def _event_date(event: dict[str, Any]) -> date | None:
    for key in ("eventDate", "date", "event_date", "data"):
        if key in event:
            d = _parse_date_any(event[key])
            if d:
                return d
    return None


def _event_text(event: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("eventType", "eventName", "name", "description", "eventDescription"):
        if key in event and event[key] is not None:
            parts.append(str(event[key]))
    details = event.get("eventDetails")
    if details is not None:
        parts.append(str(details))
        for path, value in _flatten(details):
            parts.append(f"{path}={value}")
    return " | ".join(parts)


def _extract_km(value: Any) -> int | None:
    text = str(value or "").replace("\u00a0", " ")
    # Strip potential calendar dates so dates like 12.05.2023 are not extracted as odometer km
    text_clean = re.sub(r"\b\d{2}[./-]\d{2}[./-]\d{4}\b", "", text)
    text_clean = re.sub(r"\b\d{4}[./-]\d{2}[./-]\d{2}\b", "", text_clean)

    patterns = [
        r"(\d[\d\s.]*)\s*km\b",
        r"(\d[\d\s.]*)\s*kilometr",
        r"(?:drogomierza|przebieg)[^0-9]{0,30}(\d[\d\s.]*)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text_clean, re.IGNORECASE)
        if m:
            digits = re.sub(r"\D", "", m.group(1))
            if digits:
                return int(digits)
    return None


def _latest_odometer(api: dict[str, Any]) -> tuple[int | None, date | None, str | None]:
    """Read the odometer from timeline events or raw properties."""
    candidates: list[tuple[date | None, int, str]] = []

    # 1. First check structured readings in timelineData
    timeline = api.get("timelineData", {})
    if isinstance(timeline, dict) and "odometerReadings" in timeline:
        for reading in timeline.get("odometerReadings", []):
            if isinstance(reading, dict) and reading.get("value"):
                r_date = _parse_date_any(reading.get("date") or reading.get("readingDate") or reading.get("eventDate"))
                try:
                    candidates.append((r_date, int(reading["value"]), "timelineData.odometerReadings"))
                except (ValueError, TypeError):
                    pass

    # 2. Check basicData in technicalData
    tech = api.get("technicalData", {}) if isinstance(api.get("technicalData"), dict) else {}
    basic = tech.get("basicData", {}) if isinstance(tech.get("basicData"), dict) else {}
    if isinstance(basic, dict) and "odometerReadings" in basic:
        val = basic.get("odometerReadings")
        if isinstance(val, (int, str)):
            km = _extract_km(str(val))
            if km is not None:
                candidates.append((None, km, "technicalData.basicData.odometerReadings"))

    # 3. Check timeline events
    for event in _timeline_events(api):
        text = _event_text(event)
        km = _extract_km(text)
        if km is not None:
            candidates.append((_event_date(event), km, text[:500]))

    if not candidates:
        return None, None, None

    with_date = [x for x in candidates if x[0] is not None]
    if with_date:
        chosen = max(with_date, key=lambda x: x[0] or date.min)
        return chosen[1], chosen[0], chosen[2]

    chosen = candidates[-1]
    return chosen[1], chosen[0], chosen[2]


def _latest_inspection(api: dict[str, Any]) -> tuple[date | None, date | None, str | None]:
    """Return event date, expiry date, and source text for latest periodic inspection."""
    candidates = []

    # Check basicData in technicalData for new vehicles or direct properties
    tech = api.get("technicalData", {}) if isinstance(api.get("technicalData"), dict) else {}
    basic = tech.get("basicData", {}) if isinstance(tech.get("basicData"), dict) else {}
    for key in ("technicalInspectionExpiryDate", "nextTechnicalInspectionDate", "inspectionExpiryDate"):
        if basic.get(key):
            d = _parse_date_any(basic[key])
            if d:
                candidates.append((None, d, f"basicData.{key}"))

    for event in _timeline_events(api):
        text = _event_text(event)
        low = text.lower()
        if "badanie techniczne" not in low:
            continue

        event_d = _event_date(event)
        expiry = None
        m = re.search(r"wa[zż]ne?\s+do\s+(\d{2}[./-]\d{2}[./-]\d{4})", text, re.IGNORECASE)
        if m:
            expiry = _parse_date_any(m.group(1))

        if event_d or expiry:
            candidates.append((event_d, expiry, text[:800]))

    if not candidates:
        return None, None, None

    with_date = [x for x in candidates if x[0] is not None]
    if with_date:
        chosen = max(with_date, key=lambda x: x[0] or date.min)
        return chosen

    chosen = candidates[0]
    return chosen


def _oc_expiry(api: dict[str, Any]) -> date | None:
    timeline = api.get("timelineData", {})
    if isinstance(timeline, dict) and "insuranceExpiryDate" in timeline:
        d = _parse_date_any(timeline["insuranceExpiryDate"])
        if d:
            return d

    for _, value in _find_values(api, {"insuranceExpiryDate", "insurance_expiry_date"}):
        d = _parse_date_any(value)
        if d:
            return d
    return None


def _is_stolen(api: dict[str, Any]) -> bool:
    tech = api.get("technicalData", {}) if isinstance(api.get("technicalData"), dict) else {}
    basic = tech.get("basicData", {}) if isinstance(tech.get("basicData"), dict) else {}
    for key in ("isStolen", "stolen", "poszukiwany", "stolenStatus", "hasStolenRecord"):
        if key in basic:
            val = basic[key]
            if isinstance(val, bool):
                return val
            if isinstance(val, str):
                return val.strip().lower() in ("tak", "true", "1", "odnotowano", "poszukiwany")

    timeline = api.get("timelineData", {})
    if isinstance(timeline, dict):
        events = timeline.get("events") or timeline.get("event") or []
        if isinstance(events, list):
            for ev in events:
                if isinstance(ev, dict):
                    text = f"{ev.get('eventType', '')} {ev.get('eventName', '')} {ev.get('description', '')}".lower()
                    if "kradzie" in text:
                        return True
    return False


def extract_api_data(coordinator: Any) -> dict[str, Any]:
    """Return the actual CEPiK API payload, unwrapping coordinator data."""
    data = coordinator.data if hasattr(coordinator, "data") else coordinator
    if isinstance(data, CepikVehicleData):
        return data.raw
    if not isinstance(data, dict):
        return {}
    api = data.get("api")
    return api if isinstance(api, dict) else data


def device_info_obj(coordinator: Any) -> DeviceInfo:
    """Create HA DeviceInfo for the vehicle coordinator."""
    make = "CEPiK"
    model = None
    data = getattr(coordinator, "data", None)
    if isinstance(data, CepikVehicleData):
        make = data.make or "CEPiK"
        model = data.model
    elif isinstance(data, dict):
        api = data.get("api", data)
        if isinstance(api, dict):
            tech = api.get("technicalData", {}) if isinstance(api.get("technicalData"), dict) else {}
            basic = tech.get("basicData", {}) if isinstance(tech.get("basicData"), dict) else {}
            make = basic.get("make") or basic.get("brand") or "CEPiK"
            model = basic.get("model")

    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.vehicle_id)},
        name=f"CEPiK {coordinator.registration}",
        manufacturer=make,
        model=model,
        serial_number=coordinator.vin,
    )


# Public aliases
flatten = _flatten
find_values = _find_values
to_date = _to_date
parse_date_any = _parse_date_any
timeline_events = _timeline_events
extract_km = _extract_km
latest_odometer = _latest_odometer
latest_inspection = _latest_inspection
oc_expiry = _oc_expiry
is_stolen = _is_stolen


@dataclass
class CepikVehicleData:
    """Domain model representing parsed vehicle data from CEPiK."""

    registration: str | None = None
    vin: str | None = None
    first_registration_date: str | None = None
    make: str | None = None
    model: str | None = None
    production_year: str | int | None = None

    odometer_km: int | None = None
    odometer_date: date | None = None
    odometer_source: str | None = None

    inspection_event_date: date | None = None
    inspection_expiry_date: date | None = None
    inspection_source: str | None = None
    technical_inspection_status: str | None = None
    is_inspection_valid: bool | None = None

    has_current_oc: bool | None = None
    has_current_oc_raw: Any = None
    oc_expiry_date: date | None = None
    api_insurance_expiry_date: str | None = None

    odometer_readings_raw: Any = None
    is_stolen: bool = False
    report_generation_date: date | None = None
    timeline_events_count: int = 0

    raw: dict[str, Any] = field(default_factory=dict)
    http_status: int = 200
    last_update: str | None = None

    def __getitem__(self, key: str) -> Any:
        if key == "api":
            return self.raw
        if key == "http_status":
            return self.http_status
        if key == "last_update":
            return self.last_update
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: object) -> bool:
        return key in ("api", "http_status", "last_update")

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        http_status: int = 200,
        last_update: str | None = None,
    ) -> CepikVehicleData:
        """Parse raw API dictionary into domain model."""
        api = data.get("api") if isinstance(data, dict) and "api" in data else data
        if not isinstance(api, dict):
            api = {}

        tech = api.get("technicalData", {}) if isinstance(api.get("technicalData"), dict) else {}
        basic = tech.get("basicData", {}) if isinstance(tech.get("basicData"), dict) else {}

        make = basic.get("make") or basic.get("brand") or None
        model = basic.get("model")
        production_year = basic.get("productionYear") or basic.get("yearOfProduction")

        odometer_km, odometer_date, odometer_source = _latest_odometer(api)
        inspection_event, inspection_expiry, inspection_source = _latest_inspection(api)
        oc_expiry_val = _oc_expiry(api)

        raw_oc = basic.get("hasCurrentOCPolicy")
        if isinstance(raw_oc, bool):
            has_current_oc: bool | None = raw_oc
        elif isinstance(raw_oc, str):
            has_current_oc = raw_oc.strip().lower() in ("tak", "true", "aktualna", "aktualne", "1")
        elif raw_oc is not None:
            has_current_oc = bool(raw_oc)
        else:
            has_current_oc = None

        raw_status = basic.get("technicalInspectionStatus")
        if raw_status is None:
            is_inspection_valid = None
        else:
            is_inspection_valid = str(raw_status).strip().lower() in ("aktualne", "aktualny", "pozytywne", "true")

        is_stolen_val = _is_stolen(api)

        timeline = api.get("timelineData", {})
        report_gen_date = None
        if isinstance(timeline, dict) and "reportGenerationDate" in timeline:
            report_gen_date = _parse_date_any(timeline["reportGenerationDate"])

        timeline_count = len(_timeline_events(api))

        return cls(
            registration=api.get("registrationNumber"),
            vin=api.get("VINNumber"),
            first_registration_date=api.get("firstRegistrationDate"),
            make=make,
            model=model,
            production_year=production_year,
            odometer_km=odometer_km,
            odometer_date=odometer_date,
            odometer_source=odometer_source,
            inspection_event_date=inspection_event,
            inspection_expiry_date=inspection_expiry,
            inspection_source=inspection_source,
            technical_inspection_status=raw_status,
            is_inspection_valid=is_inspection_valid,
            has_current_oc=has_current_oc,
            has_current_oc_raw=raw_oc,
            oc_expiry_date=oc_expiry_val,
            api_insurance_expiry_date=api.get("insuranceExpiryDate"),
            odometer_readings_raw=basic.get("odometerReadings"),
            is_stolen=is_stolen_val,
            report_generation_date=report_gen_date,
            timeline_events_count=timeline_count,
            raw=api,
            http_status=data.get("http_status", http_status) if isinstance(data, dict) else http_status,
            last_update=data.get("last_update", last_update) if isinstance(data, dict) else last_update,
        )
