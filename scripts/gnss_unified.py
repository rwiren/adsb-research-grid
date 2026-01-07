"""
ADS-B Research Grid - Scientific GNSS Dashboard
-----------------------------------------------
Generates a comprehensive "Stability Dashboard" correlating:
  1. Nanosecond Timing Jitter (PPS)
  2. Position Drift (CEP Analysis)
  3. Temporal Stability (Time Series)
"""

import argparse
import glob
import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import Circle
from datetime import datetime

# Formatting
sns.set_theme(style="whitegrid", context="paper")
OUTPUT_DIR = "analysis/gnss_unified"

def nmea_to_decimal(value, direction):
    """Converts NMEA ddmm.mmmmm to decimal degrees."""
    if not value or value == '': return None
    try:
        dot_pos = value.find('.')
        if dot_pos == -1: return None
        degrees_len = dot_pos - 2
        degrees = float(value[:degrees_len])
        minutes = float(value[degrees_len:])
        decimal = degrees + (minutes / 60.0)
        if direction in ['S', 'W']: decimal = -decimal
        return decimal
    except: return None

def parse_dataset(input_dir):
    files = sorted(glob.glob(os.path.join(input_dir, "raw_gnss_*")))
    print(f"[INFO] Scanning {len(files)} files in {input_dir}...")
    
    pps_data = []
    pos_data = []
    
    for f in files:
        is_json = f.endswith('.json')
        try:
            with open(f, 'r') as h:
                for line in h:
                    line = line.strip()
                    if not line: continue
                    
                    if is_json:
                        try:
                            if not line.startswith('{'): continue
                            entry = json.loads(line)
                            
                            # PPS Timing (Nanoseconds)
                            if entry.get('class') == 'PPS':
                                pps_data.append({
                                    'ts': entry.get('real_sec'), # UNIX Timestamp
                                    'real_sec': entry.get('real_sec'),
                                    'real_nsec': entry.get('real_nsec'),
                                    'clock_sec': entry.get('clock_sec'),
                                    'clock_nsec': entry.get('clock_nsec')
                                })
                            
                            # TPV Position (Lat/Lon)
                            elif entry.get('class') == 'TPV' and entry.get('mode', 0) >= 2:
                                # Parse ISO timestamp to UNIX for syncing
                                t_str = entry.get('time', '')
                                if t_str:
                                    # Handle ISO8601 variations (Z)
                                    dt = datetime.strptime(t_str.split('.')[0], "%Y-%m-%dT%H:%M:%S")
                                    ts = dt.timestamp()
                                else:
                                    ts = 0
                                    
                                pos_data.append({
                                    'ts': ts,
                                    'lat': entry.get('lat'),
                                    'lon': entry.get('lon'),
                                    'source': 'JSON'
                                })
                        except: pass
                    else:
                        # NMEA Legacy Parsing
                        if line.startswith('$GNGGA') or line.startswith('$GPGGA'):
                            parts = line.split(',')
                            try:
                                if int(parts[6]) > 0:
                                    lat = nmea_to_decimal(parts[2], parts[3])
                                    lon = nmea_to_decimal(parts[4], parts[5])
                                    if lat and lon:
                                        # NMEA has time but no date. Approx logic or skip TS for now.
                                        pos_data.append({'ts': 0, 'lat': lat, 'lon': lon, 'source': 'NMEA'})
                            except: pass
        except: pass

    return pd.DataFrame(pps_data), pd.DataFrame(pos_data)

