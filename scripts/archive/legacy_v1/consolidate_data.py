#!/usr/bin/env python3
"""
==============================================================================
FILE: scripts/consolidate_data.py
VERSION: 2.1.0
DESCRIPTION:
  Scans sensor directories, finds raw CSV fragments, and merges them 
  into a single MASTER CSV file per log type (aircraft, stats, gnss).
==============================================================================
"""

import os
import glob
import pandas as pd
import warnings

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore")

DATA_DIR = "research_data"

def get_log_type(filename):
    """Determines log type based on filename."""
    if "aircraft" in filename: return "aircraft"
    if "stats" in filename: return "stats"
    if "gnss" in filename: return "gnss"
    return "unknown"

def merge_fragments(sensor_path, date_str, sensor_name):
    """Finds and merges raw fragments in a specific sensor folder."""
    raw_dir = os.path.join(sensor_path, "raw_fragments")
    
    if not os.path.exists(raw_dir):
        # Fallback: check root of sensor dir if raw_fragments doesn't exist
        raw_dir = sensor_path

    # Group files by type
    fragments = {"aircraft": [], "stats": [], "gnss": []}
    
    # scan for csv files
    for filepath in glob.glob(os.path.join(raw_dir, "*.csv")):
        filename = os.path.basename(filepath)
        # Skip existing master files to avoid duplication loops
        if "MASTER" in filename: continue
        
        ltype = get_log_type(filename)
        if ltype in fragments:
            fragments[ltype].append(filepath)

    # Process each type
    for ltype, files in fragments.items():
        if not files: continue
        
        print(f"   🔹 Merging {len(files)} {ltype} logs for {sensor_name}...")
        
        dfs = []
        for f in files:
            try:
                # Read csv, ensure everything is treated as string initially to prevent mismatch
                df = pd.read_csv(f, dtype=str)
                dfs.append(df)
            except Exception as e:
                print(f"      ⚠️ Error reading {os.path.basename(f)}: {e}")

        if dfs:
            master_df = pd.concat(dfs, ignore_index=True)
            
            # Sort by time if possible
            sort_col = next((c for c in master_df.columns if 'time' in c.lower() or 'now' in c.lower()), None)
            if sort_col:
                master_df[sort_col] = pd.to_datetime(master_df[sort_col], errors='coerce')
                master_df = master_df.sort_values(by=sort_col)

            # Save Master File
            output_filename = f"{sensor_name}_{ltype}_MASTER_{date_str}.csv"
            output_path = os.path.join(sensor_path, output_filename)
            master_df.to_csv(output_path, index=False)
            print(f"      ✅ Created: {output_filename} ({len(master_df)} rows)")

def main():
    print("🧹 Starting Data Consolidation...")
    
    # 1. Iterate over Date Folders
    if not os.path.exists(DATA_DIR):
        print(f"❌ Error: {DATA_DIR} not found.")
        return

    for date_folder in sorted(os.listdir(DATA_DIR)):
        date_path = os.path.join(DATA_DIR, date_folder)
        if not os.path.isdir(date_path): continue

        # 2. Iterate over Sensor Folders (e.g., sensor-west, sensor-north)
        for sensor in sorted(os.listdir(date_path)):
            sensor_path = os.path.join(date_path, sensor)
            if not os.path.isdir(sensor_path): continue
            
            # Skip the 'raw_fragments' folder if it appears at this level mistakenly
            if sensor == "raw_fragments": continue

            merge_fragments(sensor_path, date_folder, sensor)

if __name__ == "__main__":
    main()
