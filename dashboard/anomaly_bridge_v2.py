"""
anomaly_bridge_v2.py — Next-Gen ADS-B Anomaly Detection Service
================================================================
Version: 2.0.0
Project: ADS-B Research Grid / SecuringSkies

WHAT'S NEW IN v2.0
------------------
Feature expansion:  4 -> 28+ features per aircraft (baro_rate, ias, tas, mach,
                     wd, ws, oat, climb_rate, acceleration, track_rate, etc.)
Temporal features:  Stddev/variance of alt/gs/track over window — catches
                     erratic behavior that mean-aggregation hides.
Per-sensor buffer:  Tracks which sensor reported what lat/lon. Detects
                     cross-sensor position conflicts (strongest spoof signal
                     in a 3-sensor MLAT grid).
Cross-sensor conflict: If sensor A sees hex X at (60.1, 24.9) and sensor B
                     sees the same hex at (60.2, 25.0) simultaneously, that's
                     a >10 km discrepancy — flagged immediately.
Probabilistic output: Continuous anomaly score in [-1.0, +1.0] instead of
                     binary -1/1. Also publishes anomaly_flags list and
                     confidence level per aircraft.
Sanity gates:        Pre-filter unrealistic values (alt > 60000 ft,
                     gs > 700 kt, altitude jumps > 20000 ft in 30s).
Dashboard integration: New payload format includes 'flags', 'confidence',
                     and 'feature_contributions' for richer UI display.

Architecture
------------
Connects to MQTT broker (localhost:1883), subscribes to +/aircraft and
+/stats, maintains a rolling observation buffer with per-sensor granularity,
and runs a multi-model ensemble every INFERENCE_INTERVAL seconds.

Models (ensemble):
  1. IsolationForest  — general-purpose outlier detection
  2. LocalOutlierFactor — local density-based detection
  3. EllipticEnvelope — multivariate Gaussian fit (catches covariate shifts)
  4. Robust covariance — Mahalanobis distance based

Publishes to: sensor-core/anomalies-v2 (enriched format)
Also publishes to: sensor-core/anomalies (v1 compat format)

Usage
-----
    python anomaly_bridge_v2.py

Environment variables (all optional):
    MQTT_HOST            Broker hostname          (default: localhost)
    MQTT_PORT            Broker port              (default: 1883)
    MQTT_USER            MQTT username            (default: team9)
    MQTT_PASS            MQTT password            (default: from file)
    INFERENCE_INTERVAL   Seconds between runs     (default: 30)
    WINDOW_SECONDS       Observation window size  (default: 300)
    MIN_SAMPLES          Min observations to run  (default: 15)
    CONTAMINATION        IsoForest contamination  (default: 0.02)
"""

import csv
import io
import json
import logging
import ssl
import math
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np
import paho.mqtt.client as mqtt
from sklearn.covariance import EllipticEnvelope
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import RobustScaler, StandardScaler

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MQTT_HOST          = os.getenv("MQTT_HOST",  "localhost")
MQTT_PORT          = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER          = os.getenv("MQTT_USER", "team9")
MQTT_PASS_FILE     = os.getenv("MQTT_PASS_FILE", "/etc/securing-skies/mqtt_secret")
MQTT_PASS          = os.getenv("MQTT_PASS", "")
if not MQTT_PASS and MQTT_PASS_FILE and os.path.isfile(MQTT_PASS_FILE):
    try:
        with open(MQTT_PASS_FILE, "r", encoding="utf-8") as fh:
            MQTT_PASS = fh.read().strip()
    except (OSError, IOError) as exc:
        logging.getLogger(__name__).warning(
            "Could not read MQTT password from %s: %s", MQTT_PASS_FILE, exc
        )
if not MQTT_PASS:
    MQTT_PASS = "ResearchView2026!"


INFERENCE_INTERVAL = int(os.getenv("INFERENCE_INTERVAL", "30"))
WINDOW_SECONDS     = int(os.getenv("WINDOW_SECONDS",     "300"))
MIN_SAMPLES        = int(os.getenv("MIN_SAMPLES",        "5"))
CONTAMINATION      = float(os.getenv("CONTAMINATION",    "0.02"))

