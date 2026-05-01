"""
anomaly_bridge.py — Live ADS-B Anomaly Detection Service
=========================================================
Version: 1.0.0
Project: ADS-B Research Grid / SecuringSkies

Runs on the same server as Mosquitto and the dashboard.
Connects to the broker via localhost (no TLS needed for local traffic),
subscribes to all sensor aircraft feeds, runs a rolling Isolation Forest
+ Local Outlier Factor ensemble every INFERENCE_INTERVAL seconds, then
publishes the resulting anomaly scores to sensor-core/anomalies where the
dashboard picks them up automatically.

Usage
-----
    python scripts/anomaly_bridge.py

Environment variables (all optional, sensible defaults for local server):
    MQTT_HOST            Broker hostname          (default: localhost)
    MQTT_PORT            Broker port              (default: 1883)
    MQTT_USER            MQTT username            (default: team9)
    MQTT_PASS            MQTT password            (default: ResearchView2026!)
    INFERENCE_INTERVAL   Seconds between runs     (default: 30)
    WINDOW_SECONDS       Observation window size  (default: 300)
    MIN_SAMPLES          Min observations to run  (default: 20)
    CONTAMINATION        IsoForest contamination  (default: 0.02)
"""

import json
import logging
import ssl
import os
import time
from collections import defaultdict

import numpy as np
import paho.mqtt.client as mqtt
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler

# ---------------------------------------------------------------------------
# Configuration (overridable via environment variables)
# ---------------------------------------------------------------------------
MQTT_HOST          = os.getenv("MQTT_HOST",  "localhost")
MQTT_PORT          = int(os.getenv("MQTT_PORT", "1883"))
# Credentials are optional — local Mosquitto runs with allow_anonymous true.
# Set MQTT_USER and MQTT_PASS only if your broker requires authentication.
MQTT_USER          = os.getenv("MQTT_USER", "")
# Credentials: prefer direct MQTT_PASS env var, fall back to file
MQTT_PASS_FILE     = os.getenv("MQTT_PASS_FILE", "")
MQTT_PASS          = os.getenv("MQTT_PASS", "")
if not MQTT_PASS and MQTT_PASS_FILE and os.path.isfile(MQTT_PASS_FILE):
    try:
        with open(MQTT_PASS_FILE, "r", encoding="utf-8") as fh:
            MQTT_PASS = fh.read().strip()
    except (OSError, IOError) as exc:
        logging.getLogger(__name__).warning(
            "Could not read MQTT password from %s: %s", MQTT_PASS_FILE, exc
        )
if not MQTT_PASS and not MQTT_PASS_FILE:
    raise SystemExit(
        "ERROR: MQTT password required. Set MQTT_PASS_FILE (e.g. /etc/securing-skies/mqtt_secret) "
        "or MQTT_PASS environment variable."
    )


INFERENCE_INTERVAL = int(os.getenv("INFERENCE_INTERVAL", "30"))   # seconds
WINDOW_SECONDS     = int(os.getenv("WINDOW_SECONDS",     "300"))  # 5 minutes
MIN_SAMPLES        = int(os.getenv("MIN_SAMPLES",        "10"))
CONTAMINATION      = float(os.getenv("CONTAMINATION",   "0.02"))

# Features extracted from each aircraft observation
FEATURE_COLS = ["alt", "gs", "track", "rssi"]

TOPIC_SUBSCRIBE = "+/aircraft"
TOPIC_PUBLISH   = "sensor-core/anomalies"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [anomaly_bridge] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory observation buffer
#   buffer[icao_hex] = list of (timestamp, alt, gs, track, rssi)
# ---------------------------------------------------------------------------
buffer: dict[str, list] = defaultdict(list)


def _extract_features(ac: dict) -> tuple | None:
    """
    Return (alt, gs, track, rssi) for one aircraft entry, or None if
    any required field is missing/non-numeric.
    """
    try:
        alt   = float(ac.get("alt_baro") or ac.get("alt") or 0)
        gs    = float(ac.get("gs")       or 0)
        track = float(ac.get("track")    or 0)
        rssi  = float(ac.get("rssi")     or -50)   # neutral default
        return (alt, gs, track, rssi)
    except (TypeError, ValueError):
        return None


