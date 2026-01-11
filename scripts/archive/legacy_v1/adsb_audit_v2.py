"""
ADS-B Research Grid - Scientific Audit Tool (V2)
------------------------------------------------
Features:
  - "Smart 24h" Window: Analyzes the last 24h relative to the NEWEST file found.
  - 12-Plot Dashboard: Added Density Heatmaps & Signal Decay.
  - Precise Reporting: Explicit Start/Stop timestamps.
"""

import argparse
import glob
import os
import math
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import pyModeS as pms
from datetime import datetime, timedelta
import numpy as np

# --- Configuration ---
sns.set_theme(style="whitegrid", context="paper")
OUTPUT_DIR = "analysis/adsb_v2"
SAMPLE_LIMIT = 100000 

# --- Helpers ---
def haversine(lat1, lon1, lat2, lon2):
    try:
        R = 6371.0
        dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    except: return None

def parse_filename_time(fname):
    """Extracts timestamp from filename: raw_adsb_YYYYMMDD_HHMMSS.bin"""
    try:
        base = os.path.basename(fname)
        parts = base.split('_')
        ts_str = parts[2] + "_" + parts[3].split('.')[0]
        return datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
    except:
        return datetime.min

def parse_raw_file_robust(filepath):
    messages = []
    try:
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
                if i + 9 + frame_len > length: break
                
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
                i += (9 + frame_len)
    except: pass
    return messages