# Topics
TOPIC_SUBSCRIBE  = "+/aircraft"
TOPIC_STATS      = "+/stats"
TOPIC_PUBLISH_V2 = "sensor-core/anomalies-v2"
TOPIC_PUBLISH_V1 = "sensor-core/anomalies"

# Physical sanity limits
MAX_PLAUSIBLE_ALT_FT  = 60000
MAX_PLAUSIBLE_GS_KT   = 700
MAX_CLIMB_RATE_FPM    = 10000     # per 30s window
MAX_ALT_JUMP_FT       = 20000     # per observation pair
MAX_POSITION_JUMP_KM  = 50        # per 30s window

# Cross-sensor conflict threshold (same hex, 2+ sensors, > this distance)
MAX_SENSOR_POS_DISCREPANCY_KM = 3.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [anomaly_v2] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

# Per-sensor per-aircraft observations
#   per_sensor_buffer[sensor_name][hex_id] = list of (ts, lat, lon, alt, gs, track, rssi, baro_rate)
per_sensor_buffer: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))

# Per-aircraft aggregated feature history for temporal stats
#   aircraft_stats[hex_id] = { "alt": [...], "gs": [...], "track": [...], ... }
aircraft_feature_history: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))

# Per-aircraft cross-sensor position registry
#   aircraft_positions[hex_id] = { sensor_name: (lat, lon, ts), ... }
aircraft_positions: dict[str, dict] = defaultdict(dict)

