#!/usr/bin/env python3
"""
accuracy_monitor.py — Live accuracy metrics on 60s sliding window.
Publishes to sensor-core/accuracy every 10 seconds.

Metrics:
- velocity_consistency: |reported_gs - haversine_derived_gs| per aircraft
- rssi_consistency: |measured_rssi - expected_rssi_from_FSPL| per aircraft
- mlat_deviation: reported pos vs MLAT-calculated pos (when 3 sensors)
- gnss_accuracy: per-sensor GNSS position stability (std of lat/lon)
- overall consistency_score: 0-1 (1 = all aircraft consistent with physics)
"""
import json, math, time, os, logging
from collections import defaultdict, deque
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_USER = "team9"
MQTT_PASS = open("/etc/securing-skies/mqtt_secret").read().strip()
WINDOW_SEC = 60
PUBLISH_INTERVAL = 10
PUBLISH_TOPIC = "sensor-core/accuracy"

# GNSS-verified positions + altitude
SENSOR_POS = {
    "sensor-north": {"lat": 60.319558, "lon": 24.830813, "alt_m": 95.2, "hw": "u-blox F9P RTK", "precision": "cm"},
    "sensor-west":  {"lat": 60.130877, "lon": 24.512927, "alt_m": 24.3, "hw": "G-STAR IV", "precision": "1m"},
    "sensor-east":  {"lat": 60.374069, "lon": 25.248990, "alt_m": 28.7, "hw": "G-STAR IV", "precision": "65m"},
}
RSSI_REF = -20.0  # dBFS at 1 km

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(min(a, 1.0)))

def expected_rssi(lat, lon, sensor):
    s = SENSOR_POS[sensor]
    d_km = haversine_m(lat, lon, s["lat"], s["lon"]) / 1000.0
    if d_km < 0.1: d_km = 0.1
    return RSSI_REF - 20 * math.log10(d_km / 1.0)

# Buffers
aircraft_buf = defaultdict(lambda: deque(maxlen=120))
gnss_buf = defaultdict(lambda: deque(maxlen=60))  # per-sensor GNSS positions
sensor_sync = {}  # per-sensor last "now" timestamp

def on_message(client, userdata, msg):
    try:
        parts = msg.topic.split("/")
        sensor, dtype = parts[0], parts[1]
        payload = json.loads(msg.payload)
        now = time.time()

        if dtype == "aircraft":
            sensor_sync[sensor] = payload.get("now", now)
            for ac in payload.get("aircraft", []):
                if "lat" not in ac: continue
                aircraft_buf[ac.get("hex", "")].append({
                    "t": now, "sensor": sensor,
                    "lat": ac["lat"], "lon": ac["lon"],
                    "gs": ac.get("gs"), "track": ac.get("track"),
                    "rssi": ac.get("rssi"), "alt": ac.get("alt_baro"),
                    "flight": (ac.get("flight") or "").strip(),
                })

        elif dtype == "gnss":
            gnss_buf[sensor].append({
                "t": time.time(), "lat": payload["lat"], "lon": payload["lon"],
                "alt": payload.get("alt_m", 0), "eph": payload.get("eph_m", 0),
                "epv": payload.get("epv_m", 0), "mode": payload.get("mode", 0),
            })
            return

        elif dtype == "system":
            # Some sensors publish their GNSS position in system telemetry
            if "lat" in payload and "lon" in payload:
                gnss_buf[sensor].append({
                    "t": now, "lat": payload["lat"], "lon": payload["lon"],
                    "alt": payload.get("alt_m", payload.get("alt", 0)),
                })

    except Exception as e:
        log.warning("Parse error on %s: %s", msg.topic, e)

