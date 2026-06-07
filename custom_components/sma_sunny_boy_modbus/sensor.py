"""Sensor entities for SMA Sunny Boy Modbus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME, DOMAIN
from .coordinator import SMACoordinator


@dataclass(frozen=True)
class SMAEntityDescription(SensorEntityDescription):
    """Extends SensorEntityDescription with a data key."""
    data_key: str = ""


SENSORS: tuple[SMAEntityDescription, ...] = (
    SMAEntityDescription(
        key="real_power",
        data_key="real_power",
        name="Current Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:solar-power",
    ),
    SMAEntityDescription(
        key="daily_yield",
        data_key="daily_yield",
        name="Today's Yield",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:weather-sunny",
    ),
    SMAEntityDescription(
        key="total_yield",
        data_key="total_yield",
        name="Total Yield",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:chart-line",
    ),
    SMAEntityDescription(
        key="ac_voltage",
        data_key="ac_voltage",
        name="AC Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
    ),
    SMAEntityDescription(
        key="ac_current",
        data_key="ac_current",
        name="AC Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:current-ac",
    ),
    SMAEntityDescription(
        key="ac_frequency",
        data_key="ac_frequency",
        name="AC Frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sine-wave",
    ),
    SMAEntityDescription(
        key="temperature",
        data_key="temperature",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
    ),
    SMAEntityDescription(
        key="device_status",
        data_key="device_status",
        name="Status",
        icon="mdi:information-outline",
    ),
    SMAEntityDescription(
        key="power_limit_percent",
        data_key="power_limit_percent",
        name="Power Limit",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:speedometer",
    ),
    SMAEntityDescription(
        key="power_limit_watt",
        data_key="power_limit_watt",
        name="Power Limit (W)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:speedometer",
    ),
    SMAEntityDescription(
        key="power_mode",
        data_key="power_mode",
        name="Power Control Mode",
        icon="mdi:tune",
    ),
    SMAEntityDescription(
        key="operating_hours",
        data_key="operating_hours",
        name="Operating Hours",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:timer-outline",
    ),
    SMAEntityDescription(
        key="last_updated",
        data_key="last_updated",
        name="Last Updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SMACoordinator = hass.data[DOMAIN][entry.entry_id]
    device_name: str = entry.data.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME)

    async_add_entities(
        SMASensor(coordinator, description, entry, device_name)
        for description in SENSORS
    )


class SMASensor(CoordinatorEntity[SMACoordinator], SensorEntity):
    """A sensor entity for one data point from the SMA Sunny Boy."""

    entity_description: SMAEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SMACoordinator,
        description: SMAEntityDescription,
        entry: ConfigEntry,
        device_name: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._device_name = device_name
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._device_name,
            manufacturer="SMA",
            model="Sunny Boy",
        )

    @property
    def native_value(self) -> Any:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.data_key)
