import pandas as pd
import numpy as np
import glob
import os
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# ==============================================================================
# FILE: scripts/generate_ml_dataset.py
# VERSION: 1.1.0 (Fixed Timezone Mismatch)
# PURPOSE: Normalize raw ADSB logs for AI/ML Spoofing Detection Training
# OUTPUT: research_data/ml_ready/training_dataset_20260111.csv
# ==============================================================================

RAW_DIR = "research_data/2026-01-11"
OUTPUT_DIR = "research_data/ml_ready"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_and_normalize(sensor_name, file_pattern, is_legacy_format=False):
    """Reads CSV, fixes timestamps to UTC-Aware, and standardizes columns."""
    files = glob.glob(os.path.join(RAW_DIR, sensor_name, file_pattern))
    if not files:
        print(f"⚠️  No files found for {sensor_name}")
        return pd.DataFrame()

    print(f"📥 Loading {len(files)} files for {sensor_name}...")
    df_list = []
    
    for f in files:
        try:
            # Read CSV (skip bad lines if any)
            temp_df = pd.read_csv(f, on_bad_lines='skip')
            
            # 1. Normalize Column Names
            temp_df.rename(columns={'alt_baro': 'alt', 'gs': 'ground_speed'}, inplace=True)
            
            # 2. Normalize Timestamps (CRITICAL FIX)
            if is_legacy_format:
                # North: Unix Epoch -> Naive -> Localize to UTC
                temp_df['timestamp'] = pd.to_datetime(temp_df['timestamp'], unit='s', errors='coerce')
                temp_df['timestamp'] = temp_df['timestamp'].dt.tz_localize('UTC')
            else:
                # East/West: ISO 8601 -> May be mixed -> Convert to UTC
                temp_df['timestamp'] = pd.to_datetime(temp_df['timestamp'], format='mixed', errors='coerce')
                # If naive, localize. If aware, convert.
                if temp_df['timestamp'].dt.tz is None:
                    temp_df['timestamp'] = temp_df['timestamp'].dt.tz_localize('UTC')
                else:
                    temp_df['timestamp'] = temp_df['timestamp'].dt.tz_convert('UTC')

            temp_df['sensor_id'] = sensor_name
            df_list.append(temp_df)
        except Exception as e:
            print(f"❌ Error reading {f}: {e}")

    if not df_list: return pd.DataFrame()
    return pd.concat(df_list, ignore_index=True)

# --- MAIN ETL PROCESS ---
print("🚀 Starting ETL Pipeline for AI/ML...")

# 1. Ingest Data
df_north = load_and_normalize("sensor-north", "*aircraft_log*.csv", is_legacy_format=True)
df_east  = load_and_normalize("sensor-east",  "*aircraft_log*.csv", is_legacy_format=False)
df_west  = load_and_normalize("sensor-west",  "*aircraft_log*.csv", is_legacy_format=False)

# 2. Merge All Sensors
df_final = pd.concat([df_north, df_east, df_west], ignore_index=True)
print(f"📊 Total Raw Rows: {len(df_final)}")

# 3. Data Cleaning
df_clean = df_final.dropna(subset=['lat', 'lon', 'alt', 'hex'])
print(f"🧹 Cleaned Rows (Valid Position): {len(df_clean)}")

# 4. Feature Engineering
print("⚙️  Engineering Features...")

# Sort (Now safe because everything is UTC-Aware)
df_clean = df_clean.sort_values(by=['hex', 'timestamp'])

# Calculate Time Delta & Distance Delta
df_clean['time_gap'] = df_clean.groupby('hex')['timestamp'].diff().dt.total_seconds()
df_clean['lat_diff'] = df_clean.groupby('hex')['lat'].diff()
df_clean['lon_diff'] = df_clean.groupby('hex')['lon'].diff()

# Approx Distance (Meters)
df_clean['dist_delta_approx_m'] = np.sqrt(
    (df_clean['lat_diff'] * 111000)**2 + 
    (df_clean['lon_diff'] * 111000 * np.cos(np.radians(df_clean['lat'])))**2
)

# Velocities
df_clean['calc_velocity_ms'] = df_clean['dist_delta_approx_m'] / df_clean['time_gap']
df_clean['reported_velocity_ms'] = df_clean['ground_speed'] * 0.514444
df_clean['velocity_discrepancy'] = abs(df_clean['calc_velocity_ms'] - df_clean['reported_velocity_ms'])

# 5. Export
output_file = os.path.join(OUTPUT_DIR, "training_dataset_20260111.csv")
df_clean.to_csv(output_file, index=False)
print(f"✅ Saved Gold Standard Dataset: {output_file}")

# --- EDA VISUALIZATION ---
print("🎨 Generating EDA Plots...")

# Plot 1: Signal Strength Distribution
plt.figure(figsize=(10, 6))
sns.histplot(data=df_clean, x='rssi', hue='sensor_id', kde=True, element="step")
plt.title("Signal Strength (RSSI) Distribution by Sensor")
plt.xlabel("RSSI (dBFS)")
plt.savefig(f"{OUTPUT_DIR}/eda_rssi_distribution.png")

# Plot 2: Altitude vs Signal Strength
plt.figure(figsize=(10, 6))
sns.scatterplot(data=df_clean[::100], x='alt', y='rssi', hue='sensor_id', alpha=0.3)
plt.title("Physics Consistency: Altitude vs Signal Strength")
plt.savefig(f"{OUTPUT_DIR}/eda_physics_check.png")

print("✅ EDA Complete.")