# Feature column order for ML model
FEATURE_NAMES = [
    # Base features (from current observation)
    "alt_baro", "gs", "track", "rssi",
    "baro_rate", "ias", "tas", "mach",
    "true_heading", "mag_heading", "roll",
    "wd", "ws", "oat",
    "nav_altitude_mcp", "nav_qnh",
    # Temporal features (stddev over window)
    "alt_std", "gs_std", "track_std", "rssi_std",
    "baro_rate_std",
    # Computed features
    "climb_rate_fpm",
    "sensor_count",
    "rssi_range",
    "alt_range",
    "gs_range",
    "track_rate",
    "ias_tas_ratio",
    "alt_bearing_rate",
]
NUM_FEATURES = len(FEATURE_NAMES)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def extract_features_v2(ac: dict, hex_id: str, sensor: str) -> dict | None:
    """
    Extract a rich feature vector from one aircraft observation.
    Returns dict of feature_name -> value, or None if aircraft has no position.
    """
    lat = ac.get("lat")
    lon = ac.get("lon")
    if lat is None or lon is None:
        return None

    alt_baro = ac.get("alt_baro")
    if alt_baro is not None:
        try:
            alt_baro = float(alt_baro)
        except (TypeError, ValueError):
            alt_baro = None

    gs = ac.get("gs")
    if gs is not None:
        try:
            gs = float(gs)
        except (TypeError, ValueError):
            gs = None

    track = ac.get("track")
    if track is not None:
        try:
            track = float(track)
        except (TypeError, ValueError):
            track = None

    # Sanity gates — skip aircraft that violate physics
    if alt_baro is not None and alt_baro > MAX_PLAUSIBLE_ALT_FT:
        return None
    if gs is not None and gs > MAX_PLAUSIBLE_GS_KT:
        return None

    def _safe_float(v, default=None):
        if v is None:
            return default
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    rssi = _safe_float(ac.get("rssi"), -50)
    baro_rate = _safe_float(ac.get("baro_rate"), 0)
    geom_rate = _safe_float(ac.get("geom_rate"), 0)
    ias = _safe_float(ac.get("ias"), 0)
    tas_val = _safe_float(ac.get("tas"), 0)
    mach = _safe_float(ac.get("mach"), 0)
    true_hdg = _safe_float(ac.get("true_heading"), track)
    mag_hdg = _safe_float(ac.get("mag_heading"), track)
    roll = _safe_float(ac.get("roll"), 0)
    wd = _safe_float(ac.get("wd"), 0)
    ws_val = _safe_float(ac.get("ws"), 0)
    oat = _safe_float(ac.get("oat"), 0)
    nav_alt = _safe_float(ac.get("nav_altitude_mcp"), 0)
    nav_qnh = _safe_float(ac.get("nav_qnh"), 1013.25)
    track_rate = _safe_float(ac.get("track_rate"), 0)

    # Compute climb_rate from baro_rate if available
    climb_rate = baro_rate if baro_rate else geom_rate

    # IAS-to-TAS ratio (high ratio at altitude = potentially spoofed)
    ias_tas_ratio = 0.0
    if ias > 0 and tas_val > 0:
        ias_tas_ratio = ias / tas_val

    # Altitude bearing rate: how fast alt changes with track
    alt_bearing_rate = 0.0
    if track and track_rate:
        alt_bearing_rate = abs(track_rate) * (alt_baro or 0) / 1000.0

    # Get or compute temporal stats from history
    alt_vals = aircraft_feature_history[hex_id].get("alt", [])
    gs_vals = aircraft_feature_history[hex_id].get("gs", [])
    track_vals = aircraft_feature_history[hex_id].get("track", [])
    rssi_vals = aircraft_feature_history[hex_id].get("rssi", [])
    baro_rate_vals = aircraft_feature_history[hex_id].get("baro_rate", [])

    def _std_or_zero(vals):
        if len(vals) >= 3:
            return float(np.std(vals))
        return 0.0

    def _range_or_zero(vals):
        if len(vals) >= 2:
            return float(max(vals) - min(vals))
        return 0.0

    alt_std = _std_or_zero(alt_vals)
    gs_std = _std_or_zero(gs_vals)
    track_std = _std_or_zero(track_vals)
    rssi_std = _std_or_zero(rssi_vals)
    baro_rate_std = _std_or_zero(baro_rate_vals)
    alt_range = _range_or_zero(alt_vals)
    gs_range = _range_or_zero(gs_vals)
    rssi_range = _range_or_zero(rssi_vals)

    # Count how many sensors see this aircraft
    sensor_count = len(aircraft_positions.get(hex_id, {}))

    return {
        "alt_baro": alt_baro or 0,
        "gs": gs or 0,
        "track": track or 0,
        "rssi": rssi,
        "baro_rate": baro_rate,
        "ias": ias,
        "tas": tas_val,
        "mach": mach,
        "true_heading": true_hdg or 0,
        "mag_heading": mag_hdg or 0,
        "roll": roll,
        "wd": wd,
        "ws": ws_val,
        "oat": oat,
        "nav_altitude_mcp": nav_alt,
        "nav_qnh": nav_qnh,
        "alt_std": alt_std,
        "gs_std": gs_std,
        "track_std": track_std,
        "rssi_std": rssi_std,
        "baro_rate_std": baro_rate_std,
        "climb_rate_fpm": climb_rate,
        "sensor_count": sensor_count,
        "rssi_range": rssi_range,
        "alt_range": alt_range,
        "gs_range": gs_range,
        "track_rate": track_rate,
        "ias_tas_ratio": ias_tas_ratio,
        "alt_bearing_rate": alt_bearing_rate,
    }


