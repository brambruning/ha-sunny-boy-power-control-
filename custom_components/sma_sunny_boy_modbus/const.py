"""Constants for the SMA Sunny Boy Modbus integration."""

DOMAIN = "sma_sunny_boy_modbus"

# Config keys
CONF_HOST = "host"
CONF_PORT = "port"
CONF_UNIT_ID = "unit_id"
CONF_INSTALLER_PASSWORD = "installer_password"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_DEVICE_NAME = "device_name"

# Defaults
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 3
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_TIMEOUT = 10
DEFAULT_DEVICE_NAME = "SMA Sunny Boy"

# ── Modbus register addresses (SMA Sunny Boy) ──────────────────────────────
# These addresses are sent as-is in the Modbus PDU (SMA convention).

# Status / identification
REG_DEVICE_STATUS   = 30201   # U32 ENUM  — device operating status
REG_NOMINAL_POWER   = 30203   # U32 FIX0  — rated AC output power (W)

# Energy yield
REG_TOTAL_YIELD     = 30513   # U64 Wh    — lifetime energy yield
REG_DAILY_YIELD     = 30517   # U64 Wh    — today's energy yield
REG_OPERATING_TIME  = 30521   # U64 s     — total operating seconds

# AC electrical values
REG_REAL_POWER      = 30775   # S32 FIX0  — AC real power (W)
REG_AC_VOLTAGE      = 30783   # U32 FIX2  — AC voltage / 100 = Volt
REG_AC_CURRENT      = 30795   # U32 FIX3  — AC current / 1000 = Ampere
REG_AC_FREQUENCY    = 30803   # U32 FIX2  — AC frequency / 100 = Hz

# Active power control — status / setpoints (read-only)
REG_POWER_MODE_STATUS      = 30835  # U32 ENUM  — active power mode (status)
REG_SETPOINT_WATT          = 30837  # U32 FIX0  — active setpoint (W)
REG_SETPOINT_PERCENT       = 30839  # U32 FIX0  — active setpoint (%)

# Temperature
REG_TEMPERATURE     = 30953   # S32 FIX1  — internal temperature / 10 = °C

# Active power control — writable config (holding registers)
REG_ACTIVE_POWER_MODE    = 40210   # U32 ENUM  — write power control mode
REG_POWER_LIMIT_WATT     = 40212   # U32 FIX0  — write limit in Watts
REG_POWER_LIMIT_PERCENT  = 40214   # U32 FIX0  — write limit in %

# SMA Grid Guard login register
SMA_LOGIN_REGISTER = 43090

# ── Power mode codes ───────────────────────────────────────────────────────
POWER_MODE_OFF      = 303
POWER_MODE_WATT     = 1077
POWER_MODE_PERCENT  = 1078
POWER_MODE_EXTERNAL = 1079
POWER_MODE_ANALOG   = 1390
POWER_MODE_DIGITAL  = 1391

POWER_MODE_LABELS = {
    POWER_MODE_OFF:      "Off",
    POWER_MODE_WATT:     "Manual (W)",
    POWER_MODE_PERCENT:  "Manual (%)",
    POWER_MODE_EXTERNAL: "External",
    POWER_MODE_ANALOG:   "Analog input",
    POWER_MODE_DIGITAL:  "Digital inputs",
}

# ── Device status codes ────────────────────────────────────────────────────
DEVICE_STATUS_LABELS = {
    35:  "Error",
    303: "Off",
    307: "OK",
    455: "Warning",
}

# ── Register read batches ──────────────────────────────────────────────────
# Each tuple: (start_address, count).  Grouped to minimise TCP round-trips.
READ_BATCHES = [
    (30201, 6),    # device status, nominal power
    (30513, 12),   # total yield, daily yield, operating time
    (30773, 36),   # real power, AC voltage, current, frequency
    (30833, 10),   # power mode status, setpoints
    (30951, 6),    # temperature
    (40209, 8),    # active power mode config, limit W, limit %
]
