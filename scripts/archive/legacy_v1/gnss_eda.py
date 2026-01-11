"""
ADS-B Research Grid - GNSS NMEA Audit Tool
------------------------------------------
Parses Raw NMEA logs ($GNRMC, $GNGGA) to analyze:
  1. 2D Position Drift (Lat/Lon Stability)
  2. Altitude Stability (if $GNGGA is present)
"""

import argparse
import glob
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# --- Configuration ---
sns.set_theme(style="whitegrid")
OUTPUT_DIR = "analysis/gnss_latest"

def nmea_to_decimal(value, direction):
    """Converts NMEA ddmm.mmmmm to decimal degrees."""
    if not value or value == '': return None
    try:
        # NMEA format: DDDMM.MMMMM
        # Last 2 chars of integer part + decimals are Minutes.
        # The rest is Degrees.
        dot_pos = value.find('.')
        if dot_pos == -1: return None
        
        degrees_len = dot_pos - 2
        if degrees_len < 1: return None # Safety
        
        degrees = float(value[:degrees_len])
        minutes = float(value[degrees_len:])
        decimal = degrees + (minutes / 60.0)
        
        if direction in ['S', 'W']:
            decimal = -decimal
        return decimal
    except:
        return None

def parse_gnss_logs(input_dir):
    files = sorted(glob.glob(os.path.join(input_dir, "raw_gnss_*.log")))
    if not files:
        print(f"[!] No log files found in {input_dir}")
        return pd.DataFrame()

    print(f"[INFO] Parsing {len(files)} NMEA log files...")
    
    data = []

    for filepath in files:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line.startswith('$'): continue
                
                parts = line.split(',')
                msg_type = parts[0][3:] # Remove $GN / $GP prefix (e.g., RMC, GGA)
                
                # $GNRMC: Recommended Minimum Data (Lat, Lon, Speed, Date)
                if msg_type == 'RMC':
                    # Structure: $GNRMC,Time,Status,Lat,NS,Lon,EW,Spd,Trk,Date...
                    try:
                        if parts[2] == 'A': # A = Active/Valid
                            time_str = parts[1]
                            date_str = parts[9]
                            lat = nmea_to_decimal(parts[3], parts[4])
                            lon = nmea_to_decimal(parts[5], parts[6])
                            
                            # Construct timestamp
                            if time_str and date_str:
                                dt_str = f"{date_str} {time_str}"
                                ts = datetime.strptime(dt_str, "%d%m%y %H%M%S.%f")
                                
                                data.append({
                                    'timestamp': ts,
                                    'lat': lat,
                                    'lon': lon,
                                    'type': '2D'
                                })
                    except (ValueError, IndexError):
                        pass

                # $GNGGA: Fix Data (includes Altitude)
                elif msg_type == 'GGA':
                    # Structure: $GNGGA,Time,Lat,NS,Lon,EW,Qual,Sats,HDOP,Alt,M...
                    try:
                        if int(parts[6]) > 0: # Fix Quality > 0
                            lat = nmea_to_decimal(parts[2], parts[3])
                            lon = nmea_to_decimal(parts[4], parts[5])
                            alt = float(parts[9]) if parts[9] else None
                            
                            # GGA doesn't have date, so we skip timestamp or infer it
                            # For simple distribution analysis, we just take the values
                            if alt is not None:
                                data.append({
                                    'lat': lat,
                                    'lon': lon,
                                    'alt': alt,
                                    'type': '3D'
                                })
                    except (ValueError, IndexError):
                        pass

    df = pd.DataFrame(data)
    return df

def generate_dashboard(df):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    if df.empty:
        print("[!] No valid GPS fixes found in logs.")
        return

    print(f"[INFO] Analyzing {len(df)} position samples...")

    # 1. Position Drift (Scatter Plot)
    plt.figure(figsize=(8, 8))
    sns.scatterplot(x='lon', y='lat', data=df, alpha=0.3, s=10, color='purple')
    
    # Calculate Center
    center_lat = df['lat'].mean()
    center_lon = df['lon'].mean()
    plt.plot(center_lon, center_lat, 'r+', markersize=15, label='Mean Position')
    
    plt.title(f"GPS Position Drift\nMean: {center_lat:.5f}, {center_lon:.5f}")
    plt.axis('equal')
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/A_Position_Drift.png")
    print(f"[PLOT] Saved Drift Map to {OUTPUT_DIR}")

    # 2. Altitude Stability (If available)
    if 'alt' in df.columns and df['alt'].notnull().any():
        df_alt = df.dropna(subset=['alt'])
        mean_alt = df_alt['alt'].mean()
        std_alt = df_alt['alt'].std()
        
        plt.figure(figsize=(10, 6))
        sns.histplot(df_alt['alt'], bins=30, kde=True, color='navy')
        plt.axvline(mean_alt, color='red', linestyle='--', label=f'Mean: {mean_alt:.2f}m')
        plt.title(f"Altitude Distribution (StdDev: {std_alt:.2f}m)")
        plt.xlabel("Altitude (Meters)")
        plt.legend()
        plt.savefig(f"{OUTPUT_DIR}/B_Altitude_Dist.png")
        print(f"[PLOT] Saved Altitude stats (Mean: {mean_alt:.2f}m)")
    else:
        print("[WARN] No Altitude data found (Only RMC messages present?)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="./research_data/raw_logs")
    args = parser.parse_args()
    
    df = parse_gnss_logs(args.dir)
    generate_dashboard(df)