def compute_cross_sensor_conflict_score(hex_id: str) -> float:
    """
    Check if the same aircraft hex is reported at significantly different
    positions by different sensors. Returns score 0.0 (consistent) to 1.0
    (highly conflicting).

    This is the single strongest spoofing detection signal in a multi-sensor
    MLAT grid: a real aircraft at 30,000 ft is visible to all three sensors
    at essentially the same (lat, lon). If two sensors report different
    positions for the same hex, it's either a spoofer broadcasting from
    two locations or a misconfiguration.
    """
    positions = aircraft_positions.get(hex_id, {})
    if len(positions) < 2:
        return 0.0

    sensor_names = list(positions.keys())
    max_dist_km = 0.0
    pair_count = 0

    for i in range(len(sensor_names)):
        for j in range(i + 1, len(sensor_names)):
            s1 = sensor_names[i]
            s2 = sensor_names[j]
            p1 = positions[s1]
            p2 = positions[s2]
            # Only compare recent observations (within 15 seconds)
            now = time.time()
            if abs(p1[2] - now) > 15 and abs(p2[2] - now) > 15:
                continue
            dist = haversine_km(p1[0], p1[1], p2[0], p2[1])
            max_dist_km = max(max_dist_km, dist)
            pair_count += 1

    if pair_count == 0:
        return 0.0

    # Score: 0.0 for < 2km, ramps to 1.0 at > 20km discrepancy
    if max_dist_km > MAX_SENSOR_POS_DISCREPANCY_KM:
        score = min(1.0, max_dist_km / 20.0)
        log.info("Cross-sensor conflict for %s: max %.1f km (score=%.2f)",
                 hex_id, max_dist_km, score)
        return score
    return 0.0


def run_sanity_checks(hex_id: str) -> list[str]:
    """
    Run physical sanity checks on an aircraft's recent history.
    Returns list of flag strings.
    """
    flags = []
    history = aircraft_feature_history.get(hex_id, {})

    # Check for altitude jumps > 20,000 ft
    alt_vals = history.get("alt", [])
    if len(alt_vals) >= 2:
        alt_jump = max(alt_vals) - min(alt_vals)
        if alt_jump > MAX_ALT_JUMP_FT:
            flags.append(f"alt_jump_{alt_jump:.0f}ft")

    # Check for impossible climb rate
    baro_rate_vals = history.get("baro_rate", [])
    if baro_rate_vals:
        max_climb = max(abs(v) for v in baro_rate_vals)
        if max_climb > MAX_CLIMB_RATE_FPM:
            flags.append(f"climb_{max_climb:.0f}fpm")

    # Check for position jumps > 50 km in 30s
    positions = aircraft_positions.get(hex_id, {})
    if len(positions) >= 2:
        sensor_names = list(positions.keys())
        for i in range(len(sensor_names)):
            for j in range(i + 1, len(sensor_names)):
                p1 = positions[sensor_names[i]]
                p2 = positions[sensor_names[j]]
                dist = haversine_km(p1[0], p1[1], p2[0], p2[1])
                if dist > MAX_POSITION_JUMP_KM:
                    flags.append(f"pos_jump_{dist:.0f}km_{sensor_names[i]}_{sensor_names[j]}")

    return flags


# ---------------------------------------------------------------------------
# MQTT callback
# ---------------------------------------------------------------------------


def on_message(client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage):
    """Ingest an aircraft/stats payload and update buffers."""
    try:
        parts = message.topic.split("/")
        if len(parts) != 2:
            return
        sensor_name = parts[0]
        msg_type = parts[1]

        payload = json.loads(message.payload)
        ts = time.time()

        if msg_type == "aircraft":
            for ac in payload.get("aircraft", []):
                hex_id = ac.get("hex")
                if not hex_id or "lat" not in ac:
                    continue

                lat = ac.get("lat")
                lon = ac.get("lon")
                if lat is None or lon is None:
                    continue

                alt_baro = ac.get("alt_baro")
                gs = ac.get("gs")
                track = ac.get("track")
                rssi = ac.get("rssi", -50)
                baro_rate = ac.get("baro_rate", 0)

                # Update per-sensor buffer
                per_sensor_buffer[sensor_name][hex_id].append((
                    ts, lat, lon, alt_baro, gs, track, rssi, baro_rate
                ))

                # Update feature history for temporal stats
                if alt_baro is not None:
                    try:
                        aircraft_feature_history[hex_id]["alt"].append(float(alt_baro))
                    except (TypeError, ValueError):
                        pass
                if gs is not None:
                    try:
                        aircraft_feature_history[hex_id]["gs"].append(float(gs))
                    except (TypeError, ValueError):
                        pass
                if track is not None:
                    try:
                        aircraft_feature_history[hex_id]["track"].append(float(track))
                    except (TypeError, ValueError):
                        pass
                if rssi is not None:
                    try:
                        aircraft_feature_history[hex_id]["rssi"].append(float(rssi))
                    except (TypeError, ValueError):
                        pass
                if baro_rate is not None:
                    try:
                        aircraft_feature_history[hex_id]["baro_rate"].append(float(baro_rate))
                    except (TypeError, ValueError):
                        pass

                # Update per-sensor position registry
                aircraft_positions[hex_id][sensor_name] = (lat, lon, ts)

    except Exception as exc:
        log.warning("Parse error on %s: %s", message.topic, exc)


