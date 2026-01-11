#!/usr/bin/env python3
import os
import glob
import pandas as pd

# CONFIG
DATA_ROOT = "research_data"
HISTORY_FILE = os.path.join("data", "storage_history.csv")

def main():
    print(f"[ETL] Merging Logs -> {HISTORY_FILE}")
    # 1. Find Files
    files = glob.glob(os.path.join(DATA_ROOT, "**", "*stats_log*.csv"), recursive=True)
    raw_files = [f for f in files if "MASTER" not in f and "unknown" not in f]
    
    if not raw_files:
        print("⚠️  No new logs found.")
        return

    # 2. Extract Data
    new_records = []
    for f in raw_files:
        try:
            df = pd.read_csv(f)
            if 'disk_usage' in df.columns:
                node = os.path.basename(f).split('_stats_log')[0]
                latest = df.iloc[-1]
                new_records.append({
                    'timestamp': latest['timestamp'],
                    'node_name': node,
                    'disk_used_kb': float(latest['disk_usage']) * 10000, 
                    'recording_size_kb': 0
                })
        except: pass

    # 3. Merge & Save
    if new_records:
        if os.path.exists(HISTORY_FILE):
            df_hist = pd.read_csv(HISTORY_FILE)
        else:
            df_hist = pd.DataFrame(columns=['timestamp', 'node_name', 'disk_used_kb', 'recording_size_kb'])
        
        df_combined = pd.concat([df_hist, pd.DataFrame(new_records)], ignore_index=True)
        df_combined.drop_duplicates(subset=['timestamp', 'node_name'], keep='last', inplace=True)
        df_combined.to_csv(HISTORY_FILE, index=False)
        print(f"✅ Saved {len(df_combined)} records to {HISTORY_FILE}")

if __name__ == "__main__":
    main()
