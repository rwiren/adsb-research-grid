# ==============================================================================
# File: dashboard.py
# Version: 3.3.0 (Enhanced: Trail History, Emergency Alerts, TDOA Uncertainty,
#                  Connection Indicator, Fade-Out, Alt Filter, Anomaly Overlay,
#                  Popup Enrichment, Ring Toggle, Mobile Layout)
# Date: 2026-04-11
# Maintainer: Team-9 Secure Skies
# Description: Ten UX/research improvements layered on top of v3.2.0.
#   1.  Aircraft trail history  — deque(maxlen=60), fading polylines on map
#   2.  Emergency squawk alarm  — 7500/7600/7700 → banner + CSS pulse
#   3.  TDOA uncertainty circle — sync-error → position-uncertainty radius
#   4.  Connection status badge — LIVE / STALE / DISCONNECTED
#   5.  Aircraft age fade-out   — linear opacity decay over last 5 s
#   6.  Altitude filter slider  — client-side dual-thumb range slider
#   7.  Anomaly score overlay   — sensor-core/anomalies MQTT topic + ring
#   8.  Popup category lookup   — ICAO ADS-B category → human label
#   9.  Coverage rings toggle   — Leaflet layerGroup buttons
#   10. Mobile-responsive layout — slide-up drawer with CSS media queries
# ==============================================================================
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt
import json
import math
import ssl
import time
import logging
from collections import deque

logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')

# Emergency squawk codes
EMERGENCY_SQUAWKS = {"7500", "7600", "7700"}

# Speed of light (m/s) — for TDOA uncertainty calculation
C = 299792458.0

# Server-side sensor positions (WGS-84)
SENSOR_POS = {
    "sensor-north": (60.319555, 24.830816),
    "sensor-west":  (60.130919, 24.512869),
    "sensor-east":  (60.350000, 25.350000),
}

# Spoofing heuristic thresholds
MAX_CREDIBLE_CLIMB_FPM = 6000   # ft/min — above this is physically impossible for civil AC
MAX_GS_DISCREPANCY     = 0.50   # 50 % difference between computed and reported groundspeed

state = {
    "aircraft": {},
    "sensors": {
        "sensor-north": {"now": 0, "signal": 0, "noise": 0, "msg_rate": 0, "max_range_km": 0, "gain_db": 0, "ac_with_pos": 0, "ac_total": 0, "msg_rate_history": deque(maxlen=120), "temp_c": None, "load_1m": None},
        "sensor-west":  {"now": 0, "signal": 0, "noise": 0, "msg_rate": 0, "max_range_km": 0, "gain_db": 0, "ac_with_pos": 0, "ac_total": 0, "msg_rate_history": deque(maxlen=120), "temp_c": None, "load_1m": None},
        "sensor-east":  {"now": 0, "signal": 0, "noise": 0, "msg_rate": 0, "max_range_km": 0, "gain_db": 0, "ac_with_pos": 0, "ac_total": 0, "msg_rate_history": deque(maxlen=120), "temp_c": None, "load_1m": None},
    },
    "sync":    {"delta_ms": 0.0, "per_sensor": {}},
    "anomalies": {},   # icao_hex -> score  (-1 = anomaly flagged by ML pipeline)
    "jamming": [],     # list of sensor names currently showing jamming signature
}


def haversine_m(lat1, lon1, lat2, lon2):
    """Return the great-circle distance in metres between two lat/lon points."""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(min(a, 1.0)))


def tdoa_uncertainty_radius_m(sync_delta_ms):
    """
    Convert the measured inter-sensor clock sync error to a TDOA position
    uncertainty radius.

    For a bistatic TDOA system the position error caused by a timing error Δt
    is bounded by:
        r ≈ c * Δt / 2
    This is the radius of the circular "uncertainty bubble" that would be drawn
    around a full-lock aircraft on the map.  When sync is tight (< 1 ms) the
    bubble is small (< 150 km); when sensors drift the bubble grows, giving
    researchers an immediate visual indication of TDOA solution quality.
    """
    return (sync_delta_ms / 1000.0) * C / 2.0


def compute_spoof_score(entry):
    """
    Heuristic spoofing confidence score in [0.0, 1.0] with named flag strings.

    Three independent physics checks — any trigger raises the score.  The score
    is intentionally conservative: a single flag gives 0.3–0.4, making 1.0 only
    reachable if multiple independent anomalies coincide.

    Flags
    -----
    1-sensor>10kft  — seen by only 1 of 3 sensors but alt > 10 000 ft.
                      At that altitude, LoS geometry means all three RPi nodes
                      should receive the signal.  Single-sensor = likely spoofer
                      transmitting from close range on one beam.
    climb>Xfpm      — derived climb/descent rate from alt_history exceeds
                      MAX_CREDIBLE_CLIMB_FPM.  Civil aircraft do not exceed
                      ~6 000 fpm; this catches instant altitude teleportation.
    GS Yvsz kt      — computed groundspeed from position trail differs from the
                      ADS-B-reported gs by more than MAX_GS_DISCREPANCY.
                      A spoofer replaying a fixed trajectory will have a
                      mismatch between the declared gs and actual movement.
    """
    score = 0.0
    flags = []
    alt     = entry.get("alt")
    seen_by = entry.get("seen_by", set())

    # Check 1: single-sensor high-altitude
    if len(seen_by) == 1 and isinstance(alt, (int, float)) and alt > 10000:
        score += 0.4
        flags.append("1-sensor>10kft")

    # Check 2: impossible climb / descent rate
    ah = list(entry.get("alt_history", []))
    if len(ah) >= 2:
        t1, a1 = ah[-2]
        t2, a2 = ah[-1]
        if isinstance(a1, (int, float)) and isinstance(a2, (int, float)) and t2 > t1:
            dt_min = (t2 - t1) / 60.0
            if dt_min > 0:
                fpm = abs(a2 - a1) / dt_min
                if fpm > MAX_CREDIBLE_CLIMB_FPM:
                    score += 0.35
                    flags.append("climb>{:.0f}fpm".format(fpm))

    # Check 3: groundspeed inconsistency
    trail    = list(entry.get("trail", []))
    last_seen = entry.get("last_seen", 0)
    prev_seen = entry.get("prev_seen", 0)
    if len(trail) >= 2 and 0 < prev_seen < last_seen:
        d_m  = haversine_m(trail[-2][0], trail[-2][1], trail[-1][0], trail[-1][1])
        dt_s = last_seen - prev_seen
        if dt_s > 0:
            computed_kt  = (d_m / dt_s) * 1.94384   # m/s → knots
            reported_gs  = entry.get("gs")
            if reported_gs and reported_gs > 20 and computed_kt > 20:
                ratio = abs(computed_kt - reported_gs) / max(reported_gs, 1.0)
                if ratio > MAX_GS_DISCREPANCY:
                    score += 0.3
                    flags.append("GS{:.0f}vs{:.0f}kt".format(reported_gs, computed_kt))

    return min(score, 1.0), flags


