#!/usr/bin/env python3
import os
import glob
from datetime import datetime

# CONFIGURATION
DATA_DIR = "research_data"

def scan_and_validate():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting Dataset Validation...")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Target Directory: ./{DATA_DIR}")
    print("-" * 60)

    if not os.path.exists(DATA_DIR):
        print(f"❌ Error: Directory '{DATA_DIR}' not found.")
        return

    total_files = 0
    total_rows = 0
    
    # Iterate over Date folders
    for date_folder in sorted(os.listdir(DATA_DIR)):
        date_path = os.path.join(DATA_DIR, date_folder)
        if not os.path.isdir(date_path) or date_folder.startswith('.'):
            continue

        print(f"\n📅 DATE: {date_folder}")

        # Iterate over Sensor folders
        for sensor in sorted(os.listdir(date_path)):
            sensor_path = os.path.join(date_path, sensor)
            if not os.path.isdir(sensor_path):
                continue
            
            csv_files = glob.glob(os.path.join(sensor_path, "*.csv"))
            file_count = len(csv_files)
            total_files += file_count
            
            if file_count == 0:
                print(f"   ⚠️  {sensor}: No CSV files found.")
                continue

            print(f"   📍 SENSOR: {sensor} ({file_count} raw files)")

            unknown_sensor_files = 0
            sensor_rows = 0
            empty_files = 0
            
            for f in csv_files:
                if os.path.getsize(f) == 0:
                    empty_files += 1
                    continue
                
                if "sensor-unknown" in f:
                    unknown_sensor_files += 1

                # Estimate row count (minus header)
                try:
                    with open(f, 'r', encoding='utf-8', errors='ignore') as file_handle:
                        row_count = sum(1 for line in file_handle) - 1
                    sensor_rows += max(0, row_count)
                except Exception as e:
                    print(f"      ❌ Error reading {os.path.basename(f)}: {e}")

            print(f"      • Records Captured: {sensor_rows:,}")
            if empty_files > 0:
                print(f"      • ⚠️  Empty Files: {empty_files}")
            if unknown_sensor_files > 0:
                print(f"      • 🔴 ANOMALY: {unknown_sensor_files} files have 'sensor-unknown'.")

            total_rows += sensor_rows

    print("-" * 60)
    print(f"✅ VALIDATION COMPLETE")
    print(f"   Total Files Scanned: {total_files}")
    print(f"   Total Data Rows:     {total_rows:,}")

if __name__ == "__main__":
    scan_and_validate()
