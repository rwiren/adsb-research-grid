#!/usr/bin/env python3
import pandas as pd
import glob
import os
from datetime import datetime

# ==============================================================================
# Script: tail_logs.py
# Description: Prints the last 5 rows of ALL log files in the latest dataset.
#              Useful for quick integrity checks.
# ==============================================================================

def get_latest_data_dir(base_dir="research_data"):
    """Finds the most recent date directory."""
    dirs = glob.glob(os.path.join(base_dir, "202*"))
    if not dirs:
        return None
    return sorted(dirs)[-1]  # Return the last one (latest date)

def tail_file(filepath, n=5):
    """Reads last n rows of a CSV (handles gzip automatically)."""
    try:
        # Determine compression
        comp = 'gzip' if filepath.endswith('.gz') else None
        
        # Read Data
        df = pd.read_csv(filepath, compression=comp, on_bad_lines='skip')
        
        # Formatting
        print(f"\n📄 FILE: {os.path.basename(filepath)}")
        print(f"📍 PATH: {filepath}")
        print(f"📊 SHAPE: {df.shape[0]} rows x {df.shape[1]} cols")
        print("-" * 80)
        
        if df.empty:
            print("⚠️  [EMPTY FILE]")
        else:
            print(df.tail(n).to_string(index=False))
        print("-" * 80)
        
    except Exception as e:
        print(f"❌ ERROR reading {os.path.basename(filepath)}: {e}")

def main():
    latest_dir = get_latest_data_dir()
    if not latest_dir:
        print("❌ No data directories found in 'research_data/'")
        return

    print(f"🔎 Inspecting Data from: {latest_dir}")
    print("=" * 80)

    # Patterns to search for
    patterns = [
        "**/*_aircraft_log*.csv*",   # Aircraft Telemetry
        "**/*_stats_log*.csv*",      # Hardware Performance
        "**/storage_history.csv",    # Disk Usage
        "**/hardware_health.csv",    # Voltage/Temp (Forensics)
        "**/*_gnss_log*.csv*"        # GNSS Raw (if active)
    ]

    found_files = []
    for p in patterns:
        found_files.extend(glob.glob(os.path.join(latest_dir, p), recursive=True))

    if not found_files:
        print("⚠️  No log files found matching standard patterns.")
        return

    # Sort for consistent output
    for log_file in sorted(found_files):
        tail_file(log_file)

if __name__ == "__main__":
    main()
