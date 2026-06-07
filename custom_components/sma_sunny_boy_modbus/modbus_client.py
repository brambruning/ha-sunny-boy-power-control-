"""Async Modbus TCP client for SMA Sunny Boy inverters."""

from __future__ import annotations

import asyncio
import logging
import struct
from typing import Optional

from .const import (
    DEFAULT_TIMEOUT,
    DEVICE_STATUS_LABELS,
    POWER_MODE_LABELS,
    POWER_MODE_OFF,
    POWER_MODE_PERCENT,
    POWER_MODE_WATT,
    POWER_MODE_EXTERNAL,
    POWER_MODE_ANALOG,
    POWER_MODE_DIGITAL,
    READ_BATCHES,
    REG_AC_CURRENT,
    REG_AC_FREQUENCY,
    REG_AC_VOLTAGE,
    REG_ACTIVE_POWER_MODE,
    REG_DAILY_YIELD,
    REG_DEVICE_STATUS,
    REG_NOMINAL_POWER,
    REG_OPERATING_TIME,
    REG_POWER_LIMIT_PERCENT,
    REG_POWER_LIMIT_WATT,
    REG_POWER_MODE_STATUS,
    REG_REAL_POWER,
    REG_SETPOINT_PERCENT,
    REG_SETPOINT_WATT,
    REG_TEMPERATURE,
    REG_TOTAL_YIELD,
    SMA_LOGIN_REGISTER,
)

_LOGGER = logging.getLogger(__name__)


class SMAModbusError(Exception):
    """Raised when a Modbus communication error occurs."""


