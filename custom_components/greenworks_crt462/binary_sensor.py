"""Binary sensors for Greenworks CRT4262."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GreenworksCoordinator


@dataclass(frozen=True)
class GreenworksBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a Greenworks binary sensor."""
    data_key: str = ""


BINARY_SENSORS: tuple[GreenworksBinarySensorDescription, ...] = (
    GreenworksBinarySensorDescription(
        key="online",
        name="Online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        data_key="is_online",
        icon="mdi:lan-connect",
    ),
    GreenworksBinarySensorDescription(
        key="active",
        name="Active",
        device_class=BinarySensorDeviceClass.RUNNING,
        data_key="is_active",
        icon="mdi:robot-mower",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GreenworksCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        GreenworksBinarySensor(coordinator, desc) for desc in BINARY_SENSORS
    )


class GreenworksBinarySensor(
    CoordinatorEntity[GreenworksCoordinator], BinarySensorEntity
):
    """A binary sensor for the Greenworks mower."""

    _attr_has_entity_name = True
    entity_description: GreenworksBinarySensorDescription

    def __init__(
        self,
        coordinator: GreenworksCoordinator,
        description: GreenworksBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        sn = coordinator.data.get("sn", "unknown")
        self._attr_unique_id = f"{sn}_{description.key}"
        self._attr_device_info = _device_info(coordinator)

    @property
    def is_on(self) -> bool | None:
        return bool(self.coordinator.data.get(self.entity_description.data_key))


def _device_info(coordinator: GreenworksCoordinator) -> DeviceInfo:
    data = coordinator.data
    return DeviceInfo(
        identifiers={(DOMAIN, data.get("sn", "crt4262"))},
        name=data.get("name", "Greenworks Mower"),
        model="CRT4262",
        manufacturer="Greenworks",
        sw_version=data.get("firmware_version") or None,
        hw_version=data.get("mcu_version") or None,
        serial_number=data.get("sn") or None,
    )
