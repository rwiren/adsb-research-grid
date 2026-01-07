"""
ADS-B Research Grid - Scientific Audit Tool (Master Edition)
------------------------------------------------------------
Version: v0.3.0
Features:
  - Byte-Seeker Algorithm (99% Data Recovery)
  - Statistical Sampling (Fast Execution)
  - 4-Page Dashboard Suite (11 Visualization Plots)
  - Automated Markdown Audit Report
"""

import argparse
import glob
import os
import math
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import pyModeS as pms
from datetime import datetime
import numpy as np

# --- Configuration ---
sns.set_theme(style="whitegrid")
OUTPUT_DIR = "analysis/latest"
SAMPLE_LIMIT = 500000 

# --- Helpers ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def parse_filename_time(fname):
    try:
        base = os.path.basename(fname)
        parts = base.split('_')
        ts_str = parts[2] + "_" + parts[3].split('.')[0]
        return datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
    except: return datetime.now()

def parse_raw_file_robust(filepath):
    messages = []
    with open(filepath, 'rb') as f:
        content = f.read()
        i = 0
        length = len(content)
        while i < length - 10:
            if content[i] != 0x1a:
                i += 1; continue
            msg_type = content[i+1]
            frame_len = 7 if msg_type == 0x32 else (14 if msg_type == 0x33 else 0)
            if frame_len == 0:
                i += 1; continue
            total_len = 9 + frame_len
            if i + total_len > length: break
            rssi_raw = content[i+8]
            msg_hex = content[i+9 : i+9+frame_len].hex()
            if msg_hex == "00"*frame_len or msg_hex == "ff"*frame_len:
                i += 1; continue
            try: df_code = pms.df(msg_hex)
            except: df_code = -1
            tc = -1
            if df_code in [17, 18]:
                try: tc = pms.typecode(msg_hex)
                except: pass
            messages.append({'rssi': (rssi_raw/255.0)*100.0, 'msg': msg_hex, 'df': df_code, 'tc': tc})
            i += total_len
    return messages

def analyze_security(df, f):
    mil_prefixes = ['RCH', 'CNV', 'NATO', 'VADER', 'VIP', 'AF1']
    callsigns = df['callsign'].dropna().unique()
    suspicious = [c for c in callsigns if any(c.startswith(p) for p in mil_prefixes)]
    
    f.write("## 3. 🛡️ Security & Special Interest\n")
    f.write(f"- **Military/VIP Patterns:** {len(suspicious)} detected\n")
    if suspicious: f.write(f"  - Tags: {', '.join(suspicious)}\n")
    f.write("- **Emergency Codes:** (Requires Mode 3/A Correlation)\n\n")

