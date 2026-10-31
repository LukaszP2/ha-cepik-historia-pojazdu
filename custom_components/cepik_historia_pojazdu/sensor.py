"""CEPiK sensors."""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CepikCoordinator

_LOGGER = logging.getLogger(__name__)


def _api(coordinator: CepikCoordinator) -> dict[str, Any]:
    """Return the actual CEPiK API payload, unwrapping coordinator metadata."""
    data = coordinator.data
    if not isinstance(data, dict):
        return {}
    api = data.get("api")
    return api if isinstance(api, dict) else data


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
    return [(path, value) for path, value in _flatten(obj)
            if path.rsplit(".", 1)[-1].split("[", 1)[0].lower() in wanted]


def _to_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if value is None:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            from datetime import datetime
            return datetime.strptime(text[:10], fmt).date()  # noqa: DTZ007
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
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = re.search(r"(?<!\d)(20\d{2})[-/](\d{2})[-/](\d{2})(?!\d)", text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
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
    patterns = [
        r"(\d[\d\s.]*)\s*km\b",
        r"(\d[\d\s.]*)\s*kilometr",
        r"(?:drogomierza|przebieg)[^0-9]{0,30}(\d[\d\s.]*)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            digits = re.sub(r"\D", "", m.group(1))
            if digits:
                return int(digits)
    return None


def _latest_odometer(api: dict[str, Any]) -> tuple[int | None, date | None, str | None]:
    """Read the odometer from timeline events or raw properties."""
    candidates: list[tuple[date | None, int, str]] = []

    for event in _timeline_events(api):
        text = _event_text(event)
        km = _extract_km(text)
        if km is not None:
            candidates.append((_event_date(event), km, text[:500]))

    timeline = api.get("timelineData", {})
    if isinstance(timeline, dict) and "odometerReadings" in timeline:
        for reading in timeline.get("odometerReadings", []):
            if isinstance(reading, dict) and reading.get("value"):
                candidates.append((None, int(reading["value"]), "timelineData.odometerReadings"))

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
        
    chosen = max(candidates, key=lambda x: x[0] or date.min)
    return chosen


def _oc_expiry(api: dict[str, Any]) -> date | None:
    timeline = api.get("timelineData", {})
    if isinstance(timeline, dict) and "insuranceExpiryDate" in timeline:
        d = _parse_date_any(timeline["insuranceExpiryDate"])
        if d:
            return d
            
    for path, value in _find_values(api, {"insuranceExpiryDate", "insurance_expiry_date"}):
        d = _parse_date_any(value)
        if d:
            return d
    return None


def _device_info(coordinator: CepikCoordinator) -> dict[str, Any]:
    api = _api(coordinator)
    return {
        "identyfikator_pojazdu": coordinator.vehicle_id,
        "rejestracja": api.get("registrationNumber"),
        "VIN": api.get("VINNumber"),
        "data_pierwszej_rejestracji": api.get("firstRegistrationDate"),
    }


class CepikMainSensor(CoordinatorEntity[CepikCoordinator], SensorEntity):
    _attr_icon = "mdi:car-info"

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.vehicle_id)}, name=f"CEPiK {coordinator.registration}")
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.vehicle_id}_main"
        self._attr_has_entity_name = True
        self._attr_translation_key = "status"

    @property
    def native_value(self) -> str:
        return "data_current" if self.coordinator.last_update_success else "data_error"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        api = _api(self.coordinator)
        attrs = _device_info(self.coordinator)
        basic = api.get("technicalData", {}).get("basicData", {}) if isinstance(api.get("technicalData"), dict) else {}
        attrs.update({
            "api_technicalInspectionStatus": basic.get("technicalInspectionStatus"),
            "api_validOcInsurance": basic.get("hasCurrentOCPolicy"),
            "api_insuranceExpiryDate": api.get("insuranceExpiryDate"),
            "api_odometerReadings": basic.get("odometerReadings"),
            "api_technicalData": api.get("technicalData"),
        })
        return attrs


class CepikOdometerSensor(CoordinatorEntity[CepikCoordinator], SensorEntity):
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = "km"
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.vehicle_id)}, name=f"CEPiK {coordinator.registration}")
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.vehicle_id}_odometer"
        self._attr_has_entity_name = True
        self._attr_translation_key = "odometer"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> int | None:
        km, _, _ = _latest_odometer(_api(self.coordinator))
        return km

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        _km, d, source = _latest_odometer(_api(self.coordinator))
        api = _api(self.coordinator)
        
        return {
            "data_odczytu": d.isoformat() if d else None,
            "zrodlo": source,
            "liczba_eventow_timeline": len(_timeline_events(api)),
            "timelineData": api.get("timelineData", {}), 
        }


class CepikOdometerDateSensor(CoordinatorEntity[CepikCoordinator], SensorEntity):
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.vehicle_id)}, name=f"CEPiK {coordinator.registration}")
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.vehicle_id}_odometer_date"
        self._attr_has_entity_name = True
        self._attr_translation_key = "odometer_date"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> date | None:
        _, d, _ = _latest_odometer(_api(self.coordinator))
        return d


class CepikInspectionDateSensor(CoordinatorEntity[CepikCoordinator], SensorEntity):
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:car-wrench"

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.vehicle_id)}, name=f"CEPiK {coordinator.registration}")
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.vehicle_id}_inspection_expiry"
        self._attr_has_entity_name = True
        self._attr_translation_key = "inspection_expiry"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> date | None:
        _, expiry, _ = _latest_inspection(_api(self.coordinator))
        return expiry


class CepikOcDateSensor(CoordinatorEntity[CepikCoordinator], SensorEntity):
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:shield-car"

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.vehicle_id)}, name=f"CEPiK {coordinator.registration}")
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.vehicle_id}_oc_expiry"
        self._attr_has_entity_name = True
        self._attr_translation_key = "oc_expiry"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> date | None:
        return _oc_expiry(_api(self.coordinator))


class CepikUpdateDateSensor(CoordinatorEntity[CepikCoordinator], SensorEntity):
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:cloud-refresh"

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.vehicle_id)}, name=f"CEPiK {coordinator.registration}")
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.vehicle_id}_update_date"
        self._attr_has_entity_name = True
        self._attr_translation_key = "update_date"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> date | None:
        api = _api(self.coordinator)
        timeline = api.get("timelineData", {})
        if isinstance(timeline, dict) and "reportGenerationDate" in timeline:
            return _parse_date_any(timeline["reportGenerationDate"])
        return None
        
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "description_key": "report_generation"
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CepikCoordinator = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.debug("Adding CEPiK sensor entities for %s (%s)", coordinator.registration, coordinator.vehicle_id)
    async_add_entities([
        CepikMainSensor(coordinator),
        CepikOdometerSensor(coordinator),
        CepikOdometerDateSensor(coordinator),
        CepikInspectionDateSensor(coordinator),
        CepikOcDateSensor(coordinator),
        CepikUpdateDateSensor(coordinator),
    ])