#!/usr/bin/env python3
"""
ml_continual_eval.py — Continual Evaluation Harness for ML Inference
=====================================================================
Version: 1.0.0
Date: 2026-05-24
Maintainer: Richard Wirén

Continuously monitors the GRU autoencoder's live performance by subscribing
to sensor-core/ml-anomaly scores and computing rolling health metrics.

Publishes to: sensor-core/ml-health (every EVAL_INTERVAL seconds)

Metrics tracked:
  - fp_rate: fraction of inferences flagged as anomaly (rolling window)
  - threshold_drift: current adaptive threshold vs base threshold ratio
  - score_p50/p95/p99: score distribution percentiles
  - feature_dominance: which feature contributes most error (detects bias)
  - aircraft_coverage: unique aircraft scored in window
  - inference_rate: inferences per second
  - status: "healthy" | "degraded" | "critical"

Alerts (published as status):
  - "degraded": FP rate > 1% OR threshold drift > 2× OR score_p95 > base/2
  - "critical": FP rate > 5% OR threshold drift > 3× OR no inferences for 60s

Usage:
    python3 ml_continual_eval.py

Environment:
    MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASS_FILE (same as other services)
    EVAL_INTERVAL  — seconds between health publishes (default: 60)
    EVAL_WINDOW    — seconds of history to evaluate (default: 300)
"""

import json
import ssl
import time
import os
import logging
from collections import deque
from datetime import datetime, timezone

import numpy as np
import paho.mqtt.client as mqtt

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MQTT_HOST = os.getenv("MQTT_HOST", "mqtt.securingskies.eu")
MQTT_PORT = int(os.getenv("MQTT_PORT", "8443"))
MQTT_USER = os.getenv("MQTT_USER", "team9")
MQTT_PASS_FILE = os.getenv("MQTT_PASS_FILE", "/etc/securing-skies/mqtt_secret")
MQTT_TRANSPORT = os.getenv("MQTT_TRANSPORT", "websockets")
MQTT_TLS = os.getenv("MQTT_TLS", "true").lower() in ("true", "1", "yes")

EVAL_INTERVAL = int(os.getenv("EVAL_INTERVAL", "60"))
EVAL_WINDOW = int(os.getenv("EVAL_WINDOW", "300"))

SUBSCRIBE_TOPIC = "sensor-core/ml-anomaly"
PUBLISH_TOPIC = "sensor-core/ml-health"

# Base threshold from production model (h256/l4)
BASE_THRESHOLD = 0.136

# Alert thresholds
FP_RATE_DEGRADED = 0.01
FP_RATE_CRITICAL = 0.05
THRESHOLD_DRIFT_DEGRADED = 2.0
THRESHOLD_DRIFT_CRITICAL = 3.0
SILENCE_CRITICAL_SEC = 60

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ml_eval] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

# Each entry: (timestamp, score, threshold, is_anomaly, top_feature, hex_id)
observations = deque(maxlen=10000)
last_message_ts = 0.0


# ---------------------------------------------------------------------------
# MQTT Callbacks
# ---------------------------------------------------------------------------

def on_connect(client, userdata, flags, rc):
    log.info("Connected to MQTT (rc=%d)", rc)
    client.subscribe(SUBSCRIBE_TOPIC)


