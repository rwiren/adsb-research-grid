#!/usr/bin/env python3
# ==============================================================================
# File: scripts/compare_gnss.py
# Version: 2.0.0 (Unified Scientific Dashboard)
# Author: Research Operations
# Date: 2026-01-10
# Description: 
#   Advanced GNSS comparative analysis (East vs West).
#   - Layout: 3-Panel Dashboard (Horizontal Plan, Vertical Profile, Signal Health).
#   - Features: Altitude drift analysis, Corrected Satellite counting.
# ==============================================================================

import subprocess
import json
import threading
import time
import argparse
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import pandas as pd
from datetime import datetime
import os

# --- Configuration ---
NODES = {
    "sensor-east": "pi@192.168.192.120",
    "sensor-west": "pi@192.168.192.110"
}
OUTPUT_DIR = "output/gnss_comparison"

def parse_arguments():
    parser = argparse.ArgumentParser(description="Compare GNSS Performance")
    parser.add_argument("--duration", type=int, default=60, help="Capture duration in seconds")
    return parser.parse_args()

def collect_data(node_name, host_str, duration, result_bucket):
    print(f" -> [{node_name}] Starting capture ({duration}s) from {host_str}...")
    cmd = f"ssh {host_str} 'timeout {duration} gpspipe -w'"
    
    try:
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        
        data = []
        for line in stdout.splitlines():
            try:
                msg = json.loads(line)
                if msg["class"] in ["TPV", "SKY"]:
                    msg["_node"] = node_name
                    data.append(msg)
            except:
                continue
        
        result_bucket[node_name] = data
        print(f" -> [{node_name}] Capture complete. {len(data)} records.")
        
    except Exception as e:
        print(f"❌ [{node_name}] Connection Failed: {e}")
        result_bucket[node_name] = []

def analyze_data(raw_data, node_name):
    tpv_list = []
    sky_list = []
    
    for msg in raw_data:
        # TPV: Position (Lat/Lon/Alt)
        if msg["class"] == "TPV":
            # Filter out '0.0' lat/lon which are cold-start artifacts
            if msg.get("lat", 0) == 0.0 or msg.get("lon", 0) == 0.0:
                continue
                
            tpv_list.append({
                "time": msg.get("time"),
                "lat": msg.get("lat"),
                "lon": msg.get("lon"),
                "alt": msg.get("altHAE", msg.get("alt", 0)), # Prefer HAE (Ellipsoid)
            })
            
        # SKY: Satellites
        elif msg["class"] == "SKY":
            sats = msg.get("satellites", [])
            used_sats = [s for s in sats if s.get("used", False)]
            
            # Only count frames that actually have data
            if sats: 
                avg_snr = np.mean([s.get("ss", 0) for s in used_sats]) if used_sats else 0
                sky_list.append({
                    "time": msg.get("time"),
                    "sat_count_used": len(used_sats),
                    "sat_count_visible": len(sats),
                    "avg_snr": avg_snr
                })
            
    return pd.DataFrame(tpv_list), pd.DataFrame(sky_list)