def on_message(client, userdata, message):
    """Ingest an aircraft payload and update the rolling buffer."""
    try:
        parts = message.topic.split("/")
        if len(parts) != 2 or parts[1] != "aircraft":
            return

        payload = json.loads(message.payload)
        ts = time.time()

        for ac in payload.get("aircraft", []):
            hex_id = ac.get("hex")
            if not hex_id or "lat" not in ac:
                continue
            feats = _extract_features(ac)
            if feats is None:
                continue
            buffer[hex_id].append((ts, *feats))

    except Exception as exc:
        log.warning("Parse error on %s: %s", message.topic, exc)


def _prune_buffer(cutoff: float) -> None:
    """Remove observations older than `cutoff` from every aircraft's list."""
    stale = [h for h, obs in buffer.items() if not obs or obs[-1][0] < cutoff]
    for h in stale:
        del buffer[h]

    for hex_id in list(buffer.keys()):
        buffer[hex_id] = [o for o in buffer[hex_id] if o[0] >= cutoff]
        if not buffer[hex_id]:
            del buffer[hex_id]


def run_inference(client: mqtt.Client) -> None:
    """
    Build a feature matrix from current buffer, run the ensemble, and
    publish {icao_hex: score} to sensor-core/anomalies.
    Score convention matches ds_pipeline_master.py and the dashboard:
        -1 → anomaly    1 → normal
    """
    cutoff = time.time() - WINDOW_SECONDS
    _prune_buffer(cutoff)

    if not buffer:
        log.debug("Buffer empty — skipping inference cycle.")
        return

    # Aggregate: one feature vector per aircraft (mean of recent observations)
    hex_ids = []
    X_raw   = []
    for hex_id, obs_list in buffer.items():
        if len(obs_list) < 2:           # need at least 2 points per aircraft
            continue
        arr = np.array([o[1:] for o in obs_list], dtype=float)  # drop timestamp
        hex_ids.append(hex_id)
        X_raw.append(arr.mean(axis=0))

    if len(hex_ids) < MIN_SAMPLES:
        log.info(
            "Only %d aircraft in buffer (need %d) — skipping inference.",
            len(hex_ids), MIN_SAMPLES,
        )
        return

    X = np.array(X_raw, dtype=float)

    # Replace any NaN / inf with column medians
    col_medians = np.nanmedian(X, axis=0)
    inds = np.where(~np.isfinite(X))
    X[inds] = np.take(col_medians, inds[1])

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # --- Model 1: Isolation Forest ---
    iso = IsolationForest(
        contamination=CONTAMINATION,
        random_state=42,
        n_jobs=-1,
    )
    scores_iso = iso.fit_predict(X_scaled)   # -1 / +1

    # --- Model 2: Local Outlier Factor (only when dataset is manageable) ---
    if len(hex_ids) <= 50_000:
        lof = LocalOutlierFactor(
            n_neighbors=min(20, len(hex_ids) - 1),
            contamination=CONTAMINATION,
            n_jobs=-1,
        )
        scores_lof = lof.fit_predict(X_scaled)   # -1 / +1
    else:
        log.info("LOF skipped — dataset too large (%d aircraft).", len(hex_ids))
        scores_lof = np.ones(len(hex_ids), dtype=int)

    # Ensemble: flag as anomaly only if BOTH models agree
    ensemble = {}
    anomaly_count = 0
    for i, hex_id in enumerate(hex_ids):
        vote = scores_iso[i] + scores_lof[i]   # -2 = both anomaly, 0 = split, +2 = both normal
        if vote <= -2:
            ensemble[hex_id] = -1
            anomaly_count += 1
        else:
            ensemble[hex_id] = 1

    log.info(
        "Inference complete — %d aircraft evaluated, %d anomalies flagged.",
        len(hex_ids), anomaly_count,
    )

    # Publish
    payload = json.dumps(ensemble)
    result = client.publish(TOPIC_PUBLISH, payload, qos=0, retain=False)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        log.warning("Publish failed (rc=%d)", result.rc)
    else:
        log.debug("Published %d scores to %s", len(ensemble), TOPIC_PUBLISH)


def main() -> None:
    client = mqtt.Client(client_id="anomaly-bridge", transport="websockets")
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)

    if MQTT_USER and MQTT_PASS:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    client.on_message = on_message

    log.info("Connecting to MQTT broker at %s:%d (WSS)...", MQTT_HOST, MQTT_PORT)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.subscribe(TOPIC_SUBSCRIBE)
    client.loop_start()
    log.info(
        "Subscribed to %s — inference every %ds, window %ds, min %d samples.",
        TOPIC_SUBSCRIBE, INFERENCE_INTERVAL, WINDOW_SECONDS, MIN_SAMPLES,
    )

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
