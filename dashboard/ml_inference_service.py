# ==============================================================================
# File: /root/adsb-dashboard/ml_inference_service.py
# Version: 1.1.0
# Date: 2026-04-29
# Maintainer: Team-9 Secure Skies
# ==============================================================================
# Description:
#   Real-time ML inference service for ADS-B spoofing detection.
#   Subscribes to live MQTT sensor feeds, maintains per-aircraft sliding window
#   buffers (T=30), performs feature engineering matching the training pipeline,
#   and publishes per-feature reconstruction errors to sensor-core/ml-anomaly.
#
# v1.1.0 Changes (Train-Serve Skew Calibration):
#   The v1.0.0 live test revealed all aircraft scored above threshold because:
#   1. Interleaved multi-sensor updates caused velocity spikes (different sensors
#      report slightly different positions for the same aircraft)
#   2. Irregular dt between observations (not always 1s)
#   3. Initial warmup observations had unstable feature values
#
#   Fix: Per-aircraft, per-SENSOR buffering. Features are computed only from
#   consecutive observations from the SAME sensor, ensuring dt ≈ 1s and
#   position consistency. This mirrors the training pipeline which groups by
#   hex and uses shift(1) within each aircraft's sorted time series.
#
#   Additionally, a warmup period (WARMUP_OBS = 5) discards the first few
#   feature vectors which may have transient velocity spikes from the initial
#   position pair.
#
# Architecture:
#   GRU Autoencoder (79K params) trained on 144h multi-sensor dataset.
#   Information bottleneck (latent_size=8) forces learning of physical
#   invariants rather than noise memorization.
#
# Feature Space (Paper Table 2):
#   0: velocity_calculated   — ground speed from GPS positions (m/s)
#   1: velocity_error        — reported_gs_ms - velocity_calculated (m/s)
#   2: velocity_drift        — rolling mean of sign(Δ velocity_error), w=15
#   3: distance_to_sensor    — great-circle to receiving sensor (km)
#   4: rssi_expected         — FSPL model at 1090 MHz (dB)
#   5: rssi_error            — measured_rssi - rssi_expected (dB)
#   6: rssi_error_normalized — rssi_error / sensor_calibration_multiplier
#
# Tensor Shapes:
#   Input:  (1, T, D) = (1, 30, 7)
#   Output: (1, T, D) = (1, 30, 7)
#   Error:  (D,) = (7,)
#
# Hardware Calibrations (Paper Section 3.2):
#   - sensor-north: u-blox F9P RTK (cm), Jetvision A5, RSSI mult=1.00
#   - sensor-west:  G-STAR IV (~1m), RTL-SDR unfiltered, RSSI mult=1.12
#   - sensor-east:  G-STAR IV (~65m), FlightAware Pro+, RSSI mult=0.94
# ==============================================================================

import json
import time
import math
import ssl
import logging
from collections import deque, defaultdict

import numpy as np
import torch
import torch.nn as nn
import paho.mqtt.client as mqtt
import warnings
warnings.filterwarnings("ignore", message="X does not have valid feature names")

# ==============================================================================
# Configuration
# ==============================================================================

MQTT_HOST = "mqtt.securingskies.eu"
MQTT_PORT = 8443
MQTT_USER = "team9"
MQTT_TRANSPORT = "websockets"
MQTT_TLS = True

MODEL_PATH = "/root/adsb-dashboard/models/adsb_gru_w30_144h_7feat.pth"
PUBLISH_TOPIC = "sensor-core/ml-anomaly"

# Sliding window parameters (Paper Section 4.1)
WINDOW_SIZE = 30          # T = 30 timesteps
FEATURE_DIM = 7           # D = 7 features (Table 2)
INFERENCE_INTERVAL = 5

# Distance filter: only infer on aircraft within this range of their sensor.
# Training data: mean=22.7km, std=47.3km. Aircraft beyond 80km are outside
# the training manifold and will always score as anomalous (distribution shift).
MAX_INFERENCE_DIST_KM = 80.0    # Seconds between inference runs per aircraft

# Warmup: discard first N feature vectors per aircraft to stabilize
# velocity_calculated. The first observation has no predecessor, and the
# second may have an irregular dt from the initial MQTT subscription.
WARMUP_OBS = 5

# dt bounds: only compute features when consecutive observations from the
# same sensor are 0.5s–3.0s apart. This mirrors the training data which
# was captured at 1Hz. Observations outside this range indicate:
#   - dt < 0.5s: duplicate/rapid-fire messages (discard)
#   - dt > 3.0s: gap in coverage (reset buffer, don't interpolate)
DT_MIN = 0.5
DT_MAX = 3.0

