"""Sensor platform for SiLO."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import SiLOEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}

    entities: list[SensorEntity] = [
        HpeValueSensor(coordinator, "ilo_firmware", "iLO firmware", icon="mdi:chip"),
        HpeValueSensor(coordinator, "bios_version", "BIOS version", icon="mdi:chip"),
        HpeValueSensor(coordinator, "power_state", "Power state", icon="mdi:power"),
        HpeValueSensor(coordinator, "cpu_model", "CPU model", icon="mdi:cpu-64-bit"),
        HpeValueSensor(coordinator, "cpu_count", "CPU count", icon="mdi:cpu-64-bit"),
        HpeValueSensor(coordinator, "cpu_cores", "CPU cores", icon="mdi:cpu-64-bit"),
        HpeValueSensor(coordinator, "cpu_threads", "CPU threads", icon="mdi:cpu-64-bit"),
        HpeValueSensor(coordinator, "ram_gib", "RAM", icon="mdi:memory", unit="GiB"),
        HpeValueSensor(coordinator, "ram_health", "Memory health", icon="mdi:memory"),
        HpeValueSensor(coordinator, "fw_integrity", "Firmware integrity", icon="mdi:shield-check"),
        HpeTimestampSensor(coordinator, "fw_last_scan", "Firmware last scan"),
    ]

    if data.get("critical_events") is not None:
        entities.append(
            HpeValueSensor(
                coordinator, "critical_events", "Critical events",
                icon="mdi:alert-circle", state_class=SensorStateClass.MEASUREMENT,
            )
        )

    for name in (data.get("temperatures") or {}):
        entities.append(HpeTempSensor(coordinator, name))
    for name in (data.get("fans") or {}):
        entities.append(HpeFanSensor(coordinator, name))
    for name in (data.get("firmware") or {}):
        entities.append(HpeFirmwareComponentSensor(coordinator, name))

    async_add_entities(entities)


class HpeValueSensor(SiLOEntity, SensorEntity):
    """Generic sensor reading a top-level coordinator key."""

    def __init__(self, coordinator, key, name, icon=None, unit=None, state_class=None):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        if icon:
            self._attr_icon = icon
        if unit:
            self._attr_native_unit_of_measurement = unit
        if state_class:
            self._attr_state_class = state_class

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self._key)


class HpeTimestampSensor(SiLOEntity, SensorEntity):
    """Timestamp sensor (e.g. last firmware integrity scan)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, key, name):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"

    @property
    def native_value(self):
        raw = (self.coordinator.data or {}).get(self._key)
        if not raw:
            return None
        return dt_util.parse_datetime(raw)


class HpeTempSensor(SiLOEntity, SensorEntity):
    """Per-sensor temperature reading."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator, sensor_name):
        super().__init__(coordinator)
        self._sensor_name = sensor_name
        self._attr_name = f"Temp {sensor_name}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_temp_{sensor_name}"

    @property
    def native_value(self):
        return ((self.coordinator.data or {}).get("temperatures") or {}).get(self._sensor_name)


class HpeFanSensor(SiLOEntity, SensorEntity):
    """Fan speed (percent)."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:fan"

    def __init__(self, coordinator, fan_name):
        super().__init__(coordinator)
        self._fan_name = fan_name
        self._attr_name = fan_name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_fan_{fan_name}"

    @property
    def native_value(self):
        return ((self.coordinator.data or {}).get("fans") or {}).get(self._fan_name)


def _fw_slug(name: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in name).strip("_")


class HpeFirmwareComponentSensor(SiLOEntity, SensorEntity):
    """Firmware version of a single component from the inventory."""

    _attr_icon = "mdi:chip"

    def __init__(self, coordinator, component_name):
        super().__init__(coordinator)
        self._component_name = component_name
        self._attr_name = f"FW {component_name}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_fw_comp_{_fw_slug(component_name)}"

    @property
    def native_value(self):
        return ((self.coordinator.data or {}).get("firmware") or {}).get(self._component_name)
