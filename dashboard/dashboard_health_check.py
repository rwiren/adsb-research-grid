#!/usr/bin/env python3
"""
Dashboard vs MQTT health check.
Compares aircraft visible on the web dashboard (via SocketIO) against
raw MQTT sensor feeds. Reports discrepancies per sensor.
Runs every 15 minutes via systemd timer.
"""
import json, time, ssl, logging
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("health-check")

def get_mqtt_aircraft():
    """Get aircraft from raw MQTT (what sensors report)."""
    import paho.mqtt.client as mqtt
    per_sensor = defaultdict(set)
    def on_msg(c, u, m):
        sensor = m.topic.split("/")[0]
        d = json.loads(m.payload)
        for ac in d.get("aircraft", []):
            if "lat" in ac:
                per_sensor[sensor].add(ac["hex"])
    c = mqtt.Client(transport="websockets")
    c.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
    c.username_pw_set("team9", open("/etc/securing-skies/mqtt_secret").read().strip())
    c.on_message = on_msg
    c.connect("mqtt.securingskies.eu", 8443, 60)
    c.subscribe("+/aircraft")
    c.loop_start()
    time.sleep(8)
    c.loop_stop()
    c.disconnect()
    return per_sensor

def get_dashboard_aircraft():
    """Get aircraft from dashboard SocketIO (what users see)."""
    import socketio
    result = {"aircraft": [], "done": False}
    sio = socketio.Client()
    @sio.on("map_update")
    def on_data(data):
        result["aircraft"] = data.get("aircraft", [])
        result["done"] = True
        sio.disconnect()
    sio.connect("http://127.0.0.1:8080")
    timeout = time.time() + 10
    while not result["done"] and time.time() < timeout:
        time.sleep(0.1)
    return result["aircraft"]

def main():
    log.info("Running dashboard health check")
    mqtt_data = get_mqtt_aircraft()
    dash_data = get_dashboard_aircraft()

    dash_hexes = {a["hex"] for a in dash_data if "lat" in a}
    mqtt_all = set()
    for hexes in mqtt_data.values():
        mqtt_all.update(hexes)

    log.info(f"MQTT total (with pos): {len(mqtt_all)} | Dashboard: {len(dash_hexes)}")

    for sensor in sorted(mqtt_data):
        s_hexes = mqtt_data[sensor]
        missing = s_hexes - dash_hexes
        short = sensor.replace("sensor-", "")
        if missing:
            log.warning(f"  {short}: {len(s_hexes)} on MQTT, {len(s_hexes - missing)} on dashboard, MISSING {len(missing)}: {list(missing)[:5]}")
        else:
            log.info(f"  {short}: {len(s_hexes)} on MQTT, all visible on dashboard")

    extra = dash_hexes - mqtt_all
    if extra:
        log.info(f"  Dashboard has {len(extra)} aircraft not in current MQTT (cached/stale): {list(extra)[:5]}")

    if len(dash_hexes) < len(mqtt_all) * 0.5 and len(mqtt_all) > 3:
        log.error(f"ALERT: Dashboard shows <50% of MQTT aircraft ({len(dash_hexes)}/{len(mqtt_all)})")

if __name__ == "__main__":
    main()