def check_jamming_alerts():
    """
    Flag sensors whose 1-minute message rate has dropped >60 % in the last
    15 s compared to the prior 60 s baseline.

    A sudden, steep drop in all three sensors simultaneously is the classic
    signature of wideband GNSS/RF jamming.  A single-sensor drop may indicate
    a hardware fault or directed jamming toward one node.
    """
    now_ts  = time.time()
    alerts  = []
    for name, s in state["sensors"].items():
        hist = list(s.get("msg_rate_history", []))
        if len(hist) < 4:
            continue
        recent = [r for t, r in hist if now_ts - t < 15]
        older  = [r for t, r in hist if 15 <= now_ts - t < 75]
        if not recent or not older:
            continue
        recent_avg = sum(recent) / len(recent)
        older_avg  = sum(older)  / len(older)
        if older_avg > 10 and recent_avg < older_avg * 0.4:
            alerts.append(name)
    return alerts


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
                    "trail":       deque(maxlen=60),   # Feature 1
                    "alt_history": deque(maxlen=10),   # climb-rate check
                    "prev_seen":   0,
                })

                lat, lon = ac["lat"], ac["lon"]

                # ── Feature 1: append position to trail ──────────────────────
                trail = entry["trail"]
                if not trail or haversine_m(lat, lon, trail[-1][0], trail[-1][1]) > 50:
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
                })
                entry["seen_by"].add(sensor)

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
                spoof_score, spoof_flags = compute_spoof_score(v)
                entry_data = {
                    **{kk: vv for kk, vv in v.items() if kk not in ("seen_by", "trail", "alt_history", "prev_seen")},
                    "hex":          k,
                    "seen_by":      list(v["seen_by"]),
                    "trail":        list(v["trail"]),
                    # Feature 7: anomaly score from ML pipeline
                    "anomaly_score": state["anomalies"].get(k),
                    # v3.4: spoofing heuristics
                    "spoof_score":  round(spoof_score, 3),
                    "spoof_flags":  spoof_flags,
                }
                if len(v["seen_by"]) == 3:
                    entry_data["tdoa_uncertainty_m"] = tdoa_r
                aircraft_list.append(entry_data)

            # Jamming detection
            state["jamming"] = check_jamming_alerts()

            socketio.emit('map_update', {
                "sync":     state["sync"],
                # Exclude non-serialisable msg_rate_history deque from sensors dict
                "sensors":  {k: {kk: vv for kk, vv in v.items() if kk != "msg_rate_history"}
                             for k, v in state["sensors"].items()},
                "aircraft": aircraft_list,
                "jamming":  state["jamming"],
            })

    except Exception as e:
        log.warning("MQTT parse error on %s: %s", message.topic, e)


mqtt_client = mqtt.Client()
mqtt_client.username_pw_set("team9", "ResearchView2026!")
# TLS — verify broker certificate against the system CA store (no custom cert needed)
mqtt_client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
mqtt_client.on_message = on_message