def generate_dashboard(df_pps, df_pos):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 2)
    
    # --- 1. TIMING JITTER HISTOGRAM (Top Left) ---
    ax1 = fig.add_subplot(gs[0, 0])
    jitter_std = 0
    if not df_pps.empty:
        df_pps['diff_sec'] = df_pps['clock_sec'] - df_pps['real_sec']
        df_pps['diff_nsec'] = df_pps['clock_nsec'] - df_pps['real_nsec']
        df_pps['jitter_us'] = (df_pps['diff_sec'] * 1000000) + (df_pps['diff_nsec'] / 1000.0)
        
        jitter_std = df_pps['jitter_us'].std()
        sns.histplot(df_pps['jitter_us'], kde=True, bins=50, color='teal', ax=ax1)
        ax1.set_title(f"A. Timing Stability (Jitter)\nStdDev: {jitter_std:.3f} µs")
        ax1.set_xlabel("Offset (microseconds)")
    
    # --- 2. CEP TARGET PLOT (Top Right) ---
    ax2 = fig.add_subplot(gs[0, 1])
    cep_50, cep_95 = 0, 0
    if not df_pos.empty:
        mean_lat = df_pos['lat'].mean()
        mean_lon = df_pos['lon'].mean()
        meters_per_lat = 111320
        meters_per_lon = 111320 * np.cos(np.radians(mean_lat))
        
        df_pos['north_m'] = (df_pos['lat'] - mean_lat) * meters_per_lat
        df_pos['east_m'] = (df_pos['lon'] - mean_lon) * meters_per_lon
        
        # Calculate Distance from Mean
        df_pos['dist_m'] = np.sqrt(df_pos['north_m']**2 + df_pos['east_m']**2)
        cep_50 = np.percentile(df_pos['dist_m'], 50)
        cep_95 = np.percentile(df_pos['dist_m'], 95)
        
        # Plot Scatter
        sns.scatterplot(x='east_m', y='north_m', data=df_pos, hue='source', alpha=0.5, s=15, ax=ax2)
        
        # Draw CEP Rings
        c50 = Circle((0, 0), cep_50, color='green', fill=False, lw=2, linestyle='--', label=f'CEP-50 ({cep_50:.2f}m)')
        c95 = Circle((0, 0), cep_95, color='red', fill=False, lw=2, linestyle='--', label=f'CEP-95 ({cep_95:.2f}m)')
        ax2.add_patch(c50)
        ax2.add_patch(c95)
        
        # Center Crosshair
        ax2.plot(0, 0, 'k+', markersize=15, markeredgewidth=2)
        
        limit = max(cep_95 * 1.5, 2) # Ensure we see at least 2m
        ax2.set_xlim(-limit, limit)
        ax2.set_ylim(-limit, limit)
        ax2.set_aspect('equal')
        ax2.legend(loc='upper right')
        ax2.set_title(f"B. Position Drift (CEP Analysis)\n50% within {cep_50:.2f}m")
        ax2.set_xlabel("East Error (meters)")
        ax2.set_ylabel("North Error (meters)")

    # --- 3. TEMPORAL STABILITY (Bottom Row - Shared X Axis) ---
    ax3 = fig.add_subplot(gs[1, :])
    
    # Plot 1: Jitter over Time (Left Axis)
    if not df_pps.empty:
        # Normalize time to start at 0 (Elapsed Minutes)
        start_time = df_pps['ts'].min()
        df_pps['elapsed_min'] = (df_pps['ts'] - start_time) / 60.0
        
        sns.lineplot(x='elapsed_min', y='jitter_us', data=df_pps, color='teal', alpha=0.6, label='Timing Jitter (µs)', ax=ax3)
        ax3.set_ylabel("Jitter (µs)", color='teal')
        ax3.tick_params(axis='y', labelcolor='teal')
    
    # Plot 2: Position Error over Time (Right Axis)
    if not df_pos.empty:
        ax4 = ax3.twinx()
        # Filter JSON only for time alignment
        json_pos = df_pos[df_pos['source'] == 'JSON'].copy()
        if not json_pos.empty:
            start_time_pos = json_pos['ts'].min()
            json_pos['elapsed_min'] = (json_pos['ts'] - start_time_pos) / 60.0
            
            sns.lineplot(x='elapsed_min', y='dist_m', data=json_pos, color='crimson', alpha=0.5, label='Position Error (m)', ax=ax4)
            ax4.set_ylabel("Pos Error (m)", color='crimson')
            ax4.tick_params(axis='y', labelcolor='crimson')
            ax4.set_ylim(0, max(5, json_pos['dist_m'].max() * 1.2))

    ax3.set_xlabel("Elapsed Time (Minutes)")
    ax3.set_title("C. Temporal Correlation: Timing Stability vs. Position Accuracy")
    
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/A_Scientific_Dashboard.png")
    print(f"[PLOT] Dashboard saved to {OUTPUT_DIR}/A_Scientific_Dashboard.png")

    # --- GENERATE TEXT REPORT ---
    with open(f"{OUTPUT_DIR}/REPORT_SUMMARY.md", "w") as f:
        f.write("# GNSS Sensor Baseline Report\n\n")
        f.write(f"**Date:** {datetime.now()}\n\n")
        f.write("## 1. Timing Stability (PPS)\n")
        if not df_pps.empty:
            f.write(f"- **Sample Count:** {len(df_pps)}\n")
            f.write(f"- **Mean Jitter:** {df_pps['jitter_us'].mean():.4f} µs\n")
            f.write(f"- **Std Dev:** {jitter_std:.4f} µs\n")
            f.write(f"- **Max Spike:** {df_pps['jitter_us'].abs().max():.4f} µs\n\n")
        else:
            f.write("No PPS data available.\n\n")
            
        f.write("## 2. Position Accuracy (CEP)\n")
        if not df_pos.empty:
            f.write(f"- **Sample Count:** {len(df_pos)}\n")
            f.write(f"- **CEP-50 (Median Error):** {cep_50:.4f} meters\n")
            f.write(f"- **CEP-95 (95% Confidence):** {cep_95:.4f} meters\n")
        else:
            f.write("No Position data available.\n")
    
    print(f"[REPORT] Stats saved to {OUTPUT_DIR}/REPORT_SUMMARY.md")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="./research_data/raw_logs")
    args = parser.parse_args()
    
    df_pps, df_pos = parse_dataset(args.dir)
    generate_dashboard(df_pps, df_pos)
