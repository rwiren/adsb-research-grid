#!/usr/bin/env python3
"""
# ==============================================================================
# FILE: scripts/plot_storage.py
# PROJECT: ADS-B Spoofing Data Collection
# VERSION: 0.4.9 (Git Tag Prep)
# DESCRIPTION: Visualizes storage usage trends across all sensor nodes.
# ==============================================================================
"""
import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime

# --- CONFIGURATION ---
INPUT_FILE = os.path.join("data", "storage_history.csv")
# UPDATED: Structured output path for better organization
OUTPUT_DIR = os.path.join("output", "plots", "storage")

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Missing: {INPUT_FILE}")
        return

    # Load data
    try:
        df = pd.read_csv(INPUT_FILE)
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return

    if df.empty:
        print("⚠️  Dataset is empty.")
        return

    # [FIX] Handle mixed timestamp formats (ISO8601 with/without micros)
    try:
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed')
    except Exception as e:
        print(f"❌ Timestamp parsing failed: {e}")
        return

    # Setup Plot
    plt.figure(figsize=(10, 6))
    
    nodes = df['node_name'].unique()
    for node in nodes:
        subset = df[df['node_name'] == node].sort_values('timestamp')
        plt.plot(subset['timestamp'], subset['disk_used_kb'], label=node, marker='o')

    plt.title(f"Grid Storage Usage (v0.4.9)")
    plt.ylabel("Disk Usage (KB)")
    plt.xlabel("Time")
    plt.legend()
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Save
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"storage_report_{ts}.png")
    
    plt.savefig(output_path)
    print(f"✅ Report saved to {output_path}")

if __name__ == "__main__":
    main()
