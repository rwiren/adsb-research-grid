# ==============================================================================
# File: config.py
# Version: 5.0.0
# Date: 2026-04-26
# Maintainer: Team-9 Secure Skies
# Description: Centralised configuration — constants, environment variables,
#              thresholds, and sensor positions.  Keeps all tunables in one
#              place so the dashboard and sub-modules read from a single source.
# ==============================================================================
import os

# ------------------------------------------------------------------------------
# MQTT
# ------------------------------------------------------------------------------
MQTT_HOST      = os.getenv("MQTT_HOST", "mqtt.securingskies.eu")
MQTT_PORT      = int(os.getenv("MQTT_PORT", "8443"))
MQTT_USER      = os.getenv("MQTT_USER", "team9")
MQTT_PASS_FILE = os.getenv("MQTT_PASS_FILE", "/etc/securing-skies/mqtt_secret")
MQTT_TLS       = os.getenv("MQTT_TLS", "true").lower() in ("true", "1", "yes")

# ------------------------------------------------------------------------------
# Physics & geometry
# ------------------------------------------------------------------------------
C = 299_792_458.0          # Speed of light (m/s)
MLAT_TTL = 15.0            # Seconds to hold last valid MLAT solution (decay)

# ------------------------------------------------------------------------------
# Sensor positions (WGS-84, decimal degrees)
# ------------------------------------------------------------------------------
SENSOR_POS = {
    "sensor-north": (60.319555, 24.830816),
    "sensor-west":  (60.130919, 24.512869),
    "sensor-east":  (60.373781, 25.250081),
}

# ------------------------------------------------------------------------------
# Heuristic thresholds
# ------------------------------------------------------------------------------
MAX_CREDIBLE_CLIMB_FPM = 8_000          # ft/min
MAX_GS_DISCREPANCY     = 1.5           # fraction

# ------------------------------------------------------------------------------
# Emergency / UAV squawk codes
# ------------------------------------------------------------------------------
EMERGENCY_SQUAWKS = {"7500", "7600", "7700"}
UAV_SQUAWKS       = {"7400"}
_UAV_CATEGORIES   = {"B4", "B6", "B7"}


def is_uav_category(category: str) -> bool:
    """Return True if the ADS-B emitter category indicates an unmanned aircraft."""
    return category in _UAV_CATEGORIES if category else False
