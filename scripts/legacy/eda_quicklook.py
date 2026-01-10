#!/usr/bin/env python3
import os
import pandas as pd
import glob

DATA_DIR = "research_data"

def analyze_sensor_performance():
    print("\n🔬 ACADEMIC QUICK-LOOK REPORT")
    print("=============================")

    for date_folder in sorted(os.listdir(DATA_DIR)):
        date_path = os.path.join(DATA_DIR, date_folder)
        if not os.path.isdir(date_path) or date_folder.startswith('.'): continue

        print(f"\n📅 DATE: {date_folder}")

        for sensor in sorted(os.listdir(date_path)):
            sensor_path = os.path.join(date_path, sensor)
            if not os.path.isdir(sensor_path): continue
            
            print(f"   📡 SENSOR: {sensor}")
            
            # 1. Analyze Aircraft Traffic
            aircraft_master = glob.glob(os.path.join(sensor_path, "*aircraft_MASTER*.csv"))
            if aircraft_master:
                df = pd.read_csv(aircraft_master[0])
                total_msgs = len(df)
                # distinct hex codes = unique aircraft
                unique_aircraft = df['hex'].nunique() if 'hex' in df.columns else 0
                
                print(f"      ✈️  Aircraft Data:")
                print(f"          - Total Messages:   {total_msgs:,}")
                print(f"          - Unique Aircraft:  {unique_aircraft}")
                if 'rssi' in df.columns:
                     print(f"          - Avg Signal (RSSI): {df['rssi'].mean():.1f} dBFS")

            # 2. Analyze GNSS Hardware (Crucial for your hardware test)
            gnss_master = glob.glob(os.path.join(sensor_path, "*gnss_MASTER*.csv"))
            if gnss_master:
                df_gnss = pd.read_csv(gnss_master[0])
                print(f"      🛰️  GNSS Hardware Stats:")
                # Assuming standard gpsd/chrony columns like 'sats' or 'fix'
                # Adjust column names based on your specific CSV schema
                if 'sats' in df_gnss.columns:
                    avg_sats = df_gnss['sats'].mean()
                    print(f"          - Avg Satellites:    {avg_sats:.1f}")
                print(f"          - Data Points:       {len(df_gnss)}")
            else:
                print("      ⚠️  No GNSS Master log found.")

if __name__ == "__main__":
    analyze_sensor_performance()