class SMAModbusClient:
    """
    Async Modbus TCP client that mirrors the SMA Sunny Boy PHP implementation.

    Register addresses are sent as-is (SMA convention — no offset subtraction).
    All read operations use FC 0x03 (Read Holding Registers).
    All write operations use FC 0x10 (Write Multiple Registers) for U32 values.
    """

    def __init__(
        self,
        host: str,
        port: int = 502,
        unit_id: int = 3,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._host = host
        self._port = port
        self._unit_id = unit_id
        self._timeout = timeout
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._transaction_id: int = 0
        self._lock = asyncio.Lock()

    # ── Connection ────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Open a TCP connection to the inverter."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=self._timeout,
            )
        except Exception as exc:
            raise SMAModbusError(
                f"Cannot connect to {self._host}:{self._port} — {exc}"
            ) from exc

    async def disconnect(self) -> None:
        """Close the TCP connection."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            finally:
                self._writer = None
                self._reader = None

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    # ── Low-level Modbus I/O ──────────────────────────────────────────────

    def _next_tid(self) -> int:
        self._transaction_id = (self._transaction_id + 1) & 0xFFFF
        return self._transaction_id

    async def _read_registers_raw(self, address: int, count: int) -> list[int]:
        """FC 0x03 — read *count* holding registers starting at *address*."""
        if not self.connected:
            raise SMAModbusError("Not connected")

        tid = self._next_tid()
        request = struct.pack(
            ">HHHBBHH",
            tid, 0, 6,
            self._unit_id, 0x03,
            address, count,
        )

        try:
            self._writer.write(request)
            await self._writer.drain()

            raw_header = await asyncio.wait_for(
                self._reader.readexactly(6), timeout=self._timeout
            )
            _, _, length = struct.unpack(">HHH", raw_header)

            body = await asyncio.wait_for(
                self._reader.readexactly(length), timeout=self._timeout
            )
        except asyncio.TimeoutError as exc:
            raise SMAModbusError(f"Timeout reading address {address}") from exc
        except asyncio.IncompleteReadError as exc:
            raise SMAModbusError(f"Connection closed reading address {address}") from exc

        if len(body) < 3:
            raise SMAModbusError("Response too short")

        _unit, func, byte_count = struct.unpack("BBB", body[:3])

        if func >= 0x80:
            raise SMAModbusError(
                f"Modbus exception 0x{body[2]:02X} reading address {address}"
            )

        num_regs = byte_count // 2
        return list(struct.unpack_from(f">{num_regs}H", body, 3))

    async def _write_u32_register(self, address: int, value: int) -> None:
        """FC 0x10 — write a 32-bit unsigned value to two consecutive registers."""
        if not self.connected:
            raise SMAModbusError("Not connected")

        value = max(0, int(value)) & 0xFFFFFFFF
        high_word = (value >> 16) & 0xFFFF
        low_word = value & 0xFFFF

        tid = self._next_tid()
        request = struct.pack(
            ">HHHBBHHBHH",
            tid, 0, 11,
            self._unit_id, 0x10,
            address, 2, 4,
            high_word, low_word,
        )

        try:
            self._writer.write(request)
            await self._writer.drain()

            raw_header = await asyncio.wait_for(
                self._reader.readexactly(6), timeout=self._timeout
            )
            _, _, length = struct.unpack(">HHH", raw_header)
            body = await asyncio.wait_for(
                self._reader.readexactly(length), timeout=self._timeout
            )
        except asyncio.TimeoutError as exc:
            raise SMAModbusError(f"Timeout writing address {address}") from exc
        except asyncio.IncompleteReadError as exc:
            raise SMAModbusError(f"Connection closed writing address {address}") from exc

        if len(body) >= 2 and body[1] >= 0x80:
            exc_code = body[2] if len(body) > 2 else 0
            raise SMAModbusError(
                f"Modbus write exception 0x{exc_code:02X} at address {address}"
            )

    async def _login_grid_guard(self, password: str) -> None:
        """Write the SMA Grid Guard code to unlock protected registers."""
        if not password or not password.isdigit():
            raise SMAModbusError(
                "Grid Guard code must be a numeric string"
            )
        code = int(password)
        high_word = (code >> 16) & 0xFFFF
        low_word = code & 0xFFFF

        tid = self._next_tid()
        request = struct.pack(
            ">HHHBBHHBHH",
            tid, 0, 11,
            self._unit_id, 0x10,
            SMA_LOGIN_REGISTER, 2, 4,
            high_word, low_word,
        )
        try:
            self._writer.write(request)
            await self._writer.drain()
            raw_header = await asyncio.wait_for(
                self._reader.readexactly(6), timeout=self._timeout
            )
            _, _, length = struct.unpack(">HHH", raw_header)
            await asyncio.wait_for(
                self._reader.readexactly(length), timeout=self._timeout
            )
        except Exception as exc:
            raise SMAModbusError(f"Grid Guard login failed: {exc}") from exc

        await asyncio.sleep(0.1)  # 100 ms settle time

    # ── Register helpers ──────────────────────────────────────────────────

    @staticmethod
    def _invalid_u32(w0: int, w1: int) -> bool:
        return (w0 == 0xFFFF and w1 == 0xFFFF) or (w0 == 0x8000 and w1 == 0x0000)

    @staticmethod
    def _to_u32(w0: int, w1: int) -> Optional[int]:
        if SMAModbusClient._invalid_u32(w0, w1):
            return None
        return (w0 << 16) | (w1 & 0xFFFF)

    @staticmethod
    def _to_s32(w0: int, w1: int) -> Optional[int]:
        raw = SMAModbusClient._to_u32(w0, w1)
        if raw is None:
            return None
        return raw - 0x100000000 if (raw & 0x80000000) else raw

    @staticmethod
    def _to_u64(w0: int, w1: int, w2: int, w3: int) -> Optional[int]:
        if all(w == 0xFFFF for w in (w0, w1, w2, w3)):
            return None
        return (w0 << 48) | (w1 << 32) | (w2 << 16) | w3

    # ── High-level data API ───────────────────────────────────────────────

    async def read_all_data(self) -> dict:
        """
        Read all sensor data from the inverter.
        Returns a dict with parsed, scaled values.
        Raises SMAModbusError on communication failure.
        """
        regs: dict[int, int] = {}

        async with self._lock:
            for start, count in READ_BATCHES:
                try:
                    values = await self._read_registers_raw(start, count)
                    for offset, val in enumerate(values):
                        regs[start + offset] = val
                    await asyncio.sleep(0.05)  # 50 ms inter-batch pause
                except SMAModbusError as exc:
                    _LOGGER.warning("Failed reading batch at %d: %s", start, exc)

        def get(addr: int) -> Optional[int]:
            return regs.get(addr)

        def u32(addr: int) -> Optional[int]:
            w0, w1 = get(addr), get(addr + 1)
            if w0 is None or w1 is None:
                return None
            return self._to_u32(w0, w1)

        def s32(addr: int) -> Optional[int]:
            w0, w1 = get(addr), get(addr + 1)
            if w0 is None or w1 is None:
                return None
            return self._to_s32(w0, w1)

        def u64(addr: int) -> Optional[int]:
            words = [get(addr + i) for i in range(4)]
            if any(w is None for w in words):
                return None
            return self._to_u64(*words)

        # ── Parse values ──────────────────────────────────────────────────

        real_power_raw = s32(REG_REAL_POWER)
        real_power = real_power_raw if real_power_raw is not None else 0

        voltage_raw = u32(REG_AC_VOLTAGE)
        ac_voltage = round(voltage_raw / 100, 1) if voltage_raw is not None else None

        current_raw = u32(REG_AC_CURRENT)
        ac_current = round(current_raw / 1000, 3) if current_raw is not None else None

        frequency_raw = u32(REG_AC_FREQUENCY)
        ac_frequency = round(frequency_raw / 100, 2) if frequency_raw is not None else None

        daily_raw = u64(REG_DAILY_YIELD)
        daily_yield = round(daily_raw / 1000, 3) if daily_raw is not None else None

        total_raw = u64(REG_TOTAL_YIELD)
        total_yield = round(total_raw / 1000, 3) if total_raw is not None else None

        temp_raw = s32(REG_TEMPERATURE)
        temperature = round(temp_raw / 10, 1) if temp_raw is not None else None

        op_raw = u64(REG_OPERATING_TIME)
        operating_hours = round(op_raw / 3600, 1) if op_raw is not None else None

        device_status_code = u32(REG_DEVICE_STATUS) or 0
        device_status = DEVICE_STATUS_LABELS.get(device_status_code, f"Unknown ({device_status_code})")

        nominal_power = u32(REG_NOMINAL_POWER) or 4000

        # ── Power limit state ─────────────────────────────────────────────
        mode_code = u32(REG_POWER_MODE_STATUS)
        cfg_mode = u32(REG_ACTIVE_POWER_MODE)
        cfg_watt = u32(REG_POWER_LIMIT_WATT)
        cfg_percent = u32(REG_POWER_LIMIT_PERCENT)
        sp_watt = u32(REG_SETPOINT_WATT)
        sp_percent = u32(REG_SETPOINT_PERCENT)

        # cfg_mode (40210) may revert to EXTERNAL after the Grid Guard session
        # expires, even though the limit written to cfg_percent (40214) persists
        # and the inverter continues to honour it. Always use cfg_percent as the
        # authoritative percentage value; fall back to sp_percent only when
        # cfg_percent is not available.
        active_mode = cfg_mode if cfg_mode is not None else mode_code

        _LOGGER.debug(
            "Power registers — mode_status(30835)=%s cfg_mode(40210)=%s "
            "cfg_pct(40214)=%s sp_pct(30839)=%s cfg_watt(40212)=%s sp_watt(30837)=%s",
            mode_code, cfg_mode, cfg_percent, sp_percent, cfg_watt, sp_watt,
        )

        effective_percent: Optional[float] = (
            float(cfg_percent) if cfg_percent is not None
            else float(sp_percent) if sp_percent is not None
            else None
        )

        effective_watt: Optional[int] = None
        if active_mode == POWER_MODE_WATT:
            effective_watt = cfg_watt
        elif active_mode in (POWER_MODE_EXTERNAL, POWER_MODE_ANALOG, POWER_MODE_DIGITAL):
            effective_watt = sp_watt

        if effective_watt is None and effective_percent is not None:
            effective_watt = round(nominal_power * (effective_percent / 100))
        if effective_percent is None and effective_watt is not None:
            effective_percent = round((effective_watt / nominal_power) * 100, 1)
        if effective_watt is None:
            effective_watt = cfg_watt or nominal_power
        if effective_percent is None:
            effective_percent = 100.0

        return {
            "real_power": real_power,
            "ac_voltage": ac_voltage,
            "ac_current": ac_current,
            "ac_frequency": ac_frequency,
            "daily_yield": daily_yield,
            "total_yield": total_yield,
            "temperature": temperature,
            "operating_hours": operating_hours,
            "device_status": device_status,
            "device_status_code": device_status_code,
            "nominal_power": nominal_power,
            "power_limit_percent": effective_percent,
            "power_limit_percent_cfg": float(cfg_percent) if cfg_percent is not None else 100.0,
            "power_limit_watt": effective_watt,
            "power_mode": POWER_MODE_LABELS.get(active_mode, f"Unknown ({active_mode})") if active_mode is not None else "Unknown",
            "power_mode_code": active_mode,
        }

    async def set_power_limit_percent(
        self, percent: float, installer_password: str = ""
    ) -> None:
        """Set the active power limit as a percentage (0–100 %)."""
        percent = max(0.0, min(100.0, float(percent)))

        async with self._lock:
            if installer_password:
                await self._login_grid_guard(installer_password)
                await asyncio.sleep(0.1)

            await self._write_u32_register(REG_POWER_LIMIT_PERCENT, round(percent))
            await asyncio.sleep(0.1)
            await self._write_u32_register(REG_ACTIVE_POWER_MODE, POWER_MODE_PERCENT)

    async def set_power_limit_watt(
        self, watts: int, installer_password: str = ""
    ) -> None:
        """Set the active power limit in Watts."""
        watts = max(0, int(watts))

        async with self._lock:
            if installer_password:
                await self._login_grid_guard(installer_password)
                await asyncio.sleep(0.1)

            await self._write_u32_register(REG_POWER_LIMIT_WATT, watts)
            await asyncio.sleep(0.1)
            await self._write_u32_register(REG_ACTIVE_POWER_MODE, POWER_MODE_WATT)

    async def test_connection(self) -> dict:
        """
        Quick connectivity test.
        Connects, reads device status, and disconnects.
        Returns {"success": bool, "error": str}.
        """
        try:
            await self.connect()
            raw = await self._read_registers_raw(REG_DEVICE_STATUS, 2)
            await self.disconnect()
            return {"success": True, "error": ""}
        except SMAModbusError as exc:
            await self.disconnect()
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            await self.disconnect()
            return {"success": False, "error": str(exc)}
