# ==============================================================================
# File: mqtt_handler.py
# Version: 5.0.0
# Date: 2026-04-26
# Maintainer: Team-9 Secure Skies
# Description: MQTT client setup, Paho callbacks, and message routing.
#              Uses dependency injection for the SocketIO instance so this
#              module stays decoupled from Flask bootstrap code.
# ==============================================================================
import json
import math
import paho.mqtt.client as mqtt
import ssl
import time
import logging
from collections import deque

from config import (
    MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_TLS,
    SENSOR_POS, C, EMERGENCY_SQUAWKS, UAV_SQUAWKS, is_uav_category,
    MLAT_TTL,
)
from state import state
from mlat import solve_mlat_2d, calculate_tdoa_pairs
from utils import (
    decdeg_to_dms, haversine_m, tdoa_uncertainty_radius_m,
    compute_spoof_score, check_jamming_alerts, _load_mqtt_password,
)

log = logging.getLogger(__name__)

_socketio = None  # dependency injection
def on_message(client, userdata, message):
    try:
        parts = message.topic.split('/')
        sensor, dtype = parts[0], parts[1]
        payload = json.loads(message.payload)

        # ── Feature 7: anomaly scores from the ML pipeline ───────────────────
        if sensor == "sensor-core" and dtype == "anomalies":
            # Payload is {icao_hex: score, ...}  (-1 = anomaly, 1 = normal)
            state["anomalies"].update(payload)
            return

        # ── Feature 7v2: enriched anomaly scores from v2 pipeline ──────────
        if sensor == "sensor-core" and dtype == "accuracy":
            state["accuracy"] = payload
            return

        # ── Phase 3: ML autoencoder inference scores ──────────────────────────
        # Published by ml_inference_service.py (GRU Autoencoder, 79K params).
        # Payload: {hex, flight, anomaly_score, threshold, is_anomaly, per_feature_error}
        # Per-feature error decomposes reconstruction error by dimension (Paper Eq. 2).
        if sensor == "sensor-core" and dtype == "ml-anomaly":
            hex_id = payload.get("hex")
            if hex_id and hex_id in state["aircraft"]:
                state["aircraft"][hex_id]["ml_score"] = payload.get("anomaly_score")
                state["aircraft"][hex_id]["ml_threshold"] = payload.get("threshold")
                state["aircraft"][hex_id]["ml_is_anomaly"] = payload.get("is_anomaly")
                state["aircraft"][hex_id]["ml_features"] = payload.get("per_feature_error", {})
            return

        if sensor == "sensor-core" and dtype == "anomalies-v2":
            # v2.0 enriched payload:
            #   {"ts": ..., "model": "ensemble-v2.0", "anomalies": {
            #     "hex": {"score": ..., "label": -1/1, "confidence": ..., "flags": [...], ...}
            #   }}
            anomalies_payload = payload.get("anomalies", {})
            for hex_id, anomaly_data in anomalies_payload.items():
                v2_entry = {
                    "label": anomaly_data.get("label", 1),
                    "confidence": anomaly_data.get("confidence"),
                    "score": anomaly_data.get("score"),
                    "flags": anomaly_data.get("flags", []),
                    "conflict_score": anomaly_data.get("conflict_score"),
                    "features": anomaly_data.get("features", []),
                }
                state["anomalies_v2"][hex_id] = v2_entry
                # Also update legacy anomalies dict for backward compat
                state["anomalies"][hex_id] = v2_entry["label"]
            # Keep anomalies_v2 fresh — remove stale entries (not in latest payload)
            current_hexes = set(anomalies_payload.keys())
            for stale_hex in list(state["anomalies_v2"].keys()):
                if stale_hex not in current_hexes:
                    state["anomalies_v2"].pop(stale_hex, None)
                    state["anomalies"].pop(stale_hex, None)
            return

        if dtype == "system":
            s = state["sensors"].setdefault(sensor, {})
            if "temp_c" in payload:
                s["temp_c"]  = float(payload["temp_c"])
            if "load_1m" in payload:
                s["load_1m"] = float(payload["load_1m"])
            return

        if dtype == "stats":
            s = state["sensors"].setdefault(sensor, {})
            s["now"]         = float(payload.get("now", 0))
            s["gain_db"]     = payload.get("gain_db", 0)
            s["ac_with_pos"] = payload.get("aircraft_with_pos", 0)
            s["ac_total"]    = s["ac_with_pos"] + payload.get("aircraft_without_pos", 0)
            l1               = payload.get("last1min", {}).get("local", {})
            s["signal"]      = l1.get("signal", 0)
            s["noise"]       = l1.get("noise", 0)
            msg_rate         = payload.get("last1min", {}).get("messages_valid", 0)
            s["msg_rate"]    = msg_rate
            s["max_range_km"] = round(payload.get("last15min", {}).get("max_distance", 0) / 1000, 1)
            # Record for jamming detection
            s.setdefault("msg_rate_history", deque(maxlen=120)).append((time.time(), msg_rate))

        elif dtype == "aircraft":
            if "now" not in payload:
                return

            # Sync math
            state["sensors"].setdefault(sensor, {})["now"] = float(payload["now"])
            nows = {k: v["now"] for k, v in state["sensors"].items() if v.get("now", 0) > 0}
            state["sync"]["per_sensor"] = nows
            vals = list(nows.values())
            if len(vals) > 1:
                sub = (max(vals) - min(vals)) % 1.0
                if sub > 0.5:
                    sub = 1.0 - sub
                state["sync"]["delta_ms"] = sub * 1000

            # Aircraft tracking
            for ac in payload.get("aircraft", []):
                hex_id = ac.get("hex")
                if not hex_id or "lat" not in ac:
                    continue

                entry = state["aircraft"].setdefault(hex_id, {
                    "seen_by":     set(),
                    "trail":       deque(maxlen=30),   # Feature 1
                    "alt_history": deque(maxlen=10),   # climb-rate check
                    "prev_seen":   0,
                    # MLAT persistence: hold last valid solution with decay
                    "last_mlat_lat": None,
                    "last_mlat_lon": None,
                    "last_mlat_confidence": 0.0,
                    "last_mlat_ts": 0,
                    # v4.2: highest timestamp seen for this ICAO (out-of-order gate)
                    "max_ts":      0.0,
                })
