#!/usr/bin/env python3
# ==============================================================================
# File: system_telemetry.py
# Description: Lightweight agent deployed on each sensor node (North/West/East).
#              Reads CPU temperature and 1-minute load average every 60 seconds
#              and publishes them to the broker under the topic:
#                  {hostname}/system
#              e.g. sensor-east/system
#
#              The dashboard (dashboard.py) subscribes to +/system and renders
#              the values in the Sensor Health cards.
#
# Deploy: copy this file to /root/system_telemetry.py on each sensor node.
# Run permanently: enable the accompanying systemd service
#                  (see scripts/maintenance/system_telemetry.service).
# Credentials: MQTT password is read from PASS_FILE at startup (same pattern
#              as /usr/local/bin/adsb-mqtt-publish.sh).
#              Create the file with: echo -n 'yourpassword' > /etc/securing-skies/mqtt_secret
#              Restrict access:      chmod 600 /etc/securing-skies/mqtt_secret
# ==============================================================================
import json
import socket
import ssl
import sys
import time
import logging

import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

# Automatically derive sensor ID from the node hostname (e.g. "sensor-east")
SENSOR_ID = socket.gethostname()
BROKER    = "mqtt.securingskies.eu"
PORT      = 8883
MQTT_USER = "team9"
PASS_FILE = "/etc/securing-skies/mqtt_secret"
TOPIC     = f"{SENSOR_ID}/system"
INTERVAL  = 60  # seconds between publishes


def read_mqtt_password(path: str) -> str:
    """Read the MQTT password from a secret file, mirroring adsb-mqtt-publish.sh."""
    try:
        with open(path, "r") as fh:
            return fh.read().strip()
    except OSError as exc:
        log.error("ERROR: Secret file missing or unreadable: %s", exc)
        sys.exit(1)


def get_cpu_temp() -> float:
    """Read the SoC temperature from the kernel thermal interface (°C)."""
    with open("/sys/class/thermal/thermal_zone0/temp", "r") as fh:
        return round(int(fh.read().strip()) / 1000.0, 1)


def get_cpu_load() -> float:
    """Return the 1-minute load average from /proc/loadavg."""
    with open("/proc/loadavg", "r") as fh:
        return float(fh.read().split()[0])


def build_payload() -> dict:
    payload = {}
    try:
        payload["temp_c"]  = get_cpu_temp()
    except Exception as exc:
        log.warning("Could not read CPU temperature: %s", exc)
    try:
        payload["load_1m"] = get_cpu_load()
    except Exception as exc:
        log.warning("Could not read CPU load: %s", exc)
    return payload


def main():
    mqtt_pass = read_mqtt_password(PASS_FILE)
    client = mqtt.Client(client_id=f"{SENSOR_ID}-telemetry")
    client.username_pw_set(MQTT_USER, mqtt_pass)
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED)

    try:
        client.connect(BROKER, PORT, keepalive=60)
        client.loop_start()
        log.info("Connected to %s:%d — publishing on topic '%s'", BROKER, PORT, TOPIC)

        while True:
            payload = build_payload()
            if payload:
                client.publish(TOPIC, json.dumps(payload), qos=1, retain=True)
                log.info("Published: %s", payload)
            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        log.info("Interrupted — disconnecting")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
