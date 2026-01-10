"""
ADS-B Research Grid - GNSS Scientific Audit (Master Edition)
------------------------------------------------------------
Version: v2.0 (NMEA Native)
Features:
  - Meter-level Drift Analysis (ENU Conversion)
  - CEP50 / R95 Accuracy Rings
  - Signal Health Tracking (HDOP / Satellite Counts)
  - Static Hold Detection
"""

import argparse
import glob
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import seaborn as sns
from datetime import datetime, timedelta

# --- Configuration ---
sns.set_theme(style="whitegrid", context="paper")
OUTPUT_DIR = "analysis/gnss_master"

# Constants for WGS84
METERS_PER_DEG_LAT = 111320.0

def nmea_to_decimal(value, direction):
    """Converts NMEA ddmm.mmmmm to decimal degrees."""
    if not value or value == '': return None
    try:
        dot_pos = value.find('.')
        if dot_pos == -1: return None
        degrees_len = dot_pos - 2
        if degrees_len < 1: return None
        degrees = float(value[:degrees_len])
        minutes = float(value[degrees_len:])
        decimal = degrees + (minutes / 60.0)
        if direction in ['S', 'W']: decimal = -decimal
        return decimal
    except: return None

def parse_logs(input_dir):
    files = sorted(glob.glob(os.path.join(input_dir, "raw_gnss_*.log")))
    if not files: return pd.DataFrame()
    
    print(f"[INFO] Ingesting {len(files)} logs...")
    data = []
    
    # Track date from RMC to apply to GGA
    current_date = None

    for filepath in files:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line.startswith('$'): continue
                parts = line.split(',')
                msg = parts[0][3:] # RMC, GGA
                
                try:
                    # GNRMC: Date & coarse pos
                    if msg == 'RMC' and parts[2] == 'A':
                        if parts[9]: current_date = parts[9] # DDMMYY
                    
                    # GNGGA: Precision pos, Alt, Sats, HDOP
                    elif msg == 'GGA' and int(parts[6]) > 0:
                        ts_str = parts[1]
                        lat = nmea_to_decimal(parts[2], parts[3])
                        lon = nmea_to_decimal(parts[4], parts[5])
                        n_sats = int(parts[7])
                        hdop = float(parts[8]) if parts[8] else 0.0
                        alt = float(parts[9]) if parts[9] else None
                        
                        # Build Timestamp
                        dt = datetime.now() # Fallback
                        if current_date and ts_str:
                            dt_str = f"{current_date} {ts_str}"
                            try:
                                dt = datetime.strptime(dt_str, "%d%m%y %H%M%S.%f")
                            except: pass

                        if lat and lon:
                            data.append({
                                'datetime': dt,
                                'lat': lat,
                                'lon': lon,
                                'alt': alt,
                                'sats': n_sats,
                                'hdop': hdop
                            })
                except (ValueError, IndexError): pass

    return pd.DataFrame(data)

def calculate_error_metrics(df):
    # Calculate Mean Center
    mean_lat = df['lat'].mean()
    mean_lon = df['lon'].mean()
    
    # Approx conversion to meters (valid for small drift)
    meters_per_deg_lon = METERS_PER_DEG_LAT * np.cos(np.radians(mean_lat))
    
    df['north_m'] = (df['lat'] - mean_lat) * METERS_PER_DEG_LAT
    df['east_m'] = (df['lon'] - mean_lon) * meters_per_deg_lon
    df['radial_error'] = np.sqrt(df['north_m']**2 + df['east_m']**2)
    
    cep50 = np.percentile(df['radial_error'], 50)
    r95 = np.percentile(df['radial_error'], 95)
    
    return df, mean_lat, mean_lon, cep50, r95

