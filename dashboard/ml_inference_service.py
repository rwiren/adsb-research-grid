# ==============================================================================
# File: /root/adsb-dashboard/ml_inference_service.py
# Version: 1.0.0
# Date: 2026-04-29
# Maintainer: Team-9 Secure Skies
# ==============================================================================
# Description:
#   Real-time ML inference service for ADS-B spoofing detection.
#   Subscribes to live MQTT sensor feeds, maintains per-aircraft sliding window
#   buffers (T=30), performs feature engineering matching the training pipeline,
#   and publishes per-feature reconstruction errors to sensor-core/ml-anomaly.
#
# Architecture:
#   Uses the GRU Autoencoder (79K params) trained on the 144h multi-sensor
#   dataset with GNSS-corrected positions. The model learns to reconstruct
#   authentic flight patterns via an information bottleneck (latent_size=8).
#   Spoofed signals that violate learned physics produce high reconstruction
#   error, decomposable per feature dimension (Paper Eq. 2).
#
# Feature Space (Paper Table 2):
#   0: velocity_calculated   — ground speed derived from GPS positions (m/s)
#   1: velocity_error        — deviation: reported_gs - calculated_gs (m/s)
#   2: velocity_drift        — rolling mean of sign(Δ velocity_error), window=15
#   3: distance_to_sensor    — great-circle distance to receiving sensor (km)
#   4: rssi_expected         — expected RSSI from free-space path loss model (dB)
#   5: rssi_error            — deviation: measured_rssi - expected_rssi (dB)
#   6: rssi_error_normalized — rssi_error / sensor_rssi_multiplier
#
# Sliding Window (T=30):
#   Each aircraft accumulates a deque of T=30 feature vectors at ~1Hz.
#   Inference runs when the buffer is full (30 consecutive observations).
#   The window slides by 1 on each new observation (stride=1).
#
# Tensor Shapes:
#   Input:  (1, T, D) = (1, 30, 7)  — single sequence, 30 timesteps, 7 features
#   Output: (1, T, D) = (1, 30, 7)  — reconstructed sequence
#   Error:  (D,) = (7,)             — per-feature MSE across T timesteps
#
# MQTT Output Topic: sensor-core/ml-anomaly
#   Publishes JSON with per-aircraft scores when anomaly_score > threshold.
#
# Hardware Calibrations (Paper Section 3.2):
#   - sensor-north: u-blox F9P RTK (cm precision), Jetvision A5, RSSI mult=1.00
#   - sensor-west:  G-STAR IV (~1m), RTL-SDR unfiltered, RSSI mult=1.12
#   - sensor-east:  G-STAR IV (~65m jitter), FlightAware Pro+, RSSI mult=0.94
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
MIN_WINDOW_FILL = 30      # Only infer when buffer is full
INFERENCE_INTERVAL = 5    # Seconds between inference runs per aircraft

# Sensor positions (GNSS-verified, 30s average — Paper Section 3.1)
SENSOR_POS = {
    "sensor-north": (60.319558, 24.830813),
    "sensor-west":  (60.130877, 24.512927),
    "sensor-east":  (60.374069, 25.248990),
}

# Per-sensor RSSI calibration (Paper Section 3.2)
# Accounts for heterogeneous SDR hardware and antenna characteristics.
SENSOR_RSSI_MULT = {
    "sensor-north": 1.00,   # Jetvision A5 (filtered, calibrated baseline)
    "sensor-west":  1.12,   # RTL-SDR (unfiltered, elevated noise floor)
    "sensor-east":  0.94,   # FlightAware Pro Stick Plus (filtered, slight attenuation)
}

# RSSI free-space path loss reference (1090 MHz)
RSSI_REF_DBM = -40.0       # Reference power at ref_dist
RSSI_REF_DIST_KM = 1.0     # Reference distance (1 km)

# Velocity drift rolling window (Paper Section 3.3)
VELOCITY_DRIFT_WINDOW = 15

