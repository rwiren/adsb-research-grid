#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
ADS-B Research Grid - Exploratory Data Analysis (EDA) Tool
--------------------------------------------------------------------------------
Version: 0.2.2
Author:  Riku Wiren
License: MIT
Context: Reads raw Beast Binary (.bin) files from 'readsb' and generates 
         health-check visualizations.

Usage:
    python3 scripts/eda_check.py --input data/raw/latest.bin --output analysis/report
--------------------------------------------------------------------------------
"""

import os
import sys
import glob
import struct
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import pyModeS as pms
from datetime import datetime

# --- Configuration ---
__version__ = "0.2.2"
SENSOR_LAT = 60.319555
SENSOR_LON = 24.830816
# Beast binary escape character
BEAST_ESCAPE = 0x1A

def parse_beast_file(file_path):
    """
    Parses a Beast Binary file into a list of decoded messages.
    Format: <0x1a> <1 byte type> <6 byte timestamp> <signal> <N byte msg>
    """
    messages = []
    print(f"[INFO] Reading binary file: {file_path}")
    
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        print("[WARN] File is empty. Skipping.")
        return pd.DataFrame()

    with open(file_path, 'rb') as f:
        data = f.read()
        
    i = 0
    total_len = len(data)
    
    while i < total_len:
        if data[i] != BEAST_ESCAPE:
            i += 1
            continue
            
        # We found 0x1A. Next byte is type.
        if i + 1 >= total_len: break
        msg_type = data[i+1]
        
        # Beast Types: 0x31 (Mode-AC), 0x32 (Mode-S Short), 0x33 (Mode-S Long)
        # We skip the 0x1A escape itself (index i)
        
        if msg_type == 0x32: # Mode-S Short (56-bit)
            msg_len = 7
        elif msg_type == 0x33: # Mode-S Long (112-bit)
            msg_len = 14
        else:
            # Other types (status, etc) or double-escape. Skip.
            i += 2
            continue
            
        # Frame structure: [Type:1][MLAT:6][Signal:1][Message:N]
        # Total frame length excluding 0x1a is 1 + 6 + 1 + N
        frame_len = 1 + 6 + 1 + msg_len
        
        if i + 1 + frame_len > total_len:
            break
            
        # Extract Signal Strength (RSSI)
        # Signal is at offset: 1 (type) + 6 (timestamp) = 7 (0-indexed relative to type)
        signal_idx = i + 1 + 1 + 6
        signal_raw = data[signal_idx]
        
        # Calculate RSSI (approximate formula for RTL-SDR in Beast)
        # RSSI = 10 * log10(signal^2 / impedance) ... simplified map:
        rssi_db = (signal_raw / 255.0) * 100.0 # Normalized 0-100 scale for this plot
        
        # Extract Message Hex
        msg_start = signal_idx + 1
        msg_end = msg_start + msg_len
        msg_bytes = data[msg_start:msg_end]
        msg_hex = msg_bytes.hex().upper()
        
        # Append raw data
        messages.append({
            'timestamp_raw': i, # Using byte offset as relative time for now
            'type': msg_type,
            'hex': msg_hex,
            'rssi': rssi_db,
            'len': msg_len
        })
        
        # Advance pointer
        i += (1 + frame_len)

    print(f"[INFO] Parsed {len(messages)} raw frames.")
    return pd.DataFrame(messages)

def decode_messages(df):
    """
    Decodes raw Mode-S hex strings using pyModeS.
    """
    print("[INFO] Decoding Mode-S frames (this may take a moment)...")
    
    decoded = []
    for _, row in df.iterrows():
        msg = row['hex']
        
        try:
            icao = pms.df(msg)
            tc = pms.typecode(msg)
            
            # Identify basic contents
            entry = {
                'hex': msg,
                'rssi': row['rssi'],
                'icao': icao,
                'tc': tc,
                'lat': None, 'lon': None, 'alt': None, 'speed': None
            }
            
            # Simple decoding of position/velocity if type matches
            # (Note: Full position decoding requires odd/even frame matching, 
            #  this is a simplified 'check' to see if data exists)
            if 9 <= tc <= 18:
                entry['is_position'] = True
                entry['alt'] = pms.adsb.altitude(msg)
            elif tc == 19:
                entry['is_velocity'] = True
                entry['speed'] = pms.adsb.velocity(msg)[0] # speed, heading, etc
                
            decoded.append(entry)
            
        except Exception:
            continue
            
    return pd.DataFrame(decoded)

def generate_plots(df, output_dir):
    """
    Generates the 5 key health-check plots.
    """
    if df.empty:
        print("[ERR] No data to plot.")
        return

    sns.set_theme(style="whitegrid")
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. RSSI Distribution
    plt.figure(figsize=(10, 6))
    sns.histplot(df['rssi'], bins=50, color='blue', kde=True)
    plt.title(f"Signal Strength Distribution (N={len(df)})")
    plt.xlabel("Signal Quality (0-100 Scale)")
    plt.savefig(f"{output_dir}/01_rssi_dist.png")
    plt.close()
    
    # 2. Traffic Volume (Message Counts)
    plt.figure(figsize=(10, 6))
    df['rssi'].plot(kind='line', linewidth=0.5, alpha=0.5)
    plt.title("Message Stream Density")
    plt.xlabel("Message Index")
    plt.ylabel("Signal Strength")
    plt.savefig(f"{output_dir}/02_traffic_density.png")
    plt.close()

    # 3. Message Type Code Distribution
    if 'tc' in df.columns:
        plt.figure(figsize=(8, 8))
        df['tc'].value_counts().sort_index().plot(kind='bar')
        plt.title("ADS-B Message Type Codes (1-4=ID, 9-18=Pos, 19=Vel)")
        plt.xlabel("Type Code")
        plt.savefig(f"{output_dir}/03_type_codes.png")
        plt.close()

    print(f"[SUCCESS] Plots generated in {output_dir}/")

def main():
    parser = argparse.ArgumentParser(description="ADS-B EDA Tool")
    parser.add_argument('--input', required=True, help="Path to .bin file")
    parser.add_argument('--output', default="analysis/latest", help="Output directory")
    args = parser.parse_args()

    print(f"--- ADS-B Research Grid EDA v{__version__} ---")
    
    df_raw = parse_beast_file(args.input)
    if not df_raw.empty:
        df_decoded = decode_messages(df_raw)
        generate_plots(df_decoded, args.output)
        
        # Summary Table
        print("\n--- Capture Summary ---")
        print(f"Total Messages: {len(df_raw)}")
        print(f"Decodable Mode-S: {len(df_decoded)}")
        print(f"Unique Aircraft (ICAO): {df_decoded['icao'].nunique() if not df_decoded.empty else 0}")
        if not df_decoded.empty:
            print(f"Avg Signal Quality: {df_decoded['rssi'].mean():.2f}")

if __name__ == "__main__":
    main()