def start_mqtt():
    try:
        mqtt_client.connect("mqtt.securingskies.eu", 8883, 60)
        mqtt_client.subscribe("+/aircraft")
        mqtt_client.subscribe("+/stats")
        mqtt_client.subscribe("+/system")           # System telemetry (temp, load)
        mqtt_client.subscribe("sensor-core/anomalies")   # Feature 7
        mqtt_client.loop_start()
        log.warning("MQTT connected to mqtt.securingskies.eu:8883 (TLS)")
    except Exception as e:
        log.error("MQTT Connect Error: %s", e)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>SecuringSkies MLAT Hub v3.4</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        * { box-sizing: border-box; }
        body { margin:0; background:#0d1117; color:#c9d1d9; font-family:'Courier New',monospace; overflow:hidden; }

        /* ── Core layout ── */
        #map        { height:75vh; width:100%; border-bottom:2px solid #30363d; position:relative; }
        #dashboard  { height:25vh; display:flex; gap:8px; background:#161b22; padding:10px; overflow:hidden; }

        .panel         { background:#0d1117; border:1px solid #30363d; border-radius:4px; padding:10px; display:flex; flex-direction:column; }
        .panel-sync    { flex:0.8; align-items:center; justify-content:center; text-align:center; }
        .panel-sensors { flex:2; }
        .panel-legend  { flex:1.2; }

        .label     { font-size:0.75em; color:#8b949e; text-transform:uppercase; margin-bottom:4px; letter-spacing:0.5px; }
        .value-big { font-size:3em; font-weight:bold; color:#3fb950; line-height:1; margin-bottom:5px; }
        .value-sub { font-size:0.85em; color:#8b949e; margin-top:2px; }

        /* Sensor health grid */
        .sensor-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; height:100%; }
        .sensor-card { background:#161b22; border:1px solid #30363d; border-radius:4px; padding:6px; display:flex; flex-direction:column; gap:2px; }
        .sensor-card .name { font-size:0.85em; font-weight:bold; margin-bottom:2px; }
        .sensor-card .row  { display:flex; justify-content:space-between; font-size:0.75em; }
        .sensor-card .row .k { color:#8b949e; }
        .sensor-card .row .v { color:#c9d1d9; }
        .snr-bar      { height:4px; background:#21262d; border-radius:2px; margin-top:auto; }
        .snr-bar-fill { height:100%; border-radius:2px; transition:width 0.5s; }

        /* Coverage legend */
        .legend-grid { display:grid; grid-template-columns:1fr 1fr; gap:4px; font-size:0.8em; margin-top:5px; }
        .legend-item { display:flex; align-items:center; }
        .dot { width:10px; height:10px; border-radius:50%; margin-right:8px; border:1px solid rgba(255,255,255,0.15); flex-shrink:0; }

        /* Popups */
        .leaflet-popup-content-wrapper, .leaflet-popup-tip { background:#161b22; color:#c9d1d9; border:1px solid #30363d; box-shadow:0 0 15px rgba(0,0,0,0.8); }
        .leaflet-popup-content { margin:10px; line-height:1.5; font-family:'Courier New',monospace; font-size:0.9em; }

        /* Flight labels */
        .flight-label { background:none; border:none; color:#c9d1d9; font-family:'Courier New',monospace;
                        font-size:11px; font-weight:bold; white-space:nowrap;
                        text-shadow:1px 1px 2px #000, -1px -1px 2px #000; }

        /* ── Feature 4: Connection status badge ── */
        #conn-badge {
            position:absolute; top:10px; right:10px; z-index:1000;
            padding:4px 10px; border-radius:12px; font-size:0.75em; font-weight:bold;
            border:1px solid rgba(255,255,255,0.2); pointer-events:none;
            transition:background 0.5s, color 0.5s;
        }
        #conn-badge.live         { background:#0d2b1a; color:#3fb950; border-color:#3fb950; }
        #conn-badge.stale        { background:#2b2200; color:#d29922; border-color:#d29922; }
        #conn-badge.disconnected { background:#2b0a0a; color:#f85149; border-color:#f85149; }

        /* ── v3.4: Jamming alert banner ── */
        #jamming-banner {
            display:none; position:absolute; top:0; left:0; right:0; z-index:1900;
            background:#7d4000; color:#fff; padding:6px 12px; font-size:0.85em;
            font-weight:bold; text-align:center; border-bottom:2px solid #d29922;
            pointer-events:none;
        }
        /* Emergency banner sits above jamming banner */
        #emergency-banner { z-index:2000; }

        /* ── v3.4: Spoof score ring animation ── */
        @keyframes spoof-pulse {
            0%   { opacity:0.9; }
            50%  { opacity:0.3; }
            100% { opacity:0.9; }
        }
        .spoof-ring { animation:spoof-pulse 1.5s ease-in-out infinite; }

        /* ── Feature 2: Emergency banner ── */
        #emergency-banner {
            display:none; position:absolute; top:0; left:0; right:0; z-index:2000;
            background:#7d0000; color:#fff; padding:6px 12px; font-size:0.85em;
            font-weight:bold; text-align:center; border-bottom:2px solid #f85149;
            pointer-events:none;
        }

        /* Emergency marker pulse animation */
        @keyframes emergency-pulse {
            0%   { filter:drop-shadow(0 0 6px #f85149); }
            50%  { filter:drop-shadow(0 0 1px #f85149); opacity:0.6; }
            100% { filter:drop-shadow(0 0 6px #f85149); }
        }
        .emergency-marker { animation:emergency-pulse 1s ease-in-out infinite; }

        /* ── Feature 6: Altitude filter ── */
        #alt-filter {
            position:absolute; bottom:8px; left:50%; transform:translateX(-50%);
            z-index:1000; background:#161b22cc; border:1px solid #30363d;
            border-radius:6px; padding:4px 12px;
            display:flex; align-items:center; gap:8px; font-size:0.75em;
        }
        #alt-filter label  { color:#8b949e; white-space:nowrap; }
        #alt-filter input[type=range] { width:80px; accent-color:#58a6ff; cursor:pointer; }
        #alt-filter span   { color:#c9d1d9; min-width:34px; text-align:right; }

        /* ── Feature 9: Ring toggle buttons ── */
        #ring-controls {
            position:absolute; top:10px; left:50px; z-index:1000;
            display:flex; flex-direction:column; gap:4px;
        }
        .ring-btn {
            background:#161b22cc; border:1px solid #30363d; border-radius:4px;
            color:#8b949e; font-size:0.7em; padding:3px 7px; cursor:pointer;
            font-family:'Courier New',monospace; white-space:nowrap;
        }
        .ring-btn.active { color:#c9d1d9; border-color:#58a6ff; }

        /* ── Feature 10: Mobile layout ── */
        @media (max-width:768px) {
            body { overflow:auto; }
            #map { height:60vh; }
            #dashboard {
                height:auto; flex-direction:column; position:relative;
                overflow:hidden; max-height:42px; transition:max-height 0.3s ease;
            }
            #dashboard.expanded { max-height:600px; }
            #mobile-bar {
                display:flex; align-items:center; justify-content:space-between;
                padding:6px 10px; background:#161b22; cursor:pointer;
                border-bottom:1px solid #30363d; flex-shrink:0; min-height:42px;
            }
            #mobile-chevron { transition:transform 0.3s; display:inline-block; }
            #dashboard.expanded #mobile-chevron { transform:rotate(180deg); }
            .panel { flex:unset; }
        }
        @media (min-width:769px) {
            #mobile-bar { display:none; }
        }
    </style>
</head>
<body>
    <!-- Feature 2: Emergency banner (shown above the map) -->
    <div id="emergency-banner"></div>
    <!-- v3.4: Jamming alert banner -->
    <div id="jamming-banner"></div>

    <div id="map">
        <!-- Feature 4: Connection status badge -->
        <div id="conn-badge" class="live">● LIVE</div>

        <!-- Feature 9: Coverage ring toggle buttons -->
        <div id="ring-controls">
            <button class="ring-btn active" id="btn-inner" onclick="toggleRings('inner')">◯ 100 km</button>
            <button class="ring-btn active" id="btn-outer" onclick="toggleRings('outer')">◯ 200 km</button>
        </div>

        <!-- Feature 6: Altitude filter -->
        <div id="alt-filter">
            <label>ALT</label>
            <input type="range" id="alt-min" min="0" max="45000" step="1000" value="0">
            <span id="alt-min-lbl">GND</span>
            <label>–</label>
            <input type="range" id="alt-max" min="0" max="45000" step="1000" value="45000">
            <span id="alt-max-lbl">45k</span>
            <label>ft</label>
        </div>
    </div>

    <div id="dashboard">
        <!-- Feature 10: Mobile summary bar (hidden on desktop) -->
        <div id="mobile-bar" onclick="toggleMobileDashboard()">
            <span>⬆ <span id="mob-ac">0</span> targets &nbsp;·&nbsp; Δ <span id="mob-sync">0.00</span> ms</span>
            <span id="mobile-chevron">∧</span>
        </div>

        <div class="panel panel-sync">
            <div class="label">Array Sync Δ</div>
            <div id="sync-delta" class="value-big">0.00</div>
            <div style="font-size:1em;color:#8b949e;">ms</div>
            <div id="sync-detail" class="value-sub"></div>
            <div style="margin-top:auto;">
                <div class="label">Targets</div>
                <div id="ac-count" class="value-big" style="font-size:2em;">0</div>
            </div>
        </div>

        <div class="panel panel-sensors">
            <div class="label">Sensor Health (Live Telemetry)</div>
            <div class="sensor-grid">
                <div class="sensor-card" id="card-north">
                    <div class="name" style="color:#58a6ff;">▲ NORTH</div>
                    <div class="row"><span class="k">Signal</span><span class="v" id="n-sig">—</span></div>
                    <div class="row"><span class="k">SNR</span><span class="v" id="n-snr">—</span></div>
                    <div class="row"><span class="k">Gain</span><span class="v" id="n-gain">—</span></div>
                    <div class="row"><span class="k">Msg/min</span><span class="v" id="n-msg">—</span></div>
                    <div class="row"><span class="k">Max Range</span><span class="v" id="n-range">—</span></div>
                    <div class="row"><span class="k">AC (pos/all)</span><span class="v" id="n-ac">—</span></div>
                    <div class="row"><span class="k">CPU Temp</span><span class="v" id="n-temp">—</span></div>
                    <div class="row"><span class="k">Load 1m</span><span class="v" id="n-load">—</span></div>
                    <div class="snr-bar"><div class="snr-bar-fill" id="n-bar" style="width:0%;background:#58a6ff;"></div></div>
                </div>
                <div class="sensor-card" id="card-west">
                    <div class="name" style="color:#3fb950;">◀ WEST</div>
                    <div class="row"><span class="k">Signal</span><span class="v" id="w-sig">—</span></div>
                    <div class="row"><span class="k">SNR</span><span class="v" id="w-snr">—</span></div>
                    <div class="row"><span class="k">Gain</span><span class="v" id="w-gain">—</span></div>
                    <div class="row"><span class="k">Msg/min</span><span class="v" id="w-msg">—</span></div>
                    <div class="row"><span class="k">Max Range</span><span class="v" id="w-range">—</span></div>
                    <div class="row"><span class="k">AC (pos/all)</span><span class="v" id="w-ac">—</span></div>
                    <div class="row"><span class="k">CPU Temp</span><span class="v" id="w-temp">—</span></div>
                    <div class="row"><span class="k">Load 1m</span><span class="v" id="w-load">—</span></div>
                    <div class="snr-bar"><div class="snr-bar-fill" id="w-bar" style="width:0%;background:#3fb950;"></div></div>
                </div>
                <div class="sensor-card" id="card-east">
                    <div class="name" style="color:#f85149;">▶ EAST</div>
                    <div class="row"><span class="k">Signal</span><span class="v" id="e-sig">—</span></div>
                    <div class="row"><span class="k">SNR</span><span class="v" id="e-snr">—</span></div>
                    <div class="row"><span class="k">Gain</span><span class="v" id="e-gain">—</span></div>
                    <div class="row"><span class="k">Msg/min</span><span class="v" id="e-msg">—</span></div>
                    <div class="row"><span class="k">Max Range</span><span class="v" id="e-range">—</span></div>
                    <div class="row"><span class="k">AC (pos/all)</span><span class="v" id="e-ac">—</span></div>
                    <div class="row"><span class="k">CPU Temp</span><span class="v" id="e-temp">—</span></div>
                    <div class="row"><span class="k">Load 1m</span><span class="v" id="e-load">—</span></div>
                    <div class="snr-bar"><div class="snr-bar-fill" id="e-bar" style="width:0%;background:#f85149;"></div></div>
                </div>
            </div>
        </div>

        <div class="panel panel-legend">
            <div class="label">Coverage Legend</div>
            <div class="legend-grid">
                <div class="legend-item"><span class="dot" style="background:#58a6ff"></span>North <span id="cnt-n" style="color:#8b949e;margin-left:auto;">0</span></div>
                <div class="legend-item"><span class="dot" style="background:#39c5cf"></span>N+W   <span id="cnt-nw" style="color:#8b949e;margin-left:auto;">0</span></div>
                <div class="legend-item"><span class="dot" style="background:#3fb950"></span>West  <span id="cnt-w" style="color:#8b949e;margin-left:auto;">0</span></div>
                <div class="legend-item"><span class="dot" style="background:#d2a8ff"></span>N+E   <span id="cnt-ne" style="color:#8b949e;margin-left:auto;">0</span></div>
                <div class="legend-item"><span class="dot" style="background:#f85149"></span>East  <span id="cnt-e" style="color:#8b949e;margin-left:auto;">0</span></div>
                <div class="legend-item"><span class="dot" style="background:#d29922"></span>W+E   <span id="cnt-we" style="color:#8b949e;margin-left:auto;">0</span></div>
                <div class="legend-item" style="grid-column:span 2;margin-top:4px;padding-top:4px;border-top:1px solid #30363d;">
                    <span class="dot" style="background:#fff;box-shadow:0 0 8px #fff;"></span>
                    <b>FULL LOCK (N+W+E)</b>
                    <span id="cnt-all" style="color:#8b949e;margin-left:auto;">0</span>
                </div>
                <!-- Feature 7: Anomaly count row -->
                <div class="legend-item" style="grid-column:span 2;margin-top:2px;">
                    <span style="margin-right:8px;">🚨</span>Anomalies
                    <span id="cnt-anomaly" style="color:#d29922;font-weight:bold;margin-left:auto;">0</span>
                </div>
                <!-- v3.4: Spoofing suspects row -->
                <div class="legend-item" style="grid-column:span 2;margin-top:2px;">
                    <span style="margin-right:8px;">⚡</span>Spoof suspects
                    <span id="cnt-spoof" style="color:#f85149;font-weight:bold;margin-left:auto;">0</span>
                </div>
            </div>
        </div>
    </div>

<script>
// ── Feature 8: ICAO ADS-B category lookup table ────────────────────────────
var CAT_LABELS = {
    "A0":"Unknown","A1":"Light (<15 500 lbs)","A2":"Small (15 500–75 000 lbs)",
    "A3":"Large (75 000–300 000 lbs)","A4":"B757","A5":"Heavy (>300 000 lbs)",
    "A6":"High Performance","A7":"Rotorcraft",
    "B0":"Unknown","B1":"Glider/Sailplane","B2":"Lighter-than-air",
    "B3":"Parachutist","B4":"UAV/Drone","B5":"Space","B6":"UAV","B7":"UAV",
    "C0":"Unknown","C1":"Emergency Surface","C2":"Service Surface",
    "C3":"Fixed Ground Obstruction","C4":"Cluster Obstacle","C5":"Line Obstacle",
    "C6":"Spare","C7":"Spare"
};

// ── Temperature thresholds for sensor health colour coding ─────────────────
var TEMP_WARN_C = 60;   // °C — amber above this
var TEMP_CRIT_C = 75;   // °C — red above this

// ── Map setup ──────────────────────────────────────────────────────────────
var map = L.map('map', {zoomControl:false});
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{attribution:''}).addTo(map);

// Per-aircraft layer stores
var markers = {}, labels = {}, arrows = {}, trails = {}, tdoaCircles = {}, anomalyRings = {}, spoofRings = {};

// Client-side last-seen timestamps (Date.now()/1000) for opacity fade
var markerLastSeen = {};

var nodes = {
    "sensor-north": {pos:[60.319555,24.830816], col:"#58a6ff", lbl:"N"},
    "sensor-west":  {pos:[60.130919,24.512869], col:"#3fb950",  lbl:"W"},
    "sensor-east":  {pos:[60.350000,25.350000], col:"#f85149",  lbl:"E"}
};

// ── Feature 9: Ring layer groups ──────────────────────────────────────────
var innerRingLayer = L.layerGroup().addTo(map);
var outerRingLayer = L.layerGroup().addTo(map);
var ringsVisible   = {inner:true, outer:true};

Object.keys(nodes).forEach(function(id) {
    var n = nodes[id];
    L.circleMarker(n.pos, {radius:8, fillColor:n.col, color:"#fff", weight:2, fillOpacity:1, pane:'markerPane'})
     .addTo(map)
     .bindPopup('<b style="font-family:monospace">NODE: '+id.toUpperCase()+'</b>');
    L.circle(n.pos, {radius:100000, color:n.col, weight:1,   fillOpacity:0, dashArray:'3,8'} ).addTo(innerRingLayer);
    L.circle(n.pos, {radius:200000, color:n.col, weight:0.5, fillOpacity:0, dashArray:'2,12'}).addTo(outerRingLayer);
});

function toggleRings(which) {
    ringsVisible[which] = !ringsVisible[which];
    var layer = which === 'inner' ? innerRingLayer : outerRingLayer;
    var btn   = document.getElementById('btn-' + which);
    if (ringsVisible[which]) { layer.addTo(map);    btn.classList.add('active'); }
    else                     { map.removeLayer(layer); btn.classList.remove('active'); }
}

// Auto-fit to sensor triangle
map.fitBounds(L.latLngBounds([
    nodes["sensor-north"].pos,
    nodes["sensor-west"].pos,
    nodes["sensor-east"].pos
]), {padding:[50,50]});

// Hide flight labels when zoomed out
map.on('zoomend', function() {
    var show = map.getZoom() >= 10;
    document.querySelectorAll('.flight-label').forEach(function(el) {
        el.style.display = show ? 'block' : 'none';
    });
});

// ── Feature 6: Altitude filter state ──────────────────────────────────────
var altMin = 0, altMax = 45000;
document.getElementById('alt-min').addEventListener('input', function() {
    altMin = parseInt(this.value);
    if (altMin >= altMax) { altMin = altMax - 1000; this.value = altMin; }
    document.getElementById('alt-min-lbl').textContent = altMin === 0 ? 'GND' : (altMin/1000).toFixed(0)+'k';
});
document.getElementById('alt-max').addEventListener('input', function() {
    altMax = parseInt(this.value);
    if (altMax <= altMin) { altMax = altMin + 1000; this.value = altMax; }
    document.getElementById('alt-max-lbl').textContent = (altMax/1000).toFixed(0)+'k';
});

// ── Color by sensor coverage ──────────────────────────────────────────────
function getColor(sb) {
    var n=sb.includes("sensor-north"), w=sb.includes("sensor-west"), e=sb.includes("sensor-east");
    if(n&&w&&e) return "#fff";
    if(n&&w)    return "#39c5cf";
    if(n&&e)    return "#d2a8ff";
    if(w&&e)    return "#d29922";
    if(n)       return "#58a6ff";
    if(w)       return "#3fb950";
    if(e)       return "#f85149";
    return "#888";
}

// ── Heading arrow SVG ─────────────────────────────────────────────────────
function arrowSvg(track, col) {
    var rot = track || 0;
    return '<svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">' +
        '<g transform="rotate('+rot+',12,12)">' +
        '<polygon points="12,2 8,18 12,14 16,18" fill="'+col+'" stroke="#000" stroke-width="0.8" opacity="0.9"/>' +
        '</g></svg>';
}

// ── Sensor health row updater ──────────────────────────────────────────────
function updateSensor(prefix, s) {
    var snr = (s.signal && s.noise) ? (s.signal - s.noise).toFixed(1) : '—';
    document.getElementById(prefix+'-sig').textContent   = s.signal      ? s.signal.toFixed(1)+' dB'  : '—';
    document.getElementById(prefix+'-snr').textContent   = snr !== '—'   ? snr+' dB'                  : '—';
    document.getElementById(prefix+'-gain').textContent  = s.gain_db     ? s.gain_db+' dB'             : '—';
    document.getElementById(prefix+'-msg').textContent   = s.msg_rate    ? s.msg_rate.toLocaleString() : '—';
    document.getElementById(prefix+'-range').textContent = s.max_range_km? s.max_range_km+' km'        : '—';
    document.getElementById(prefix+'-ac').textContent    = (s.ac_with_pos||0)+'/'+(s.ac_total||0);
    var pct = snr !== '—' ? Math.min(Math.max(parseFloat(snr)/30*100, 0), 100) : 0;
    document.getElementById(prefix+'-bar').style.width = pct+'%';

    // System telemetry: temperature and CPU load
    var tempEl = document.getElementById(prefix+'-temp');
    var loadEl = document.getElementById(prefix+'-load');
    if (s.temp_c != null) {
        var t = parseFloat(s.temp_c);
        var tcol = t >= TEMP_CRIT_C ? '#f85149' : t >= TEMP_WARN_C ? '#d29922' : '#3fb950';
        tempEl.textContent = t.toFixed(1)+'°C';
        tempEl.style.color = tcol;
    } else {
        tempEl.textContent = '—';
        tempEl.style.color = '';
    }
    if (s.load_1m != null) {
        loadEl.textContent = parseFloat(s.load_1m).toFixed(2);
        loadEl.style.color = '';
    } else {
        loadEl.textContent = '—';
        loadEl.style.color = '';
    }
}

// ── Feature 4: Connection state indicator ─────────────────────────────────
var lastUpdateTime = 0;
var connBadge = document.getElementById('conn-badge');

var socket = io();

socket.on('connect', function() {
    connBadge.className = 'live';
    connBadge.textContent = '● LIVE';
});
socket.on('disconnect', function() {
    connBadge.className = 'disconnected';
    connBadge.textContent = '● DISCONNECTED';
});

setInterval(function() {
    if (!socket.connected) return;
    var age = (Date.now() - lastUpdateTime) / 1000;
    if      (age < 3)  { connBadge.className = 'live';  connBadge.textContent = '● LIVE'; }
    else if (age < 10) { connBadge.className = 'stale'; connBadge.textContent = '● STALE ('+age.toFixed(0)+'s)'; }
    else               { connBadge.className = 'stale'; connBadge.textContent = '● STALE ('+age.toFixed(0)+'s)'; }
}, 1000);

// ── Feature 5: Opacity fade for ageing aircraft ───────────────────────────
// Aircraft are removed server-side at 15 s.  Start fading at 10 s so the
// disappearance feels smooth rather than a hard cut.
setInterval(function() {
    var now = Date.now() / 1000;
    Object.keys(markers).forEach(function(h) {
        var ls = markerLastSeen[h];
        if (!ls) return;
        var age = now - ls;
        var opacity = age > 10 ? Math.max(0.2, 1 - (age - 10) / 5) : 1.0;
        try { markers[h].setStyle({fillOpacity: opacity * 0.9}); } catch(ignored) {}
    });
    Object.keys(arrows).forEach(function(h) {
        var ls = markerLastSeen[h];
        if (!ls) return;
        var age = now - ls;
        var opacity = age > 10 ? Math.max(0.2, 1 - (age - 10) / 5) : 1.0;
        try { arrows[h].setOpacity(opacity); } catch(ignored) {}
    });
}, 500);

// ── Feature 10: Mobile dashboard toggle ───────────────────────────────────
function toggleMobileDashboard() {
    document.getElementById('dashboard').classList.toggle('expanded');
}

// ── Main map_update handler ───────────────────────────────────────────────
socket.on('map_update', function(data) {
    lastUpdateTime = Date.now();

    // Sync panel
    var dEl = document.getElementById('sync-delta');
    dEl.textContent  = data.sync.delta_ms.toFixed(2);
    dEl.style.color  = data.sync.delta_ms < 50 ? '#3fb950' : data.sync.delta_ms < 200 ? '#d29922' : '#f85149';

    var ps = data.sync.per_sensor || {};
    var psVals = Object.values(ps).filter(function(v){ return v > 0; });
    var refTime = psVals.length ? Math.min.apply(null, psVals) : 0;
    var detail = Object.entries(ps).map(function(e) {
        var short = e[0].replace('sensor-','').charAt(0).toUpperCase();
        var off = ((e[1] - refTime) % 1.0) * 1000;
        if (off > 500) off = off - 1000;
        return short+':'+off.toFixed(0)+'ms';
    }).join(' ');
    document.getElementById('sync-detail').textContent = detail;

    // Sensor health
    if (data.sensors) {
        if (data.sensors["sensor-north"]) updateSensor('n', data.sensors["sensor-north"]);
        if (data.sensors["sensor-west"])  updateSensor('w', data.sensors["sensor-west"]);
        if (data.sensors["sensor-east"])  updateSensor('e', data.sensors["sensor-east"]);
    }

    // Aircraft total count + mobile bar
    document.getElementById('ac-count').textContent  = data.aircraft.length;
    document.getElementById('mob-ac').textContent    = data.aircraft.length;
    document.getElementById('mob-sync').textContent  = data.sync.delta_ms.toFixed(2);

    // ── Feature 6: Altitude filter ────────────────────────────────────────
    var filtered = data.aircraft.filter(function(ac) {
        if (ac.alt === "ground" || ac.alt === "Ground") return altMin === 0;
        var a = parseInt(ac.alt) || 0;
        return a >= altMin && a <= altMax;
    });

    var activeHexes    = new Set();
    var allServerHexes = new Set(data.aircraft.map(function(a) { return a.hex; }));
    var counts         = {n:0, w:0, e:0, nw:0, ne:0, we:0, all:0};
    var emergencyMsgs  = [];
    var anomalyCount   = 0;
    var spoofCount     = 0;

    filtered.forEach(function(ac) {
        activeHexes.add(ac.hex);
        var col = getColor(ac.seen_by);
        var loc = L.latLng(ac.lat, ac.lon);
        var callsign = ac.flight || ac.hex.toUpperCase();
        var altStr   = (ac.alt === "ground" || ac.alt === "Ground")
                       ? "GND"
                       : (ac.alt ? parseInt(ac.alt).toLocaleString()+"ft" : "?");

        // Store client-side timestamp for opacity fade (Feature 5)
        markerLastSeen[ac.hex] = Date.now() / 1000;

        // Coverage counts
        var n=ac.seen_by.includes("sensor-north"),
            w=ac.seen_by.includes("sensor-west"),
            e=ac.seen_by.includes("sensor-east");
        if(n&&w&&e) counts.all++;
        else if(n&&w) counts.nw++;
        else if(n&&e) counts.ne++;
        else if(w&&e) counts.we++;
        else if(n)    counts.n++;
        else if(w)    counts.w++;
        else if(e)    counts.e++;

        // Feature 2: collect emergency squawks
        if (ac.emergency) emergencyMsgs.push('⚠ '+callsign+' SQUAWK '+ac.squawk);

        // Feature 7: anomaly count
        if (ac.anomaly_score === -1) anomalyCount++;

        // v3.4: spoof count
        var spoofScore = ac.spoof_score || 0;
        if (spoofScore >= 0.2) spoofCount++;

        // v3.4: ghost aircraft = single-sensor high-altitude
        var isGhost = (ac.seen_by.length === 1 && typeof ac.alt === 'number' && ac.alt > 10000);

        // Sensor distances for popup
        var dN = n ? (map.distance(loc, L.latLng(nodes["sensor-north"].pos))/1000).toFixed(1)+' km' : '—';
        var dW = w ? (map.distance(loc, L.latLng(nodes["sensor-west"].pos))/1000).toFixed(1)+' km'  : '—';
        var dE = e ? (map.distance(loc, L.latLng(nodes["sensor-east"].pos))/1000).toFixed(1)+' km'  : '—';

        // Feature 8: decoded category label
        var catLabel = ac.category ? (CAT_LABELS[ac.category] || ac.category) : '—';

        // Feature 7: anomaly badge for popup
        var anomalyBadge = (ac.anomaly_score !== null && ac.anomaly_score !== undefined)
            ? '<span style="color:'+(ac.anomaly_score===-1?'#d29922':'#3fb950')+';">'
              +(ac.anomaly_score===-1?'⚠ ANOMALY':'✓ Normal')+'</span>'
            : '—';

        // Feature 3: TDOA uncertainty info for popup
        var tdoaStr = '';
        if (ac.tdoa_uncertainty_m !== undefined) {
            var um = ac.tdoa_uncertainty_m;
            tdoaStr = '<hr style="border:0;border-top:1px dashed #30363d;margin:6px 0;">'
                    + '<span style="color:#8b949e;font-size:0.9em;">TDOA UNCERTAINTY:</span><br>'
                    + (um < 1000 ? um.toFixed(0)+' m' : (um/1000).toFixed(1)+' km')+' radius<br>';
        }

        // v3.4: spoof score badge for popup
        var spoofBadge = '';
        if (spoofScore > 0) {
            var scol = spoofScore >= 0.5 ? '#f85149' : '#d29922';
            var pct  = Math.round(spoofScore * 100);
            var flagStr = (ac.spoof_flags && ac.spoof_flags.length) ? ac.spoof_flags.join(', ') : '';
            spoofBadge = '<hr style="border:0;border-top:1px dashed #30363d;margin:6px 0;">'
                + '<span style="color:'+scol+';font-weight:bold;">&#9889; SPOOF: '+pct+'%</span>'
                + (flagStr ? '<br><span style="color:#8b949e;font-size:0.85em;">'+flagStr+'</span>' : '');
        }

        var popupHTML =
            '<div style="font-family:monospace;min-width:175px;">'
            +(ac.emergency ? '<div style="color:#f85149;font-weight:bold;margin-bottom:4px;">⚠ EMERGENCY SQUAWK</div>' : '')
            +'<b style="color:'+col+';font-size:1.2em;">'+callsign+'</b><br>'
            +'ICAO: '+ac.hex+'<br>'
            +'SQWK: '+(ac.squawk||'—')+(ac.emergency?' <b style="color:#f85149;">⚠</b>':'')+'<br>'
            +'ALT : '+altStr+'<br>'
            +'GS  : '+(ac.gs ? ac.gs.toFixed(0)+' kt' : '—')+'<br>'
            +'HDG : '+(ac.track != null ? ac.track.toFixed(0)+'°' : '—')+'<br>'
            +'RSSI: '+(ac.rssi ? ac.rssi.toFixed(1)+' dB' : '—')+'<br>'
            +'TYPE: '+(ac.type||'—')+'<br>'
            +'CAT : '+catLabel+'<br>'
            +'MLAT: '+anomalyBadge+'<br>'
            +'<hr style="border:0;border-top:1px dashed #30363d;margin:6px 0;">'
            +'<span style="color:#8b949e;font-size:0.9em;">RANGES:</span><br>'
            +'<span style="color:#58a6ff">[N]</span> '+dN+'<br>'
            +'<span style="color:#3fb950">[W]</span> '+dW+'<br>'
            +'<span style="color:#f85149">[E]</span> '+dE+'<br>'
            +tdoaStr
            +'<span style="color:#8b949e;font-size:0.85em;">Sensors: '+ac.seen_by.length+'/3</span>'
            +spoofBadge
            +(isGhost ? '<br><span style="color:#d29922;font-size:0.85em;">&#9655; GHOST candidate</span>' : '')
            +'</div>';

        // ── Feature 1: Trail polyline ─────────────────────────────────────
        if (ac.trail && ac.trail.length > 1) {
            var trailPts = ac.trail.map(function(p) { return L.latLng(p[0], p[1]); });
            if (trails[ac.hex]) {
                trails[ac.hex].setLatLngs(trailPts).setStyle({color: col});
            } else {
                trails[ac.hex] = L.polyline(trailPts, {
                    color: col, weight:1.5, opacity:0.45, dashArray:'4,4', interactive:false
                }).addTo(map);
            }
        }

        // ── Feature 3: TDOA uncertainty circle ────────────────────────────
        if (ac.tdoa_uncertainty_m !== undefined && ac.tdoa_uncertainty_m > 0) {
            // Cap visual radius at 200 km to keep map readable
            var r = Math.min(ac.tdoa_uncertainty_m, 200000);
            if (tdoaCircles[ac.hex]) {
                tdoaCircles[ac.hex].setLatLng(loc).setRadius(r);
            } else {
                tdoaCircles[ac.hex] = L.circle(loc, {
                    radius: r, color:'#f0a000', weight:1,
                    fillOpacity:0.05, dashArray:'3,6', interactive:false
                }).addTo(map);
            }
        }

        // ── Feature 7: Anomaly outer ring ─────────────────────────────────
        if (ac.anomaly_score === -1) {
            if (anomalyRings[ac.hex]) {
                anomalyRings[ac.hex].setLatLng(loc);
            } else {
                anomalyRings[ac.hex] = L.circleMarker(loc, {
                    radius:14, fillColor:'transparent', color:'#d29922',
                    weight:2, fillOpacity:0, pane:'markerPane', interactive:false
                }).addTo(map);
            }
        }

        // ── v3.4: Spoofing score outer ring ───────────────────────────────
        if (spoofScore >= 0.2) {
            var ringColor  = spoofScore >= 0.5 ? '#f85149' : '#d29922';
            var ringRadius = spoofScore >= 0.5 ? 20 : 17;
            if (spoofRings[ac.hex]) {
                spoofRings[ac.hex].setLatLng(loc).setStyle({color: ringColor, radius: ringRadius});
            } else {
                spoofRings[ac.hex] = L.circleMarker(loc, {
                    radius: ringRadius, fillColor:'transparent', color: ringColor,
                    weight: 2.5, fillOpacity:0, pane:'markerPane', interactive:false,
                    className:'spoof-ring'
                }).addTo(map);
            }
        } else if (spoofRings[ac.hex]) {
            map.removeLayer(spoofRings[ac.hex]);
            delete spoofRings[ac.hex];
        }

        // ── v3.4: Ghost aircraft dashed ring ──────────────────────────────
        if (isGhost && !anomalyRings[ac.hex]) {
            // Reuse anomalyRings slot with a distinct dashed style
            if (anomalyRings[ac.hex]) {
                anomalyRings[ac.hex].setLatLng(loc);
            } else {
                anomalyRings[ac.hex] = L.circleMarker(loc, {
                    radius:16, fillColor:'transparent', color:'#d29922',
                    weight:1.5, fillOpacity:0, dashArray:'3,4',
                    pane:'markerPane', interactive:false
                }).addTo(map);
            }
        }

        // ── Heading arrow / circle marker ─────────────────────────────────
        var markerCol  = ac.emergency ? '#f85149' : col;
        var emClass    = ac.emergency ? ' class="emergency-marker"' : '';

        if (ac.track != null && ac.gs && ac.gs > 10) {
            var iconHtml = '<div'+emClass+'>'+arrowSvg(ac.track, markerCol)+'</div>';
            var icon = L.divIcon({html:iconHtml, className:'', iconSize:[24,24], iconAnchor:[12,12]});
            if (arrows[ac.hex]) {
                arrows[ac.hex].setLatLng(loc).setIcon(icon);
                if (arrows[ac.hex].getPopup()) arrows[ac.hex].getPopup().setContent(popupHTML);
            } else {
                arrows[ac.hex] = L.marker(loc, {icon:icon, pane:'markerPane'}).bindPopup(popupHTML).addTo(map);
            }
            if (markers[ac.hex]) { map.removeLayer(markers[ac.hex]); delete markers[ac.hex]; }
        } else {
            if (markers[ac.hex]) {
                markers[ac.hex].setLatLng(loc).setStyle({fillColor:markerCol, color:"#000"});
                if (markers[ac.hex].getPopup()) markers[ac.hex].getPopup().setContent(popupHTML);
            } else {
                markers[ac.hex] = L.circleMarker(loc, {
                    radius:6, fillColor:markerCol, color:"#000",
                    weight:1, fillOpacity:0.9,
                    className: ac.emergency ? 'emergency-marker' : ''
                }).bindPopup(popupHTML).addTo(map);
            }
            if (arrows[ac.hex]) { map.removeLayer(arrows[ac.hex]); delete arrows[ac.hex]; }
        }

        // Flight label
        var labelIcon = L.divIcon({
            html:'<span>'+callsign+'</span>',
            className:'flight-label', iconSize:[80,14], iconAnchor:[-8,7]
        });
        if (labels[ac.hex]) {
            labels[ac.hex].setLatLng(loc).setIcon(labelIcon);
        } else {
            labels[ac.hex] = L.marker(loc, {icon:labelIcon, interactive:false, pane:'tooltipPane'}).addTo(map);
        }
    });

    // ── Feature 2: Emergency banner ───────────────────────────────────────
    var banner = document.getElementById('emergency-banner');
    if (emergencyMsgs.length > 0) {
        banner.style.display = 'block';
        banner.textContent = emergencyMsgs.join('   |   ');
    } else {
        banner.style.display = 'none';
    }

    // ── v3.4: Jamming alert banner ────────────────────────────────────────
    var jammingBanner = document.getElementById('jamming-banner');
    var jamList = data.jamming || [];
    if (jamList.length > 0) {
        var jamNames = jamList.map(function(s) { return s.replace('sensor-','').toUpperCase(); });
        jammingBanner.style.display = 'block';
        jammingBanner.textContent   = '&#x26A1; JAMMING DETECTED: ' + jamNames.join(', ')
            + ' — message rate dropped >60%';
    } else {
        jammingBanner.style.display = 'none';
    }

    // Legend counts
    document.getElementById('cnt-n').textContent       = counts.n;
    document.getElementById('cnt-w').textContent       = counts.w;
    document.getElementById('cnt-e').textContent       = counts.e;
    document.getElementById('cnt-nw').textContent      = counts.nw;
    document.getElementById('cnt-ne').textContent      = counts.ne;
    document.getElementById('cnt-we').textContent      = counts.we;
    document.getElementById('cnt-all').textContent     = counts.all;
    document.getElementById('cnt-anomaly').textContent = anomalyCount;
    document.getElementById('cnt-spoof').textContent   = spoofCount;

    // Clean up markers for aircraft no longer in the current display set
    // Use allServerHexes for markerLastSeen cleanup (keep data for off-screen filtered aircraft)
    // Use activeHexes for map layer cleanup (respect altitude filter)
    var hx;
    for (hx in markers)      { if (!activeHexes.has(hx))    { map.removeLayer(markers[hx]);      delete markers[hx]; } }
    for (hx in arrows)        { if (!activeHexes.has(hx))    { map.removeLayer(arrows[hx]);        delete arrows[hx]; } }
    for (hx in labels)        { if (!activeHexes.has(hx))    { map.removeLayer(labels[hx]);        delete labels[hx]; } }
    for (hx in trails)        { if (!activeHexes.has(hx))    { map.removeLayer(trails[hx]);        delete trails[hx]; } }
    for (hx in tdoaCircles)   { if (!activeHexes.has(hx))    { map.removeLayer(tdoaCircles[hx]);   delete tdoaCircles[hx]; } }
    for (hx in anomalyRings)  { if (!activeHexes.has(hx))    { map.removeLayer(anomalyRings[hx]);  delete anomalyRings[hx]; } }
    for (hx in spoofRings)    { if (!activeHexes.has(hx))    { map.removeLayer(spoofRings[hx]);    delete spoofRings[hx]; } }
    for (hx in markerLastSeen){ if (!allServerHexes.has(hx)) { delete markerLastSeen[hx]; } }
});
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    start_mqtt()
    socketio.run(app, host='0.0.0.0', port=8080)
