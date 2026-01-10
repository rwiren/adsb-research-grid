#!/usr/bin/env python3
# ==============================================================================
# File: scripts/plot_storage.py
# Version: 3.1.0 (Academic Release)
# Author: Gemini (Ref: User Requirements 2026-01-10)
# Description: 
#   Visualizes storage growth across the distributed ADS-B grid.
#   - Updated with Verified Hardware Limits (West=64GB, East=16GB, North=32GB).
#   - Default View: Last 3 Hours.
#   - Features: Ghost record cleaning, Linear forecasting, High-Contrast Style.
# ==============================================================================

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta, timezone
import os
import csv
import sys
import argparse

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_DATA_PATH = os.path.join(PROJECT_ROOT, "storage_history.csv")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")

# Verified Hardware Limits (Usable Space from df -h)
NODE_LIMITS = {
    "sensor-east": 15.0,  # 16GB Card (~15G usable)
    "sensor-north": 29.0, # 32GB Card (~29G usable)
    "sensor-west": 58.0,  # 64GB Card (~58G usable)
    "default": 29.0
}

# Academic Color Palette (High Contrast)
COLORS = {
    "sensor-east": "#0072B2",  # Blue
    "sensor-north": "#D55E00", # Vermillion
    "sensor-west": "#009E73",  # Bluish Green
    "default": "#999999"       # Grey
}

def parse_arguments():
    parser = argparse.ArgumentParser(description="Plot ADS-B Sensor Storage Growth")
    parser.add_argument("csv_file", nargs="?", default=DEFAULT_DATA_PATH, 
                        help="Path to the source CSV file")
    parser.add_argument("--hours", type=float, default=3.0, 
                        help="Hours of history to show (default: 3)")
    parser.add_argument("--all", action="store_true", 
                        help="Show all available history (overrides --hours)")
    return parser.parse_args()

def load_robust_csv(filepath):
    """Ingests logs handling mixed schemas (3-col vs 4-col)."""
    rows = []
    if not os.path.exists(filepath):
        print(f"❌ [ERROR] Data file not found: {filepath}")
        return pd.DataFrame()

    try:
        with open(filepath, 'r') as f:
            reader = csv.reader(f)
            try:
                first_line = next(reader, None)
            except StopIteration:
                return pd.DataFrame()
                
            if first_line:
                if "timestamp" not in first_line[0].lower():
                    _process_row(first_line, rows)

            for line in reader:
                if not line: continue
                _process_row(line, rows)
                
    except Exception as e:
        print(f"❌ [ERROR] Failed to read CSV: {e}")
        return pd.DataFrame()

    return pd.DataFrame(rows)

def _process_row(line, rows):
    try:
        node = "sensor-unknown"
        disk = 0.0
        
        if len(line) == 3: # Legacy
            disk = float(line[1]) if line[1] else 0
        elif len(line) >= 4: # Modern
            node = line[1]
            disk = float(line[2]) if line[2] else 0
            
        rows.append({
            "timestamp": line[0],
            "node_name": node,
            "disk_used_kb": disk
        })
    except ValueError:
        pass