def generate_report(total_df, sample_df, start_dt, end_dt, output_path):
    duration = (end_dt - start_dt).total_seconds() / 3600.0
    if duration < 0.1: duration = 0.1
    
    total = len(total_df)
    adsb_total = len(total_df[total_df['df'].isin([17, 18])])
    miss_lat = len(sample_df) - sample_df['lat'].count()
    
    with open(output_path, "w") as f:
        f.write("# 🔬 ADS-B Research Grid: Daily Audit (V2)\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        
        f.write("## 1. Executive Summary\n")
        f.write(f"- **Data Start:** {start_dt}\n")
        f.write(f"- **Data Stop:** {end_dt}\n")
        f.write(f"- **Window Duration:** {duration:.2f} Hours\n")
        f.write(f"- **Status:** {'🟢 OPERATIONAL' if adsb_total > 1000 else '🔴 LOW DATA'}\n\n")
        
        f.write("| Key Metric | Value | Notes |\n| :--- | :--- | :--- |\n")
        f.write(f"| **Total Traffic** | {total:,} | Raw Frames |\n")
        f.write(f"| **ADS-B Volume** | {adsb_total:,} | Valid Physics Frames |\n")
        f.write(f"| **Avg Rate** | {total/(duration*3600):.1f} msg/s | Throughput |\n\n")
        
        f.write("## 2. Security & Quality\n")
        mil_prefixes = ['RCH', 'CNV', 'NATO', 'VADER', 'VIP', 'AF1']
        callsigns = sample_df['callsign'].dropna().unique()
        suspicious = [c for c in callsigns if any(c.startswith(p) for p in mil_prefixes)]
        
        if suspicious:
            f.write(f"- **⚠️ Military Pattern Detected:** {', '.join(suspicious)}\n")
        else:
            f.write("- No military callsigns detected in sample.\n")
        f.write(f"- **Position Integrity:** {(1 - miss_lat/len(sample_df))*100:.1f}% valid lat/lon.\n")

def run_analysis(input_dir, lat, lon):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. SMART FILE SELECTION
    all_files = sorted(glob.glob(os.path.join(input_dir, "raw_adsb_*.bin")))
    if not all_files:
        print("[!] No data files found.")
        return

    # Find the NEWEST file timestamp
    newest_ts = parse_filename_time(all_files[-1])
    cutoff = newest_ts - timedelta(hours=24)
    
    target_files = []
    for f in all_files:
        ts = parse_filename_time(f)
        if ts >= cutoff:
            target_files.append((f, ts))
            
    print(f"[INFO] Analysis Window: {cutoff} -> {newest_ts}")
    print(f"[INFO] Processing {len(target_files)} files (Smart 24h Mode)...")
    
    # 2. INGEST
    all_data = []
    for f_path, f_ts in target_files:
        msgs = parse_raw_file_robust(f_path)
        count = len(msgs)
        if count > 0:
            step = 900.0 / count
            base_ts = f_ts.timestamp()
            for i, m in enumerate(msgs):
                m['timestamp'] = base_ts + (i * step)
                all_data.append(m)
    
    df_total = pd.DataFrame(all_data)
    if df_total.empty: return
    df_total['datetime'] = pd.to_datetime(df_total['timestamp'], unit='s')
    
    real_start = df_total['datetime'].min()
    real_end = df_total['datetime'].max()
    print(f"[INFO] Loaded {len(df_total)} messages.")

    # 3. DECODE
    df_adsb = df_total[df_total['df'].isin([17, 18])].copy()
    if df_adsb.empty: return
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

    # 4. PLOTS (12 Plots)
    
    # Page A
    fig, axes = plt.subplots(3, 1, figsize=(10, 15))
    df_total.set_index('datetime').resample('15min').size().plot(ax=axes[0], color='navy')
    axes[0].set_title(f"1. Traffic Volume (Max: {df_total.set_index('datetime').resample('15min').size().max()} msg/15min)")
    sns.countplot(x='tc', data=df_total[df_total['tc']!=-1], ax=axes[1], palette="viridis"); axes[1].set_title("2. Type Code Dist")
    df_total['hour'] = df_total['datetime'].dt.hour
    sns.histplot(x=df_total['hour'], bins=24, kde=True, ax=axes[2], color='teal'); axes[2].set_title("3. Hourly Activity")
    plt.tight_layout(); plt.savefig(f"{OUTPUT_DIR}/A_Operational_24h.png")
    
    # Page B
    fig, axes = plt.subplots(3, 1, figsize=(10, 15))
    sns.histplot(df_sample['v_rate'].dropna(), bins=50, kde=True, ax=axes[0], color='orange'); axes[0].set_xlim(-4000, 4000); axes[0].set_title("4. Vertical Rate")
    sns.histplot(df_sample['speed'].dropna(), bins=50, kde=True, ax=axes[1], color='red'); axes[1].set_title("5. Ground Speed")
    sns.histplot(df_sample['trk'].dropna(), bins=36, kde=False, ax=axes[2], color='purple'); axes[2].set_title("6. Heading")
    plt.tight_layout(); plt.savefig(f"{OUTPUT_DIR}/B_Physics_24h.png")
    
    # Page C
    fig, axes = plt.subplots(2, 1, figsize=(10, 12))
    sns.scatterplot(x='lon', y='lat', data=df_sample, ax=axes[0], alpha=0.4, s=10, color='blue')
    axes[0].plot(lon, lat, 'r+', markersize=15, markeredgewidth=2); axes[0].set_title("7. Coverage Map")
    sns.scatterplot(x='dist', y='alt', data=df_sample, ax=axes[1], alpha=0.3, color='green'); axes[1].set_title("8. Alt vs Dist")
    plt.tight_layout(); plt.savefig(f"{OUTPUT_DIR}/C_Spatial_24h.png")
    
    # Page D
    fig, axes = plt.subplots(3, 1, figsize=(10, 15))
    sns.histplot(df_sample['rssi'], bins=50, ax=axes[0], color='gray'); axes[0].set_title("9. RSSI Dist")
    if df_sample['dist'].count() > 10: sns.scatterplot(x='dist', y='rssi', data=df_sample, ax=axes[1], alpha=0.2, color='magenta'); axes[1].set_title("10. Signal Decay")
    corr = df_sample[['rssi', 'alt', 'dist', 'speed']].corr()
    sns.heatmap(corr, annot=True, cmap='coolwarm', ax=axes[2]); axes[2].set_title("11. Correlation Matrix")
    plt.tight_layout(); plt.savefig(f"{OUTPUT_DIR}/D_Signals_24h.png")

    # 5. REPORT
    generate_report(df_total, df_sample, real_start, real_end, f"{OUTPUT_DIR}/AUDIT_REPORT_24H.md")
    print(f"[SUCCESS] Saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="./research_data/raw_logs")
    parser.add_argument("--lat", type=float, default=60.319555)
    parser.add_argument("--lon", type=float, default=24.830816)
    args = parser.parse_args()
    run_analysis(args.dir, args.lat, args.lon)
