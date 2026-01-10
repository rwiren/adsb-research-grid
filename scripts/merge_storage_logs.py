#!/usr/bin/env python3
# ==============================================================================
# File: scripts/merge_storage_logs.py
# Version: 2.2.0
# Description: 
#   Aggregates distributed storage logs into a single master CSV.
#   Crucially, it INJECTS the node name based on the directory structure
#   if the source log file is missing that column (legacy support).
# ==============================================================================

import os
import csv
import sys

# Define paths relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "research_data")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "storage_history.csv")

def main():
    print("--------------------------------------------------------")
    print(" [ETL] Merging Remote Storage Logs -> Master History")
    print("--------------------------------------------------------")
    
    if not os.path.exists(DATA_DIR):
        print(f"❌ Data directory not found: {DATA_DIR}")
        print("   Run 'make fetch' first.")
        sys.exit(1)

    # 1. Prepare Master File with correct 4-column header
    with open(OUTPUT_FILE, "w") as out:
        out.write("timestamp,node_name,disk_used_kb,recording_size_kb\n")

    count_total = 0
    count_files = 0

    # 2. Walk the directory tree (research_data/YYYY/sensor-X/...)
    for root, dirs, files in os.walk(DATA_DIR):
        for file in files:
            # We are looking for the raw metrics file usually named 'storage_history.csv' 
            # (or similar, depending on what the sensor saves locally)
            if "storage" in file and file.endswith(".csv"):
                full_path = os.path.join(root, file)
                
                # Deduce Node Name from Folder Path
                # Expected path: .../research_data/2026-01-10/sensor-west/storage_history.csv
                path_parts = full_path.split(os.sep)
                try:
                    # The folder containing the file should be the hostname
                    node_name = path_parts[-2]
                    # Sanity check: if folder is date, go one deeper? 
                    # Actually fetch.yml puts it in /date/hostname/, so -2 is correct.
                    if "sensor" not in node_name:
                        node_name = "sensor-unknown"
                except:
                    node_name = "sensor-unknown"

                # 3. Read and Transmute
                try:
                    with open(full_path, "r") as f_in:
                        reader = csv.reader(f_in)
                        for row in reader:
                            if not row: continue
                            
                            # Filter junk headers or empty lines
                            if "timestamp" in row[0].lower(): continue
                            if not row[0].startswith("20"): continue # Skip bad dates

                            # Normalize Columns
                            # Case A: Legacy (3 cols) -> [Time, Disk, Rec]
                            if len(row) == 3:
                                timestamp = row[0]
                                disk = row[1]
                                rec = row[2]
                                # Inject Node Name
                                with open(OUTPUT_FILE, "a") as f_out:
                                    f_out.write(f"{timestamp},{node_name},{disk},{rec}\n")
                                count_total += 1
                                
                            # Case B: Modern (4 cols) -> [Time, Node, Disk, Rec]
                            elif len(row) >= 4:
                                # Write as-is (but maybe force the node name from folder to be safe?)
                                with open(OUTPUT_FILE, "a") as f_out:
                                    # We use the row's own data, or override if 'sensor-unknown'
                                    r_node = row[1] if "sensor" in row[1] else node_name
                                    f_out.write(f"{row[0]},{r_node},{row[2]},{row[3]}\n")
                                count_total += 1
                        
                        count_files += 1
                        
                except Exception as e:
                    print(f"⚠️  Skipping {file}: {e}")

    print("-" * 40)
    print(f"✅ Merged {count_files} files.")
    print(f"📊 Total Records: {count_total}")
    print(f"💾 Output: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