def on_message(client, userdata, message):
    global last_message_ts
    try:
        data = json.loads(message.payload.decode())
        now = time.time()
        last_message_ts = now

        score = data.get("anomaly_score", 0)
        threshold = data.get("threshold", BASE_THRESHOLD)
        is_anomaly = data.get("is_anomaly", False)
        hex_id = data.get("hex", "")

        # Find dominant feature
        pfe = data.get("per_feature_error", {})
        top_feature = ""
        if pfe:
            top_feature = max(pfe, key=lambda k: pfe[k].get("mse", 0))

        observations.append((now, score, threshold, is_anomaly, top_feature, hex_id))
    except Exception as e:
        log.warning("Parse error: %s", e)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate():
    """Compute health metrics from recent observations."""
    now = time.time()
    cutoff = now - EVAL_WINDOW

    # Filter to evaluation window
    window = [(ts, sc, th, anom, feat, hx)
              for ts, sc, th, anom, feat, hx in observations if ts >= cutoff]

    if not window:
        silence = now - last_message_ts if last_message_ts > 0 else 0
        return {
            "status": "critical" if silence > SILENCE_CRITICAL_SEC else "unknown",
            "reason": f"no_inferences_for_{silence:.0f}s",
            "aircraft_coverage": 0,
            "inference_count": 0,
        }

    scores = np.array([w[1] for w in window])
    thresholds = [w[2] for w in window]
    anomalies = [w[3] for w in window]
    features = [w[4] for w in window]
    hexes = set(w[5] for w in window)

    n = len(window)
    anomaly_count = sum(anomalies)
    fp_rate = anomaly_count / n

    # Threshold drift
    current_threshold = thresholds[-1]
    threshold_drift = current_threshold / BASE_THRESHOLD

    # Score distribution
    score_p50 = float(np.percentile(scores, 50))
    score_p95 = float(np.percentile(scores, 95))
    score_p99 = float(np.percentile(scores, 99))
    score_max = float(scores.max())

    # Feature dominance (which feature is top contributor most often)
    feature_counts = {}
    for f in features:
        if f:
            feature_counts[f] = feature_counts.get(f, 0) + 1
    dominant_feature = max(feature_counts, key=feature_counts.get) if feature_counts else ""
    dominance_pct = feature_counts.get(dominant_feature, 0) / n if n > 0 else 0

    # Inference rate
    time_span = window[-1][0] - window[0][0]
    inference_rate = n / time_span if time_span > 0 else 0

    # Determine status
    reasons = []
    status = "healthy"

    if fp_rate > FP_RATE_CRITICAL:
        status = "critical"
        reasons.append(f"fp_rate={fp_rate:.3f}")
    elif fp_rate > FP_RATE_DEGRADED:
        status = "degraded"
        reasons.append(f"fp_rate={fp_rate:.3f}")

    if threshold_drift > THRESHOLD_DRIFT_CRITICAL:
        status = "critical"
        reasons.append(f"threshold_drift={threshold_drift:.2f}x")
    elif threshold_drift > THRESHOLD_DRIFT_DEGRADED:
        if status != "critical":
            status = "degraded"
        reasons.append(f"threshold_drift={threshold_drift:.2f}x")

    if score_p95 > BASE_THRESHOLD / 2:
        if status == "healthy":
            status = "degraded"
        reasons.append(f"score_p95={score_p95:.4f}")

    return {
        "status": status,
        "reason": ",".join(reasons) if reasons else "all_nominal",
        "eval_window_sec": EVAL_WINDOW,
        "inference_count": n,
        "inference_rate_hz": round(inference_rate, 2),
        "aircraft_coverage": len(hexes),
        "fp_rate": round(fp_rate, 4),
        "anomaly_count": anomaly_count,
        "threshold_current": round(current_threshold, 6),
        "threshold_base": BASE_THRESHOLD,
        "threshold_drift_ratio": round(threshold_drift, 3),
        "score_p50": round(score_p50, 6),
        "score_p95": round(score_p95, 6),
        "score_p99": round(score_p99, 6),
        "score_max": round(score_max, 6),
        "dominant_feature": dominant_feature,
        "dominant_feature_pct": round(dominance_pct * 100, 1),
        "ts": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Load MQTT password
    mqtt_pass = ""
    if os.path.isfile(MQTT_PASS_FILE):
        with open(MQTT_PASS_FILE) as f:
            mqtt_pass = f.read().strip()
    if not mqtt_pass:
        mqtt_pass = os.getenv("MQTT_PASS", "")

    client = mqtt.Client(client_id="ml-continual-eval", transport=MQTT_TRANSPORT)
    client.username_pw_set(MQTT_USER, mqtt_pass)
    if MQTT_TLS:
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(1, 120)

    log.info("Connecting to %s:%d", MQTT_HOST, MQTT_PORT)
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()

    log.info("Continual eval harness started (window=%ds, interval=%ds)", EVAL_WINDOW, EVAL_INTERVAL)
    log.info("Warming up for %ds before first evaluation...", EVAL_INTERVAL)

    time.sleep(EVAL_INTERVAL)

    try:
        while True:
            metrics = evaluate()
            payload = json.dumps(metrics)
            client.publish(PUBLISH_TOPIC, payload, qos=0, retain=True)

            status = metrics["status"]
            if status == "healthy":
                log.info("✅ %s | ac=%d rate=%.1f/s fp=%.2f%% τ_drift=%.2fx p95=%.6f dom=%s(%.0f%%)",
                         status, metrics["aircraft_coverage"], metrics["inference_rate_hz"],
                         metrics["fp_rate"] * 100, metrics["threshold_drift_ratio"],
                         metrics["score_p95"], metrics["dominant_feature"], metrics["dominant_feature_pct"])
            elif status == "degraded":
                log.warning("⚠️  %s | %s | ac=%d fp=%.2f%% τ_drift=%.2fx",
                            status, metrics["reason"], metrics["aircraft_coverage"],
                            metrics["fp_rate"] * 100, metrics["threshold_drift_ratio"])
            else:
                log.error("🚨 %s | %s", status, metrics["reason"])

            time.sleep(EVAL_INTERVAL)
    except KeyboardInterrupt:
        log.info("Shutting down.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
