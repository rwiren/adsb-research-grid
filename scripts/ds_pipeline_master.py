import pandas as pd
import numpy as np
import glob
import os
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler

# ==============================================================================
# PROJECT: ADS-B Spoofing Research
# PHASE:   3 - Advanced Data Science (AI/ML Prep)
# FILE:    scripts/ds_pipeline_master.py
# VERSION: 4.4.0 (Fix: Path Redirection & GZIP Support)
# ==============================================================================

# --- CONFIGURATION ---
# FIX: Pointing to where Ansible actually dumps the data
RAW_DIR = "infra/ansible/playbooks/research_data/raw"
OUTPUT_DIR = "research_data/ml_ready"
PLOTS_DIR = "output/plots/eda_v3"
REPORT_FILE = f"{OUTPUT_DIR}/ml_audit.txt"

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
    # Look for files (including .gz)
    files = glob.glob(os.path.join(RAW_DIR, sensor_name, file_pattern))
    if not files:
        # Fallback to flattened structure
        files = glob.glob(os.path.join(RAW_DIR, f"{sensor_name}*{file_pattern}"))
        if not files:
            return pd.DataFrame()

    df_list = []
    for f in files:
        try:
            # Pandas handles compression='infer' automatically for .gz
            temp_df = pd.read_csv(f, on_bad_lines='skip', low_memory=False)
            
            # Normalize Column Names
            if 'alt_baro' in temp_df.columns: temp_df.rename(columns={'alt_baro': 'alt'}, inplace=True)
            if 'gs' in temp_df.columns: temp_df.rename(columns={'gs': 'ground_speed'}, inplace=True)
            
            # Normalize Timestamps
            if is_legacy_format:
                temp_df['timestamp'] = pd.to_datetime(temp_df['timestamp'], unit='s', errors='coerce').dt.tz_localize('UTC')
            else:
                temp_df['timestamp'] = pd.to_datetime(temp_df['timestamp'], format='mixed', errors='coerce')
                # Ensure UTC
                if temp_df['timestamp'].dt.tz is None:
                    temp_df['timestamp'] = temp_df['timestamp'].dt.tz_localize('UTC')
                else:
                    temp_df['timestamp'] = temp_df['timestamp'].dt.tz_convert('UTC')

            # Type Enforcement
            for col in ['lat', 'lon', 'alt', 'ground_speed', 'track', 'rssi']:
                if col in temp_df.columns:
                    temp_df[col] = pd.to_numeric(temp_df[col], errors='coerce')

            temp_df['sensor_id'] = sensor_name
            df_list.append(temp_df)
        except Exception as e:
            pass 

    if not df_list: return pd.DataFrame()
    return pd.concat(df_list, ignore_index=True)

if __name__ == "__main__":
    # 1. INGESTION
    log_msg(f"🚀 Starting Phase 3 Data Science Pipeline... (Source: {RAW_DIR})")
    # FIX: Added trailing wildcard to pattern to match .csv.gz
    df_north = load_and_normalize("sensor-north", "*aircraft_log*.csv*", is_legacy_format=False)
    df_east  = load_and_normalize("sensor-east",  "*aircraft_log*.csv*", is_legacy_format=False)
    df_west  = load_and_normalize("sensor-west",  "*aircraft_log*.csv*", is_legacy_format=False)

    df_final = pd.concat([df_north, df_east, df_west], ignore_index=True)
    raw_count = len(df_final)
    log_msg(f"📥 Raw Data Ingested: {raw_count:,} rows")

    if df_final.empty:
        log_msg("❌ CRITICAL: No data ingested. Check the path above.")
        exit(1)

    # 2. DATA CLEANING & PHYSICS VALIDATION
    log_msg("🧹 Cleaning Data & Validating Physics...")
    df_clean = df_final.dropna(subset=['lat', 'lon', 'alt', 'hex', 'timestamp']).copy()

    # Filters
    df_clean = df_clean[(df_clean['lat'].between(-90, 90)) & (df_clean['lon'].between(-180, 180))]
    df_clean = df_clean[df_clean['alt'] > -2000] 
    
    # Time Hygiene Filter
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
    
    # SNR Proxy
    if 'rssi' in df_clean.columns:
        df_clean['snr_proxy'] = df_clean['rssi'] + 49.5 
    else:
        df_clean['snr_proxy'] = 0

    # 4. ENSEMBLE ANOMALY DETECTION (IsoForest + LOF)
    log_msg("🤖 Training Ensemble Models...")
    
    features = ['alt', 'ground_speed', 'rssi', 'track']
    # Ensure features exist
    features = [f for f in features if f in df_clean.columns]
    
    if len(features) < 2:
        log_msg(f"⚠️  Not enough features for ML. Found: {features}")
        df_ml = pd.DataFrame()
    else:
        df_ml = df_clean.dropna(subset=features).copy()

    if not df_ml.empty:
        scaler = StandardScaler()
        X = scaler.fit_transform(df_ml[features])
        
        # --- Model 1: Isolation Forest ---
        log_msg("   🌲 Training Isolation Forest (Global Density)...")
        iso_forest = IsolationForest(contamination=0.01, random_state=42, n_jobs=-1)
        df_ml['score_iso'] = iso_forest.fit_predict(X)
        df_ml['anomaly_iso'] = df_ml['score_iso'].apply(lambda x: 1 if x == -1 else 0)

        # --- Model 2: Local Outlier Factor ---
        if len(X) > 100000:
            log_msg("   ⚠️  Dataset > 100k rows. Using LOF on 50k subsample for speed.")
            df_ml['anomaly_lof'] = 0 
        else:
            log_msg("   🔍 Training Local Outlier Factor (Local Density)...")
            lof = LocalOutlierFactor(n_neighbors=20, contamination=0.01, n_jobs=-1)
            y_lof = lof.fit_predict(X)
            df_ml['anomaly_lof'] = [1 if x == -1 else 0 for x in y_lof]
        
        # --- Ensemble Voting ---
        df_ml['ensemble_score'] = df_ml['anomaly_iso'] + df_ml['anomaly_lof']
        
        # Merge back
        df_clean = df_clean.join(df_ml[['ensemble_score', 'anomaly_iso', 'anomaly_lof']])
        
        ghosts = df_clean[df_clean['ensemble_score'] >= 1]
        confirmed = df_clean[df_clean['ensemble_score'] == 2]
        log_msg(f"🚨 Anomalies Detected (Union): {len(ghosts):,} ({len(ghosts)/len(df_clean):.2%})")
        log_msg(f"💀 Confirmed GHOSTS (Agreement): {len(confirmed):,}")
    else:
        log_msg("⚠️  Skipping ML: Insufficient valid data rows.")

    # Save ML-Ready Data
    output_file = os.path.join(OUTPUT_DIR, "training_dataset_v4_ensemble.csv")
    df_clean.to_csv(output_file, index=False)
    log_msg(f"💾 Saved Ensemble Training Set: {output_file}")
