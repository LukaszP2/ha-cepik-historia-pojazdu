"""CEPiK binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
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
    is_stolen as _is_stolen,
)

# Re-exported helpers for backward compatibility
_api = extract_api_data
_device_info_obj = device_info_obj

__all__ = [
    "CepikBinaryEntity",
    "CepikInspectionBinarySensor",
    "CepikOcBinarySensor",
    "CepikStolenBinarySensor",
    "_api",
    "_device_info_obj",
    "_is_stolen",
    "async_setup_entry",
]


class CepikBinaryEntity(CoordinatorEntity[CepikCoordinator], BinarySensorEntity):
    """Base binary sensor for CEPiK."""

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


class CepikOcBinarySensor(CepikBinaryEntity):
    _attr_icon = "mdi:shield-check"

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = "oc_status"
        self._attr_unique_id = f"{coordinator.vehicle_id}_oc"

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.last_update_success:
            return None
        return self.vehicle_data.has_current_oc


class CepikInspectionBinarySensor(CepikBinaryEntity):
    _attr_icon = "mdi:car-wrench"

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = "inspection_status"
        self._attr_unique_id = f"{coordinator.vehicle_id}_inspection"

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.last_update_success:
            return None
        return self.vehicle_data.is_inspection_valid


class CepikStolenBinarySensor(CepikBinaryEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:car-emergency"

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = "stolen_status"
        self._attr_unique_id = f"{coordinator.vehicle_id}_stolen"

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.last_update_success:
            return None
        return self.vehicle_data.is_stolen


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            CepikOcBinarySensor(coordinator),
            CepikInspectionBinarySensor(coordinator),
            CepikStolenBinarySensor(coordinator),
        ]
    )