# --- MLAT: Ensure arrival_times dict exists ---
                if "arrival_times" not in entry:
                    entry["arrival_times"] = {}

                # ── v4.2: per-ICAO timestamp gate ───────────────────────────
                msg_timestamp = float(
                    ac.get("seen_at") or ac.get("now") or payload.get("now") or time.time()
                )
                # --- MLAT: Record arrival time & sensor FIRST ---
                entry["seen_by"].add(sensor)
                entry["arrival_times"][sensor] = msg_timestamp

                if msg_timestamp < entry.get("max_ts", 0):
                    # Out-of-order update; skip to prevent UI jumping
                    continue
                entry["max_ts"] = msg_timestamp

                raw_lat, raw_lon = ac["lat"], ac["lon"]
                seen_pos = ac.get("seen_pos", 0)

                # ── Position: lock to one sensor, ignore others unless stale ──
                prev_sensor = entry.get("_pos_sensor")
                if prev_sensor is None or sensor == prev_sensor or seen_pos < entry.get("_seen_pos", 999):
                    # Same sensor or fresher — accept
                    lat, lon = raw_lat, raw_lon
                    entry["_seen_pos"] = seen_pos
                    entry["_pos_sensor"] = sensor
                else:
                    # Different sensor, not fresher — ignore
                    lat, lon = entry.get("lat", raw_lat), entry.get("lon", raw_lon)

                # ── Feature 1: append position to trail ──────────────────────
                trail = entry["trail"]
                if not trail or haversine_m(lat, lon, trail[-1][0], trail[-1][1]) > 200:
                    trail.append((lat, lon))

                squawk  = ac.get("squawk")
                alt     = ac.get("alt_baro", "ground")

                # Track altitude history for climb-rate spoofing check
                if isinstance(alt, (int, float)):
                    ah = entry["alt_history"]
                    if not ah or alt != ah[-1][1]:
                        ah.append((time.time(), alt))

                # Keep prev_seen for groundspeed consistency check
                entry["prev_seen"] = entry.get("last_seen", 0)

                entry.update({
                    "lat": lat, "lon": lon,
                    "flight":    (ac.get("flight") or "").strip() or None,
                    "squawk":    squawk,
                    "alt":       alt,
                    "gs":        ac.get("gs"),
                    "track":     ac.get("track"),
                    "rssi":      ac.get("rssi"),
                    "type":      ac.get("type"),
                    "category":  ac.get("category"),
                    "last_seen": time.time(),
                    # Feature 2: mark emergency squawks server-side
                    "emergency": squawk in EMERGENCY_SQUAWKS if squawk else False,
                    # UAV/unmanned detection: squawk-based OR ADS-B category-based
                    "uav": (
                        (squawk in UAV_SQUAWKS if squawk else False)
                        or is_uav_category(ac.get("category"))
                    ),
                })


            # Stale cleanup
            now_ts = time.time()
            state["aircraft"] = {
                k: v for k, v in state["aircraft"].items()
                if now_ts - v["last_seen"] < 15
            }

            # ── Feature 3: TDOA uncertainty radius for full-lock aircraft ─────
            tdoa_r = tdoa_uncertainty_radius_m(state["sync"]["delta_ms"])

            aircraft_list = []
            for k, v in state["aircraft"].items():
                # Preserve injected demo scores (bypass heuristic)
                if v.get("_injected") and v.get("spoof_score"):
                    spoof_score = v["spoof_score"]
                    spoof_flags = v.get("spoof_flags", ["INJECTED"])
                else:
                    spoof_score, spoof_flags = compute_spoof_score(v)
                entry_data = {
                    **{kk: vv for kk, vv in v.items() if kk not in ("seen_by", "trail", "alt_history", "prev_seen")},
                    "hex":          k,
                    "seen_by":      list(v["seen_by"]),
                    "trail":        list(v["trail"]),
                    # Feature 7: anomaly score from ML pipeline
                    "anomaly_score": state["anomalies"].get(k),
                    # Feature 7v2: enriched anomaly data
                    "anomaly_v2": state["anomalies_v2"].get(k),
                    # v3.4: spoofing heuristics
                    "spoof_score":  round(spoof_score, 3),
                    "spoof_flags":  spoof_flags,
                    # MLAT: per-sensor timestamp count
                    "arrival_count": len(v.get("arrival_times", {})),
                }

                # --- MLAT: Calculate when 3+ sensors have timestamps ---
                arrival_times = v.get("arrival_times", {})
                # Prune stale per-sensor timestamps (>5s)
                now_ts = time.time()
                arrival_times = {s: t for s, t in arrival_times.items() if now_ts - t < 15.0}
                v["arrival_times"] = arrival_times

                mlat_ok = False
                if len(arrival_times) >= 3:
                    sync_offsets = {}
                    for s_name, s_data in state["sensors"].items():
                        if s_name in SENSOR_POS and "now" in s_data:
                            nows = [d.get("now") for d in state["sensors"].values() if d.get("now")]
                            if nows:
                                ref_now = max(nows)
                                sync_offsets[s_name] = (s_data["now"] - ref_now) * 1000
                    
                    tdoa_data = calculate_tdoa_pairs(arrival_times, sync_offsets)
                    if tdoa_data and len(tdoa_data["pairs"]) >= 2:
                        alt_m = v.get("alt")
                        if isinstance(alt_m, (int, float)) and alt_m != "ground":
                            alt_m = alt_m * 0.3048
                        else:
                            alt_m = None
                        
                        mlat_result = solve_mlat_2d(SENSOR_POS, tdoa_data["pairs"], alt_m)
                        if mlat_result:
                            mlat_ok = True
                            entry_data["mlat_lat"] = round(mlat_result[0], 6)
                            entry_data["mlat_lon"] = round(mlat_result[1], 6)
                            entry_data["mlat_confidence"] = round(mlat_result[2], 3)
                            entry_data["mlat_sync_ms"] = round(tdoa_data["sync_quality_ms"], 3)
                            entry_data["mlat_lat_dms"] = decdeg_to_dms(mlat_result[0], is_lat=True)
                            entry_data["mlat_lon_dms"] = decdeg_to_dms(mlat_result[1], is_lat=False)
                            # Persist into state for decay fallback
                            v["last_mlat_lat"] = entry_data["mlat_lat"]
                            v["last_mlat_lon"] = entry_data["mlat_lon"]
                            v["last_mlat_confidence"] = entry_data["mlat_confidence"]
                            v["last_mlat_ts"] = now_ts

                aircraft_list.append(entry_data)

                # Fallback: show last valid MLAT with decayed confidence
                if not mlat_ok and v.get("last_mlat_ts", 0) > now_ts - MLAT_TTL:
                    age = now_ts - v["last_mlat_ts"]
                    decay = max(0.0, 1.0 - age / MLAT_TTL)
                    entry_data["mlat_lat"] = v["last_mlat_lat"]
                    entry_data["mlat_lon"] = v["last_mlat_lon"]
                    entry_data["mlat_confidence"] = round(v["last_mlat_confidence"] * decay, 3)
                    entry_data["mlat_sync_ms"] = None
                    entry_data["mlat_stale"] = True
                    if v["last_mlat_lat"] is not None:
                        entry_data["mlat_lat_dms"] = decdeg_to_dms(v["last_mlat_lat"], is_lat=True)
                    if v["last_mlat_lon"] is not None:
                        entry_data["mlat_lon_dms"] = decdeg_to_dms(v["last_mlat_lon"], is_lat=False)


            # Jamming detection
            state["jamming"] = check_jamming_alerts(state["sensors"])

            _socketio.emit('map_update', {
                "sync":     state["sync"],
                # Exclude non-serialisable msg_rate_history deque from sensors dict
                "sensors":  {k: {kk: vv for kk, vv in v.items() if kk != "msg_rate_history"}
                             for k, v in state["sensors"].items()},
                "aircraft": aircraft_list,
                "jamming":  state["jamming"],
                "accuracy": state.get("accuracy", {}),
            })

    except Exception as e:
        log.warning("MQTT parse error on %s: %s", message.topic, e)