# Feature names (must match training order)
FEATURE_NAMES = [
    "velocity_calculated",
    "velocity_error",
    "velocity_drift",
    "distance_to_sensor",
    "rssi_expected",
    "rssi_error",
    "rssi_error_normalized",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("ml_inference")


# ==============================================================================
# Model Definition (must match training architecture exactly)
# ==============================================================================

class GRUAutoencoder(nn.Module):
    """
    GRU Autoencoder with information bottleneck (Paper Section 4.1).

    Architecture:
        Encoder GRU (input_size → hidden_size, num_layers) → last hidden state
        Bottleneck Linear (hidden_size → latent_size) — information compression
        Expand Linear (latent_size → hidden_size) — reconstruction seed
        Decoder GRU (input_size → hidden_size, num_layers) — temporal reconstruction
        Output Linear (hidden_size → input_size) — feature space projection

    The bottleneck forces the model to learn physical invariants (momentum
    conservation, RF propagation laws) rather than memorizing noise.
    """
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
        # x shape: (batch, T, D) = (1, 30, 7)
        _, h = self.encoder(x)          # h: (num_layers, batch, hidden)
        z = self.bottleneck(h[-1])      # z: (batch, latent) — compressed representation
        h0 = self.expand(z).unsqueeze(0).repeat(self.num_layers, 1, 1)
        out, _ = self.decoder(x, h0)    # out: (batch, T, hidden)
        return self.output(out)         # (batch, T, D) — reconstructed features


# ==============================================================================
# Feature Engineering (mirrors src/pipeline/feature_engineering.py)
# ==============================================================================

def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance using Haversine formula. Returns km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * \
        math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_features(prev_obs, curr_obs, vel_error_history, sensor):
    """
    Compute the 7-dimensional feature vector for a single timestep.

    Parameters
    ----------
    prev_obs : dict
        Previous observation {lat, lon, gs, rssi, ts}
    curr_obs : dict
        Current observation {lat, lon, gs, rssi, ts}
    vel_error_history : deque
        Rolling history of velocity_error sign changes for drift calculation
    sensor : str
        Sensor name (for position and RSSI calibration)

    Returns
    -------
    np.ndarray of shape (7,) or None if insufficient data
    """
    dt = curr_obs["ts"] - prev_obs["ts"]
    if dt <= 0:
        return None

    # Feature 0: velocity_calculated (m/s)
    # Ground speed derived from consecutive GPS positions
    dist_km = haversine_km(prev_obs["lat"], prev_obs["lon"],
                           curr_obs["lat"], curr_obs["lon"])
    velocity_calculated = (dist_km * 1000.0) / dt  # m/s

    # Feature 1: velocity_error (m/s)
    # Deviation between reported groundspeed and position-derived speed.
    # Authentic aircraft: ~0. Spoofed: large deviation.
    gs_ms = (curr_obs["gs"] or 0) * 0.514444  # knots → m/s
    velocity_error = gs_ms - velocity_calculated

    # Feature 2: velocity_drift (dimensionless, range [-1, 1])
    # Rolling mean of sign(Δ velocity_error) over window=15.
    # Detects sustained monotonic drift attacks. Normal ≈ 0.
    vel_error_history.append(velocity_error)
    if len(vel_error_history) >= 2:
        signs = [1 if vel_error_history[i] - vel_error_history[i - 1] > 0
                 else (-1 if vel_error_history[i] - vel_error_history[i - 1] < 0 else 0)
                 for i in range(1, len(vel_error_history))]
        recent = signs[-VELOCITY_DRIFT_WINDOW:]
        velocity_drift = sum(recent) / len(recent) if recent else 0.0
    else:
        velocity_drift = 0.0

    # Feature 3: distance_to_sensor (km)
    # Great-circle distance from aircraft to receiving sensor.
    sensor_pos = SENSOR_POS.get(sensor, SENSOR_POS["sensor-north"])
    distance_to_sensor = haversine_km(curr_obs["lat"], curr_obs["lon"],
                                      sensor_pos[0], sensor_pos[1])

    # Feature 4: rssi_expected (dB)
    # Free-Space Path Loss model at 1090 MHz:
    #   RSSI_expected = RSSI_ref - 20·log10(d / d_ref)
    # Assumes isotropic radiation in free space.
    d_clamped = max(distance_to_sensor, 0.01)
    rssi_expected = RSSI_REF_DBM - 20.0 * math.log10(d_clamped / RSSI_REF_DIST_KM)

    # Feature 5: rssi_error (dB)
    # Deviation from expected RSSI. Positive = stronger than expected.
    rssi_measured = curr_obs.get("rssi") or -30.0
    rssi_error = rssi_measured - rssi_expected

    # Feature 6: rssi_error_normalized (dB)
    # Normalized by per-sensor calibration multiplier to account for
    # heterogeneous SDR hardware (Paper Section 3.2).
    rssi_mult = SENSOR_RSSI_MULT.get(sensor, 1.0)
    rssi_error_normalized = rssi_error / rssi_mult

    return np.array([
        velocity_calculated,
        velocity_error,
        velocity_drift,
        distance_to_sensor,
        rssi_expected,
        rssi_error,
        rssi_error_normalized,
    ], dtype=np.float32)


# ==============================================================================
# Per-Aircraft State Buffer
# ==============================================================================

class AircraftBuffer:
    """
    Maintains a T=30 sliding window of feature vectors for one aircraft.

    The buffer accumulates observations at ~1Hz. Once full (30 timesteps),
    inference can be performed. The window slides by 1 on each new observation.
    """
    def __init__(self):
        self.features = deque(maxlen=WINDOW_SIZE)  # (T,) deque of (D,) arrays
        self.vel_error_history = deque(maxlen=50)  # For velocity_drift calc
        self.prev_obs = None
        self.sensor = None
        self.last_inference_ts = 0.0

    def update(self, obs, sensor):
        """
        Add a new observation and compute features.

        Parameters
        ----------
        obs : dict with keys {lat, lon, gs, rssi, ts}
        sensor : str
        """
        self.sensor = sensor
        if self.prev_obs is not None:
            feat = compute_features(self.prev_obs, obs, self.vel_error_history, sensor)
            if feat is not None:
                self.features.append(feat)
        self.prev_obs = obs

    def ready(self):
        """True if buffer has T=30 feature vectors for inference."""
        return len(self.features) >= MIN_WINDOW_FILL

    def get_window(self):
        """
        Return the current window as a numpy array.

        Returns
        -------
        np.ndarray of shape (T, D) = (30, 7)
        """
        return np.array(list(self.features), dtype=np.float32)


# ==============================================================================
# Inference Engine
# ==============================================================================

class InferenceEngine:
    """
    Loads the trained GRU Autoencoder and StandardScaler, performs inference
    on sliding windows, and computes per-feature reconstruction errors.
    """
    def __init__(self, model_path):
        log.info(f"Loading model from {model_path}")
        ckpt = torch.load(model_path, map_location="cpu", weights_only=False)

        # Reconstruct model from hyperparameters
        hp = ckpt["hyperparameters"]
        self.model = GRUAutoencoder(
            input_size=hp["input_size"],
            hidden_size=hp["hidden_size"],
            latent_size=hp["latent_size"],
            num_layers=hp["num_layers"],
            dropout=hp["dropout"],
        )
        self.model.load_state_dict(ckpt["model_state_dict"])
        self.model.eval()

        # StandardScaler parameters (fitted on training data)
        self.scaler = ckpt["scaler"]  # sklearn StandardScaler object
        self.threshold = ckpt["anomaly_threshold"]

        log.info(f"Model loaded: {hp['input_size']}D, threshold τ={self.threshold:.6f}")
        log.info(f"Scaler mean: {self.scaler.mean_}")
        log.info(f"Scaler scale: {self.scaler.scale_}")

    def infer(self, window):
        """
        Run inference on a single window.

        Parameters
        ----------
        window : np.ndarray of shape (T, D) = (30, 7)

        Returns
        -------
        dict with keys:
            - anomaly_score: float (overall MSE)
            - per_feature_error: dict {feature_name: float}
            - is_anomaly: bool (score > threshold)
        """
        # Z-score normalize using training scaler
        # Shape: (T, D) → (T, D)
        window_scaled = self.scaler.transform(window)

        # Convert to tensor: (1, T, D)
        x = torch.FloatTensor(window_scaled).unsqueeze(0)

        # Forward pass (no gradient needed for inference)
        with torch.no_grad():
            x_hat = self.model(x)  # (1, T, D)

        # Reconstruction error per feature (Paper Eq. 2):
        #   e_i = (1/T) * Σ_t (x_t,i - x̂_t,i)²
        # Shape: (1, T, D) → (D,) after mean over T and squeeze batch
        per_feature_mse = ((x - x_hat) ** 2).mean(dim=1).squeeze(0).numpy()

        # Overall anomaly score: mean across all features
        anomaly_score = float(per_feature_mse.mean())

        # Build per-feature attribution dict
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
# MQTT Handler
# ==============================================================================

class MLInferenceService:
    """
    Main service: subscribes to sensor MQTT feeds, maintains per-aircraft
    buffers, runs inference, and publishes results.
    """
    def __init__(self):
        self.buffers = defaultdict(AircraftBuffer)
        self.engine = InferenceEngine(MODEL_PATH)
        self.mqtt_client = None

    def start(self):
        """Connect to MQTT and start the event loop."""
        with open("/etc/securing-skies/mqtt_secret") as f:
            mqtt_pass = f.read().strip()

        self.mqtt_client = mqtt.Client(
            client_id="ml-inference-v1",
            transport=MQTT_TRANSPORT,
        )
        self.mqtt_client.username_pw_set(MQTT_USER, mqtt_pass)

        if MQTT_TLS:
            self.mqtt_client.tls_set(cert_reqs=ssl.CERT_REQUIRED,
                                     tls_version=ssl.PROTOCOL_TLS_CLIENT)

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
        """
        Process incoming aircraft.json messages from each sensor.
        For each aircraft with position data, update the sliding window
        buffer and run inference when the buffer is full.
        """
        try:
            sensor = message.topic.split("/")[0]
            payload = json.loads(message.payload)
            now = time.time()

            for ac in payload.get("aircraft", []):
                hex_id = ac.get("hex")
                if not hex_id or "lat" not in ac or "lon" not in ac:
                    continue

                # Build observation dict
                obs = {
                    "lat": ac["lat"],
                    "lon": ac["lon"],
                    "gs": ac.get("gs", 0),
                    "rssi": ac.get("rssi", -30.0),
                    "ts": now,
                }

                # Update per-aircraft buffer
                buf = self.buffers[hex_id]
                buf.update(obs, sensor)

                # Run inference if buffer is full and enough time has passed
                if buf.ready() and (now - buf.last_inference_ts) >= INFERENCE_INTERVAL:
                    buf.last_inference_ts = now
                    window = buf.get_window()
                    result = self.engine.infer(window)

                    # Publish if anomalous (or periodically for monitoring)
                    if result["is_anomaly"]:
                        self._publish_anomaly(hex_id, ac, result, sensor)

        except Exception as e:
            log.warning(f"Error processing message: {e}")

    def _publish_anomaly(self, hex_id, ac, result, sensor):
        """Publish ML anomaly detection result to MQTT."""
        payload = {
            "ts": time.time(),
            "hex": hex_id,
            "flight": (ac.get("flight") or "").strip(),
            "sensor": sensor,
            "anomaly_score": result["anomaly_score"],
            "threshold": result["threshold"],
            "is_anomaly": result["is_anomaly"],
            "per_feature_error": result["per_feature_error"],
        }
        self.mqtt_client.publish(
            PUBLISH_TOPIC,
            json.dumps(payload),
            qos=0,
        )
        log.info(
            f"ANOMALY {hex_id} ({ac.get('flight','').strip()}): "
            f"score={result['anomaly_score']:.6f} > τ={result['threshold']:.6f}"
        )


# ==============================================================================
# Entry Point
# ==============================================================================

if __name__ == "__main__":
    log.info("Starting ML Inference Service v1.0.0")
    log.info(f"Window: T={WINDOW_SIZE}, Features: D={FEATURE_DIM}")
    log.info(f"Inference interval: {INFERENCE_INTERVAL}s per aircraft")
    service = MLInferenceService()
    service.start()