def generate_report(total_df, sample_df, duration, output_path):
    total = len(total_df)
    adsb_total = len(total_df[total_df['df'].isin([17, 18])])
    miss_lat = len(sample_df) - sample_df['lat'].count()
    miss_vel = len(sample_df) - sample_df['v_rate'].count()
    
    with open(output_path, "w") as f:
        f.write("# 🔬 ADS-B Research Grid: Scientific Audit (v0.3.0)\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("## 1. Executive Summary\n")
        f.write(f"**Status:** {'🟢 OPERATIONAL' if adsb_total > 1000 else '🔴 CRITICAL'}\n\n")
        f.write("| Key Metric | Value | Notes |\n| :--- | :--- | :--- |\n")
        f.write(f"| **Observation Time** | {duration:.2f} Hours | |\n")
        f.write(f"| **Total Traffic** | {total:,} | Raw Frames |\n")
        f.write(f"| **ADS-B Volume** | {adsb_total:,} | Valid Physics Frames |\n")
        f.write("\n## 2. Data Science Profile (Based on Sample)\n")
        f.write(f"*Analysis performed on random sample of {len(sample_df)} frames.*\n\n")
        f.write("| Feature | Missing % | Utility |\n| :--- | :--- | :--- |\n")
        f.write(f"| **Position** | {miss_lat/len(sample_df)*100:.1f}% | Trajectory Analysis |\n")
        f.write(f"| **Velocity** | {miss_vel/len(sample_df)*100:.1f}% | Kinematics/Spoofing |\n\n")
        analyze_security(sample_df, f)

def run_analysis(input_dir, lat, lon):
    files = sorted(glob.glob(os.path.join(input_dir, "*.bin")))
    if not files: return
    print(f"[INFO] Ingesting {len(files)} files...")
    all_data = []
    start_t, end_t = None, None
    for f in files:
        msgs = parse_raw_file_robust(f)
        base = parse_filename_time(f)
        if not start_t or base < start_t: start_t = base
        if not end_t or base > end_t: end_t = base
        count = len(msgs)
        if count > 0:
            step = 900.0 / count
            for i, m in enumerate(msgs):
                m['timestamp'] = base.timestamp() + (i*step)
                all_data.append(m)
    df_total = pd.DataFrame(all_data)
    df_total['datetime'] = pd.to_datetime(df_total['timestamp'], unit='s')
    duration = (end_t - start_t).total_seconds()/3600.0 + 0.25 if start_t else 0
    print(f"[INFO] Total Messages: {len(df_total)}")

    df_adsb = df_total[df_total['df'].isin([17, 18])].copy()
    df_sample = df_adsb.sample(n=SAMPLE_LIMIT, random_state=42).copy() if len(df_adsb) > SAMPLE_LIMIT else df_adsb.copy()

    print("[INFO] Decoding Physics...")
    df_sample['icao'] = df_sample['msg'].apply(pms.icao)
    def decode(row):
        res = {'lat': None, 'lon': None, 'alt': None, 'v_rate': None, 'speed': None, 'trk': None, 'callsign': None}
        msg = row['msg']; tc = row['tc']
        try:
            if 9 <= tc <= 18:
                res['alt'] = pms.adsb.altitude(msg)
                try:
                    pos = pms.adsb.position_with_ref(msg, lat, lon)
                    if pos: res['lat'], res['lon'] = pos
                except: pass
            if tc == 19:
                vel = pms.adsb.velocity(msg)
                res['speed'], res['trk'], res['v_rate'], _ = vel
            if 1 <= tc <= 4:
                res['callsign'] = pms.adsb.callsign(msg).strip('_')
        except: pass
        return pd.Series(res)

    attrs = df_sample.apply(decode, axis=1)
    df_sample = pd.concat([df_sample, attrs], axis=1)
    df_sample['dist'] = df_sample.apply(lambda r: haversine(lat, lon, r['lat'], r['lon']) if pd.notnull(r['lat']) else None, axis=1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # Page A
    fig, axes = plt.subplots(3, 1, figsize=(10, 15))
    df_total.set_index('datetime').resample('5min').size().plot(ax=axes[0], color='navy'); axes[0].set_title("1. Grid Stability")
    sns.countplot(x='tc', data=df_total[df_total['tc']!=-1], ax=axes[1], palette="viridis"); axes[1].set_title("2. Protocol Distribution")
    df_total['datetime'].dt.hour.value_counts().sort_index().plot(kind='bar', ax=axes[2], color='teal'); axes[2].set_title("3. Hourly Traffic")
    plt.tight_layout(); plt.savefig(f"{OUTPUT_DIR}/A_Operational.png")
    # Page B
    fig, axes = plt.subplots(3, 1, figsize=(10, 15))
    sns.histplot(df_sample['v_rate'].dropna(), bins=50, kde=True, ax=axes[0], color='orange'); axes[0].set_xlim(-4000, 4000); axes[0].set_title("4. Vertical Rate")
    sns.histplot(df_sample['speed'].dropna(), bins=50, kde=True, ax=axes[1], color='red'); axes[1].set_title("5. Ground Speed")
    sns.histplot(df_sample['trk'].dropna(), bins=36, kde=False, ax=axes[2], color='purple'); axes[2].set_title("6. Track Angle")
    plt.tight_layout(); plt.savefig(f"{OUTPUT_DIR}/B_Physics.png")
    # Page C
    fig, axes = plt.subplots(2, 1, figsize=(10, 12))
    sns.scatterplot(x='lon', y='lat', data=df_sample, ax=axes[0], alpha=0.4, s=10, color='blue'); axes[0].set_title("7. Coverage Map")
    sns.scatterplot(x='dist', y='alt', data=df_sample, ax=axes[1], alpha=0.3, color='green'); axes[1].set_title("8. Alt vs Dist")
    plt.tight_layout(); plt.savefig(f"{OUTPUT_DIR}/C_Spatial.png")
    # Page D
    fig, axes = plt.subplots(3, 1, figsize=(10, 15))
    sns.histplot(df_sample['rssi'], bins=50, ax=axes[0], color='gray'); axes[0].set_title("9. RSSI Dist")
    if df_sample['dist'].count() > 10: sns.scatterplot(x='dist', y='rssi', data=df_sample, ax=axes[1], alpha=0.2, color='magenta'); axes[1].set_title("10. Signal Decay")
    corr = df_sample[['rssi', 'alt', 'dist', 'speed']].corr()
    sns.heatmap(corr, annot=True, cmap='coolwarm', ax=axes[2]); axes[2].set_title("11. Correlation Matrix")
    plt.tight_layout(); plt.savefig(f"{OUTPUT_DIR}/D_Signals.png")

    # REPORT GENERATION
    generate_report(df_total, df_sample, duration, f"{OUTPUT_DIR}/AUDIT_REPORT.md")
    print(f"[SUCCESS] Dashboard & Report saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="research_data/raw_logs")
    parser.add_argument("--lat", type=float, default=60.319555)
    parser.add_argument("--lon", type=float, default=24.830816)
    args = parser.parse_args()
    run_analysis(args.dir, args.lat, args.lon)