def main():
    args = parse_arguments()

    print("--------------------------------------------------------")
    print(" [ANALYSIS] Storage Growth & Capacity Forecast v3.1.0")
    print("--------------------------------------------------------")

    # 1. Load Data
    print(f" -> Loading repository: {args.csv_file}")
    df = load_robust_csv(args.csv_file)
    
    if df.empty:
        print(" -> [WARN] No data available.")
        return

    # 2. Process Data
    try:
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', utc=True)
        df['disk_used_gb'] = df['disk_used_kb'] / (1024 * 1024)
        
        # Cleanup
        initial_count = len(df)
        df = df[df['node_name'] != 'sensor-unknown']
        cleaned_count = len(df)
        if initial_count > cleaned_count:
            print(f" -> Cleaned {initial_count - cleaned_count} ghost records.")
            
    except Exception as e:
        print(f"❌ [ERROR] Data processing failed: {e}")
        return

    # 3. Apply Time Filtering
    if not args.all:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=args.hours)
        df = df[df['timestamp'] >= cutoff_time]
        print(f" -> Time Window: Last {args.hours} hours")
    else:
        print(" -> Time Window: ALL HISTORY")
        
    if df.empty:
        print("⚠️  No data found in this time window.")
        return

    # 4. Generate Plot (Academic Style)
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Clean layout
    try:
        plt.style.use('seaborn-v0_8-whitegrid')
    except:
        plt.style.use('ggplot')

    fig, ax = plt.subplots(figsize=(12, 7))
    nodes = sorted(df['node_name'].unique())
    
    # Track max limit for graph scaling
    global_max_limit = 0

    for node in nodes:
        node_data = df[df['node_name'] == node].sort_values('timestamp')
        if len(node_data) == 0: continue

        color = COLORS.get(node, COLORS['default'])
        limit = NODE_LIMITS.get(node, NODE_LIMITS["default"])
        global_max_limit = max(global_max_limit, limit)

        # Plot Line
        ax.plot(node_data['timestamp'], node_data['disk_used_gb'], 
                marker='o', markersize=4, linestyle='-', linewidth=2, 
                color=color, label=node)

        # Metrics & Forecasting
        current_usage = node_data['disk_used_gb'].iloc[-1]
        percent_full = (current_usage / limit) * 100
        
        est_days_str = "Stable"
        rate_str = "0.00"

        if len(node_data) > 1:
            duration = (node_data['timestamp'].iloc[-1] - node_data['timestamp'].iloc[0]).total_seconds() / 3600
            if duration > 0.1:
                growth = current_usage - node_data['disk_used_gb'].iloc[0]
                rate_day = (growth / duration) * 24
                rate_str = f"{rate_day:.2f}"
                
                if rate_day > 0.01:
                    days_left = (limit - current_usage) / rate_day
                    est_days_str = f"{days_left:.1f} days"
                elif rate_day < -0.01:
                    est_days_str = "Cleaning"

        print(f"    - {node:<15} | {percent_full:5.1f}% | Rate: {rate_str} GB/d | Full: {est_days_str}")

        # Anomaly Check: Is usage > limit? (Hardware swap?)
        if current_usage > limit:
             print(f"      ⚠️  [ALERT] Usage ({current_usage:.1f}GB) exceeds configured limit ({limit}GB). Update NODE_LIMITS.")

        # Capacity Line (Only draw if relevant to current view)
        if percent_full > 10:
            ax.axhline(y=limit, color=color, linestyle=':', alpha=0.6, linewidth=1.5)
            # Annotate limit on the right axis
            ax.text(node_data['timestamp'].iloc[-1], limit + 0.2, f"{limit}G", 
                    color=color, fontsize=9, fontweight='bold')
            # Annotate % full on the last point
            ax.text(node_data['timestamp'].iloc[-1], current_usage + 0.2, f"{percent_full:.0f}%", 
                    color=color, fontsize=8)

    # 5. Labels and Formatting
    time_desc = "All History" if args.all else f"Last {args.hours} Hours"
    ax.set_title(f"ADS-B Sensor Network: Storage Utilization ({time_desc})", fontsize=14, pad=15)
    ax.set_ylabel("Disk Usage (GB)", fontsize=11)
    ax.set_xlabel("Time (UTC)", fontsize=11)
    
    # Scale Y axis slightly above max usage or max relevant limit
    ax.set_ylim(bottom=0)
    
    # Improved Date Formatting
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    fig.autofmt_xdate()
    
    # Legend
    ax.legend(loc="upper left", frameon=True, framealpha=0.9)
    
    # Metadata Footer
    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    plt.figtext(0.99, 0.01, f"Generated: {gen_time} | System: ADS-B Research Grid", 
                horizontalalignment='right', fontsize=8, color='gray')

    # Save
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(OUTPUT_DIR, f"storage_report_{timestamp_str}.png")
    plt.savefig(out_path, dpi=200, bbox_inches='tight')
    print(f"✅ [SUCCESS] Report saved: {out_path}")

if __name__ == "__main__":
    main()