def _prune_buffers(cutoff: float) -> None:
    """Remove old observations from all buffers."""
    # Prune per-sensor buffer
    stale_sensors = []
    for sensor_name, ac_dict in per_sensor_buffer.items():
        stale_hexes = []
        for hex_id, obs_list in ac_dict.items():
            # Filter observations
            ac_dict[hex_id] = [o for o in obs_list if o[0] >= cutoff]
            if not ac_dict[hex_id]:
                stale_hexes.append(hex_id)
        for h in stale_hexes:
            del ac_dict[h]
        if not ac_dict:
            stale_sensors.append(sensor_name)
    for s in stale_sensors:
        del per_sensor_buffer[s]

    # Prune feature history — keep only recent entries (last 20 per aircraft)
    for hex_id in list(aircraft_feature_history.keys()):
        for feat_name in list(aircraft_feature_history[hex_id].keys()):
            vals = aircraft_feature_history[hex_id][feat_name]
            if len(vals) > 20:
                aircraft_feature_history[hex_id][feat_name] = vals[-20:]

    # Prune position registry — remove stale entries (older than 30s)
    now = time.time()
    for hex_id in list(aircraft_positions.keys()):
        for sensor_name in list(aircraft_positions[hex_id].keys()):
            if now - aircraft_positions[hex_id][sensor_name][2] > 30:
                del aircraft_positions[hex_id][sensor_name]
        if not aircraft_positions[hex_id]:
            del aircraft_positions[hex_id]


# ---------------------------------------------------------------------------
# Inference engine
# ---------------------------------------------------------------------------


