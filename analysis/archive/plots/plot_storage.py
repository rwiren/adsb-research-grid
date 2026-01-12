#!/usr/bin/env python3
# Path: analysis/plots/plot_storage.py
# Revision: 2.0
# Description: Visualizes storage growth and forecasts disk full events.
#              Handles mixed CSV formats (legacy 3-col vs new 4-col with node_name).

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import os
import csv
import sys

# --- Configuration ---
# Look for csv in the logs directory relative to where this script is likely run
DATA_FILE_PATH = "../../storage_history.csv" 
OUTPUT_DIR = "output"
DEFAULT_NODE_NAME = "sensor-unknown"

def load_robust_csv(filepath):
    """
    Reads a CSV that may have changing column counts (schema evolution).
    Returns a normalized DataFrame.
    """
    rows = []
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return pd.DataFrame()

    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        
        for line in reader:
            if not line: continue
            
            # Legacy Format: [timestamp, disk_used, recording_size]
            if len(line) == 3:
                rows.append({
                    "timestamp": line[0],
                    "node_name": DEFAULT_NODE_NAME,
                    "disk_used_kb": float(line[1]) if line[1] else 0,
                    "recording_size_kb": float(line[2]) if line[2] else 0
                })
            # New Format: [timestamp, node_name, disk_used, recording_size]
            elif len(line) == 4:
                rows.append({
                    "timestamp": line[0],
                    "node_name": line[1],
                    "disk_used_kb": float(line[2]) if line[2] else 0,
                    "recording_size_kb": float(line[3]) if line[3] else 0
                })

    return pd.DataFrame(rows)

def main():
    # 1. Setup Output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 2. Check for Data
    # Allow passing file path as argument, otherwise use default
    data_file = sys.argv[1] if len(sys.argv) > 1 else DATA_FILE_PATH
    
    print(f"🔍 Loading data from {data_file}...")
    df = load_robust_csv(data_file)
    
    if df.empty:
        print("⚠️ No data found or file is empty.")
        return

    # 3. Preprocess
    try:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['disk_used_gb'] = df['disk_used_kb'] / (1024 * 1024)
    except Exception as e:
        print(f"❌ Error processing data types: {e}")
        return
    
    # 4. Plot by Node
    plt.figure(figsize=(12, 6))
    
    nodes = df['node_name'].unique()
    for node in nodes:
        node_data = df[df['node_name'] == node].sort_values('timestamp')
        
        if len(node_data) == 0:
            continue

        plt.plot(node_data['timestamp'], node_data['disk_used_gb'], 
                 marker='o', linestyle='-', label=f"{node} Used")
        
        # Simple Forecast (Linear Projection based on last 2 points)
        if len(node_data) > 1:
            last_two = node_data.iloc[-2:]
            growth_gb = last_two['disk_used_gb'].iloc[-1] - last_two['disk_used_gb'].iloc[0]
            time_diff_h = (last_two['timestamp'].iloc[-1] - last_two['timestamp'].iloc[0]).total_seconds() / 3600
            
            if time_diff_h > 0.01: # Avoid division by zero
                rate = growth_gb / time_diff_h
                print(f"📈 {node} Growth Rate: {rate:.2f} GB/hour")
            else:
                 print(f"ℹ️ {node}: Not enough time separation for rate calc.")

    plt.title("Sensor Storage Growth Over Time")
    plt.xlabel("Time")
    plt.ylabel("Disk Usage (GB)")
    plt.grid(True, which='both', linestyle='--', alpha=0.7)
    plt.legend()
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    plt.gcf().autofmt_xdate()
    
    # 5. Save
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(OUTPUT_DIR, f"storage_report_{timestamp_str}.png")
    plt.savefig(out_path)
    print(f"✅ Plot saved to: {out_path}")

if __name__ == "__main__":
    main()
