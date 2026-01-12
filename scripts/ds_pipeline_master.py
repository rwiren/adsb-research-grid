import pandas as pd
import numpy as np
import glob
import os
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# ==============================================================================
# PROJECT: ADS-B Spoofing Research
# PHASE:   3 - Advanced Data Science (AI/ML Prep)
# FILE:    scripts/ds_pipeline_master.py
# VERSION: 3.2.0 (Time Hygiene + 3D MLAT Ready)
# ==============================================================================

# --- CONFIGURATION ---
RAW_DIR = "research_data/2026-01-12"
OUTPUT_DIR = "research_data/ml_ready"
PLOTS_DIR = "output/plots/eda_v3"
REPORT_FILE = f"{OUTPUT_DIR}/academic_validation_report_v3.txt"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(PLOTS_DIR, exist_ok=True)

# Academic Aesthetics
sns.set_theme(style="ticks", context="paper", font_scale=1.2)
plt.rcParams['figure.figsize'] = (14, 8)
COLORS = {"sensor-north": "#003f5c", "sensor-east": "#bc5090", "sensor-west": "#ffa600"}

def log_msg(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def load_and_normalize(sensor_name, file_pattern, is_legacy_format=False):
    """Robust loader handling schema drift and type coercion."""
    files = glob.glob(os.path.join(RAW_DIR, sensor_name, file_pattern))
    if not files:
        log_msg(f"⚠️  No files found for {sensor_name}")
        return pd.DataFrame()

    df_list = []
    for f in files:
        try:
            temp_df = pd.read_csv(f, on_bad_lines='skip', low_memory=False)
            
            # 1. Normalize Column Names
            temp_df.rename(columns={'alt_baro': 'alt', 'gs': 'ground_speed'}, inplace=True)
            
            # 2. Normalize Timestamps (Force UTC)
            if is_legacy_format:
                temp_df['timestamp'] = pd.to_datetime(temp_df['timestamp'], unit='s', errors='coerce').dt.tz_localize('UTC')
            else:
                temp_df['timestamp'] = pd.to_datetime(temp_df['timestamp'], format='mixed', errors='coerce')
                if temp_df['timestamp'].dt.tz is None:
                    temp_df['timestamp'] = temp_df['timestamp'].dt.tz_localize('UTC')
                else:
                    temp_df['timestamp'] = temp_df['timestamp'].dt.tz_convert('UTC')

            # 3. Type Enforcement
            temp_df['alt'] = pd.to_numeric(temp_df['alt'], errors='coerce')
            for col in ['lat', 'lon', 'ground_speed', 'track', 'rssi']:
                if col in temp_df.columns:
                    temp_df[col] = pd.to_numeric(temp_df[col], errors='coerce')

            temp_df['sensor_id'] = sensor_name
            df_list.append(temp_df)
        except Exception as e:
            log_msg(f"❌ Error reading {f}: {e}")

    if not df_list: return pd.DataFrame()
    return pd.concat(df_list, ignore_index=True)

# --- PIPELINE EXECUTION ---

# 1. INGESTION
log_msg("🚀 Starting Phase 3 Data Science Pipeline...")
df_north = load_and_normalize("sensor-north", "*aircraft_log*.csv", is_legacy_format=True)
df_east  = load_and_normalize("sensor-east",  "*aircraft_log*.csv", is_legacy_format=False)
df_west  = load_and_normalize("sensor-west",  "*aircraft_log*.csv", is_legacy_format=False)

df_final = pd.concat([df_north, df_east, df_west], ignore_index=True)
raw_count = len(df_final)
log_msg(f"📥 Raw Data Ingested: {raw_count:,} rows")

# 2. DATA CLEANING & PHYSICS VALIDATION
log_msg("🧹 Cleaning Data & Validating Physics...")
df_clean = df_final.dropna(subset=['lat', 'lon', 'alt', 'hex', 'timestamp']).copy()

# A. Physics Filter (Impossible Coordinates)
df_clean = df_clean[(df_clean['lat'].between(-90, 90)) & (df_clean['lon'].between(-180, 180))]
df_clean = df_clean[df_clean['alt'] > -2000] 

# [cite_start]B. Time Hygiene Filter (The 1970 Fix) [cite: 1]
pre_filter_count = len(df_clean)
df_clean = df_clean[df_clean['timestamp'] > '2025-01-01']
dropped_time = pre_filter_count - len(df_clean)

if dropped_time > 0:
    log_msg(f"🕰️  Dropped {dropped_time:,} rows with invalid timestamps (Pre-2025)")

clean_count = len(df_clean)
log_msg(f"✅ Cleaned Dataset: {clean_count:,} rows (Removed {raw_count - clean_count:,} invalid)")

# 3. ADVANCED FEATURE ENGINEERING
log_msg("⚙️  Engineering AI Features (Kinematics & Signal)...")
df_clean = df_clean.sort_values(by=['hex', 'timestamp'])

# Calculate Derivatives
df_clean['time_gap'] = df_clean.groupby('hex')['timestamp'].diff().dt.total_seconds()
df_clean['alt_rate'] = df_clean.groupby('hex')['alt'].diff() / df_clean['time_gap'] # ft/sec

# Signal Quality Features
df_clean['snr_proxy'] = df_clean['rssi'] + 49.5 

# 4. UNSUPERVISED ANOMALY DETECTION (Isolation Forest)
log_msg("🤖 Training Anomaly Detector (Isolation Forest)...")
features = ['alt', 'ground_speed', 'rssi', 'track']
df_ml = df_clean.dropna(subset=features)

if not df_ml.empty:
    scaler = StandardScaler()
    X = scaler.fit_transform(df_ml[features])
    
    # Contamination=0.01 means we expect ~1% of data to be anomalies
    iso_forest = IsolationForest(contamination=0.01, random_state=42, n_jobs=-1)
    df_clean.loc[df_ml.index, 'anomaly_score'] = iso_forest.fit_predict(X)
    
    anomalies = df_clean[df_clean['anomaly_score'] == -1]
    log_msg(f"🚨 Anomalies Detected: {len(anomalies):,} ({len(anomalies)/len(df_clean):.2%})")
else:
    log_msg("⚠️ Not enough data for ML training.")

# Save ML-Ready Data
output_file = os.path.join(OUTPUT_DIR, "training_dataset_v3.csv")
df_clean.to_csv(output_file, index=False)
log_msg(f"💾 Saved Gold Standard Training Set: {output_file}")

# 5. ACADEMIC VISUALIZATION SUITE
log_msg("🎨 Generating Academic Figures...")

# Fig 1: Spatial Coverage
plt.figure()
sns.scatterplot(data=df_clean[::10], x='lon', y='lat', hue='sensor_id', palette=COLORS, alpha=0.5, s=10)
plt.title("Fig 1: Verified Sensor Coverage (Post-Filter)")
plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.xlim(24.3, 25.5) # Forced Zoom on Truth Triangle
plt.ylim(60.1, 60.45)
plt.legend(bbox_to_anchor=(1.05, 1), loc=2)
plt.tight_layout()
plt.savefig(f"{PLOTS_DIR}/Fig1_Spatial_Coverage.png", dpi=300)
plt.close()

# Report Generation
with open(REPORT_FILE, "w") as f:
    f.write("ADS-B RESEARCH DATASET REPORT (v3.2)\n")
    f.write("====================================\n")
    f.write(f"Generated: {datetime.now()}\n\n")
    f.write(f"Total Valid Samples: {len(df_clean):,}\n")
    f.write(f"Dropped (Bad Time): {dropped_time:,}\n")
    f.write(f"Detected Anomalies: {len(df_clean[df_clean['anomaly_score']==-1]):,}\n\n")
    f.write("Sensor Performance Metrics:\n")
    f.write(df_clean.groupby('sensor_id')[['rssi', 'ground_speed', 'alt']].agg(['mean', 'std', 'count']).to_string())

log_msg(f"✅ Pipeline Complete. Report: {REPORT_FILE}")
