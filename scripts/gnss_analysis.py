#!/usr/bin/env python3
# ------------------------------------------------------------------
# [FILE] scripts/gnss_analysis.py
# [VERSION] 1.9.0 (Strict Path Control)
# ------------------------------------------------------------------

import argparse
import json
import gzip
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import Circle
from pathlib import Path
from datetime import datetime

SEARCH_PATHS = [
    Path("research_data"), 
    Path("infra/ansible/playbooks/research_data/raw"),
    Path("infra/ansible/playbooks/research_data")
]

def nmea_to_decimal(value, direction):
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

def open_file(path):
    if path.endswith('.gz'):
        return gzip.open(path, 'rt', encoding='utf-8', errors='ignore')
    return open(path, 'r', encoding='utf-8', errors='ignore')

def load_data():
    gnss_files = []
    print("[GNSS] 🔍 Scanning for logs...")
    
    for base_dir in SEARCH_PATHS:
        abs_path = base_dir.resolve()
        if not abs_path.exists(): continue
        for root, dirs, files in os.walk(abs_path):
            for name in files:
                if "gnss" in name.lower() and ("log" in name.lower() or "raw" in name.lower()):
                    gnss_files.append(Path(os.path.join(root, name)))

    gnss_files = sorted(list(set(gnss_files)))
    
    pps_data = []
    pos_data = []
    
    for f in gnss_files:
        sid = "unknown"
        for part in f.parts:
            if part.startswith("sensor-"): sid = part; break
        
        try:
            # CSV (East/West)
            if "gnss_log" in f.name:
                try:
                    if f.suffix == '.gz':
                        with gzip.open(f, 'rt') as gf:
                            df = pd.read_csv(gf, on_bad_lines='skip')
                    else:
                        df = pd.read_csv(f, on_bad_lines='skip')
                    
                    df.columns = df.columns.str.lower().str.strip()
                    if 'lat' in df.columns and 'lon' in df.columns:
                        temp = df[['lat', 'lon']].copy()
                        temp['sensor_id'] = sid
                        temp['lat'] = pd.to_numeric(temp['lat'], errors='coerce')
                        temp['lon'] = pd.to_numeric(temp['lon'], errors='coerce')
                        pos_data.extend(temp.dropna().to_dict('records'))
                except: pass

            # Raw (North)
            elif "gnss_raw" in f.name:
                with open_file(str(f)) as h:
                    for line in h:
                        line = line.strip()
                        if not line: continue
                        if line.startswith('{') and 'class' in line:
                            try:
                                entry = json.loads(line)
                                if entry.get('class') == 'PPS':
                                    pps_data.append({
                                        'sensor_id': sid,
                                        'jitter_us': (entry.get('clock_sec',0) - entry.get('real_sec',0))*1e6 + (entry.get('clock_nsec',0) - entry.get('real_nsec',0))/1e3
                                    })
                                elif entry.get('class') == 'TPV' and entry.get('mode', 0) >= 2:
                                    pos_data.append({'sensor_id': sid, 'lat': entry.get('lat'), 'lon': entry.get('lon')})
                            except: pass
                        elif 'GGA' in line:
                            try:
                                nmea_part = line[line.find('$'):] 
                                parts = nmea_part.split(',')
                                if len(parts) > 6 and int(parts[6]) > 0: 
                                    lat = nmea_to_decimal(parts[2], parts[3])
                                    lon = nmea_to_decimal(parts[4], parts[5])
                                    if lat and lon:
                                        pos_data.append({'sensor_id': sid, 'lat': lat, 'lon': lon})
                            except: pass
        except: pass

    df_pps = pd.DataFrame(pps_data)
    df_pos = pd.DataFrame(pos_data)
    
    if not df_pos.empty:
        df_pos = df_pos[(df_pos['lat'].abs() > 1.0) & (df_pos['lon'].abs() > 1.0)]

    print("\n[GNSS] 📊 Data Extraction Audit:")
    print(f"{'Sensor ID':<15} | {'PPS Samples':<12} | {'Valid Fixes':<15}")
    print("-" * 46)
    all_sensors = set()
    if not df_pos.empty: all_sensors.update(df_pos['sensor_id'].unique())
    if not df_pps.empty: all_sensors.update(df_pps['sensor_id'].unique())
    for s in sorted(all_sensors):
        n_pps = len(df_pps[df_pps['sensor_id'] == s]) if not df_pps.empty else 0
        n_pos = len(df_pos[df_pos['sensor_id'] == s]) if not df_pos.empty else 0
        print(f"{s:<15} | {n_pps:<12} | {n_pos:<15}")
    print("-" * 46 + "\n")

    return df_pps, df_pos

def generate_plot(df_pps, df_pos, output_dir):
    # Ensure output directory exists (script does NOT append 'figures' anymore)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    plt.style.use('seaborn-v0_8-paper')
    fig = plt.figure(figsize=(14, 6))
    gs = fig.add_gridspec(1, 2)
    t_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    ax1 = fig.add_subplot(gs[0, 0])
    if not df_pps.empty:
        clean = df_pps[df_pps['jitter_us'].abs() < 500]
        if not clean.empty:
            sns.kdeplot(data=clean, x='jitter_us', hue='sensor_id', fill=True, ax=ax1)
            ax1.set_title("A. Timing Precision (PPS Jitter)")
            ax1.set_xlim(-50, 50); ax1.grid(True, alpha=0.3)
        else: ax1.text(0.5, 0.5, "Data > 500µs Jitter", ha='center')
    else: ax1.text(0.5, 0.5, "No PPS Data Available", ha='center')

    ax2 = fig.add_subplot(gs[0, 1])
    if not df_pos.empty:
        df_pos['lat_mean'] = df_pos.groupby('sensor_id')['lat'].transform('mean')
        df_pos['lon_mean'] = df_pos.groupby('sensor_id')['lon'].transform('mean')
        df_pos['north_m'] = (df_pos['lat'] - df_pos['lat_mean']) * 111320
        df_pos['east_m'] = (df_pos['lon'] - df_pos['lon_mean']) * 55800 
        
        df_clean = df_pos[(df_pos['north_m'].abs() < 100) & (df_pos['east_m'].abs() < 100)]
        if not df_clean.empty:
            sns.scatterplot(data=df_clean.sample(n=min(5000, len(df_clean))), x='east_m', y='north_m', hue='sensor_id', alpha=0.5, ax=ax2)
            ax2.add_patch(Circle((0, 0), 2.5, color='red', fill=False, linestyle='--', label='2.5m Spec'))
            ax2.set_xlim(-10, 10); ax2.set_ylim(-10, 10); ax2.set_aspect('equal')
            ax2.set_title("B. Position Drift (Zero-Centered)")
            ax2.grid(True, alpha=0.3); ax2.legend(loc='upper right')
        else: ax2.text(0.5, 0.5, ">100m Drift (Out of Bounds)", ha='center')

    plt.suptitle(f"D12: Hardware Certification (GNSS) | {t_str}", fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_dir / "D12_GNSS_Precision.png")
    print(f"[GNSS] ✅ Saved {output_dir}/D12_GNSS_Precision.png")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    df_pps, df_pos = load_data()
    generate_plot(df_pps, df_pos, args.out_dir)
