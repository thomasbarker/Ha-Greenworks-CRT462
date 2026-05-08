"""Sensors for Greenworks CRT4262."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    EntityCategory,
    PERCENTAGE,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import parse_datetime

from .const import DOMAIN
from .coordinator import GreenworksCoordinator

UNIT_RPM = "rpm"
UNIT_M2 = "m²"


def _ts(raw: Any) -> datetime | None:
    """Parse an ISO-like timestamp string to a UTC-aware datetime."""
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        dt = parse_datetime(str(raw))
        if dt is not None and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _ms_to_minutes(raw: Any) -> float | None:
    """Convert milliseconds to minutes."""
    try:
        return round(float(raw) / 60_000, 1)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class GreenworksSensorDescription(SensorEntityDescription):
    """Extended sensor description with a value extractor."""
    data_key: str = ""
    value_fn: Callable[[Any], Any] | None = None
    extra_attrs: tuple[str, ...] = field(default_factory=tuple)


SENSORS: tuple[GreenworksSensorDescription, ...] = (
    # ---- Status timestamps ----
    GreenworksSensorDescription(
        key="last_seen",
        name="Last Seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        data_key="last_login",
        value_fn=_ts,
        icon="mdi:clock-check",
    ),
    GreenworksSensorDescription(
        key="last_disconnected",
        name="Last Disconnected",
        device_class=SensorDeviceClass.TIMESTAMP,
        data_key="last_logout",
        value_fn=_ts,
        icon="mdi:clock-minus",
    ),
    # ---- GPS ----
    GreenworksSensorDescription(
        key="latitude",
        name="Latitude",
        native_unit_of_measurement=DEGREE,
        data_key="latitude",
        icon="mdi:latitude",
    ),
    GreenworksSensorDescription(
        key="longitude",
        name="Longitude",
        native_unit_of_measurement=DEGREE,
        data_key="longitude",
        icon="mdi:longitude",
    ),
    # ---- IDDS mowing statistics ----
    GreenworksSensorDescription(
        key="total_working_duration",
        name="Total Working Time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        data_key="total_working_duration_min",
        icon="mdi:timer",
    ),
    GreenworksSensorDescription(
        key="total_working_area",
        name="Total Working Area",
        native_unit_of_measurement=UNIT_M2,
        state_class=SensorStateClass.TOTAL_INCREASING,
        data_key="total_working_area_m2",
        icon="mdi:grass",
    ),
    GreenworksSensorDescription(
        key="current_session_duration",
        name="Last Session Duration",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        data_key="current_session_duration_min",
        icon="mdi:timer-play",
    ),
    GreenworksSensorDescription(
        key="current_session_area",
        name="Last Session Area",
        native_unit_of_measurement=UNIT_M2,
        data_key="current_session_area_m2",
        icon="mdi:selection-ellipse",
    ),
    GreenworksSensorDescription(
        key="session_count",
        name="Mowing Sessions",
        state_class=SensorStateClass.TOTAL_INCREASING,
        data_key="session_count",
        icon="mdi:counter",
    ),
    # ---- Motor datapoints (live when mower is running) ----
    GreenworksSensorDescription(
        key="motor_a_rpm",
        name="Drive Motor A",
        native_unit_of_measurement=UNIT_RPM,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="dp_motor_a_rpm",
        icon="mdi:engine",
    ),
    GreenworksSensorDescription(
        key="motor_b_rpm",
        name="Drive Motor B",
        native_unit_of_measurement=UNIT_RPM,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="dp_motor_b_rpm",
        icon="mdi:engine",
    ),
    GreenworksSensorDescription(
        key="blade_left_rpm",
        name="Left Blade RPM",
        native_unit_of_measurement=UNIT_RPM,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="dp_blade_left_rpm",
        icon="mdi:saw-blade",
    ),
    GreenworksSensorDescription(
        key="blade_mid_rpm",
        name="Middle Blade RPM",
        native_unit_of_measurement=UNIT_RPM,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="dp_blade_mid_rpm",
        icon="mdi:saw-blade",
    ),
    GreenworksSensorDescription(
        key="blade_right_rpm",
        name="Right Blade RPM",
        native_unit_of_measurement=UNIT_RPM,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="dp_blade_right_rpm",
        icon="mdi:saw-blade",
    ),
    # ---- Settings datapoints ----
    GreenworksSensorDescription(
        key="cut_height_mm",
        name="Cut Height",
        native_unit_of_measurement="mm",
        data_key="dp_cut_height_mm",
        icon="mdi:ruler",
    ),
    # ---- Battery ----
    GreenworksSensorDescription(
        key="battery_level",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        data_key="battery_level",
        icon="mdi:battery",
    ),
    GreenworksSensorDescription(
        key="battery_slot_1",
        name="Battery Slot 1",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="battery_slot_1",
        icon="mdi:battery",
    ),
    GreenworksSensorDescription(
        key="battery_slot_2",
        name="Battery Slot 2",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="battery_slot_2",
        icon="mdi:battery",
    ),
    GreenworksSensorDescription(
        key="battery_slot_3",
        name="Battery Slot 3",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="battery_slot_3",
        icon="mdi:battery",
    ),
    GreenworksSensorDescription(
        key="battery_slot_4",
        name="Battery Slot 4",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="battery_slot_4",
        icon="mdi:battery",
    ),
    GreenworksSensorDescription(
        key="battery_slot_5",
        name="Battery Slot 5",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="battery_slot_5",
        icon="mdi:battery",
    ),
    GreenworksSensorDescription(
        key="battery_slot_6",
        name="Battery Slot 6",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="battery_slot_6",
        icon="mdi:battery",
    ),
    # ---- Remaining cutting capacity ----
    GreenworksSensorDescription(
        key="remaining_cutting_area",
        name="Remaining Cutting Area",
        native_unit_of_measurement=UNIT_M2,
        data_key="remaining_cutting_area_m2",
        icon="mdi:grass",
    ),
    GreenworksSensorDescription(
        key="remaining_cutting_time",
        name="Remaining Cutting Time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        data_key="remaining_cutting_time_min",
        icon="mdi:timer-sand",
    ),
    # ---- Diagnostic ----
    GreenworksSensorDescription(
        key="firmware_version",
        name="Firmware Version",
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="firmware_version",
        icon="mdi:chip",
    ),
    GreenworksSensorDescription(
        key="mcu_version",
        name="MCU Version",
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="mcu_version",
        icon="mdi:chip",
    ),
    GreenworksSensorDescription(
        key="connection_count",
        name="Connection Count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="online_count",
        icon="mdi:counter",
    ),
    GreenworksSensorDescription(
        key="dp_92",
        name="Status Code (DP 92)",
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="dp_92",
        icon="mdi:information-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GreenworksCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        GreenworksSensor(coordinator, desc) for desc in SENSORS
    )


class GreenworksSensor(CoordinatorEntity[GreenworksCoordinator], SensorEntity):
    """A sensor entity for the Greenworks mower."""

    _attr_has_entity_name = True
    entity_description: GreenworksSensorDescription

    def __init__(
        self,
        coordinator: GreenworksCoordinator,
        description: GreenworksSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        sn = coordinator.data.get("sn", "unknown")
        self._attr_unique_id = f"{sn}_{description.key}"
        self._attr_device_info = _device_info(coordinator)

    @property
    def native_value(self) -> Any:
        raw = self.coordinator.data.get(self.entity_description.data_key)
        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(raw)
        return raw

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        attrs: dict[str, Any] = {}

        if self.entity_description.key == "latitude":
            attrs["gps_timestamp"] = data.get("gps_timestamp")
        elif self.entity_description.key == "current_session_duration":
            start = data.get("current_session_start_ts")
            end = data.get("current_session_end_ts")
            if start is not None:
                try:
                    attrs["session_start"] = datetime.fromtimestamp(
                        int(start) / 1000, tz=timezone.utc
                    ).isoformat()
                except (ValueError, TypeError, OSError):
                    pass
            if end is not None:
                try:
                    attrs["session_end"] = datetime.fromtimestamp(
                        int(end) / 1000, tz=timezone.utc
                    ).isoformat()
                except (ValueError, TypeError, OSError):
                    pass
        elif self.entity_description.key == "session_count":
            safe_sessions = []
            for s in (data.get("latest_sessions") or []):
                try:
                    start_ts = s.get("startTimeStamp")
                    end_ts = s.get("endTimeStamp")
                    if start_ts is None or end_ts is None:
                        continue
                    safe_sessions.append({
                        "start": datetime.fromtimestamp(
                            int(start_ts), tz=timezone.utc
                        ).isoformat(),
                        "end": datetime.fromtimestamp(
                            int(end_ts), tz=timezone.utc
                        ).isoformat(),
                        "id": s.get("sessionId", ""),
                    })
                except (ValueError, TypeError, OSError):
                    continue
            attrs["latest_sessions"] = safe_sessions
        elif self.entity_description.key == "battery_level":
            # Include IDDS battery check details as attributes when available
            total_power = data.get("battery_total_power")
            if total_power is not None:
                attrs["idds_total_power_pct"] = total_power
            slot_details = data.get("battery_slot_details")
            if slot_details:
                attrs["slot_details"] = slot_details

        return attrs


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