def set_socketio(sio):
    """Inject the Flask-SocketIO instance used for broadcasting map_update."""
    global _socketio
    _socketio = sio

mqtt_pass = _load_mqtt_password()

# Remote broker uses WSS on port 8443
mqtt_client = mqtt.Client(transport="websockets")
mqtt_client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)

if MQTT_USER and mqtt_pass:
    mqtt_client.username_pw_set(MQTT_USER, mqtt_pass)
elif MQTT_USER:
    log.warning("MQTT password missing; set MQTT_PASS or provide %s", MQTT_PASS_FILE)
mqtt_client.on_message = on_message

def start_mqtt():
    try:
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        mqtt_client.subscribe("+/aircraft")
        mqtt_client.subscribe("+/stats")
        mqtt_client.subscribe("+/system")           # System telemetry (temp, load)
        mqtt_client.subscribe("sensor-core/anomalies")   # Feature 7
        mqtt_client.subscribe("sensor-core/anomalies-v2")
        mqtt_client.subscribe("sensor-core/accuracy") # Feature 7v2: enriched
        mqtt_client.subscribe("sensor-core/ml-anomaly")  # Phase 3: live autoencoder scores
        mqtt_client.loop_start()
        log.warning("MQTT connected to %s:%d (TLS=%s)", MQTT_HOST, MQTT_PORT, MQTT_TLS)
    except Exception as e:
        log.error("MQTT Connect Error: %s", e)
