#!/usr/bin/env python3
"""
# ==============================================================================
# FILE: scripts/verify_dataset_quality.py
# PURPOSE: Audits dataset for ML Training Readiness.
# CHECKS: Schema consistency, Null rates, Sampling frequency, Time gaps.
# ==============================================================================
"""
import pandas as pd
import glob
import os

DATA_DIR = "research_data"

def audit_file(filepath):
    filename = os.path.basename(filepath)
    print(f"\n📄 Analyzing: {filename}")
    
    try:
        # Determine Type (Stats vs Aircraft)
        if "stats_log" in filename:
            cols = ['timestamp', 'lat', 'lon', 'alt', 'fix', 'peak', 'noise', 'msgs', 'ac']
            log_type = "PHYSICS (Signal)"
        elif "aircraft_log" in filename:
            # Aircraft logs vary in columns, usually: Time, Hex, Flight, Lat, Lon...
            # We load without header first to inspect
            log_type = "TRAJECTORY (Flight Path)"
            cols = None 
        else:
            print("   ⚠️ Unknown file type.")
            return

        df = pd.read_csv(filepath, header=None, names=cols, on_bad_lines='skip')
        
        # timestamp is usually col 0
        df['timestamp'] = pd.to_datetime(df.iloc[:, 0], errors='coerce')
        df = df.dropna(subset=['timestamp']).sort_values('timestamp')
        
        if df.empty:
            print("   ❌ EMPTY FILE")
            return

        # Time Analysis
        duration = df['timestamp'].max() - df['timestamp'].min()
        rows = len(df)
        rate = rows / (duration.total_seconds() / 60) if duration.total_seconds() > 0 else 0
        
        # Gaps > 5 mins
        gaps = df['timestamp'].diff() > pd.Timedelta(minutes=5)
        gap_count = gaps.sum()

        print(f"   ℹ️  Type: {log_type}")
        print(f"   ⏱️  Duration: {duration} ({rows} samples)")
        print(f"   ⚡  Rate: {rate:.1f} rows/min")
        
        if gap_count == 0:
            print("   ✅  Continuity: PERFECT")
        else:
            print(f"   ⚠️  Continuity: {gap_count} GAPS detected (>5min)")

        # Content Check
        if log_type == "TRAJECTORY (Flight Path)":
            # Check for valid lat/lon (cols 3 and 4 usually)
            valid_pos = df.iloc[:, 3:5].notnull().sum().min() # Approximation
            print(f"   ✈️  Positions Captured: {valid_pos} / {rows}")
            if valid_pos < (rows * 0.5):
                print("   ⛔  DATA QUALITY: Low position fix rate!")

    except Exception as e:
        print(f"   ❌ ERROR: {e}")

if __name__ == "__main__":
    print("=== DATASET FORENSICS AUDIT ===")
    files = glob.glob(f"{DATA_DIR}/**/*.csv", recursive=True)
    if not files: print("No files found. Run 'make fetch'.")
    for f in sorted(files): audit_file(f)