def generate_report(df, mean_lat, mean_lon, cep50, r95):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # PAGE 1: Position Accuracy (Meters)
    fig, ax = plt.subplots(figsize=(10, 10))
    sns.scatterplot(x='east_m', y='north_m', data=df, alpha=0.2, color='navy', s=15, ax=ax, label='Samples')
    
    # Draw Accuracy Rings
    circle50 = patches.Circle((0, 0), cep50, linewidth=2, edgecolor='orange', facecolor='none', label=f'CEP50: {cep50:.2f}m')
    circle95 = patches.Circle((0, 0), r95, linewidth=2, edgecolor='red', facecolor='none', label=f'R95: {r95:.2f}m')
    ax.add_patch(circle50)
    ax.add_patch(circle95)
    
    ax.set_title(f"GNSS Position Scatter (Meters)\nMean Lat/Lon: {mean_lat:.6f}, {mean_lon:.6f}", fontsize=14)
    ax.set_xlabel("East Offset (m)")
    ax.set_ylabel("North Offset (m)")
    ax.axis('equal')
    ax.grid(True, which='both', linestyle='--', alpha=0.5)
    ax.legend(loc='upper right')
    
    plt.savefig(f"{OUTPUT_DIR}/1_Position_Accuracy.png")
    
    # PAGE 2: Signal Health (Sats & HDOP)
    fig, axes = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    sns.lineplot(x='datetime', y='sats', data=df, ax=axes[0], color='green', drawstyle='steps-post')
    axes[0].set_title("Satellite Visibility (Constellation Health)")
    axes[0].set_ylabel("Satellites Locked")
    
    sns.lineplot(x='datetime', y='hdop', data=df, ax=axes[1], color='purple')
    axes[1].set_title("HDOP (Precision Dilution - Lower is Better)")
    axes[1].set_ylabel("HDOP Value")
    
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/2_Signal_Health.png")

    # PAGE 3: Stability & Drift
    fig, axes = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    df['alt_smooth'] = df['alt'].rolling(window=10).mean()
    sns.lineplot(x='datetime', y='alt', data=df, ax=axes[0], alpha=0.3, color='gray', label='Raw')
    if not df['alt_smooth'].isna().all():
        sns.lineplot(x='datetime', y='alt_smooth', data=df, ax=axes[0], color='blue', label='Smoothed (10s)')
    axes[0].set_title(f"Altitude Stability (StdDev: {df['alt'].std():.3f}m)")
    axes[0].set_ylabel("Altitude (m)")
    
    sns.lineplot(x='datetime', y='radial_error', data=df, ax=axes[1], color='red', alpha=0.6)
    axes[1].set_title("Radial Error from Mean over Time")
    axes[1].set_ylabel("Error (m)")
    
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/3_Stability.png")

    # MARKDOWN REPORT
    with open(f"{OUTPUT_DIR}/AUDIT_SUMMARY.md", "w") as f:
        f.write("# 🛰️ GNSS Sensor Audit Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"**Total Samples:** {len(df):,}\n\n")
        
        f.write("## 1. Accuracy Metrics\n")
        f.write(f"- **CEP50 (50% Confidence):** {cep50:.3f} meters\n")
        f.write(f"- **R95 (95% Confidence):** {r95:.3f} meters\n")
        f.write(f"- **Max Drift:** {df['radial_error'].max():.3f} meters\n\n")
        
        f.write("## 2. Signal Health\n")
        f.write(f"- **Avg Satellites:** {df['sats'].mean():.1f}\n")
        f.write(f"- **Avg HDOP:** {df['hdop'].mean():.2f}\n")
        f.write(f"- **Altitude StdDev:** {df['alt'].std():.4f} m\n\n")
        
        if df['alt'].std() < 0.01:
            f.write("> ⚠️ **WARNING: STATIC HOLD DETECTED**\n")
            f.write("> The Altitude Standard Deviation is near zero. The receiver is likely in 'Static Navigation' mode, masking small movements.\n")

    print(f"[SUCCESS] Analysis complete. Reports saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="./research_data/raw_logs")
    args = parser.parse_args()
    
    df = parse_logs(args.dir)
    if not df.empty:
        df_proc, mean_lat, mean_lon, cep50, r95 = calculate_error_metrics(df)
        generate_report(df_proc, mean_lat, mean_lon, cep50, r95)
    else:
        print("[!] No data found.")
