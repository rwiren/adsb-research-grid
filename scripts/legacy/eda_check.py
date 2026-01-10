#!/usr/bin/env python3
# ==============================================================================
# FILE: scripts/eda_check.py
# VERSION: 0.4.5 (CSV Edition)
# MAINTAINER: Data Science Team
# DATE: 2026-01-09
# ==============================================================================
# DESCRIPTION:
#   Performs Exploratory Data Analysis (EDA) on the latest fetched CSV datasets.
#   Generates a 4-panel scientific dashboard to validate sensor performance.
#
# FEATURES:
#   - Auto-Discovery: Finds the latest timestamped log file automatically.
#   - Physics Check: Validates Altitude/Speed distributions.
#   - Signal Check: Analyzes RSSI (Signal Strength) and Coverage.
# ==============================================================================

import glob
import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# --- CONFIGURATION ---
sns.set_theme(style="whitegrid")
# Output for visual reports
REPORT_DIR = "analysis/daily_reports"
# Input base directory
DATA_DIR = "research_data"

os.makedirs(REPORT_DIR, exist_ok=True)

# --- HELPER FUNCTIONS ---

def get_latest_log(node, log_type):
    """
    Scans the data directory to find the most recent log file for a specific node.
    Args:
        node (str): 'west' or 'north'
        log_type (str): 'aircraft', 'stats', or 'gnss'
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    # Pattern matches the dynamic timestamp format: hostname_type_YYYY-MM-DD_HHMM.csv
    hostname = f"sensor-{node}"
    search_path = f"{DATA_DIR}/{today}/{node}/{hostname}_{log_type}_log_{today}_*.csv"
    
    files = glob.glob(search_path)
    if not files:
        # Fallback: Try finding ANY file with that type if today's specific pattern fails
        fallback_path = f"{DATA_DIR}/*/{node}/*{log_type}*.csv"
        files = glob.glob(fallback_path)
    
    if not files:
        print(f"[WARN] No {log_type} logs found for {node} (Looked in: {search_path})")
        return None
        
    # Return the file with the highest creation time (newest)
    return max(files, key=os.path.getctime)

def generate_dashboard(df, node_name, date_str):
    """Generates the 4-panel Scientific Dashboard (Operational, Physics, Spatial, Signals)."""
    
    output_path = f"{REPORT_DIR}/eda_report_{date_str}.png"
    print(f"[GRAPHICS] Generating Dashboard for {node_name}...")

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle(f"ADS-B Sensor Audit: {node_name.upper()} | {date_str}", fontsize=16)

    # 1. TEMPORAL DENSITY (Messages per Minute)
    # Convert epoch timestamp to datetime
    df['dt'] = pd.to_datetime(df['timestamp'], unit='s')
    df.set_index('dt', inplace=True)
    
    resampled = df.resample('1min').size()
    resampled.plot(ax=axes[0, 0], color='navy', lw=1.5)
    axes[0, 0].set_title("Operational: Traffic Density (Msgs/min)")
    axes[0, 0].set_ylabel("Messages")

    # 2. SIGNAL STRENGTH (RSSI Distribution)
    if 'rssi' in df.columns:
        sns.histplot(df['rssi'], bins=30, kde=True, ax=axes[0, 1], color='purple')
        axes[0, 1].set_title("Signals: RSSI Distribution (dBFS)")
        axes[0, 1].set_xlabel("Signal Strength (RSSI)")

    # 3. SPATIAL COVERAGE (Lat/Lon Scatter)
    # Filter out invalid zeros for cleaner plots
    valid_pos = df[(df['lat'] != 0) & (df['lon'] != 0)]
    if not valid_pos.empty:
        sns.scatterplot(x='lon', y='lat', data=valid_pos, ax=axes[1, 0], alpha=0.3, s=15, color='teal')
        axes[1, 0].set_title("Spatial: Coverage Map")
        axes[1, 0].set_xlabel("Longitude")
        axes[1, 0].set_ylabel("Latitude")
    else:
        axes[1, 0].text(0.5, 0.5, "No Position Data", ha='center', va='center')

    # 4. PHYSICS PROFILE (Altitude vs Speed)
    if 'alt_baro' in df.columns and 'gs' in df.columns:
        # Hexbin plot for performance with large datasets
        hb = axes[1, 1].hexbin(df['gs'], df['alt_baro'], gridsize=30, cmap='inferno', mincnt=1)
        axes[1, 1].set_title("Physics: Altitude vs Ground Speed")
        axes[1, 1].set_xlabel("Ground Speed (kts)")
        axes[1, 1].set_ylabel("Altitude (ft)")
        cb = fig.colorbar(hb, ax=axes[1, 1])
        cb.set_label('Count')

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(output_path)
    print(f"[SUCCESS] Dashboard saved to: {output_path}")

# --- MAIN EXECUTION ---
def main():
    print(f"--- ADS-B Scientific Audit v0.4.5 ---")
    
    # We focus on West as the primary active sensor
    node = "west"
    
    # 1. DISCOVERY
    latest_aircraft = get_latest_log(node, "aircraft")
    latest_gnss     = get_latest_log(node, "gnss")
    
    if not latest_aircraft:
        print("[ERROR] No aircraft logs found. Aborting analysis.")
        sys.exit(1)

    print(f"[LOAD] Processing Aircraft Log: {os.path.basename(latest_aircraft)}")
    
    # 2. LOAD DATA
    try:
        df = pd.read_csv(latest_aircraft)
    except Exception as e:
        print(f"[ERROR] Corrupt CSV file: {e}")
        sys.exit(1)

    if df.empty:
        print("[WARN] Log file is empty. No analysis possible.")
        sys.exit(0)

    # 3. STATISTICAL SUMMARY
    print("\n--- 📊 Statistical Summary ---")
    print(f"Total Frames:       {len(df):,}")
    print(f"Unique Aircraft:    {df['hex'].nunique()}")
    print(f"Duration:           {(df['timestamp'].max() - df['timestamp'].min())/60:.1f} minutes")
    
    if 'rssi' in df.columns:
        print(f"Avg Signal (RSSI):  {df['rssi'].mean():.1f} dB")
    
    # 4. GNSS CROSS-CHECK (If available)
    if latest_gnss:
        print(f"\n[LOAD] Cross-checking GNSS Log: {os.path.basename(latest_gnss)}")
        df_gnss = pd.read_csv(latest_gnss)
        print(f"Sensor Fixes:       {len(df_gnss):,} (Modes: {df_gnss['mode'].unique()})")

    # 5. GENERATE VISUALS
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    generate_dashboard(df, node, today_str)

if __name__ == "__main__":
    main()
