"""Switch platform for Enki integration (power outlets)."""

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EnkiConfigEntry
from .base import EnkiBaseEntity
from .coordinator import EnkiCoordinator
from .const import LOGGER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnkiConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up switches."""
    coordinator: EnkiCoordinator = config_entry.runtime_data.coordinator

    switches = [
        EnkiSwitch(coordinator, device)
        for device in coordinator.data
        if device.get("type") == "outlets"
    ]

    async_add_entities(switches)


class EnkiSwitch(EnkiBaseEntity, SwitchEntity):
    """Enki power outlet switch."""

    _attr_device_class = SwitchDeviceClass.OUTLET

    def __init__(self, coordinator: EnkiCoordinator, device: dict[str, Any]) -> None:
        super().__init__(coordinator, device, "state")
        self._device = device

    @property
    def name(self) -> str:
        return None

    @property
    def is_on(self) -> bool | None:
        device = self.coordinator.get_node(self._device["nodeId"])
        if device is None:
            return None
        last_reported = device.get("lastReportedValue")
        if isinstance(last_reported, str):
            return last_reported == "ON"
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.api.change_power_state(
            self._device["homeId"], self._device["nodeId"], True
        )
        self.coordinator.update_data(self._device["nodeId"], None, "state", "ON")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.change_power_state(
            self._device["homeId"], self._device["nodeId"], False
        )
        self.coordinator.update_data(self._device["nodeId"], None, "state", "OFF")
