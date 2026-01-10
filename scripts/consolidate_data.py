#!/usr/bin/env python3
import os
import glob
import pandas as pd
from datetime import datetime
import shutil

# CONFIGURATION
DATA_DIR = "research_data"
ARCHIVE_DIR = "raw_fragments"  # Subfolder to hide processed fragments

def consolidate_daily_logs():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧹 Starting Data Consolidation...")
    
    # 1. Loop through Dates
    for date_folder in sorted(os.listdir(DATA_DIR)):
        date_path = os.path.join(DATA_DIR, date_folder)
        if not os.path.isdir(date_path) or date_folder.startswith('.'): 
            continue

        # 2. Loop through Sensors
        for sensor in sorted(os.listdir(date_path)):
            sensor_path = os.path.join(date_path, sensor)
            if not os.path.isdir(sensor_path): continue

            # Create archive folder for this sensor/day
            archive_path = os.path.join(sensor_path, ARCHIVE_DIR)
            os.makedirs(archive_path, exist_ok=True)

            # 3. Process each log type separately
            log_types = ['aircraft', 'gnss', 'stats']
            
            for ltype in log_types:
                # Find all RAW fragments (exclude existing MASTER files)
                pattern = f"*{ltype}_log_*.csv"
                all_files = glob.glob(os.path.join(sensor_path, pattern))
                
                # Filter out files that are ALREADY consolidated masters
                fragments = [f for f in all_files if "MASTER" not in f]

                if not fragments:
                    continue

                print(f"   🔹 Merging {len(fragments)} {ltype} logs for {sensor}...")

                # Read and Concatenate
                df_list = []
                for f in fragments:
                    try:
                        # Skip empty files
                        if os.path.getsize(f) > 0:
                            # 'dtype=str' prevents type inference errors during read (we clean later)
                            df = pd.read_csv(f, on_bad_lines='skip', dtype=str)
                            df_list.append(df)
                    except Exception as e:
                        print(f"      ❌ Warning: Could not read {os.path.basename(f)}")

                if df_list:
                    master_df = pd.concat(df_list, ignore_index=True)
                    
                    # --- ROBUST SORTING FIX ---
                    # Find the timestamp column (usually 'timestamp', 'time', or 'now')
                    time_cols = [c for c in master_df.columns if 'time' in c.lower() or 'now' in c.lower()]
                    
                    if time_cols:
                        sort_col = time_cols[0]
                        # 1. Coerce to Datetime (handles mixed floats/strings)
                        # 'coerce' turns garbage (like repeated headers) into NaT (Not a Time)
                        master_df[sort_col] = pd.to_datetime(master_df[sort_col], errors='coerce')
                        
                        # 2. Drop rows with invalid timestamps
                        master_df = master_df.dropna(subset=[sort_col])
                        
                        # 3. Sort safely
                        master_df = master_df.sort_values(by=sort_col)

                    # Save MASTER file
                    output_filename = f"{sensor}_{ltype}_MASTER_{date_folder}.csv"
                    output_path = os.path.join(sensor_path, output_filename)
                    master_df.to_csv(output_path, index=False)
                    print(f"      ✅ Created: {output_filename} ({len(master_df)} rows)")

                    # Move fragments to archive
                    for f in fragments:
                        shutil.move(f, os.path.join(archive_path, os.path.basename(f)))

if __name__ == "__main__":
    consolidate_daily_logs()