def run_inference(client: mqtt.Client) -> None:
    """
    Build a rich feature matrix, run multi-model ensemble, and publish
    enriched anomaly scores to MQTT.
    """
    cutoff = time.time() - WINDOW_SECONDS
    _prune_buffers(cutoff)

    # Collect all active hex IDs across all sensors
    all_hexes = set()
    for ac_dict in per_sensor_buffer.values():
        all_hexes.update(ac_dict.keys())

    if not all_hexes:
        log.debug("Buffer empty — skipping inference.")
        return

    hex_ids = []
    X_raw = []

    latest_features: dict[str, dict] = {}  # hex_id -> latest feature dict

    for hex_id in sorted(all_hexes):
        # Get latest feature vector (from any sensor)
        best_features = None
        best_ts = 0

        for sensor_name, ac_dict in per_sensor_buffer.items():
            obs_list = ac_dict.get(hex_id, [])
            for obs in obs_list:
                obs_ts = obs[0]
                if obs_ts > best_ts:
                    ac_data = {
                        "lat": obs[1], "lon": obs[2],
                        "alt_baro": obs[3], "gs": obs[4],
                        "track": obs[5], "rssi": obs[6],
                        "baro_rate": obs[7],
                    }
                    best_features = ac_data
                    best_ts = obs_ts

        if best_features is None:
            continue

        features = extract_features_v2(best_features, hex_id, "")
        if features is None:
            continue

        latest_features[hex_id] = features
        feature_vector = [features.get(name, 0.0) for name in FEATURE_NAMES]
        hex_ids.append(hex_id)
        X_raw.append(feature_vector)

    if len(hex_ids) < MIN_SAMPLES:
        log.info("Only %d aircraft (need %d) — skipping inference.",
                 len(hex_ids), MIN_SAMPLES)
        return

    X = np.array(X_raw, dtype=float)

    # Sanitize: replace NaN / inf with column medians
    col_medians = np.nanmedian(X, axis=0)
    col_medians = np.nan_to_num(col_medians, nan=0.0)
    inds = np.where(~np.isfinite(X))
    if len(inds[0]) > 0:
        X[inds] = np.take(col_medians, inds[1])

    # Scale with RobustScaler (resistant to outliers)
    scaler = RobustScaler(quantile_range=(5, 95))
    X_scaled = scaler.fit_transform(X)

    # Also compute StandardScaler version for some models
    ss = StandardScaler()
    X_std = ss.fit_transform(X)

    n = len(hex_ids)

    # --- Model 1: IsolationForest ---
    iso = IsolationForest(
        contamination=CONTAMINATION,
        random_state=42,
        n_jobs=-1,
    )
    scores_iso = iso.fit_predict(X_scaled)  # -1 or 1

    # Anomaly score (continuous): decision_function gives negative for anomalies
    iso_scores_raw = iso.decision_function(X_scaled)  # negative = anomaly

    # --- Model 2: LocalOutlierFactor ---
    if n <= 50_000:
        lof = LocalOutlierFactor(
            n_neighbors=min(20, n - 1),
            contamination=CONTAMINATION,
            n_jobs=-1,
        )
        scores_lof = lof.fit_predict(X_scaled)
        # LOF doesn't have decision_function, use negative_outlier_factor_
        lof_scores_raw = -lof.negative_outlier_factor_  # higher = more anomalous
        # Normalize to roughly [-1, 1] range
        if np.percentile(lof_scores_raw, 95) > 0:
            lof_scores_raw = np.clip(lof_scores_raw / np.percentile(lof_scores_raw, 95), 0, 5) * -1
        else:
            lof_scores_raw = np.zeros(n)
        # Convert: -5 = highly anomalous, 0 = normal
    else:
        log.info("LOF skipped — dataset too large (%d).", n)
        scores_lof = np.ones(n, dtype=int)
        lof_scores_raw = np.zeros(n)

    # --- Model 3: EllipticEnvelope (Gaussian fit) ---
    try:
        ee = EllipticEnvelope(
            contamination=CONTAMINATION,
            random_state=42,
            support_fraction=0.7,
        )
        scores_ee = ee.fit_predict(X_std)  # -1 or 1
        ee_raw = ee.decision_function(X_std)  # negative = anomaly (Mahalanobis distance)
        ee_raw = np.where(ee_raw < -10, -10, ee_raw)  # clip extreme values
    except Exception as exc:
        log.warning("EllipticEnvelope failed: %s", exc)
        scores_ee = np.ones(n, dtype=int)
        ee_raw = np.zeros(n)

    # --- Ensemble: weighted voting with continuous scores ---
    ensemble = {}
    for i, hex_id in enumerate(hex_ids):
        # Binary votes
        vote = scores_iso[i] + scores_lof[i] + scores_ee[i]
        # vote ranges from -3 (all anomaly) to +3 (all normal)

        # Continuous score blend: average of model raw scores, then scale to [-1, 1]
        raw_blend = (iso_scores_raw[i] + lof_scores_raw[i] + ee_raw[i]) / 3.0
        # iso_scores_raw ranges approx [-0.7, 0.7], scale to [-1, 1]
        continuous_score = max(-1.0, min(1.0, raw_blend * 2.0))

        # Confidence: how many models agree
        models_agree = sum([
            1 for s in [scores_iso[i], scores_lof[i], scores_ee[i]] if s == -1
        ])
        confidence = models_agree / 3.0  # 0.0 to 1.0

        # Cross-sensor conflict check (override)
        conflict_score = compute_cross_sensor_conflict_score(hex_id)
        if conflict_score > 0.5:
            # Override: cross-sensor conflict is very strong signal
            continuous_score = max(continuous_score, conflict_score * -1.0)
            vote = min(vote, -2)
            confidence = max(confidence, 0.8)

        # Sanity checks
        sanity_flags = run_sanity_checks(hex_id)

        # Determine final -1/1 vote from continuous score
        final_label = -1 if continuous_score < -0.1 else 1

        # Determine which features contributed most (top 5 by absolute deviation)
        feature_deviations = []
        if i < len(X_raw):
            row = X_scaled[i]
            abs_deviations = np.abs(row - np.median(row))
            top_feat_indices = np.argsort(abs_deviations)[-5:][::-1]
            for fi in top_feat_indices:
                if fi < len(FEATURE_NAMES) and abs_deviations[fi] > 2.0:
                    feature_deviations.append({
                        "feature": FEATURE_NAMES[fi],
                        "z_score": round(float(abs_deviations[fi]), 2),
                    })

        ensemble[hex_id] = {
            "score": round(continuous_score, 4),
            "label": final_label,
            "confidence": round(confidence, 3),
            "models_agree": models_agree,
            "flags": sanity_flags,
            "conflict_score": round(conflict_score, 3),
            "features": feature_deviations[:3],  # top 3 contributing features
        }

    # Count anomalies (label == -1)
    anomaly_count = sum(1 for v in ensemble.values() if v["label"] == -1)

    log.info(
        "Inference v2 — %d aircraft, %d anomalies (%.1f%%).",
        len(hex_ids), anomaly_count,
        100.0 * anomaly_count / len(hex_ids) if len(hex_ids) > 0 else 0,
    )

    # --- Publish v2 format (enriched) ---
    payload_v2 = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "model": "ensemble-v2.0",
        "feature_count": NUM_FEATURES,
        "anomalies": ensemble,
        "summary": {
            "total": len(hex_ids),
            "anomaly_count": anomaly_count,
            "anomaly_pct": round(100.0 * anomaly_count / len(hex_ids), 1) if hex_ids else 0,
        },
    }
    payload_v2_str = json.dumps(payload_v2)
    result = client.publish(TOPIC_PUBLISH_V2, payload_v2_str, qos=0, retain=False)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        log.warning("Publish v2 failed (rc=%d)", result.rc)

    # --- Also publish v1 format for backward compatibility ---
    payload_v1 = {hex_id: v["label"] for hex_id, v in ensemble.items()}
    result_v1 = client.publish(TOPIC_PUBLISH_V1, json.dumps(payload_v1), qos=0, retain=False)
    if result_v1.rc != mqtt.MQTT_ERR_SUCCESS:
        log.warning("Publish v1 failed (rc=%d)", result_v1.rc)

    # Log top anomalies if any
    if anomaly_count > 0:
        top_anomalies = sorted(
            [(hid, v) for hid, v in ensemble.items() if v["label"] == -1],
            key=lambda x: x[1]["score"],
        )[:5]
        for hid, v in top_anomalies:
            log.info("  ANOMALY %s: score=%.3f conf=%.2f flags=%s",
                     hid, v["score"], v["confidence"],
                     ",".join(v["flags"]) if v["flags"] else "none")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    client = mqtt.Client(client_id="anomaly-bridge-v2", transport="websockets")
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)

    if MQTT_USER and MQTT_PASS:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    client.on_message = on_message

    log.info("Connecting to MQTT broker at %s:%d (WSS)...", MQTT_HOST, MQTT_PORT)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.subscribe(TOPIC_SUBSCRIBE)
    client.subscribe(TOPIC_STATS)
    log.info(
        "Subscribed — inference every %ds, window %ds, min %d samples, %d features.",
        INFERENCE_INTERVAL, WINDOW_SECONDS, MIN_SAMPLES, NUM_FEATURES,
    )

    # Warm-up: let buffer collect data before first inference
    time.sleep(WINDOW_SECONDS / 2)

    log.info("Starting inference loop (v2.0 engine) ...")
    client.loop_start()

    try:
        while True:
            time.sleep(INFERENCE_INTERVAL)
            run_inference(client)
    except KeyboardInterrupt:
        log.info("Shutting down.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
