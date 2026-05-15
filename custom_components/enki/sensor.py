"""Sensor platform for Enki integration."""

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    LIGHT_LUX,
)
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
    """Set up sensors."""
    coordinator: EnkiCoordinator = config_entry.runtime_data.coordinator

    sensors = []
    for device in coordinator.data:
        if device.get("type") != "sensors":
            continue
        caps = device.get("capabilities", [])
        if "check_current_temperature" in caps:
            sensors.append(EnkiTemperatureSensor(coordinator, device))
        if "check_current_humidity" in caps:
            sensors.append(EnkiHumiditySensor(coordinator, device))
        if "check_motion_detection" in caps:
            sensors.append(EnkiPresenceSensor(coordinator, device))
        if "check_illuminance_level" in caps:
            sensors.append(EnkiLuminositySensor(coordinator, device))
        if "check_battery_health" in caps:
            sensors.append(EnkiBatterySensor(coordinator, device))

    async_add_entities(sensors)


class EnkiSensorBase(EnkiBaseEntity, SensorEntity):
    """Base class for Enki sensors."""

    _sensor_key: str
    _sensor_suffix: str

    def __init__(self, coordinator: EnkiCoordinator, device: dict[str, Any]) -> None:
        super().__init__(coordinator, device, self._sensor_suffix)
        self._device = device

    @property
    def unique_id(self) -> str:
        from .const import DOMAIN
        return f"{DOMAIN}-{self._device['nodeId']}-{self._sensor_suffix}"

    @property
    def name(self) -> str:
        return self._sensor_suffix.replace("_", " ").title()

    def _get_sensor_value(self):
        device = self.coordinator.get_node(self._device["nodeId"])
        if device is None:
            return None
        return device.get(self._sensor_key)

    @property
    def native_value(self):
        return self._get_sensor_value()


class EnkiTemperatureSensor(EnkiSensorBase):
    _sensor_key = "temperatureValue"
    _sensor_suffix = "temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS


class EnkiHumiditySensor(EnkiSensorBase):
    _sensor_key = "humidityValue"
    _sensor_suffix = "humidity"
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE


class EnkiPresenceSensor(EnkiSensorBase):
    _sensor_key = "presenceValue"
    _sensor_suffix = "presence"

    @property
    def native_value(self):
        value = self._get_sensor_value()
        if value is None:
            return None
        return "detected" if value else "clear"


class EnkiLuminositySensor(EnkiSensorBase):
    _sensor_key = "illuminanceValue"
    _sensor_suffix = "luminosity"
    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = LIGHT_LUX


class EnkiBatterySensor(EnkiSensorBase):
    _sensor_key = "batteryValue"
    _sensor_suffix = "battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
