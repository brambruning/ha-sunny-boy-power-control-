"""Number entity to set the SMA Sunny Boy power limit."""

from __future__ import annotations

import logging

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME, DOMAIN
from .coordinator import SMACoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SMACoordinator = hass.data[DOMAIN][entry.entry_id]
    device_name: str = entry.data.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME)
    async_add_entities([SMAPowerLimitNumber(coordinator, entry, device_name)])


class SMAPowerLimitNumber(CoordinatorEntity[SMACoordinator], NumberEntity):
    """
    Number entity that represents the active power limit (0–100 %).

    Writing a value immediately updates the inverter via Modbus TCP
    and triggers a coordinator refresh.
    """

    _attr_has_entity_name = True
    _attr_name = "Power Limit"
    _attr_icon = "mdi:speedometer"
    _attr_native_min_value = 0.0
    _attr_native_max_value = 100.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: SMACoordinator,
        entry: ConfigEntry,
        device_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_power_limit_control"
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
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        val = self.coordinator.data.get("power_limit_percent_cfg")
        return float(val) if val is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Called by Home Assistant when the user moves the slider."""
        _LOGGER.debug("Setting power limit to %.1f %%", value)
        await self.coordinator.async_set_power_limit_percent(value)
