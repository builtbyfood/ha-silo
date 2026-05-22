"""Shared device info / base entity for SiLO."""
from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


def build_device_info(coordinator) -> DeviceInfo:
    data = coordinator.data or {}
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.entry.entry_id)},
        manufacturer="HPE",
        name=data.get("model") or f"HPE iLO @ {coordinator.entry.data[CONF_HOST]}",
        model=data.get("model"),
        serial_number=data.get("serial"),
        sw_version=data.get("ilo_firmware"),
        configuration_url=f"https://{coordinator.entry.data[CONF_HOST]}/",
    )


class SiLOEntity(CoordinatorEntity):
    """Base entity wiring device info + availability."""

    _attr_has_entity_name = True

    def __init__(self, coordinator):
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        return build_device_info(self.coordinator)
