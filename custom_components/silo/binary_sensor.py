"""Binary sensor platform for SiLO (overall health)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SiLOEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HpeHealthBinarySensor(coordinator)])


class HpeHealthBinarySensor(SiLOEntity, BinarySensorEntity):
    """On (problem) when overall health is not OK."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Health problem"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_health_problem"

    @property
    def is_on(self):
        health = (self.coordinator.data or {}).get("health")
        if health is None:
            return None
        return health != "OK"

    @property
    def extra_state_attributes(self):
        return {"health": (self.coordinator.data or {}).get("health")}
