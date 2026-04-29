#!/usr/bin/env python3
# ==============================================================================
# File: synthetic_aircraft_injector.py
# Version: 2.1.0
# Date: 2026-04-27
# Description: Temporary aircraft feed simulator.  Publishes realistic looking
#              aircraft data via MQTT (WSS/TLS) to remote broker so MLAT
#              triangulation can be demonstrated even when physical sensors
#              are offline.
# ==============================================================================
import json
import math
import random
import signal
import ssl
import sys
import time

import paho.mqtt.client as mqtt

# ------------------------------------------------------------------------------
# Demo aircraft tracks
# ------------------------------------------------------------------------------
AIRCRAFT = [
    {"hex": "FIN1234",
     "flight": "FIN123",
     "squawk": "1234",
     "alt_baro": 8000,
     "gs": 280,
     "track": 180,
     "rssi": -15,
     "type": "adsb",
     "category": "A3",
     "lat": 60.300,
     "lon": 24.800},
    {"hex": "FIN5678",
     "flight": "FIN456",
     "squawk": "4567",
     "alt_baro": 15000,
     "gs": 400,
     "track": 45,
     "rssi": -20,
     "type": "adsb",
     "category": "A3",
     "lat": 60.150,
     "lon": 24.600},
    {"hex": "EZY01AB",
     "flight": "EZY01A",
     "squawk": "7000",
     "alt_baro": 3000,
     "gs": 200,
     "track": 270,
     "rssi": -12,
     "type": "adsb",
     "category": "A3",
     "lat": 60.250,
     "lon": 25.100},
]

# Linear motion vectors (lat/lon degrees per cycle)
MOVE = [
    ( 0.0008,  0.0015),   # FIN1234  SSE-ish
    ( 0.0010,  0.0008),   # FIN5678  NE-ish
    (-0.0005, -0.0012),   # EZY01AB  W-ish
]

SENSORS = ["sensor-north", "sensor-west", "sensor-east"]

MQTT_HOST    = "mqtt.securingskies.eu"
MQTT_PORT    = 8443
MQTT_USER    = "team9"
MQTT_PASS    = open("/etc/securing-skies/mqtt_secret", "r").read().strip()
INTERVAL     = 2.0  # seconds between publish cycles

running = True

def on_signal(sig, frame):
    global running
    running = False

signal.signal(signal.SIGTERM, on_signal)
signal.signal(signal.SIGINT, on_signal)

# ── Persistent MQTT client ──────────────────────────────────────────────────
_mqtt: mqtt.Client | None = None

def _init_mqtt() -> mqtt.Client:
    global _mqtt
    if _mqtt is not None:
        return _mqtt
    c = mqtt.Client(transport="websockets")
    c.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
    c.username_pw_set(MQTT_USER, MQTT_PASS)
    c.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    c.loop_start()
    _mqtt = c
    print(f"[injector] MQTT (WSS) connected to {MQTT_HOST}:{MQTT_PORT}")
    return _mqtt


def _publish(topic: str, payload: dict) -> None:
    try:
        c = _init_mqtt()
        c.publish(topic, json.dumps(payload))
    except Exception as e:
        print(f"[injector] MQTT publish error: {e}", flush=True)
        # Force reconnect on next call
        global _mqtt
        if _mqtt is not None:
            try:
                _mqtt.loop_stop()
                _mqtt.disconnect()
            except Exception:
                pass
            _mqtt = None


# ── Main loop ───────────────────────────────────────────────────────────────
print("[injector] Starting synthetic aircraft feed…")

counter = 0
while running:
    counter += 1
    now = time.time()

    for idx, ac in enumerate(AIRCRAFT):
        # Advance position
        ac["lat"] += MOVE[idx][0]
        ac["lon"] += MOVE[idx][1]
        # Tiny noise
        ac["lat"] += random.gauss(0, 0.00005)
        ac["lon"] += random.gauss(0, 0.00005)
        # Clamp bounds
        ac["lat"] = max(59.8, min(60.6, ac["lat"]))
        ac["lon"] = max(24.0, min(25.8, ac["lon"]))

        # Publish per-sensor with slightly offset per-sensor noise
        for sensor in SENSORS:
            msg = {
                "now": now,
                "seen_at": now,
                "aircraft": [
                    {
                        **ac,
                        "lat": ac["lat"] + random.gauss(0, 0.0001),
                        "lon": ac["lon"] + random.gauss(0, 0.0001),
                        "alt_baro": int(ac["alt_baro"] + random.gauss(0, 50)),
                    }
                ]
            }
            _publish(f"{sensor}/aircraft", msg)

    # Publish stats for each sensor
    for sensor in SENSORS:
        stats = {
            "now": now,
            "aircraft_with_pos": 7,
            "aircraft_without_pos": 2,
            "last1min": {
                "local": {
                    "signal": -20 + random.gauss(0, 2),
                    "noise": -40,
                },
                "messages_valid": 120 + int(random.gauss(0, 20)),
            },
            "last15min": {
                "max_distance": 25000 + int(random.gauss(0, 5000)),
            },
            "gain_db": 40,
        }
        _publish(f"{sensor}/stats", stats)

    time.sleep(INTERVAL)

# ── Cleanup ─────────────────────────────────────────────────────────────────
print("[injector] Exiting cleanly.")
if _mqtt is not None:
    _mqtt.loop_stop()
    _mqtt.disconnect()
