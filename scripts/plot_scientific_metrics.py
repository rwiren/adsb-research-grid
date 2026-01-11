#!/usr/bin/env python3
"""
# ==============================================================================
# FILE: scripts/plot_scientific_metrics.py
# VERSION: 1.4.0 (Schema Enforcement)
# DESCRIPTION:
#   - Forces standard column headers for headless CSV logs.
#   - Generates multi-panel 'Medical Chart' (Signal + Noise).
# ==============================================================================
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import glob
import os
from datetime import datetime

# --- CONFIGURATION ---
DATA_DIR = "research_data"
OUTPUT_DIR = "output/plots"
SNS_THEME = "darkgrid"

# FORCE THE SCHEMA: Define what the columns are (Order matters!)
# Based on your logs: Time, Lat, Lon, Alt, Fix, Peak, Noise, ...
LOG_COLUMNS = [
    'timestamp', 'lat', 'lon', 'alt', 'fix',
    'peak_signal', 'noise', 'messages', 'aircraft'
]

SENSOR_MAP = {
    '2': 'sensor-west',
    '3': 'sensor-east',
    'sensor-north': 'sensor-north',
    'sensor-east': 'sensor-east',
    'sensor-west': 'sensor-west'
}

sns.set_theme(style=SNS_THEME, context="talk")
plt.rcParams['figure.figsize'] = [16, 14]

def load_data():
    search_path = f"{DATA_DIR}/**/*stats_log_*.csv"
    all_files = glob.glob(search_path, recursive=True)
    
    print(f"[LOAD] Scanning '{DATA_DIR}'... Found {len(all_files)} log files.")
    
    dfs = []
    for filename in all_files:
        try:
            # FORCE HEADERS: Use 'names' to inject column labels
            # 'header=None' tells Pandas the first row is data, not labels
            df = pd.read_csv(filename, names=LOG_COLUMNS, header=None, on_bad_lines='skip')
            
            # Identity extraction
            basename = os.path.basename(filename)
            raw_id = basename.split('_')[0] 
            sensor_name = SENSOR_MAP.get(raw_id, raw_id)
            
            # Data Type Enforcement
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df['peak_signal'] = pd.to_numeric(df['peak_signal'], errors='coerce')
            df['noise'] = pd.to_numeric(df['noise'], errors='coerce')
            df['sensor'] = sensor_name
            
            dfs.append(df)
            
        except Exception as e:
            print(f"   [WARN] Skipping {filename}: {e}")

    if not dfs:
        return pd.DataFrame()

    master_df = pd.concat(dfs, ignore_index=True)
    master_df.dropna(subset=['timestamp', 'peak_signal'], inplace=True)
    master_df.sort_values('timestamp', inplace=True)
    return master_df

def plot_signal_physics(df):
    """Generates the Signal vs Noise 'Medical Chart'."""
    # Create 2 subplots sharing the X-axis
    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(16, 12))
    
    # --- PLOT 1: PEAK SIGNAL (The Ceiling) ---
    sns.lineplot(data=df, x='timestamp', y='peak_signal', hue='sensor', ax=ax1, linewidth=2)
    
    # Visual Guide: The "Red Zone"
    ax1.axhspan(-3, 0, color='red', alpha=0.1, label='Clipping Zone')
    ax1.axhline(-3, color='red', linestyle='--', alpha=0.5)
    
    ax1.set_title("RF Signal Integrity: Peak Signal (Target: < -3 dBFS)")
    ax1.set_ylabel("Peak Signal (dBFS)")
    ax1.set_ylim(-35, 1) # Standard RF range
    ax1.legend(loc='lower left')
    ax1.grid(True, which='both', linestyle='--', linewidth=0.5)

    # --- PLOT 2: NOISE FLOOR (The Basement) ---
    sns.lineplot(data=df, x='timestamp', y='noise', hue='sensor', ax=ax2, linewidth=2)
    
    ax2.set_title("RF Environment: Noise Floor (Lower is Better)")
    ax2.set_ylabel("Noise (dBFS)")
    # ax2.set_ylim(-50, -10) # Typical noise range
    
    # Format Time Axis
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax2.set_xlabel("Time (UTC)")
    
    plt.tight_layout()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    save_path = f"{OUTPUT_DIR}/scientific_signal_analysis_{timestamp}.png"
    plt.savefig(save_path, dpi=300)
    print(f"[PLOT] ✅ Saved Analysis -> {save_path}")

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    print("===================================================")
    print("   SCIENTIFIC PLOTTING ENGINE | v1.4")
    print("===================================================")
    
    df = load_data()
    
    if not df.empty:
        plot_signal_physics(df)
    else:
        print("   [ERR] No valid data loaded.")

if __name__ == "__main__":
    main()
