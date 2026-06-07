"""DataUpdateCoordinator for SMA Sunny Boy Modbus."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_HOST,
    CONF_INSTALLER_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_UNIT_ID,
    DOMAIN,
)
from .modbus_client import SMAModbusClient, SMAModbusError

_LOGGER = logging.getLogger(__name__)


class SMACoordinator(DataUpdateCoordinator[dict]):
    """
    Coordinator that polls the SMA Sunny Boy via Modbus TCP.

    A fresh TCP connection is opened and closed on every poll cycle.
    This matches the behaviour of the PHP reference implementation and avoids
    stale-connection issues with the inverter's Modbus server.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        conf = {**entry.data, **entry.options}
        self._host: str = conf[CONF_HOST]
        self._port: int = conf.get(CONF_PORT, DEFAULT_PORT)
        self._unit_id: int = conf.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)
        self._installer_password: str = conf.get(CONF_INSTALLER_PASSWORD, "")
        scan_interval: int = conf.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    def _make_client(self) -> SMAModbusClient:
        return SMAModbusClient(
            host=self._host,
            port=self._port,
            unit_id=self._unit_id,
            timeout=DEFAULT_TIMEOUT,
        )

    async def _async_update_data(self) -> dict:
        client = self._make_client()
        try:
            await client.connect()
            data = await client.read_all_data()
            data["last_updated"] = dt_util.now()
            return data
        except SMAModbusError as exc:
            raise UpdateFailed(f"Modbus error: {exc}") from exc
        except Exception as exc:
            raise UpdateFailed(f"Unexpected error: {exc}") from exc
        finally:
            await client.disconnect()

    async def async_set_power_limit_percent(self, percent: float) -> None:
        """Write a percentage-based power limit to the inverter."""
        client = self._make_client()
        try:
            await client.connect()
            await client.set_power_limit_percent(percent, self._installer_password)
        except SMAModbusError as exc:
            _LOGGER.error("Failed to set power limit: %s", exc)
            raise
        finally:
            await client.disconnect()

        await self.async_request_refresh()

    async def async_set_power_limit_watt(self, watts: int) -> None:
        """Write a Watt-based power limit to the inverter."""
        client = self._make_client()
        try:
            await client.connect()
            await client.set_power_limit_watt(watts, self._installer_password)
        except SMAModbusError as exc:
            _LOGGER.error("Failed to set power limit: %s", exc)
            raise
        finally:
            await client.disconnect()

        await self.async_request_refresh()