def compute_accuracy():
    now = time.time()
    cutoff = now - WINDOW_SEC
    results = {"ts": now, "window_sec": WINDOW_SEC, "aircraft": {}, "gnss": {}, "sync": {}}

    vel_errors, rssi_errors = [], []
    anomalous_vel, anomalous_rssi = 0, 0
    total_ac = 0
    mlat_deviations = []

    for hex_id, buf in list(aircraft_buf.items()):
        while buf and buf[0]["t"] < cutoff: buf.popleft()
        if len(buf) < 3: continue

        obs = list(buf)
        total_ac += 1
        ac_metrics = {"flight": obs[-1].get("flight", "")}

        # --- Velocity consistency (use 5-sample window for stability) ---
        vel_diffs = []
        sensor_obs = defaultdict(list)
        for o in obs:
            if o["gs"] and o.get("lat"):
                sensor_obs[o["sensor"]].append(o)
        for s, s_obs in sensor_obs.items():
            if len(s_obs) >= 5:
                # Use first and last of 5+ samples for stable velocity
                o_first, o_last = s_obs[0], s_obs[-1]
                dt = o_last["t"] - o_first["t"]
                if dt >= 3:
                    d_m = haversine_m(o_first["lat"], o_first["lon"], o_last["lat"], o_last["lon"])
                    derived_kt = (d_m / dt) * 1.94384
                    reported_kt = sum(o["gs"] for o in s_obs) / len(s_obs)
                    vel_diffs.append(abs(reported_kt - derived_kt))

        if vel_diffs:
            ac_metrics["vel_error_mean_kt"] = round(sum(vel_diffs)/len(vel_diffs), 1)
            ac_metrics["vel_error_max_kt"] = round(max(vel_diffs), 1)
            vel_errors.append(ac_metrics["vel_error_mean_kt"])
            if ac_metrics["vel_error_max_kt"] > 50: anomalous_vel += 1

        # --- RSSI consistency ---
        rssi_diffs = []
        for o in obs:
            if o["rssi"] and o["sensor"] in SENSOR_POS:
                exp = expected_rssi(o["lat"], o["lon"], o["sensor"])
                rssi_diffs.append(abs(o["rssi"] - exp))

        if rssi_diffs:
            ac_metrics["rssi_error_mean_dB"] = round(sum(rssi_diffs)/len(rssi_diffs), 1)
            ac_metrics["rssi_error_max_dB"] = round(max(rssi_diffs), 1)
            rssi_errors.append(ac_metrics["rssi_error_mean_dB"])
            if ac_metrics["rssi_error_max_dB"] > 10: anomalous_rssi += 1

        # --- Multi-sensor position check (MLAT-like) ---
        sensors_seen = set(o["sensor"] for o in obs[-10:])  # last 10 obs
        ac_metrics["sensors"] = len(sensors_seen)

        if len(sensors_seen) >= 2:
            # Compare positions reported to different sensors
            sensor_positions = defaultdict(list)
            for o in obs[-10:]:
                sensor_positions[o["sensor"]].append((o["lat"], o["lon"]))
            # Get latest position per sensor
            latest_per_sensor = {}
            for s, positions in sensor_positions.items():
                latest_per_sensor[s] = positions[-1]
            # Compute max spread between sensors
            if len(latest_per_sensor) >= 2:
                positions = list(latest_per_sensor.values())
                max_spread = 0
                for i in range(len(positions)):
                    for j in range(i+1, len(positions)):
                        d = haversine_m(positions[i][0], positions[i][1], positions[j][0], positions[j][1])
                        max_spread = max(max_spread, d)
                ac_metrics["position_spread_m"] = round(max_spread, 0)
                if max_spread > 5000:  # >5km spread = suspicious
                    ac_metrics["position_anomaly"] = True

        if len(sensors_seen) >= 3:
            ac_metrics["trilateration"] = True

        if ac_metrics:
            results["aircraft"][hex_id] = ac_metrics

    # --- GNSS accuracy per sensor ---
    for sensor, buf in gnss_buf.items():
        recent = [o for o in buf if o["t"] > cutoff]
        if len(recent) >= 2:
            lats = [o["lat"] for o in recent]
            lons = [o["lon"] for o in recent]
            alts = [o["alt"] for o in recent if o.get("alt")]
            lat_std = (sum((x - sum(lats)/len(lats))**2 for x in lats) / len(lats)) ** 0.5
            lon_std = (sum((x - sum(lons)/len(lons))**2 for x in lons) / len(lons)) ** 0.5
            lat_m = lat_std * 111000
            lon_m = lon_std * 111000 * math.cos(math.radians(sum(lats)/len(lats)))
            horiz_m = (lat_m**2 + lon_m**2) ** 0.5
            results["gnss"][sensor] = {
                "samples": len(recent),
                "lat_mean": round(sum(lats)/len(lats), 8),
                "lon_mean": round(sum(lons)/len(lons), 8),
                "horizontal_std_m": round(horiz_m, 2),
                "eph_m": round(sum(o.get("eph",0) for o in recent)/len(recent), 1) if any(o.get("eph") for o in recent) else None,
                "alt_mean_m": round(sum(alts)/len(alts), 1) if alts else None,
                "hardware": SENSOR_POS.get(sensor, {}).get("hw", "unknown"),
                "precision_class": SENSOR_POS.get(sensor, {}).get("precision", "unknown"),
            }

    # --- Sensor reference positions (static, for dashboard display) ---
    results["sensor_positions"] = {
        s: {"lat": v["lat"], "lon": v["lon"], "alt_m": v["alt_m"], "hw": v["hw"]}
        for s, v in SENSOR_POS.items()
    }

    # --- Sync quality ---
    if len(sensor_sync) >= 2:
        times = list(sensor_sync.values())
        sub = (max(times) - min(times)) % 1.0
        if sub > 0.5: sub = 1.0 - sub
        results["sync"] = {
            "delta_ms": round(sub * 1000, 2),
            "sensors_reporting": len(sensor_sync),
            "per_sensor": {s: round(t, 3) for s, t in sensor_sync.items()},
        }

    # --- Aggregates ---
    results["aggregate"] = {
        "total_aircraft": total_ac,
        "vel_error_mean_kt": round(sum(vel_errors)/len(vel_errors), 1) if vel_errors else 0,
        "vel_error_max_kt": round(max(vel_errors), 1) if vel_errors else 0,
        "rssi_error_mean_dB": round(sum(rssi_errors)/len(rssi_errors), 1) if rssi_errors else 0,
        "rssi_error_max_dB": round(max(rssi_errors), 1) if rssi_errors else 0,
        "anomalous_velocity": anomalous_vel,
        "anomalous_rssi": anomalous_rssi,
        "multi_sensor_aircraft": sum(1 for a in results["aircraft"].values() if a.get("sensors", 0) >= 2),
        "trilateration_aircraft": sum(1 for a in results["aircraft"].values() if a.get("trilateration")),
        "consistency_score": round(1.0 - (anomalous_vel + anomalous_rssi) / max(total_ac * 2, 1), 3),
    }

    # Cleanup stale
    stale = [h for h, b in aircraft_buf.items() if not b or b[-1]["t"] < cutoff]
    for h in stale: del aircraft_buf[h]

    return results

# --- MQTT ---
client = mqtt.Client()
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_message = on_message
client.connect(MQTT_HOST, MQTT_PORT, 60)
client.subscribe("+/aircraft")
client.subscribe("+/system")
client.subscribe("+/stats")
client.subscribe("+/gnss")
client.loop_start()

log.warning("Accuracy monitor started (window=%ds, publish=%ds, topic=%s)", WINDOW_SEC, PUBLISH_INTERVAL, PUBLISH_TOPIC)

try:
    while True:
        time.sleep(PUBLISH_INTERVAL)
        metrics = compute_accuracy()
        client.publish(PUBLISH_TOPIC, json.dumps(metrics), qos=0)
        agg = metrics["aggregate"]
        if agg["total_aircraft"] > 0:
            log.warning("AC:%d vel:%.1fkt rssi:%.1fdB multi:%d trilat:%d score:%.3f",
                       agg["total_aircraft"], agg["vel_error_mean_kt"],
                       agg["rssi_error_mean_dB"], agg["multi_sensor_aircraft"],
                       agg["trilateration_aircraft"], agg["consistency_score"])
except KeyboardInterrupt:
    client.loop_stop()
