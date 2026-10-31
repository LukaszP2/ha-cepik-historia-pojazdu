from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CepikCoordinator


class CepikOcBinarySensor(CoordinatorEntity[CepikCoordinator], BinarySensorEntity):
    _attr_icon = "mdi:shield-check"

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_translation_key = "oc_status"
        self._attr_unique_id = f"{coordinator.vehicle_id}_oc"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.vehicle_id)},
            name=f"CEPiK {coordinator.registration}",
        )

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.last_update_success:
            return None
        api = self.coordinator.data.get("api", {}) if self.coordinator.data else {}
        return (
            api.get("technicalData", {})
            .get("basicData", {})
            .get("hasCurrentOCPolicy")
        )


class CepikInspectionBinarySensor(
    CoordinatorEntity[CepikCoordinator], BinarySensorEntity
):
    _attr_icon = "mdi:car-wrench"

    def __init__(self, coordinator: CepikCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_translation_key = "inspection_status"
        self._attr_unique_id = f"{coordinator.vehicle_id}_inspection"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.vehicle_id)},
            name=f"CEPiK {coordinator.registration}",
        )

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.last_update_success:
            return None
        api = self.coordinator.data.get("api", {}) if self.coordinator.data else {}
        status = (
            api.get("technicalData", {})
            .get("basicData", {})
            .get("technicalInspectionStatus")
        )
        return str(status).lower() == "aktualne"


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            CepikOcBinarySensor(coordinator),
            CepikInspectionBinarySensor(coordinator),
        ]
    )
