"""Config flow for SMA Sunny Boy Modbus."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant

from .const import (
    CONF_DEVICE_NAME,
    CONF_HOST,
    CONF_INSTALLER_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DEFAULT_DEVICE_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_ID,
    DOMAIN,
)
from .modbus_client import SMAModbusClient

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): int,
        vol.Optional(CONF_INSTALLER_PASSWORD, default=""): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
        vol.Optional(CONF_DEVICE_NAME, default=DEFAULT_DEVICE_NAME): str,
    }
)


async def _validate_connection(hass: HomeAssistant, data: dict) -> dict[str, str]:
    """
    Try to connect to the inverter and read a register.
    Returns a dict of errors keyed by field name (or "base" for general errors).
    """
    errors: dict[str, str] = {}

    client = SMAModbusClient(
        host=data[CONF_HOST],
        port=data.get(CONF_PORT, DEFAULT_PORT),
        unit_id=data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID),
    )
    result = await client.test_connection()

    if not result["success"]:
        _LOGGER.debug("Connection test failed: %s", result["error"])
        if "refused" in result["error"].lower() or "timed out" in result["error"].lower():
            errors["host"] = "cannot_connect"
        else:
            errors["base"] = "cannot_connect"

    return errors


class SMAConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMA Sunny Boy Modbus."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            # Prevent duplicate entries for the same host/unit
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input.get(CONF_PORT, DEFAULT_PORT)}:{user_input.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)}"
            )
            self._abort_if_unique_id_configured()

            errors = await _validate_connection(self.hass, user_input)

            if not errors:
                return self.async_create_entry(
                    title=user_input.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )
