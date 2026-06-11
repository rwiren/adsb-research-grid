#!/usr/bin/env python3
"""
train_gru_autoencoder.py — GRU Autoencoder Training Pipeline
=============================================================
Version: 2.0.0 (May 2026 retrain)
Environment: Kubeflow (T4 GPU, 8GB RAM, 2 CPU)

Matches production inference service feature engineering EXACTLY.
Produces checkpoint compatible with ml_inference_service.py.

Usage:
    python train_gru_autoencoder.py --data_dir ./research_data/raw \
                                    --output_dir ./models \
                                    --epochs 50 --batch_size 512

Input: Per-sensor aircraft_log CSV files (gzipped)
Output: gru_h256_l4_production.pth (checkpoint with model + scaler + hyperparams)
"""

import argparse
import glob
import gzip
import math
import os
import time
from collections import deque
from datetime import datetime

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler

# ==============================================================================
# Configuration (must match ml_inference_service.py)
# ==============================================================================

WINDOW_SIZE = 30
FEATURE_DIM = 11
DT_MIN = 0.5
DT_MAX = 3.0
VELOCITY_DRIFT_WINDOW = 15

SENSOR_POS = {
    "sensor-north": (60.319558, 24.830813),
    "sensor-west":  (60.130877, 24.512927),
    "sensor-east":  (60.374069, 25.248990),
}

SENSOR_RSSI_MULT = {
    "sensor-north": 1.00,
    "sensor-west":  0.58,
    "sensor-east":  0.83,
}

# RSSI normalization offsets (empirically measured May 2026)
# East reads +8.8 dB higher due to FlightAware Pro+ preamp
SENSOR_RSSI_OFFSET = {
    "sensor-north": 0.0,
    "sensor-east": -8.8,
    "sensor-west": 0.0,
}

RSSI_REF_DBM = -20.0
RSSI_REF_DIST_KM = 1.0
EFHK_LAT, EFHK_LON = 60.317222, 24.963333

FEATURE_NAMES = [
    "velocity_calculated", "velocity_error", "velocity_drift",
    "velocity_drift_weighted", "displacement_error",
    "distance_to_sensor", "rssi_expected", "rssi_error", "rssi_error_normalized",
    "distance_to_airport", "msg_interval_variance",
]


# ==============================================================================
# Model (identical to ml_inference_service.py)
# ==============================================================================

class GRUAutoencoder(nn.Module):
    def __init__(self, input_size, hidden_size=256, latent_size=8, num_layers=4, dropout=0.2):
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
# Feature Engineering (identical to ml_inference_service.py)
# ==============================================================================

def haversine_km(lat1, lon1, lat2, lon2):
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * \
        math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_features_batch(df_aircraft, sensor_name):
    """Compute feature sequences for one aircraft from one sensor."""
    sensor_pos = SENSOR_POS.get(sensor_name, SENSOR_POS["sensor-north"])
    rssi_mult = SENSOR_RSSI_MULT.get(sensor_name, 1.0)
    rssi_offset = SENSOR_RSSI_OFFSET.get(sensor_name, 0.0)

    features = []
    vel_error_history = deque(maxlen=50)
    dt_history = deque(maxlen=10)

    for i in range(1, len(df_aircraft)):
        prev = df_aircraft.iloc[i - 1]
        curr = df_aircraft.iloc[i]

        dt = (curr["timestamp"] - prev["timestamp"]).total_seconds()
        if dt < DT_MIN or dt > DT_MAX:
            continue

        dt_history.append(dt)

        # Feature 0: velocity_calculated
        dist_km = haversine_km(prev["lat"], prev["lon"], curr["lat"], curr["lon"])
        velocity_calculated = (dist_km * 1000.0) / dt

        # Feature 1: velocity_error
        gs_ms = (curr["gs"] if pd.notna(curr["gs"]) else 0) * 0.514444
        velocity_error = gs_ms - velocity_calculated

        # Feature 2: velocity_drift
        vel_error_history.append(velocity_error)
        if len(vel_error_history) >= 2:
            signs = []
            for j in range(1, len(vel_error_history)):
                diff = vel_error_history[j] - vel_error_history[j - 1]
                signs.append(1.0 if diff > 0 else (-1.0 if diff < 0 else 0.0))
            recent = signs[-VELOCITY_DRIFT_WINDOW:]
            velocity_drift = sum(recent) / len(recent)
        else:
            velocity_drift = 0.0

        # Feature 3: velocity_drift_weighted
        if len(vel_error_history) >= 2:
            diffs = [vel_error_history[j] - vel_error_history[j-1]
                     for j in range(1, len(vel_error_history))]
            recent = diffs[-VELOCITY_DRIFT_WINDOW:]
            weights = list(range(1, len(recent) + 1))
            velocity_drift_weighted = sum(d * w for d, w in zip(recent, weights)) / sum(weights)
        else:
            velocity_drift_weighted = 0.0

        # Range attenuation
        distance_to_sensor = haversine_km(curr["lat"], curr["lon"], sensor_pos[0], sensor_pos[1])
        range_factor = min(1.0, 60.0 / max(distance_to_sensor, 1.0))
        velocity_drift_weighted *= range_factor

        # Feature 4: displacement_error
        expected_dist = velocity_calculated * dt / 1000.0
        displacement_error = dist_km - expected_dist

        # Feature 5: distance_to_sensor (already computed)

        # Feature 6: rssi_expected (FSPL)
        d_clamped = max(distance_to_sensor, 0.01)
        rssi_expected = RSSI_REF_DBM - 20.0 * math.log10(d_clamped / RSSI_REF_DIST_KM)

        # Feature 7: rssi_error
        rssi_measured = curr["rssi"] + rssi_offset if pd.notna(curr["rssi"]) else -30.0
        rssi_error = rssi_measured - rssi_expected

        # Feature 8: rssi_error_normalized
        rssi_error_normalized = rssi_error / rssi_mult

        # Feature 9: distance_to_airport
        distance_to_airport = haversine_km(curr["lat"], curr["lon"], EFHK_LAT, EFHK_LON)

        # Feature 10: msg_interval_variance
        if len(dt_history) >= 2:
            dt_arr = list(dt_history)
            dt_mean = sum(dt_arr) / len(dt_arr)
            msg_interval_variance = sum((d - dt_mean)**2 for d in dt_arr) / len(dt_arr)
        else:
            msg_interval_variance = 0.0

        features.append([
            velocity_calculated, velocity_error, velocity_drift,
            velocity_drift_weighted, displacement_error,
            distance_to_sensor, rssi_expected, rssi_error, rssi_error_normalized,
            distance_to_airport, msg_interval_variance,
        ])

    return features


def build_sequences(features_list, window_size=WINDOW_SIZE):
    """Sliding window over feature list to create (N, T, D) sequences."""
    sequences = []
    for i in range(len(features_list) - window_size + 1):
        seq = features_list[i:i + window_size]
        sequences.append(seq)
    return sequences


# ==============================================================================
# Data Loading
# ==============================================================================

def load_sensor_data(data_dir, sensor_name):
    """Load all aircraft log CSVs for a sensor."""
    patterns = [
        os.path.join(data_dir, sensor_name, f"*aircraft_log*.csv*"),
        os.path.join(data_dir, f"{sensor_name}*aircraft_log*.csv*"),
    ]
    files = []
    for p in patterns:
        files.extend(glob.glob(p))
    if not files:
        print(f"  WARNING: No files found for {sensor_name}")
        return pd.DataFrame()

    dfs = []
    for f in sorted(files):
        df = pd.read_csv(f, on_bad_lines="skip", low_memory=False)
        dfs.append(df)
        print(f"    {os.path.basename(f)}: {len(df):,} rows")

    df = pd.concat(dfs, ignore_index=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="mixed", errors="coerce", utc=True)
    for col in ["lat", "lon", "gs", "rssi"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ==============================================================================
# Main Training Pipeline
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Train GRU Autoencoder for ADS-B spoofing detection")
    parser.add_argument("--data_dir", default="infra/ansible/playbooks/research_data/raw",
                        help="Directory containing sensor-north/, sensor-east/, sensor-west/")
    parser.add_argument("--output_dir", default="models", help="Output directory for checkpoint")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch_size", type=int, default=512)
    parser.add_argument("--hidden_size", type=int, default=256)
    parser.add_argument("--latent_size", type=int, default=8)
    parser.add_argument("--num_layers", type=int, default=4)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--max_aircraft", type=int, default=0, help="Limit aircraft for debugging (0=all)")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    print(f"Data dir: {args.data_dir}")
    print(f"Architecture: GRU h{args.hidden_size}/l{args.num_layers}, latent={args.latent_size}")
    print(f"Window: T={WINDOW_SIZE}, Features: D={FEATURE_DIM}")
    print()

    # --- 1. Load Data ---
    print("=" * 60)
    print("PHASE 1: Data Ingestion")
    print("=" * 60)
    all_sequences = []

    for sensor_name in ["sensor-north", "sensor-east", "sensor-west"]:
        print(f"\n  Loading {sensor_name}...")
        df = load_sensor_data(args.data_dir, sensor_name)
        if df.empty:
            continue

        # Filter: need lat, lon, valid timestamp
        df = df.dropna(subset=["lat", "lon", "timestamp"])
        df = df[df["lat"].between(-90, 90) & df["lon"].between(-180, 180)]
        # Exclude ground
        if "alt_baro" in df.columns:
            df = df[df["alt_baro"] != "ground"]

        # Group by aircraft
        aircraft_groups = df.groupby("hex")
        n_aircraft = len(aircraft_groups)
        print(f"  {sensor_name}: {len(df):,} rows, {n_aircraft} aircraft")

        processed = 0
        sensor_seqs = 0
        for hex_id, group in aircraft_groups:
            if args.max_aircraft > 0 and processed >= args.max_aircraft:
                break
            group = group.sort_values("timestamp").reset_index(drop=True)
            if len(group) < WINDOW_SIZE + 5:  # Need enough for at least 1 window
                continue

            features = compute_features_batch(group, sensor_name)
            if len(features) >= WINDOW_SIZE:
                seqs = build_sequences(features)
                all_sequences.extend(seqs)
                sensor_seqs += len(seqs)

            processed += 1
            if processed % 100 == 0:
                print(f"    {processed}/{n_aircraft} aircraft, {sensor_seqs:,} sequences...")

        print(f"  {sensor_name} done: {sensor_seqs:,} sequences from {processed} aircraft")

    print(f"\n  TOTAL: {len(all_sequences):,} sequences")

    if len(all_sequences) < 100:
        print("ERROR: Not enough sequences for training. Check data.")
        return

    # --- 2. Normalize ---
    print("\n" + "=" * 60)
    print("PHASE 2: Normalization")
    print("=" * 60)

    X = np.array(all_sequences, dtype=np.float32)  # (N, T, D)
    print(f"  Tensor shape: {X.shape}")

    # Fit scaler on flattened features
    X_flat = X.reshape(-1, FEATURE_DIM)
    scaler = StandardScaler()
    X_flat_scaled = scaler.fit_transform(X_flat)
    X_scaled = X_flat_scaled.reshape(X.shape)

    # Clip outliers (>5 sigma)
    X_scaled = np.clip(X_scaled, -5, 5)

    print(f"  Scaler mean: {scaler.mean_[:3]}...")
    print(f"  Scaler std:  {scaler.scale_[:3]}...")

    # --- 3. Train/Val Split ---
    n = len(X_scaled)
    split = int(0.9 * n)
    indices = np.random.permutation(n)
    X_train = torch.tensor(X_scaled[indices[:split]], dtype=torch.float32)
    X_val = torch.tensor(X_scaled[indices[split:]], dtype=torch.float32)
    print(f"  Train: {len(X_train):,}, Val: {len(X_val):,}")

    train_loader = DataLoader(TensorDataset(X_train), batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(TensorDataset(X_val), batch_size=args.batch_size)

    # --- 4. Train ---
    print("\n" + "=" * 60)
    print("PHASE 3: Training")
    print("=" * 60)

    model = GRUAutoencoder(
        input_size=FEATURE_DIM,
        hidden_size=args.hidden_size,
        latent_size=args.latent_size,
        num_layers=args.num_layers,
        dropout=args.dropout,
    ).to(device)

    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Model parameters: {n_params:,}")

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
    criterion = nn.MSELoss()

    best_val_loss = float("inf")
    best_state = None

    for epoch in range(args.epochs):
        # Train
        model.train()
        train_loss = 0
        for (batch,) in train_loader:
            batch = batch.to(device)
            optimizer.zero_grad()
            output = model(batch)
            loss = criterion(output, batch)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item() * len(batch)
        train_loss /= len(X_train)

        # Validate
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for (batch,) in val_loader:
                batch = batch.to(device)
                output = model(batch)
                loss = criterion(output, batch)
                val_loss += loss.item() * len(batch)
        val_loss /= len(X_val)

        scheduler.step(val_loss)
        lr = optimizer.param_groups[0]["lr"]

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = model.state_dict().copy()
            marker = " ★"
        else:
            marker = ""

        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"  Epoch {epoch+1:3d}/{args.epochs} | "
                  f"Train: {train_loss:.6f} | Val: {val_loss:.6f} | "
                  f"LR: {lr:.2e}{marker}")

    # --- 5. Compute Threshold ---
    print("\n" + "=" * 60)
    print("PHASE 4: Threshold Calibration")
    print("=" * 60)

    model.load_state_dict(best_state)
    model.eval()

    all_scores = []
    with torch.no_grad():
        for (batch,) in val_loader:
            batch = batch.to(device)
            output = model(batch)
            mse = ((batch - output) ** 2).mean(dim=(1, 2)).cpu().numpy()
            all_scores.extend(mse)

    scores = np.array(all_scores)
    threshold = float(np.percentile(scores, 99.9))
    p95 = float(np.percentile(scores, 95))
    p99 = float(np.percentile(scores, 99))

    print(f"  Score P50: {np.median(scores):.6f}")
    print(f"  Score P95: {p95:.6f}")
    print(f"  Score P99: {p99:.6f}")
    print(f"  Score P99.9 (threshold τ): {threshold:.6f}")
    print(f"  Score max: {scores.max():.6f}")

    # --- 6. Save Checkpoint ---
    print("\n" + "=" * 60)
    print("PHASE 5: Save Checkpoint")
    print("=" * 60)

    os.makedirs(args.output_dir, exist_ok=True)
    ckpt_path = os.path.join(args.output_dir, "gru_h256_l4_production.pth")

    checkpoint = {
        "model_state_dict": best_state,
        "scaler": scaler,
        "hyperparams": {
            "input_size": FEATURE_DIM,
            "hidden_size": args.hidden_size,
            "latent_size": args.latent_size,
            "num_layers": args.num_layers,
            "dropout": args.dropout,
        },
        "threshold": threshold,
        "score_p95": p95,
        "score_p99": p99,
        "training_info": {
            "date": datetime.utcnow().isoformat(),
            "n_sequences": len(all_sequences),
            "n_train": len(X_train),
            "n_val": len(X_val),
            "best_val_loss": best_val_loss,
            "epochs": args.epochs,
            "feature_names": FEATURE_NAMES,
            "window_size": WINDOW_SIZE,
            "sensor_rssi_offsets": SENSOR_RSSI_OFFSET,
        },
    }

    torch.save(checkpoint, ckpt_path)
    print(f"  Saved: {ckpt_path}")
    print(f"  Size: {os.path.getsize(ckpt_path) / 1024 / 1024:.1f} MB")
    print(f"\n  ✅ Training complete. Deploy to /root/adsb-dashboard/models/")


if __name__ == "__main__":
    main()