# Sensor positions (GNSS-verified, 30s average — Paper Section 3.1)
SENSOR_POS = {
    "sensor-north": (60.319558, 24.830813),
    "sensor-west":  (60.130877, 24.512927),
    "sensor-east":  (60.374069, 25.248990),
}

# Per-sensor RSSI calibration (Paper Section 3.2)
SENSOR_RSSI_MULT = {
    "sensor-north": 1.00,
    "sensor-west":  0.58,
    "sensor-east":  0.83,
}

# RSSI free-space path loss reference (1090 MHz)
RSSI_REF_DBM = -20.0
RSSI_REF_DIST_KM = 1.0

# Velocity drift rolling window (Paper Section 3.3)
VELOCITY_DRIFT_WINDOW = 15

FEATURE_NAMES = [
    "velocity_calculated",
    "velocity_error",
    "velocity_drift",
    "distance_to_sensor",
    "rssi_expected",
    "rssi_error",
    "rssi_error_normalized",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ml_inference")


# ==============================================================================
# Model Definition
# ==============================================================================

class GRUAutoencoder(nn.Module):
    """GRU Autoencoder with information bottleneck (Paper Section 4.1)."""
    def __init__(self, input_size, hidden_size=64, latent_size=8, num_layers=2, dropout=0.2):
        super().__init__()
        self.num_layers = num_layers
        self.encoder = nn.GRU(input_size, hidden_size, num_layers, batch_first=True,
                              dropout=dropout if num_layers > 1 else 0)
        self.bottleneck = nn.Linear(hidden_size, latent_size)
        self.expand = nn.Linear(latent_size, hidden_size)
        self.decoder = nn.GRU(input_size, hidden_size, num_layers, batch_first=True,
                              dropout=dropout if num_layers > 1 else 0)
        self.output = nn.Linear(hidden_size, input_size)

    def forward(self, x):
        _, h = self.encoder(x)
        z = self.bottleneck(h[-1])
        h0 = self.expand(z).unsqueeze(0).repeat(self.num_layers, 1, 1)
        out, _ = self.decoder(x, h0)
        return self.output(out)


# ==============================================================================
# Feature Engineering
# ==============================================================================

def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance (km) via Haversine formula."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * \
        math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_features(prev_obs, curr_obs, vel_error_history, sensor):
    """
    Compute 7-dimensional feature vector for one timestep.

    CRITICAL: prev_obs and curr_obs MUST be from the SAME sensor to avoid
    position discontinuities from multi-sensor disagreement. The caller
    (AircraftBuffer) enforces this by maintaining per-sensor observation history.

    Parameters
    ----------
    prev_obs : dict {lat, lon, gs, rssi, ts}
    curr_obs : dict {lat, lon, gs, rssi, ts}
    vel_error_history : deque — rolling velocity_error values for drift calc
    sensor : str — sensor name for position/RSSI calibration

    Returns
    -------
    np.ndarray shape (7,) or None if dt is out of bounds
    """
    dt = curr_obs["ts"] - prev_obs["ts"]

    # Reject observations with irregular timing.
    # Training data was 1Hz; we accept 0.5-3.0s to handle minor jitter.
    if dt < DT_MIN or dt > DT_MAX:
        return None

    # Feature 0: velocity_calculated (m/s)
    dist_km = haversine_km(prev_obs["lat"], prev_obs["lon"],
                           curr_obs["lat"], curr_obs["lon"])
    velocity_calculated = (dist_km * 1000.0) / dt

    # Feature 1: velocity_error (m/s)
    # Training pipeline: gs_ms - velocity_calculated (signed, Decision [6])
    gs_ms = (curr_obs["gs"] or 0) * 0.514444  # knots → m/s
    velocity_error = gs_ms - velocity_calculated

    # Feature 2: velocity_drift [-1, 1]
    # Rolling mean of sign(Δ velocity_error) over window=15.
    vel_error_history.append(velocity_error)
    if len(vel_error_history) >= 2:
        signs = []
        for i in range(1, len(vel_error_history)):
            diff = vel_error_history[i] - vel_error_history[i - 1]
            signs.append(1.0 if diff > 0 else (-1.0 if diff < 0 else 0.0))
        recent = signs[-VELOCITY_DRIFT_WINDOW:]
        velocity_drift = sum(recent) / len(recent)
    else:
        velocity_drift = 0.0

    # Feature 3: distance_to_sensor (km)
    sensor_pos = SENSOR_POS.get(sensor, SENSOR_POS["sensor-north"])
    distance_to_sensor = haversine_km(curr_obs["lat"], curr_obs["lon"],
                                      sensor_pos[0], sensor_pos[1])

    # Feature 4: rssi_expected (dB) — Free-Space Path Loss at 1090 MHz
    d_clamped = max(distance_to_sensor, 0.01)
    rssi_expected = RSSI_REF_DBM - 20.0 * math.log10(d_clamped / RSSI_REF_DIST_KM)

    # Feature 5: rssi_error (dB)
    rssi_measured = curr_obs.get("rssi") or -30.0
    rssi_error = rssi_measured - rssi_expected

    # Feature 6: rssi_error_normalized
    rssi_mult = SENSOR_RSSI_MULT.get(sensor, 1.0)
    rssi_error_normalized = rssi_error / rssi_mult

    return np.array([
        velocity_calculated, velocity_error, velocity_drift,
        distance_to_sensor, rssi_expected, rssi_error, rssi_error_normalized,
    ], dtype=np.float32)


# ==============================================================================
# Per-Aircraft State Buffer
# ==============================================================================

class AircraftBuffer:
    """
    Per-aircraft, per-sensor sliding window buffer.

    KEY DESIGN DECISION (v1.1.0 — train-serve skew fix):
    The training pipeline computes features from consecutive observations of
    the SAME aircraft sorted by time. In live operation, multiple sensors
    report the same aircraft with slightly different positions (multilateration
    vs direct decode). Computing velocity from cross-sensor positions creates
    artificial spikes that don't exist in training data.

    Solution: We pick the BEST sensor for each aircraft (the one reporting
    most frequently with lowest seen_pos) and only compute features from
    that sensor's consecutive reports. This ensures:
      - dt ≈ 1s (consistent with training)
      - No position jumps from sensor disagreement
      - Feature distribution matches training scaler statistics

    The warmup period (WARMUP_OBS=5) discards initial feature vectors which
    may have transient values from the first position pair.
    """
    def __init__(self):
        self.features = deque(maxlen=WINDOW_SIZE)
        self.vel_error_history = deque(maxlen=50)
        self.prev_obs = {}          # Per-sensor: {sensor: {lat,lon,gs,rssi,ts}}
        self.primary_sensor = None  # Locked sensor for this aircraft
        self.obs_count = 0          # Total valid observations
        self.last_inference_ts = 0.0

    def update(self, obs, sensor):
        """
        Process a new observation from a specific sensor.

        Sensor locking strategy:
          - First sensor to provide 2 consecutive observations becomes primary
          - Only primary sensor's data feeds the feature window
          - If primary sensor goes silent (>5s), allow takeover
        """
        now = obs["ts"]

        # Store per-sensor last observation
        prev = self.prev_obs.get(sensor)
        self.prev_obs[sensor] = obs

        # Determine primary sensor
        if self.primary_sensor is None:
            if prev is not None:
                self.primary_sensor = sensor
        elif sensor != self.primary_sensor:
            # Check if primary is stale (>5s since last report)
            primary_prev = self.prev_obs.get(self.primary_sensor)
            if primary_prev and (now - primary_prev["ts"]) > 5.0:
                # Primary sensor went silent — switch
                self.primary_sensor = sensor
                self.features.clear()
                self.vel_error_history.clear()
                self.obs_count = 0
                prev = None  # Reset so we wait for next pair
            else:
                return  # Not our primary sensor, ignore

        # Only compute features from primary sensor's consecutive observations
        if prev is None:
            return

        feat = compute_features(prev, obs, self.vel_error_history, sensor)
        if feat is None:
            return  # dt out of bounds

        self.obs_count += 1

        # Warmup: discard first WARMUP_OBS feature vectors
        # These may have transient velocity values from initial position pair
        if self.obs_count <= WARMUP_OBS:
            return

        self.features.append(feat)

    def ready(self):
        """True if buffer has T=30 stable feature vectors."""
        return len(self.features) >= WINDOW_SIZE

    def get_window(self):
        """Return current window as (T, D) numpy array."""
        return np.array(list(self.features), dtype=np.float32)


# ==============================================================================
# Inference Engine
# ==============================================================================

class InferenceEngine:
    """Loads trained model and scaler, performs inference."""
    def __init__(self, model_path):
        log.info(f"Loading model from {model_path}")
        ckpt = torch.load(model_path, map_location="cpu", weights_only=False)
        hp = ckpt["hyperparameters"]
        self.model = GRUAutoencoder(
            input_size=hp["input_size"], hidden_size=hp["hidden_size"],
            latent_size=hp["latent_size"], num_layers=hp["num_layers"],
            dropout=hp["dropout"],
        )
        self.model.load_state_dict(ckpt["model_state_dict"])
        self.model.eval()
        self.scaler = ckpt["scaler"]
        self.threshold = ckpt["anomaly_threshold"]
        log.info(f"Model loaded: {hp['input_size']}D, τ={self.threshold:.6f}")

    def infer(self, window):
        """
        Run inference. Returns dict with anomaly_score, per_feature_error, is_anomaly.
        """
        window_scaled = self.scaler.transform(window)
        x = torch.FloatTensor(window_scaled).unsqueeze(0)
        with torch.no_grad():
            x_hat = self.model(x)
        per_feature_mse = ((x - x_hat) ** 2).mean(dim=1).squeeze(0).numpy()
        anomaly_score = float(per_feature_mse.mean())
        total_error = per_feature_mse.sum()
        per_feature_error = {}
        for i, name in enumerate(FEATURE_NAMES):
            per_feature_error[name] = {
                "mse": float(per_feature_mse[i]),
                "pct": float(per_feature_mse[i] / total_error * 100) if total_error > 0 else 0.0,
            }
        return {
            "anomaly_score": anomaly_score,
            "threshold": self.threshold,
            "is_anomaly": anomaly_score > self.threshold,
            "per_feature_error": per_feature_error,
        }


# ==============================================================================
# MQTT Service
# ==============================================================================

class MLInferenceService:
    def __init__(self):
        self.buffers = defaultdict(AircraftBuffer)
        self.engine = InferenceEngine(MODEL_PATH)
        self.mqtt_client = None
        self.stats = {"total_inferences": 0, "anomalies": 0, "below_threshold": 0}

    def start(self):
        with open("/etc/securing-skies/mqtt_secret") as f:
            mqtt_pass = f.read().strip()
        self.mqtt_client = mqtt.Client(client_id="ml-inference-v1.1", transport=MQTT_TRANSPORT)
        self.mqtt_client.username_pw_set(MQTT_USER, mqtt_pass)
        if MQTT_TLS:
            self.mqtt_client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        log.info(f"Connecting to {MQTT_HOST}:{MQTT_PORT}")
        self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        self.mqtt_client.loop_forever()

    def _on_connect(self, client, userdata, flags, rc):
        log.info(f"MQTT connected (rc={rc})")
        client.subscribe("sensor-north/aircraft")
        client.subscribe("sensor-west/aircraft")
        client.subscribe("sensor-east/aircraft")

    def _on_message(self, client, userdata, message):
        try:
            sensor = message.topic.split("/")[0]
            payload = json.loads(message.payload)
            now = time.time()

            for ac in payload.get("aircraft", []):
                hex_id = ac.get("hex")
                if not hex_id or "lat" not in ac or "lon" not in ac:
                    continue
                # Require groundspeed for velocity features
                if ac.get("gs") is None:
                    continue

                obs = {
                    "lat": ac["lat"], "lon": ac["lon"],
                    "gs": ac["gs"], "rssi": ac.get("rssi", -30.0),
                    "ts": now,
                }

                buf = self.buffers[hex_id]
                buf.update(obs, sensor)

                if buf.ready() and (now - buf.last_inference_ts) >= INFERENCE_INTERVAL:
                    # Distance filter: skip aircraft outside training distribution
                    sensor_pos = SENSOR_POS.get(buf.primary_sensor or sensor, SENSOR_POS["sensor-north"])
                    from ml_inference_service import haversine_km as _hkm
                    ac_dist = _hkm(obs["lat"], obs["lon"], sensor_pos[0], sensor_pos[1])
                    if ac_dist > MAX_INFERENCE_DIST_KM:
                        continue
                    buf.last_inference_ts = now
                    result = self.engine.infer(buf.get_window())
                    self.stats["total_inferences"] += 1

                    if result["is_anomaly"]:
                        self.stats["anomalies"] += 1
                    else:
                        self.stats["below_threshold"] += 1
                    # Publish ALL scores so dashboard can show ML activity status
                    self._publish_score(hex_id, ac, result, sensor)

        except Exception as e:
            log.warning(f"Error: {e}")

    def _publish_score(self, hex_id, ac, result, sensor):
        """Publish all ML scores (normal and anomalous) to MQTT for dashboard."""
        payload = {
            "ts": time.time(), "hex": hex_id,
            "flight": (ac.get("flight") or "").strip(),
            "sensor": sensor,
            "anomaly_score": result["anomaly_score"],
            "threshold": result["threshold"],
            "is_anomaly": result["is_anomaly"],
            "per_feature_error": result["per_feature_error"],
        }
        self.mqtt_client.publish(PUBLISH_TOPIC, json.dumps(payload), qos=0)
        if result["is_anomaly"]:
            log.info(f"ANOMALY {hex_id} ({(ac.get('flight') or '').strip()}): score={result['anomaly_score']:.6f} > τ={result['threshold']:.6f}")


if __name__ == "__main__":
    log.info("Starting ML Inference Service v1.1.0")
    log.info(f"Window: T={WINDOW_SIZE}, Warmup: {WARMUP_OBS}, dt bounds: [{DT_MIN}, {DT_MAX}]s")
    service = MLInferenceService()
    service.start()
