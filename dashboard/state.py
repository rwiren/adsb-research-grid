# ==============================================================================
# File: state.py
# Version: 5.0.0
# Date: 2026-04-26
# Maintainer: Team-9 Secure Skies
# Description: Shared runtime state.  Imported by both mqtt_handler and
#              dashboard so the SocketIO emitter can see the same object that
#              the MQTT callback mutates in place.
# ==============================================================================
from collections import deque

# ------------------------------------------------------------------------------
# Mutable live state
# ------------------------------------------------------------------------------
state = {
    "aircraft": {},
    "sensors": {
        "sensor-north": {
            "now": 0, "signal": 0, "noise": 0, "msg_rate": 0,
            "max_range_km": 0, "gain_db": 0, "ac_with_pos": 0, "ac_total": 0,
            "msg_rate_history": deque(maxlen=120), "temp_c": None, "load_1m": None,
        },
        "sensor-west": {
            "now": 0, "signal": 0, "noise": 0, "msg_rate": 0,
            "max_range_km": 0, "gain_db": 0, "ac_with_pos": 0, "ac_total": 0,
            "msg_rate_history": deque(maxlen=120), "temp_c": None, "load_1m": None,
        },
        "sensor-east": {
            "now": 0, "signal": 0, "noise": 0, "msg_rate": 0,
            "max_range_km": 0, "gain_db": 0, "ac_with_pos": 0, "ac_total": 0,
            "msg_rate_history": deque(maxlen=120), "temp_c": None, "load_1m": None,
        },
    },
    "sync": {"delta_ms": 0.0, "per_sensor": {}},
    "anomalies": {},
    "anomalies_v2": {},
    "jamming": [],
    "accuracy": {},
}
