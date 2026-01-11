#!/usr/bin/env python3
"""
# ==============================================================================
# FILE: scripts/plot_trajectory_analysis.py
# PURPOSE: Visualizes Flight Paths from 'aircraft_log.csv'.
# ROBUSTNESS: Handles mixed types, missing columns, and empty files.
# ==============================================================================
"""
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os

DATA_DIR = "research_data"
OUTPUT_DIR = "output/plots"

def load_aircraft_data():
    files = glob.glob(f"{DATA_DIR}/**/*aircraft_log*.csv", recursive=True)
    dfs = []
    print(f"🔍 Found {len(files)} aircraft log files.")
    
    # Define Schema (Matches smart_adsb_logger.py)
    cols = ['time', 'hex', 'flight', 'lat', 'lon', 'alt', 'spd', 'hdg', 'sqk', 'rssi']
    
    for f in files:
        try:
            # FORCE ALL TO STRING to prevent "Mixed Type" crash
            df = pd.read_csv(f, names=cols, header=None, on_bad_lines='skip', dtype=str)
            
            # Identify Sensor
            sensor = "Unknown"
            if "sensor-north" in f: sensor = "North"
            elif "sensor-east" in f or "3_" in f: sensor = "East"
            elif "sensor-west" in f or "2_" in f: sensor = "West"
            
            df['sensor'] = sensor
            
            # Convert Lat/Lon to Numeric (Coerce errors to NaN)
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
            
            # Drop invalid rows
            df = df.dropna(subset=['lat', 'lon'])
            
            if not df.empty:
                dfs.append(df)
                print(f"   -> {sensor}: Loaded {len(df)} points")
                
        except Exception as e: 
            print(f"   ⚠️ Skipped {os.path.basename(f)}: {e}")
    
    return pd.concat(dfs) if dfs else pd.DataFrame()

def plot_coverage(df):
    plt.figure(figsize=(14, 12))
    
    # Plot with error handling for empty data
    try:
        sns.scatterplot(data=df, x='lon', y='lat', hue='sensor', s=15, alpha=0.5, palette='bright', edgecolor=None)
        
        plt.title(f"Grid Coverage Analysis: Captured Trajectories ({len(df)} points)")
        plt.xlabel("Longitude")
        plt.ylabel("Latitude")
        plt.legend(title="Sensor Node", loc='upper right')
        plt.grid(True, alpha=0.3, linestyle='--')
        plt.axis('equal') 
        
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
            
        path = f"{OUTPUT_DIR}/trajectory_coverage_map.png"
        plt.savefig(path, dpi=300)
        print(f"✅ Map saved to: {path}")
        
    except Exception as e:
        print(f"❌ Plotting Error: {e}")

if __name__ == "__main__":
    df = load_aircraft_data()
    if not df.empty:
        plot_coverage(df)
    else:
        print("❌ No valid trajectory data found.")
