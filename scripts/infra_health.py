#!/usr/bin/env python3
# ------------------------------------------------------------------
# [FILE] scripts/infra_health.py
# [VERSION] 3.1.0 (Stats in Legend & Safe Zones)
# ------------------------------------------------------------------

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import argparse
from pathlib import Path
from datetime import datetime

BASE_DIR = Path("research_data")
SENSORS = {
    "sensor-north": "#003f5c", 
    "sensor-east":  "#bc5090", 
    "sensor-west":  "#ffa600"
}

# Capacity Limits (GB)
STORAGE_LIMITS = {
    "sensor-east": 16,
    "sensor-north": 32,
    "sensor-west": 64
}

def load_health_data():
    print("[INFRA] 🔍 Scanning for Health & Storage logs...")
    files_hw = list(BASE_DIR.rglob("*hardware_health.csv"))
    files_st = list(BASE_DIR.rglob("*storage_history.csv"))
    
    dfs = []
    for f in files_hw + files_st:
        try:
            sid = "unknown"
            for part in f.parts:
                if part.startswith("sensor-"): sid = part; break
            
            df = pd.read_csv(f, on_bad_lines='skip')
            df.columns = df.columns.str.lower().str.strip()
            df['sensor_id'] = sid
            dfs.append(df)
        except: pass
    
    if not dfs: return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)
    
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', utc=True)
    
    for col in ['temp_c', 'disk_used_kb']:
        if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
            
    print(f"[INFRA] ✅ Loaded {len(df)} records from: {df['sensor_id'].unique()}")
    return df

def generate_dashboard(df, output_dir):
    if df.empty: return
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    
    plt.style.use('seaborn-v0_8-paper')
    plt.rcParams.update({'figure.dpi': 150})
    
    # Combined Dashboard: 2 Rows, 1 Column, Shared X-Axis
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10), sharex=True)
    t_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    fig.suptitle(f"D5: Infrastructure Health Dashboard\nGenerated: {t_str}", fontweight='bold')

    # --- Subplot 1: Thermal ---
    if 'temp_c' in df.columns:
        print("[INFRA] 🎨 Generating Thermal Subplot (with stats)...")
        
        # Calculate Stats for Legend
        stats = df.groupby('sensor_id')['temp_c'].agg(['mean', 'max'])
        
        for sid in df['sensor_id'].unique():
            if sid not in SENSORS: continue
            subset = df[df['sensor_id'] == sid].dropna(subset=['temp_c'])
            if subset.empty: continue
            
            # Format Legend Label
            avg_t = stats.loc[sid, 'mean']
            max_t = stats.loc[sid, 'max']
            label = f"{sid.replace('sensor-', '').title()} (Avg:{avg_t:.1f}°C, Max:{max_t:.1f}°C)"
            
            sns.lineplot(data=subset, x='timestamp', y='temp_c', color=SENSORS[sid], ax=ax1, label=label)

        # Reference Lines & Bands
        ax1.axhline(60, color='red', linestyle='--', alpha=0.8, label='Warning (60°C)')
        ax1.axhspan(30, 60, color='green', alpha=0.05, label='Nominal Range')
        
        ax1.set_title("CPU Thermal Performance")
        ax1.set_ylabel("Temp (°C)")
        ax1.legend(loc='upper left', fontsize=8)
        ax1.grid(True, alpha=0.3)

    # --- Subplot 2: Storage ---
    if 'disk_used_kb' in df.columns:
        print("[INFRA] 🎨 Generating Storage Subplot...")
        df['disk_gb'] = df['disk_used_kb'] / 1024 / 1024
        sns.lineplot(data=df.dropna(subset=['disk_gb']), x='timestamp', y='disk_gb', hue='sensor_id', palette=SENSORS, ax=ax2, legend=False)
        
        # Add Capacity Lines
        for sid, limit in STORAGE_LIMITS.items():
            if sid in df['sensor_id'].unique():
                color = SENSORS.get(sid, 'gray')
                ax2.axhline(limit, color=color, linestyle=':', alpha=0.6)
                ax2.text(df['timestamp'].min(), limit, f" {sid.split('-')[1].title()} ({limit}GB)", color=color, va='bottom', fontsize=8)
        
        ax2.set_title("Storage Consumption")
        ax2.set_ylabel("Disk Used (GB)")
        ax2.grid(True, alpha=0.3)

    # Common Formatting
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax2.tick_params(axis='x', rotation=45)
    plt.tight_layout()
    plt.savefig(fig_dir / "D5_Infrastructure_Health.png")
    plt.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    df = load_health_data()
    generate_dashboard(df, args.out_dir)
