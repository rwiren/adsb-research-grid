#!/usr/bin/env python3
# ==============================================================================
# File: scripts/generate_showcase.py
# Description: Generates High-Res "Hero" images for documentation/website.
# ==============================================================================

import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import warnings

warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid", context="paper") 

# CONFIG
DATA_DIR = "research_data"
OUTPUT_DIR = "docs/showcase"

def load_master_data(sensor_path, log_type):
    """Robustly loads the MASTER csv for a specific log type."""
    pattern = os.path.join(sensor_path, f"*_{log_type}_MASTER_*.csv")
    files = glob.glob(pattern)
    if not files: return None
    
    try:
        df = pd.read_csv(files[0])
        time_cols = [c for c in df.columns if 'time' in c.lower() or 'now' in c.lower()]
        if time_cols:
            col = time_cols[0]
            df[col] = pd.to_datetime(df[col], unit='s', errors='coerce') 
            df = df.dropna(subset=[col]).sort_values(by=col)
            df = df.drop_duplicates(subset=[col], keep='first')
            df.set_index(col, inplace=True)
        return df
    except: return None

def create_hero_plots():
    print("🎨 Generating High-Res Showcase Artifacts...")
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    # Dynamically find the latest date and valid sensor folder
    dates = sorted([d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))])
    if not dates: 
        print("   ⚠️ No data directories found.")
        return

    target_date = dates[-1]
    
    # Try to find a sensor with actual aircraft data
    target_sensor_path = None
    df_air = None
    
    date_path = os.path.join(DATA_DIR, target_date)
    sensors = [s for s in os.listdir(date_path) if os.path.isdir(os.path.join(date_path, s))]
    
    # Prioritize sensor-west, then search others
    priority_order = ["sensor-west", "west", "sensor-north", "sensor-east"]
    sensors.sort(key=lambda x: priority_order.index(x) if x in priority_order else 99)

    for sensor in sensors:
        path = os.path.join(date_path, sensor)
        temp_df = load_master_data(path, "aircraft")
        if temp_df is not None and not temp_df.empty:
            target_sensor_path = path
            df_air = temp_df
            print(f"   🔹 Using data from: {sensor} ({target_date})")
            break
    
    if df_air is None:
        print("   ⚠️ No aircraft data found in latest logs to generate showcase.")
        return

    # =========================================================
    # 1. SMART TRAFFIC PLOT (Better Time Axis)
    # =========================================================
    fig, ax = plt.subplots(figsize=(10, 5))
    msg_rate = df_air.resample('1min').size()
    
    ax.plot(msg_rate.index, msg_rate.values, color='royalblue', linewidth=2, label='Msgs/Min')
    ax.fill_between(msg_rate.index, msg_rate.values, color='royalblue', alpha=0.1)
    
    # Smart Time Formatting (HH:MM)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    
    ax.set_title(f"ADS-B Message Ingestion Rate ({target_date})", fontsize=14, weight='bold')
    ax.set_ylabel("Messages per Minute", fontsize=12)
    ax.set_xlabel("Time (UTC)", fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "Showcase_Traffic_Rate.png"), dpi=300)
    print("   ✅ Generated: Showcase_Traffic_Rate.png (Smart Axis)")
    plt.close()

    # =========================================================
    # 2. THE "SCIENTIFIC DASHBOARD" (Combined View)
    # =========================================================
    # Layout: 1 Row, 3 Columns (Traffic | RSSI | Altitude)
    fig = plt.figure(figsize=(18, 6))
    gs = fig.add_gridspec(1, 3)
    fig.suptitle(f"ADS-B Sensor Network: Operational Dashboard ({target_date})", fontsize=16, weight='bold')

    # Panel A: Traffic Rate
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(msg_rate.index, msg_rate.values, color='#1f77b4', linewidth=2)
    ax1.fill_between(msg_rate.index, msg_rate.values, color='#1f77b4', alpha=0.1)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.set_title("A. Traffic Volume (Msgs/Min)", fontsize=12, weight='bold')
    ax1.set_ylabel("Count")
    ax1.grid(True, alpha=0.5)

    # Panel B: Signal Strength (RSSI)
    ax2 = fig.add_subplot(gs[0, 1])
    if 'rssi' in df_air.columns:
        sns.histplot(data=df_air, x='rssi', bins=40, kde=True, ax=ax2, color='#ff7f0e', element="step", alpha=0.6)
        ax2.set_title("B. Signal Strength Distribution", fontsize=12, weight='bold')
        ax2.set_xlabel("RSSI (dBFS)")
        ax2.set_ylabel("Frequency")

    # Panel C: Altitude Profile
    ax3 = fig.add_subplot(gs[0, 2])
    if 'alt_baro' in df_air.columns:
        alts = pd.to_numeric(df_air['alt_baro'], errors='coerce').dropna()
        if not alts.empty:
            sns.histplot(alts, bins=40, ax=ax3, color='#2ca02c', element="poly", alpha=0.6)
            ax3.set_title("C. Vertical Profile (Altitude)", fontsize=12, weight='bold')
            ax3.set_xlabel("Altitude (ft)")
            ax3.set_ylabel("Count")
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(os.path.join(OUTPUT_DIR, "Showcase_Scientific_Dashboard.png"), dpi=300)
    print("   ✅ Generated: Showcase_Scientific_Dashboard.png (Combined)")
    plt.close()

if __name__ == "__main__":
    create_hero_plots()
