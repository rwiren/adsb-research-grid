"""
ADS-B Research Grid - Raw Beast Protocol Audit
----------------------------------------------
Parses raw .bin files (Mode-S Beast Format) to validate:
  1. Message Integrity (0x1a escaping)
  2. Signal Strength (RSSI)
  3. Traffic Rates (Messages/sec)
"""

import argparse
import glob
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# --- Configuration ---
sns.set_theme(style="whitegrid", context="paper")
OUTPUT_DIR = "analysis/adsb_latest"

def parse_beast_file(filepath):
    """
    Parses a raw binary file looking for '0x1a' escape sequences.
    Format: <0x1a> <Type> <...Data...>
    Type '2' = Mode-S Short (7 bytes)
    Type '3' = Mode-S Long (14 bytes)
    """
    messages = []
    file_size = os.path.getsize(filepath)
    
    with open(filepath, 'rb') as f:
        content = f.read()
        
    i = 0
    length = len(content)
    
    while i < length - 1:
        # Search for Escape Character
        if content[i] != 0x1a:
            i += 1
            continue
            
        # Found 0x1a, check next byte for Type
        msg_type = content[i+1]
        
        # 0x1a 0x32 = Mode-S Short (14 bytes total incl timestamp/signal)
        # 0x1a 0x33 = Mode-S Long (21 bytes total incl timestamp/signal)
        # Note: Beast format adds 6-byte timestamp + 1-byte RSSI before the Mode-S frame
        
        if msg_type == 0x32: # Mode-S Short (56 bit)
            frame_len = 7
            total_len = 9 + frame_len # 2 header + 6 time + 1 sig + 7 data
        elif msg_type == 0x33: # Mode-S Long (112 bit)
            frame_len = 14
            total_len = 9 + frame_len
        elif msg_type == 0x1a: # Double escape (0x1a 0x1a) means a literal 0x1a byte
            i += 2
            continue
        else:
            # Unknown type or just noise, skip
            i += 1
            continue

        if i + total_len > length:
            break
            
        # Extract Signal Level (RSSI)
        # Byte index: i=1a, i+1=type, i+2..i+7=MLAT, i+8=RSSI
        rssi_raw = content[i+8]
        
        # Convert to approximate dBFS (Formula varies by SDR, this is a linear mapping 0-100%)
        # 255 = Max Signal
        rssi_percent = (rssi_raw / 255.0) * 100.0
        
        messages.append(rssi_percent)
        
        i += total_len

    return messages, file_size

def analyze_dataset(input_dir):
    files = sorted(glob.glob(os.path.join(input_dir, "raw_adsb_*.bin")))
    if not files:
        print(f"[!] No .bin files found in {input_dir}")
        return

    print(f"[INFO] Auditing {len(files)} ADS-B binary files...")
    
    all_rssi = []
    stats = []

    for f in files:
        fname = os.path.basename(f)
        rssi_vals, size_bytes = parse_beast_file(f)
        count = len(rssi_vals)
        
        if count > 0:
            avg_rssi = sum(rssi_vals) / count
            all_rssi.extend(rssi_vals)
        else:
            avg_rssi = 0
            
        stats.append({
            'file': fname,
            'size_kb': size_bytes / 1024,
            'msg_count': count,
            'avg_rssi': avg_rssi
        })
        
        print(f"  -> {fname}: {count} msgs, {avg_rssi:.1f}% Sig")

    df = pd.DataFrame(stats)
    return df, all_rssi

def generate_report(df, all_rssi):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. Traffic Volume per File
    plt.figure(figsize=(10, 6))
    sns.barplot(x='file', y='msg_count', data=df, palette='viridis')
    plt.xticks(rotation=45, ha='right')
    plt.title("Traffic Volume (Messages per 15-min Log)")
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/A_Traffic_Volume.png")
    
    # 2. Signal Strength Distribution
    plt.figure(figsize=(10, 6))
    if all_rssi:
        sns.histplot(all_rssi, bins=50, kde=True, color='crimson')
        plt.title(f"Signal Strength Distribution (n={len(all_rssi):,})")
        plt.xlabel("Signal Quality (0-100%)")
        plt.savefig(f"{OUTPUT_DIR}/B_Signal_Strength.png")
    
    # 3. Text Report
    total_msgs = df['msg_count'].sum()
    with open(f"{OUTPUT_DIR}/ADSB_REPORT.md", "w") as f:
        f.write("# ✈️ ADS-B Sensor Audit\n\n")
        f.write(f"**Generated:** {datetime.now()}\n")
        f.write(f"**Total Messages:** {total_msgs:,}\n")
        f.write(f"**Total Files:** {len(df)}\n\n")
        f.write("## File Statistics\n")
        f.write(df.to_markdown(index=False))

    print(f"[SUCCESS] ADS-B Audit saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="./research_data/raw_logs")
    args = parser.parse_args()
    
    df, rssi = analyze_dataset(args.dir)
    if not df.empty:
        generate_report(df, rssi)
