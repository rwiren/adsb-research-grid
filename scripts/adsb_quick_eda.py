import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os

# --- CONFIGURATION ---
# Get the absolute path of the script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Navigate up one level to project root, then into research_data
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "research_data", "2026-01-09")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "analysis")

def load_data():
    try:
        n_air_path = os.path.join(DATA_DIR, "north", "sensor-north_aircraft_log_2026-01-09.csv")
        n_stats_path = os.path.join(DATA_DIR, "north", "sensor-north_stats_log_2026-01-09.csv")
        w_air_path = os.path.join(DATA_DIR, "west", "sensor-west_aircraft_log_2026-01-09.csv")
        w_stats_path = os.path.join(DATA_DIR, "west", "sensor-west_stats_log_2026-01-09.csv")

        print(f"Loading North from: {n_air_path}")
        n_air = pd.read_csv(n_air_path)
        n_stats = pd.read_csv(n_stats_path)
        w_air = pd.read_csv(w_air_path)
        w_stats = pd.read_csv(w_stats_path)
        return n_air, n_stats, w_air, w_stats
        
    except FileNotFoundError:
        print(f"\n❌ ERROR: Could not find data files in: {DATA_DIR}")
        exit()

# Load
n_air, n_stats, w_air, w_stats = load_data()
n_air['sensor'] = 'North'
w_air['sensor'] = 'West'
n_stats['sensor'] = 'North'
w_stats['sensor'] = 'West'

# Combine
air = pd.concat([n_air, w_air], ignore_index=True)
stats = pd.concat([n_stats, w_stats], ignore_index=True)
air['dt'] = pd.to_datetime(air['timestamp'], unit='s')
stats['dt'] = pd.to_datetime(stats['timestamp'], unit='s')

print(f"✅ Data Loaded. Total Frames: {len(air)}")

# --- PLOTTING ---
sns.set_theme(style="whitegrid")
fig = plt.figure(figsize=(16, 12))
plt.suptitle(f"ADS-B Research Analysis: 2026-01-09", fontsize=16, fontweight='bold')

# 1. Map
plt.subplot(2, 2, 1)
sns.scatterplot(data=air, x='lon', y='lat', hue='sensor', s=10, alpha=0.5)
plt.title("Spatial Coverage")

# 2. Altitude
plt.subplot(2, 2, 2)
air['alt_numeric'] = pd.to_numeric(air['alt_baro'], errors='coerce')
sns.histplot(data=air, x='alt_numeric', hue='sensor', element="step", bins=30)
plt.title("Altitude Profile")

# 3. RSSI
plt.subplot(2, 2, 3)
sns.kdeplot(data=air, x='rssi', hue='sensor', fill=True)
plt.title("Signal Strength Distribution")

# 4. Message Rate
plt.subplot(2, 2, 4)
# Fix for pandas warning: explicitly selecting column before resample
rate = air.set_index('dt').groupby('sensor')['hex'].resample('5min').count().reset_index(name='msg_count')
sns.lineplot(data=rate, x='dt', y='msg_count', hue='sensor')
plt.title("Traffic Density (Messages/5min)")

plt.tight_layout()

# --- SAVE TO FILE ---
output_file = os.path.join(OUTPUT_DIR, "eda_report_2026-01-09.png")
plt.savefig(output_file)
print(f"\n📸 Analysis saved to: {output_file}")
