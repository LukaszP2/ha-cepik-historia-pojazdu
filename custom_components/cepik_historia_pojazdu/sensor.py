"""CEPiK sensors."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CepikCoordinator
from .models import (
    CepikVehicleData,
    device_info_obj,
    extract_api_data,
)
from .models import (
    extract_km as _extract_km,
)
from .models import (
    find_values as _find_values,
)
from .models import (
    flatten as _flatten,
)
from .models import (
    latest_inspection as _latest_inspection,
)
from .models import (
    latest_odometer as _latest_odometer,
)
from .models import (
    oc_expiry as _oc_expiry,
)
from .models import (
    parse_date_any as _parse_date_any,
)
from .models import (
    timeline_events as _timeline_events,
)
from .models import (
    to_date as _to_date,
)

_LOGGER = logging.getLogger(__name__)

# Re-exported helpers for backward compatibility
_api = extract_api_data
_device_info_obj = device_info_obj

__all__ = [
    "CepikEntity",
    "CepikInspectionDateSensor",
    "CepikMainSensor",
    "CepikOcDateSensor",
    "CepikOdometerDateSensor",
    "CepikOdometerSensor",
    "CepikProductionYearSensor",
    "CepikUpdateDateSensor",
    "_api",
    "_device_info",
    "_device_info_obj",
    "_extract_km",
    "_find_values",
    "_flatten",
    "_latest_inspection",
    "_latest_odometer",
    "_oc_expiry",
    "_parse_date_any",
    "_timeline_events",
    "_to_date",
    "async_setup_entry",
]


def _device_info(coordinator: CepikCoordinator) -> dict[str, Any]:
    api = _api(coordinator)
    return {
        "identyfikator_pojazdu": coordinator.vehicle_id,
        "rejestracja": api.get("registrationNumber"),
        "VIN": api.get("VINNumber"),
        "data_pierwszej_rejestracji": api.get("firstRegistrationDate"),
    }


class CepikEntity(CoordinatorEntity[CepikCoordinator]):
    """Base entity for CEPiK sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_device_info = device_info_obj(coordinator)

    @property
    def vehicle_data(self) -> CepikVehicleData:
        """Return parsed domain model from coordinator."""
        data = self.coordinator.data
        if isinstance(data, CepikVehicleData):
            return data
        if isinstance(data, dict):
            return CepikVehicleData.from_dict(data)
        return CepikVehicleData()


class CepikMainSensor(CepikEntity, SensorEntity):
    _attr_icon = "mdi:car-info"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.vehicle_id}_main"
        self._attr_translation_key = "status"

    @property
    def native_value(self) -> str:
        return "data_current" if self.coordinator.last_update_success else "data_error"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.vehicle_data
        return {
            "identyfikator_pojazdu": self.coordinator.vehicle_id,
            "rejestracja": data.registration,
            "VIN": data.vin,
            "data_pierwszej_rejestracji": data.first_registration_date,
            "api_technicalInspectionStatus": data.technical_inspection_status,
            "api_validOcInsurance": data.has_current_oc_raw,
            "api_insuranceExpiryDate": data.api_insurance_expiry_date,
            "api_odometerReadings": data.odometer_readings_raw,
            "marka": data.make,
            "model": data.model,
            "rok_produkcji": data.production_year,
        }


class CepikOdometerSensor(CepikEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.vehicle_id}_odometer"
        self._attr_translation_key = "odometer"

    @property
    def native_value(self) -> int | None:
        return self.vehicle_data.odometer_km

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.vehicle_data
        return {
            "data_odczytu": data.odometer_date.isoformat() if data.odometer_date else None,
            "zrodlo": data.odometer_source,
            "liczba_eventow_timeline": data.timeline_events_count,
        }


class CepikOdometerDateSensor(CepikEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.vehicle_id}_odometer_date"
        self._attr_translation_key = "odometer_date"

    @property
    def native_value(self) -> date | None:
        return self.vehicle_data.odometer_date


class CepikInspectionDateSensor(CepikEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:car-wrench"

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.vehicle_id}_inspection_expiry"
        self._attr_translation_key = "inspection_expiry"

    @property
    def native_value(self) -> date | None:
        return self.vehicle_data.inspection_expiry_date


class CepikOcDateSensor(CepikEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:shield-car"

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.vehicle_id}_oc_expiry"
        self._attr_translation_key = "oc_expiry"

    @property
    def native_value(self) -> date | None:
        return self.vehicle_data.oc_expiry_date


class CepikUpdateDateSensor(CepikEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:cloud-refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.vehicle_id}_update_date"
        self._attr_translation_key = "update_date"

    @property
    def native_value(self) -> date | None:
        return self.vehicle_data.report_generation_date

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "description_key": "report_generation"
        }


class CepikProductionYearSensor(CepikEntity, SensorEntity):
    _attr_icon = "mdi:calendar-range"

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.vehicle_id}_production_year"
        self._attr_translation_key = "production_year"

    @property
    def native_value(self) -> str | int | None:
        return self.vehicle_data.production_year


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
        CepikProductionYearSensor(coordinator),
    ])