def main():
    args = parse_arguments()
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
        
    print(f"📡 GNSS Dashboard Analysis (Duration: {args.duration}s)")
    print("--------------------------------------------------------")
    
    # 1. Collection
    threads = []
    results = {}
    for name, host in NODES.items():
        t = threading.Thread(target=collect_data, args=(name, host, args.duration, results))
        threads.append(t)
        t.start()
    for t in threads: t.join()
        
    # 2. Setup Dashboard Layout
    try:
        plt.style.use('seaborn-v0_8-whitegrid')
    except:
        plt.style.use('ggplot')

    fig = plt.figure(figsize=(16, 10))
    gs = GridSpec(2, 3, figure=fig)
    
    # Layout Definitions
    ax_pos = fig.add_subplot(gs[0, 0:2]) # Top Left (Map)
    ax_alt = fig.add_subplot(gs[0, 2])   # Top Right (Altitude)
    ax_sat = fig.add_subplot(gs[1, 0])   # Bottom Left (Sat Count)
    ax_snr = fig.add_subplot(gs[1, 1])   # Bottom Center (SNR)
    ax_txt = fig.add_subplot(gs[1, 2])   # Bottom Right (Stats)
    
    colors = {"sensor-east": "#1f77b4", "sensor-west": "#d62728"} # Blue / Red
    stats_text = "COMPARATIVE METRICS:\n--------------------\n"

    for name, data in results.items():
        if not data: continue
        df_tpv, df_sky = analyze_data(data, name)
        if df_tpv.empty: continue

        # --- METRICS ---
        # Position Drift (meters)
        mean_lat, mean_lon = df_tpv['lat'].mean(), df_tpv['lon'].mean()
        mean_alt = df_tpv['alt'].mean()
        
        # Convert degrees to meters (approx at lat 60)
        lat_m = (df_tpv['lat'] - mean_lat) * 111320
        lon_m = (df_tpv['lon'] - mean_lon) * 111320 * np.cos(np.radians(mean_lat))
        alt_m = (df_tpv['alt'] - mean_alt)
        
        # CEP (Circular Error Probable)
        cep50 = 0.59 * (lat_m.std() + lon_m.std())
        
        # Satellites (Fix for 1.1 issue: filter out 0s)
        real_sky = df_sky[df_sky['sat_count_used'] > 0]
        avg_sats = real_sky['sat_count_used'].mean() if not real_sky.empty else 0
        avg_snr = real_sky['avg_snr'].mean() if not real_sky.empty else 0

        stats_text += f"\n[{name.upper()}]\n"
        stats_text += f"  • Precision (CEP50): {cep50:.2f} m\n"
        stats_text += f"  • Alt. Variation:    ±{alt_m.std():.2f} m\n"
        stats_text += f"  • Avg Satellites:    {avg_sats:.1f}\n"
        stats_text += f"  • Avg Signal (SNR):  {avg_snr:.1f} dB\n"

        # --- PLOT 1: Horizontal Position (Bullseye) ---
        ax_pos.scatter(lon_m, lat_m, label=name, color=colors[name], alpha=0.6, s=20, edgecolors='w')
        # Draw 1m and 3m radius rings
        ax_pos.add_patch(plt.Circle((0, 0), 1, color='green', fill=False, linestyle='--', alpha=0.3))
        ax_pos.add_patch(plt.Circle((0, 0), 3, color='orange', fill=False, linestyle='--', alpha=0.3))

        # --- PLOT 2: Vertical Altitude (Distribution) ---
        ax_alt.hist(df_tpv['alt'], bins=15, alpha=0.5, label=name, color=colors[name], orientation='horizontal')
        ax_alt.axhline(mean_alt, color=colors[name], linestyle='--', alpha=0.8)

        # --- PLOT 3 & 4: Signal Health ---
        if not real_sky.empty:
            ax_sat.plot(real_sky['sat_count_used'], label=name, color=colors[name], alpha=0.8)
            ax_snr.plot(real_sky['avg_snr'], label=name, color=colors[name], alpha=0.8)

    # Styling
    ax_pos.set_title("Horizontal Drift (Target: 0m)", fontweight='bold')
    ax_pos.set_xlabel("East/West (m)")
    ax_pos.set_ylabel("North/South (m)")
    ax_pos.legend()
    ax_pos.axis('equal')
    ax_pos.grid(True, linestyle=':', alpha=0.6)

    ax_alt.set_title("Altitude Distribution (MSL/HAE)", fontweight='bold')
    ax_alt.set_xlabel("Sample Count")
    ax_alt.set_ylabel("Altitude (m)")
    
    ax_sat.set_title("Satellites Used in Fix", fontweight='bold')
    ax_sat.set_ylabel("Count")
    ax_sat.set_ylim(0, 14)

    ax_snr.set_title("Signal Strength (SNR)", fontweight='bold')
    ax_snr.set_ylabel("dB")
    ax_snr.set_ylim(10, 50)

    # Stats Panel
    ax_txt.axis('off')
    ax_txt.text(0.05, 0.95, stats_text, fontsize=12, fontfamily='monospace', verticalalignment='top')

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = os.path.join(OUTPUT_DIR, f"gnss_dashboard_{timestamp}.png")
    plt.tight_layout()
    plt.savefig(outfile, dpi=150)
    print(f"✅ Dashboard saved to: {outfile}")

if __name__ == "__main__":
    main()
