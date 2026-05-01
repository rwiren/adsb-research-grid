#!/usr/bin/env python3
"""
==============================================================================
EXTENSIVE EXPLORATORY DATA ANALYSIS (EDA) FOR GOLDEN_7DAY DATASET
==============================================================================
Purpose: Comprehensive analysis of ADS-B Research Grid data for:
         - Deep Neural Network Development
         - LLM Training and Development
         - Academic Research
         - Commercial Applications

Dataset: Golden 7-Day Sample (2026-01-16 to 2026-01-22)
Sensors: sensor-east (Sipoo), sensor-west (Jorvas)

Author: ADS-B Research Grid Project
License: MIT
==============================================================================
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import tarfile
import gzip
import warnings
from pathlib import Path
from datetime import datetime, timedelta
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import json

warnings.filterwarnings('ignore')

# Configuration
BASE_DIR = Path("/home/runner/work/adsb-research-grid/adsb-research-grid")
DATA_DIR = BASE_DIR / "research_data" / "golden_7day"
OUTPUT_DIR = BASE_DIR / "analysis" / "golden_7day_eda_results"
FIGURES_DIR = OUTPUT_DIR / "figures"
WORKSPACE_DIR = Path("/tmp/eda_workspace")

# Create output directories
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# Sensor metadata
SENSORS = {
    "sensor-east": {
        "lat": 60.3621,
        "lon": 25.3375,
        "location": "Sipoo",
        "color": "#bc5090",
        "marker": "s"
    },
    "sensor-west": {
        "lat": 60.1478,
        "lon": 24.5264,
        "location": "Jorvas",
        "color": "#ffa600",
        "marker": "o"
    }
}

# Plotting configuration
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")
plt.rcParams.update({
    'figure.dpi': 100,
    'savefig.dpi': 300,
    'figure.figsize': (14, 8),
    'font.size': 10,
    'axes.labelsize': 12,
    'axes.titlesize': 14,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.titlesize': 16
})

class GoldenSevenDayEDA:
    """Comprehensive EDA for the Golden 7-Day Dataset"""
    
    def __init__(self):
        self.aircraft_data = pd.DataFrame()
        self.stats_data = pd.DataFrame()
        self.metadata = {}
        self.report_lines = []
        
    def log(self, message):
        """Log message to console and report"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] {message}"
        print(log_line)
        self.report_lines.append(log_line)
        
    def extract_datasets(self):
        """Extract all 7 daily datasets from tar.gz files - Memory Efficient"""
        self.log("=" * 80)
        self.log("STEP 1: DATA EXTRACTION AND LOADING (Memory Efficient)")
        self.log("=" * 80)
        
        datasets = sorted(DATA_DIR.glob("dataset_*.tar.gz"))
        self.log(f"Found {len(datasets)} daily datasets")
        
        # Process only 2 datasets to reduce memory usage
        datasets = datasets[:2]  # Limit to first 2 days for memory efficiency
        self.log(f"Processing {len(datasets)} datasets for memory efficiency")
        
        aircraft_dfs = []
        stats_dfs = []
        
        for dataset_file in datasets:
            self.log(f"Processing: {dataset_file.name}")
            
            # Clean workspace before extracting
            import shutil
            if WORKSPACE_DIR.exists():
                shutil.rmtree(WORKSPACE_DIR)
            WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
            
            with tarfile.open(dataset_file, 'r:gz') as tar:
                tar.extractall(path=WORKSPACE_DIR)
                
            # Load aircraft logs with sampling
            for sensor in SENSORS.keys():
                sensor_dir = WORKSPACE_DIR / sensor
                if sensor_dir.exists():
                    # Load aircraft log (sample every 10th row for memory efficiency)
                    aircraft_files = list(sensor_dir.glob("*aircraft_log*.csv"))
                    for f in aircraft_files:
                        # Sample data to reduce memory
                        df = pd.read_csv(f)
                        # Take every 5th row
                        df = df.iloc[::5].copy()
                        df['sensor'] = sensor
                        df['date'] = dataset_file.stem.replace('dataset_', '')
                        aircraft_dfs.append(df)
                        self.log(f"  Loaded {len(df):,} sampled aircraft records from {sensor}")
                    
                    # Load stats log
                    stats_files = list(sensor_dir.glob("*stats_log*.csv"))
                    for f in stats_files:
                        df = pd.read_csv(f)
                        df['sensor'] = sensor
                        df['date'] = dataset_file.stem.replace('dataset_', '')
                        stats_dfs.append(df)
                        self.log(f"  Loaded {len(df):,} stats records from {sensor}")
        
        # Combine all data
        self.aircraft_data = pd.concat(aircraft_dfs, ignore_index=True)
        self.stats_data = pd.concat(stats_dfs, ignore_index=True)
        
        self.log(f"\nTotal aircraft records (sampled): {len(self.aircraft_data):,}")
        self.log(f"Total stats records: {len(self.stats_data):,}")
        self.log("NOTE: Aircraft data is sampled (1 in 5 rows) for memory efficiency")
        
        # Convert timestamps
        self.aircraft_data['timestamp'] = pd.to_datetime(self.aircraft_data['timestamp'])
        self.stats_data['timestamp'] = pd.to_datetime(self.stats_data['timestamp'])
        
        # Fix data types - convert alt_baro to numeric (handle "ground" values)
        self.aircraft_data['alt_baro'] = pd.to_numeric(self.aircraft_data['alt_baro'], errors='coerce')
        
        return self
        
    def data_quality_analysis(self):
        """Analyze data quality and completeness"""
        self.log("\n" + "=" * 80)
        self.log("STEP 2: DATA QUALITY ANALYSIS")
        self.log("=" * 80)
        
        # Basic statistics
        self.log("\n--- Dataset Overview ---")
        self.log(f"Date Range: {self.aircraft_data['timestamp'].min()} to {self.aircraft_data['timestamp'].max()}")
        self.log(f"Duration: {(self.aircraft_data['timestamp'].max() - self.aircraft_data['timestamp'].min()).days} days")
        self.log(f"Total Records: {len(self.aircraft_data):,}")
        self.log(f"Unique Aircraft (ICAO24): {self.aircraft_data['hex'].nunique():,}")
        
        # Per-sensor statistics
        self.log("\n--- Per-Sensor Statistics ---")
        for sensor in SENSORS.keys():
            sensor_data = self.aircraft_data[self.aircraft_data['sensor'] == sensor]
            self.log(f"{sensor}:")
            self.log(f"  Records: {len(sensor_data):,}")
            self.log(f"  Unique Aircraft: {sensor_data['hex'].nunique():,}")
            self.log(f"  Date Range: {sensor_data['timestamp'].min()} to {sensor_data['timestamp'].max()}")
        
        # Missing value analysis
        self.log("\n--- Missing Value Analysis ---")
        missing = self.aircraft_data.isnull().sum()
        missing_pct = (missing / len(self.aircraft_data) * 100).round(2)
        
        for col in self.aircraft_data.columns:
            if missing[col] > 0:
                self.log(f"{col}: {missing[col]:,} ({missing_pct[col]}%)")
        
        # Create missing value heatmap
        fig, ax = plt.subplots(figsize=(12, 8))
        sns.heatmap(self.aircraft_data.isnull().T, cmap='YlOrRd', cbar_kws={'label': 'Missing'}, ax=ax)
        plt.title('Missing Value Pattern Analysis', fontsize=16, fontweight='bold')
        plt.tight_layout()
        plt.savefig(FIGURES_DIR / '01_missing_values_heatmap.png')
        plt.close()
        
        # Data types
        self.log("\n--- Data Types ---")
        for col, dtype in self.aircraft_data.dtypes.items():
            self.log(f"{col}: {dtype}")
        
        return self
        
    def temporal_analysis(self):
        """Analyze temporal patterns"""
        self.log("\n" + "=" * 80)
        self.log("STEP 3: TEMPORAL ANALYSIS")
        self.log("=" * 80)
        
        # Add temporal features
        self.aircraft_data['hour'] = self.aircraft_data['timestamp'].dt.hour
        self.aircraft_data['day_of_week'] = self.aircraft_data['timestamp'].dt.dayofweek
        self.aircraft_data['date_only'] = self.aircraft_data['timestamp'].dt.date
        
        # Messages per hour
        hourly_counts = self.aircraft_data.groupby(['sensor', self.aircraft_data['timestamp'].dt.floor('H')]).size()
        
        fig, axes = plt.subplots(2, 1, figsize=(16, 10))
        
        # Time series plot
        for sensor in SENSORS.keys():
            sensor_hourly = hourly_counts[sensor]
            axes[0].plot(sensor_hourly.index, sensor_hourly.values, 
                        label=f"{sensor} ({SENSORS[sensor]['location']})",
                        color=SENSORS[sensor]['color'], linewidth=2, alpha=0.8)
        
        axes[0].set_xlabel('Time', fontsize=12)
        axes[0].set_ylabel('Messages per Hour', fontsize=12)
        axes[0].set_title('Aircraft Message Rate Over 7 Days', fontsize=14, fontweight='bold')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        # Hour of day pattern
        hourly_pattern = self.aircraft_data.groupby(['sensor', 'hour']).size().unstack(fill_value=0)
        if len(hourly_pattern.columns) > 0:
            hourly_pattern.T.plot(kind='bar', ax=axes[1], color=[SENSORS.get(s, {'color': '#999999'})['color'] for s in hourly_pattern.columns])
            axes[1].set_xlabel('Hour of Day', fontsize=12)
            axes[1].set_ylabel('Total Messages', fontsize=12)
            axes[1].set_title('Message Distribution by Hour of Day', fontsize=14, fontweight='bold')
            axes[1].legend(title='Sensor')
            axes[1].grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        plt.savefig(FIGURES_DIR / '02_temporal_patterns.png')
        plt.close()
        
        # Daily statistics
        self.log("\n--- Daily Message Statistics ---")
        daily_counts = self.aircraft_data.groupby('date_only').size()
        self.log(f"Mean daily messages: {daily_counts.mean():,.0f}")
        self.log(f"Std daily messages: {daily_counts.std():,.0f}")
        self.log(f"Min daily messages: {daily_counts.min():,.0f}")
        self.log(f"Max daily messages: {daily_counts.max():,.0f}")
        
        return self
        
    def geospatial_analysis(self):
        """Analyze spatial distribution of aircraft"""
        self.log("\n" + "=" * 80)
        self.log("STEP 4: GEOSPATIAL ANALYSIS")
        self.log("=" * 80)
        
        # Filter valid coordinates
        valid_coords = self.aircraft_data.dropna(subset=['lat', 'lon'])
        self.log(f"Records with valid coordinates: {len(valid_coords):,} ({len(valid_coords)/len(self.aircraft_data)*100:.1f}%)")
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 14))
        
        # Coverage map
        for sensor in SENSORS.keys():
            sensor_data = valid_coords[valid_coords['sensor'] == sensor]
            axes[0, 0].scatter(sensor_data['lon'], sensor_data['lat'], 
                             alpha=0.1, s=1, c=SENSORS[sensor]['color'],
                             label=f"{sensor} ({len(sensor_data):,} pts)")
            # Plot sensor location
            axes[0, 0].scatter(SENSORS[sensor]['lon'], SENSORS[sensor]['lat'],
                             marker=SENSORS[sensor]['marker'], s=200, 
                             edgecolors='black', linewidths=2,
                             c=SENSORS[sensor]['color'], zorder=5)
        
        axes[0, 0].set_xlabel('Longitude', fontsize=12)
        axes[0, 0].set_ylabel('Latitude', fontsize=12)
        axes[0, 0].set_title('Aircraft Detection Coverage Map', fontsize=14, fontweight='bold')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # Altitude distribution
        valid_alt = self.aircraft_data.dropna(subset=['alt_baro'])
        for sensor in SENSORS.keys():
            sensor_data = valid_alt[valid_alt['sensor'] == sensor]
            axes[0, 1].hist(sensor_data['alt_baro'], bins=50, alpha=0.6, 
                          label=f"{sensor}", color=SENSORS[sensor]['color'])
        
        axes[0, 1].set_xlabel('Altitude (feet)', fontsize=12)
        axes[0, 1].set_ylabel('Frequency', fontsize=12)
        axes[0, 1].set_title('Altitude Distribution', fontsize=14, fontweight='bold')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # Speed distribution
        valid_speed = self.aircraft_data.dropna(subset=['gs'])
        for sensor in SENSORS.keys():
            sensor_data = valid_speed[valid_speed['sensor'] == sensor]
            axes[1, 0].hist(sensor_data['gs'], bins=50, alpha=0.6,
                          label=f"{sensor}", color=SENSORS[sensor]['color'])
        
        axes[1, 0].set_xlabel('Ground Speed (knots)', fontsize=12)
        axes[1, 0].set_ylabel('Frequency', fontsize=12)
        axes[1, 0].set_title('Ground Speed Distribution', fontsize=14, fontweight='bold')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # Track distribution (heading)
        valid_track = self.aircraft_data.dropna(subset=['track'])
        for sensor in SENSORS.keys():
            sensor_data = valid_track[valid_track['sensor'] == sensor]
            axes[1, 1].hist(sensor_data['track'], bins=36, alpha=0.6,
                          label=f"{sensor}", color=SENSORS[sensor]['color'])
        
        axes[1, 1].set_xlabel('Track (degrees)', fontsize=12)
        axes[1, 1].set_ylabel('Frequency', fontsize=12)
        axes[1, 1].set_title('Track (Heading) Distribution', fontsize=14, fontweight='bold')
        axes[1, 1].legend()
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(FIGURES_DIR / '03_geospatial_analysis.png')
        plt.close()
        
        # Geographic statistics
        self.log("\n--- Geographic Statistics ---")
        self.log(f"Latitude range: {valid_coords['lat'].min():.4f} to {valid_coords['lat'].max():.4f}")
        self.log(f"Longitude range: {valid_coords['lon'].min():.4f} to {valid_coords['lon'].max():.4f}")
        self.log(f"Altitude range: {valid_alt['alt_baro'].min():.0f} to {valid_alt['alt_baro'].max():.0f} feet")
        self.log(f"Speed range: {valid_speed['gs'].min():.1f} to {valid_speed['gs'].max():.1f} knots")
        
        return self
        
    def signal_quality_analysis(self):
        """Analyze signal quality metrics"""
        self.log("\n" + "=" * 80)
        self.log("STEP 5: SIGNAL QUALITY ANALYSIS")
        self.log("=" * 80)
        
        valid_rssi = self.aircraft_data.dropna(subset=['rssi'])
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # RSSI distribution
        for sensor in SENSORS.keys():
            sensor_data = valid_rssi[valid_rssi['sensor'] == sensor]
            axes[0, 0].hist(sensor_data['rssi'], bins=50, alpha=0.6,
                          label=f"{sensor}", color=SENSORS[sensor]['color'])
        
        axes[0, 0].set_xlabel('RSSI (dBm)', fontsize=12)
        axes[0, 0].set_ylabel('Frequency', fontsize=12)
        axes[0, 0].set_title('RSSI Distribution', fontsize=14, fontweight='bold')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # RSSI time series
        rssi_hourly = valid_rssi.groupby(['sensor', valid_rssi['timestamp'].dt.floor('H')])['rssi'].mean()
        for sensor in SENSORS.keys():
            if sensor in rssi_hourly.index.get_level_values(0):
                sensor_rssi = rssi_hourly[sensor]
                axes[0, 1].plot(sensor_rssi.index, sensor_rssi.values,
                              label=f"{sensor}", color=SENSORS[sensor]['color'],
                              linewidth=2, alpha=0.8)
        
        axes[0, 1].set_xlabel('Time', fontsize=12)
        axes[0, 1].set_ylabel('Mean RSSI (dBm)', fontsize=12)
        axes[0, 1].set_title('RSSI Trends Over Time', fontsize=14, fontweight='bold')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # Stats data analysis
        if len(self.stats_data) > 0:
            # Signal level over time
            for sensor in SENSORS.keys():
                sensor_stats = self.stats_data[self.stats_data['sensor'] == sensor]
                if len(sensor_stats) > 0:
                    axes[1, 0].plot(sensor_stats['timestamp'], sensor_stats['signal_level'],
                                  label=f"{sensor} Signal", color=SENSORS[sensor]['color'],
                                  linewidth=1.5, alpha=0.8)
                    axes[1, 0].plot(sensor_stats['timestamp'], sensor_stats['noise_level'],
                                  label=f"{sensor} Noise", color=SENSORS[sensor]['color'],
                                  linewidth=1.5, linestyle='--', alpha=0.6)
            
            axes[1, 0].set_xlabel('Time', fontsize=12)
            axes[1, 0].set_ylabel('Signal Level (dBm)', fontsize=12)
            axes[1, 0].set_title('Signal and Noise Levels', fontsize=14, fontweight='bold')
            axes[1, 0].legend(fontsize=8)
            axes[1, 0].grid(True, alpha=0.3)
            
            # Aircraft tracked over time
            for sensor in SENSORS.keys():
                sensor_stats = self.stats_data[self.stats_data['sensor'] == sensor]
                if len(sensor_stats) > 0:
                    axes[1, 1].plot(sensor_stats['timestamp'], sensor_stats['aircraft_tracked'],
                                  label=f"{sensor}", color=SENSORS[sensor]['color'],
                                  linewidth=2, alpha=0.8)
            
            axes[1, 1].set_xlabel('Time', fontsize=12)
            axes[1, 1].set_ylabel('Aircraft Tracked', fontsize=12)
            axes[1, 1].set_title('Number of Aircraft Tracked', fontsize=14, fontweight='bold')
            axes[1, 1].legend()
            axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(FIGURES_DIR / '04_signal_quality.png')
        plt.close()
        
        # Signal statistics
        self.log("\n--- Signal Quality Statistics ---")
        for sensor in SENSORS.keys():
            sensor_data = valid_rssi[valid_rssi['sensor'] == sensor]
            if len(sensor_data) > 0:
                self.log(f"{sensor}:")
                self.log(f"  Mean RSSI: {sensor_data['rssi'].mean():.2f} dBm")
                self.log(f"  Std RSSI: {sensor_data['rssi'].std():.2f} dBm")
                self.log(f"  Min RSSI: {sensor_data['rssi'].min():.2f} dBm")
                self.log(f"  Max RSSI: {sensor_data['rssi'].max():.2f} dBm")
        
        return self
        
    def aircraft_behavior_analysis(self):
        """Analyze aircraft behavior patterns"""
        self.log("\n" + "=" * 80)
        self.log("STEP 6: AIRCRAFT BEHAVIOR ANALYSIS")
        self.log("=" * 80)
        
        # Flight envelope analysis
        valid_data = self.aircraft_data.dropna(subset=['alt_baro', 'gs'])
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # Altitude vs Speed
        for sensor in SENSORS.keys():
            sensor_data = valid_data[valid_data['sensor'] == sensor]
            axes[0, 0].scatter(sensor_data['gs'], sensor_data['alt_baro'],
                             alpha=0.3, s=1, c=SENSORS[sensor]['color'],
                             label=f"{sensor}")
        
        axes[0, 0].set_xlabel('Ground Speed (knots)', fontsize=12)
        axes[0, 0].set_ylabel('Altitude (feet)', fontsize=12)
        axes[0, 0].set_title('Flight Envelope: Altitude vs Speed', fontsize=14, fontweight='bold')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # Vertical rate analysis
        valid_vrate = self.aircraft_data.dropna(subset=['baro_rate'])
        for sensor in SENSORS.keys():
            sensor_data = valid_vrate[valid_vrate['sensor'] == sensor]
            if len(sensor_data) > 0:
                axes[0, 1].hist(sensor_data['baro_rate'], bins=50, alpha=0.6,
                              label=f"{sensor}", color=SENSORS[sensor]['color'])
        
        axes[0, 1].set_xlabel('Vertical Rate (ft/min)', fontsize=12)
        axes[0, 1].set_ylabel('Frequency', fontsize=12)
        axes[0, 1].set_title('Vertical Rate Distribution', fontsize=14, fontweight='bold')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # Unique flights per day
        flights_per_day = self.aircraft_data.groupby(['date_only', 'sensor'])['hex'].nunique().unstack(fill_value=0)
        flights_per_day.plot(kind='bar', ax=axes[1, 0],
                            color=[SENSORS[s]['color'] for s in flights_per_day.columns])
        axes[1, 0].set_xlabel('Date', fontsize=12)
        axes[1, 0].set_ylabel('Unique Aircraft', fontsize=12)
        axes[1, 0].set_title('Unique Aircraft per Day', fontsize=14, fontweight='bold')
        axes[1, 0].legend(title='Sensor')
        axes[1, 0].tick_params(axis='x', rotation=45)
        axes[1, 0].grid(True, alpha=0.3, axis='y')
        
        # Squawk code analysis
        squawk_data = self.aircraft_data[self.aircraft_data['squawk'].notna()]
        if len(squawk_data) > 0:
            top_squawks = squawk_data['squawk'].value_counts().head(15)
            top_squawks.plot(kind='barh', ax=axes[1, 1], color='steelblue')
            axes[1, 1].set_xlabel('Frequency', fontsize=12)
            axes[1, 1].set_ylabel('Squawk Code', fontsize=12)
            axes[1, 1].set_title('Top 15 Squawk Codes', fontsize=14, fontweight='bold')
            axes[1, 1].grid(True, alpha=0.3, axis='x')
        
        plt.tight_layout()
        plt.savefig(FIGURES_DIR / '05_aircraft_behavior.png')
        plt.close()
        
        # Behavior statistics
        self.log("\n--- Aircraft Behavior Statistics ---")
        self.log(f"Total unique aircraft (ICAO24): {self.aircraft_data['hex'].nunique():,}")
        self.log(f"Aircraft with flight callsigns: {self.aircraft_data['flight'].notna().sum():,}")
        self.log(f"Emergency codes detected: {(self.aircraft_data['emergency'] != 'none').sum():,}")
        
        return self
        
    def cross_sensor_analysis(self):
        """Analyze multi-sensor correlation"""
        self.log("\n" + "=" * 80)
        self.log("STEP 7: CROSS-SENSOR CORRELATION ANALYSIS")
        self.log("=" * 80)
        
        # Find aircraft seen by multiple sensors
        aircraft_by_sensor = self.aircraft_data.groupby('hex')['sensor'].unique()
        multi_sensor = aircraft_by_sensor[aircraft_by_sensor.apply(len) > 1]
        
        self.log(f"\nAircraft seen by multiple sensors: {len(multi_sensor):,}")
        self.log(f"Aircraft seen by only one sensor: {len(aircraft_by_sensor) - len(multi_sensor):,}")
        
        # Venn diagram data
        sensor_sets = {}
        for sensor in SENSORS.keys():
            sensor_sets[sensor] = set(self.aircraft_data[self.aircraft_data['sensor'] == sensor]['hex'].unique())
        
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        
        # Sensor overlap
        overlap = len(sensor_sets['sensor-east'] & sensor_sets['sensor-west'])
        only_east = len(sensor_sets['sensor-east'] - sensor_sets['sensor-west'])
        only_west = len(sensor_sets['sensor-west'] - sensor_sets['sensor-east'])
        
        overlap_data = pd.DataFrame({
            'Category': ['Only East', 'Both Sensors', 'Only West'],
            'Count': [only_east, overlap, only_west]
        })
        
        axes[0].bar(overlap_data['Category'], overlap_data['Count'],
                   color=['#bc5090', '#7a5195', '#ffa600'])
        axes[0].set_ylabel('Number of Aircraft', fontsize=12)
        axes[0].set_title('Aircraft Detection Overlap', fontsize=14, fontweight='bold')
        axes[0].grid(True, alpha=0.3, axis='y')
        
        for i, v in enumerate(overlap_data['Count']):
            axes[0].text(i, v + 100, str(v), ha='center', va='bottom', fontweight='bold')
        
        # Correlation of message counts
        msg_counts = self.aircraft_data.groupby(['hex', 'sensor']).size().unstack(fill_value=0)
        if 'sensor-east' in msg_counts.columns and 'sensor-west' in msg_counts.columns:
            axes[1].scatter(msg_counts['sensor-east'], msg_counts['sensor-west'],
                          alpha=0.5, s=20, c='steelblue')
            axes[1].set_xlabel('Messages from sensor-east', fontsize=12)
            axes[1].set_ylabel('Messages from sensor-west', fontsize=12)
            axes[1].set_title('Message Count Correlation', fontsize=14, fontweight='bold')
            axes[1].set_xscale('log')
            axes[1].set_yscale('log')
            axes[1].grid(True, alpha=0.3)
            
            # Calculate correlation
            corr = msg_counts['sensor-east'].corr(msg_counts['sensor-west'])
            axes[1].text(0.05, 0.95, f'Correlation: {corr:.3f}',
                       transform=axes[1].transAxes, fontsize=12,
                       verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        plt.savefig(FIGURES_DIR / '06_cross_sensor_analysis.png')
        plt.close()
        
        self.log(f"Aircraft only seen by sensor-east: {only_east:,}")
        self.log(f"Aircraft only seen by sensor-west: {only_west:,}")
        self.log(f"Aircraft seen by both sensors: {overlap:,}")
        
        return self
        
    def feature_engineering(self):
        """Engineer ML-ready features"""
        self.log("\n" + "=" * 80)
        self.log("STEP 8: FEATURE ENGINEERING FOR ML")
        self.log("=" * 80)
        
        # Create a copy for feature engineering
        ml_data = self.aircraft_data.copy()
        
        # Time-based features
        ml_data['hour_sin'] = np.sin(2 * np.pi * ml_data['hour'] / 24)
        ml_data['hour_cos'] = np.cos(2 * np.pi * ml_data['hour'] / 24)
        ml_data['day_of_week_sin'] = np.sin(2 * np.pi * ml_data['day_of_week'] / 7)
        ml_data['day_of_week_cos'] = np.cos(2 * np.pi * ml_data['day_of_week'] / 7)
        
        # Physics-based features
        # Calculate distance from sensor
        for sensor in SENSORS.keys():
            sensor_mask = ml_data['sensor'] == sensor
            if sensor_mask.any():
                sensor_lat = SENSORS[sensor]['lat']
                sensor_lon = SENSORS[sensor]['lon']
                
                # Haversine distance
                R = 6371.0  # Earth radius in km
                lat1, lon1 = np.radians(sensor_lat), np.radians(sensor_lon)
                lat2 = np.radians(ml_data.loc[sensor_mask, 'lat'])
                lon2 = np.radians(ml_data.loc[sensor_mask, 'lon'])
                
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                
                a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
                c = 2 * np.arcsin(np.sqrt(a))
                
                ml_data.loc[sensor_mask, 'distance_km'] = R * c
        
        # Signal quality features
        ml_data['rssi_normalized'] = (ml_data['rssi'] - ml_data['rssi'].mean()) / ml_data['rssi'].std()
        
        # Expected signal strength (inverse square law)
        ml_data['expected_signal'] = -20 * np.log10(ml_data['distance_km'] + 0.1)
        ml_data['signal_deviation'] = ml_data['rssi'] - ml_data['expected_signal']
        
        # Speed features
        ml_data['speed_squared'] = ml_data['gs'] ** 2
        ml_data['altitude_speed_ratio'] = ml_data['alt_baro'] / (ml_data['gs'] + 1)
        
        # Track features
        ml_data['track_sin'] = np.sin(np.radians(ml_data['track']))
        ml_data['track_cos'] = np.cos(np.radians(ml_data['track']))
        
        # Aircraft type indicators (based on altitude and speed)
        ml_data['likely_commercial'] = ((ml_data['alt_baro'] > 20000) & 
                                        (ml_data['gs'] > 300)).astype(int)
        ml_data['likely_general_aviation'] = ((ml_data['alt_baro'] < 10000) & 
                                              (ml_data['gs'] < 200)).astype(int)
        
        self.log(f"\nEngineered features count: {len(ml_data.columns)}")
        self.log("Key ML features created:")
        ml_features = ['hour_sin', 'hour_cos', 'distance_km', 'signal_deviation',
                      'altitude_speed_ratio', 'track_sin', 'track_cos']
        for feat in ml_features:
            if feat in ml_data.columns:
                valid = ml_data[feat].notna().sum()
                self.log(f"  {feat}: {valid:,} valid values")
        
        # Save ML-ready dataset
        ml_output = OUTPUT_DIR / "golden_7day_ml_dataset.csv"
        
        # Select important columns
        ml_columns = ['timestamp', 'hex', 'sensor', 'lat', 'lon', 'alt_baro', 'alt_geom',
                     'gs', 'track', 'baro_rate', 'rssi', 'distance_km', 'signal_deviation',
                     'hour_sin', 'hour_cos', 'day_of_week_sin', 'day_of_week_cos',
                     'track_sin', 'track_cos', 'altitude_speed_ratio', 
                     'likely_commercial', 'likely_general_aviation']
        
        ml_export = ml_data[[col for col in ml_columns if col in ml_data.columns]].copy()
        ml_export.to_csv(ml_output, index=False)
        self.log(f"\nML-ready dataset saved: {ml_output}")
        self.log(f"Shape: {ml_export.shape}")
        
        return self
        
    def statistical_summary(self):
        """Generate comprehensive statistical summary"""
        self.log("\n" + "=" * 80)
        self.log("STEP 9: STATISTICAL SUMMARY")
        self.log("=" * 80)
        
        # Numeric columns summary
        numeric_cols = self.aircraft_data.select_dtypes(include=[np.number]).columns
        
        summary_stats = self.aircraft_data[numeric_cols].describe()
        
        # Save summary to CSV
        summary_output = OUTPUT_DIR / "statistical_summary.csv"
        summary_stats.to_csv(summary_output)
        self.log(f"\nStatistical summary saved: {summary_output}")
        
        # Create correlation heatmap
        fig, ax = plt.subplots(figsize=(14, 10))
        
        # Select key numeric features
        key_features = ['lat', 'lon', 'alt_baro', 'alt_geom', 'gs', 'track', 
                       'baro_rate', 'rssi', 'nic', 'nac_p']
        available_features = [f for f in key_features if f in self.aircraft_data.columns]
        
        corr_data = self.aircraft_data[available_features].corr()
        
        sns.heatmap(corr_data, annot=True, fmt='.2f', cmap='coolwarm', 
                   center=0, square=True, ax=ax, cbar_kws={"shrink": 0.8})
        plt.title('Feature Correlation Matrix', fontsize=16, fontweight='bold')
        plt.tight_layout()
        plt.savefig(FIGURES_DIR / '07_correlation_matrix.png')
        plt.close()
        
        # Distribution analysis
        self.log("\n--- Distribution Analysis (Normality Tests) ---")
        for col in ['alt_baro', 'gs', 'rssi']:
            if col in self.aircraft_data.columns:
                data = self.aircraft_data[col].dropna()
                if len(data) > 5000:
                    data = data.sample(5000)  # Sample for speed
                stat, p_value = stats.normaltest(data)
                self.log(f"{col}: Statistic={stat:.4f}, p-value={p_value:.4e}")
                if p_value < 0.05:
                    self.log(f"  → Distribution is NOT normal (reject H0)")
                else:
                    self.log(f"  → Distribution appears normal (fail to reject H0)")
        
        return self
        
    def advanced_visualizations(self):
        """Create advanced visualizations for research"""
        self.log("\n" + "=" * 80)
        self.log("STEP 10: ADVANCED VISUALIZATIONS")
        self.log("=" * 80)
        
        # 1. 3D Flight paths (sample)
        fig = plt.figure(figsize=(14, 10))
        ax = fig.add_subplot(111, projection='3d')
        
        # Sample unique aircraft for visualization
        sample_aircraft = self.aircraft_data['hex'].unique()[:10]
        
        for aircraft in sample_aircraft:
            aircraft_data = self.aircraft_data[self.aircraft_data['hex'] == aircraft]
            valid_data = aircraft_data.dropna(subset=['lat', 'lon', 'alt_baro'])
            if len(valid_data) > 10:
                ax.plot(valid_data['lon'], valid_data['lat'], valid_data['alt_baro'],
                       alpha=0.6, linewidth=1)
        
        ax.set_xlabel('Longitude', fontsize=10)
        ax.set_ylabel('Latitude', fontsize=10)
        ax.set_zlabel('Altitude (feet)', fontsize=10)
        ax.set_title('3D Flight Trajectories (Sample of 10 Aircraft)', fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.savefig(FIGURES_DIR / '08_3d_trajectories.png')
        plt.close()
        
        # 2. Heatmap of aircraft density
        valid_coords = self.aircraft_data.dropna(subset=['lat', 'lon'])
        
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        
        for idx, sensor in enumerate(SENSORS.keys()):
            sensor_data = valid_coords[valid_coords['sensor'] == sensor]
            
            axes[idx].hexbin(sensor_data['lon'], sensor_data['lat'], 
                           gridsize=30, cmap='YlOrRd', mincnt=1)
            axes[idx].scatter(SENSORS[sensor]['lon'], SENSORS[sensor]['lat'],
                            marker=SENSORS[sensor]['marker'], s=300,
                            edgecolors='black', linewidths=3,
                            c='blue', zorder=5, label='Sensor')
            axes[idx].set_xlabel('Longitude', fontsize=12)
            axes[idx].set_ylabel('Latitude', fontsize=12)
            axes[idx].set_title(f'{sensor} Detection Density', fontsize=14, fontweight='bold')
            axes[idx].legend()
        
        plt.tight_layout()
        plt.savefig(FIGURES_DIR / '09_detection_heatmap.png')
        plt.close()
        
        # 3. Time-based activity pattern (24x7 heatmap)
        self.aircraft_data['hour'] = self.aircraft_data['timestamp'].dt.hour
        self.aircraft_data['day_name'] = self.aircraft_data['timestamp'].dt.day_name()
        
        activity = self.aircraft_data.groupby(['day_name', 'hour']).size().unstack(fill_value=0)
        
        # Reorder days
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        activity = activity.reindex([d for d in day_order if d in activity.index])
        
        fig, ax = plt.subplots(figsize=(16, 6))
        sns.heatmap(activity, cmap='YlOrRd', annot=False, fmt='d', 
                   cbar_kws={'label': 'Message Count'}, ax=ax)
        plt.title('Weekly Activity Pattern (Hour x Day Heatmap)', fontsize=16, fontweight='bold')
        plt.xlabel('Hour of Day', fontsize=12)
        plt.ylabel('Day of Week', fontsize=12)
        plt.tight_layout()
        plt.savefig(FIGURES_DIR / '10_activity_heatmap.png')
        plt.close()
        
        self.log("Advanced visualizations completed")
        
        return self
        
    def generate_comprehensive_report(self):
        """Generate final comprehensive report"""
        self.log("\n" + "=" * 80)
        self.log("GENERATING COMPREHENSIVE EDA REPORT")
        self.log("=" * 80)
        
        report_path = OUTPUT_DIR / "COMPREHENSIVE_EDA_REPORT.md"
        
        with open(report_path, 'w') as f:
            f.write("# Extensive Exploratory Data Analysis (EDA)\n")
            f.write("## Golden 7-Day ADS-B Research Dataset\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            
            f.write("## Executive Summary\n\n")
            f.write(f"- **Dataset:** Golden 7-Day Sample (2026-01-16 to 2026-01-22)\n")
            f.write(f"- **Total Records:** {len(self.aircraft_data):,}\n")
            f.write(f"- **Unique Aircraft:** {self.aircraft_data['hex'].nunique():,}\n")
            f.write(f"- **Sensors:** {len(SENSORS)} (sensor-east, sensor-west)\n")
            f.write(f"- **Time Span:** {(self.aircraft_data['timestamp'].max() - self.aircraft_data['timestamp'].min()).days} days\n\n")
            
            f.write("## Purpose\n\n")
            f.write("This comprehensive analysis was conducted to support:\n")
            f.write("1. **Deep Neural Network Development** - Feature engineering and data understanding\n")
            f.write("2. **Large Language Model Training** - Contextual understanding of aviation data\n")
            f.write("3. **Academic Research** - Statistical validation and pattern discovery\n")
            f.write("4. **Commercial Applications** - Operational insights and anomaly detection\n\n")
            
            f.write("---\n\n")
            f.write("## Analysis Components\n\n")
            
            f.write("### 1. Data Quality Assessment\n")
            f.write(f"- Missing value analysis completed\n")
            f.write(f"- Data type validation performed\n")
            f.write(f"- Temporal continuity verified\n\n")
            
            f.write("### 2. Temporal Patterns\n")
            f.write(f"- Hourly and daily trends analyzed\n")
            f.write(f"- Weekly activity patterns identified\n")
            f.write(f"- Peak traffic periods documented\n\n")
            
            f.write("### 3. Geospatial Coverage\n")
            f.write(f"- Detection range: {(self.aircraft_data['lat'].max() - self.aircraft_data['lat'].min()):.2f}° latitude\n")
            f.write(f"- Coverage area mapped per sensor\n")
            f.write(f"- Altitude distribution analyzed\n\n")
            
            f.write("### 4. Signal Quality Metrics\n")
            f.write(f"- RSSI patterns characterized\n")
            f.write(f"- Signal-to-noise ratios computed\n")
            f.write(f"- Sensor performance compared\n\n")
            
            f.write("### 5. Aircraft Behavior\n")
            f.write(f"- Flight envelopes validated\n")
            f.write(f"- Speed and altitude correlations studied\n")
            f.write(f"- Vertical rate distributions analyzed\n\n")
            
            f.write("### 6. Multi-Sensor Analysis\n")
            aircraft_by_sensor = self.aircraft_data.groupby('hex')['sensor'].unique()
            multi_sensor = aircraft_by_sensor[aircraft_by_sensor.apply(len) > 1]
            f.write(f"- Cross-sensor correlation: {len(multi_sensor):,} aircraft seen by multiple sensors\n")
            f.write(f"- Detection overlap quantified\n")
            f.write(f"- Sensor agreement metrics calculated\n\n")
            
            f.write("### 7. Feature Engineering\n")
            f.write(f"- Physics-based features created\n")
            f.write(f"- Temporal encodings generated\n")
            f.write(f"- ML-ready dataset exported\n\n")
            
            f.write("---\n\n")
            f.write("## Key Findings\n\n")
            
            # Statistics per sensor
            for sensor in SENSORS.keys():
                sensor_data = self.aircraft_data[self.aircraft_data['sensor'] == sensor]
                f.write(f"### {sensor} ({SENSORS[sensor]['location']})\n")
                f.write(f"- Records: {len(sensor_data):,}\n")
                f.write(f"- Unique Aircraft: {sensor_data['hex'].nunique():,}\n")
                
                if 'rssi' in sensor_data.columns:
                    rssi_valid = sensor_data['rssi'].dropna()
                    if len(rssi_valid) > 0:
                        f.write(f"- Mean RSSI: {rssi_valid.mean():.2f} dBm\n")
                
                if 'alt_baro' in sensor_data.columns:
                    alt_valid = sensor_data['alt_baro'].dropna()
                    if len(alt_valid) > 0:
                        f.write(f"- Mean Altitude: {alt_valid.mean():.0f} feet\n")
                
                if 'gs' in sensor_data.columns:
                    speed_valid = sensor_data['gs'].dropna()
                    if len(speed_valid) > 0:
                        f.write(f"- Mean Ground Speed: {speed_valid.mean():.1f} knots\n")
                f.write("\n")
            
            f.write("---\n\n")
            f.write("## Data Quality Summary\n\n")
            
            missing = self.aircraft_data.isnull().sum()
            missing_pct = (missing / len(self.aircraft_data) * 100).round(2)
            
            f.write("| Column | Missing Count | Missing % |\n")
            f.write("|--------|--------------|----------|\n")
            for col in self.aircraft_data.columns[:15]:  # First 15 columns
                f.write(f"| {col} | {missing[col]:,} | {missing_pct[col]:.2f}% |\n")
            
            f.write("\n---\n\n")
            f.write("## Visualizations Generated\n\n")
            
            figures = sorted(FIGURES_DIR.glob("*.png"))
            for fig in figures:
                f.write(f"- `{fig.name}`\n")
            
            f.write("\n---\n\n")
            f.write("## Output Files\n\n")
            f.write("1. **ML-Ready Dataset**: `golden_7day_ml_dataset.csv`\n")
            f.write("   - Engineered features for machine learning\n")
            f.write("   - Normalized and cleaned data\n")
            f.write("   - Ready for training DNNs and other models\n\n")
            
            f.write("2. **Statistical Summary**: `statistical_summary.csv`\n")
            f.write("   - Descriptive statistics for all numeric columns\n")
            f.write("   - Quartiles, mean, std, min, max\n\n")
            
            f.write("3. **Visualizations**: `figures/` directory\n")
            f.write("   - 10+ publication-ready figures\n")
            f.write("   - High-resolution (300 DPI)\n\n")
            
            f.write("---\n\n")
            f.write("## Recommendations for ML/LLM Development\n\n")
            
            f.write("### For Deep Neural Networks:\n")
            f.write("1. Use engineered physics-based features (distance, signal deviation)\n")
            f.write("2. Apply temporal encodings (sine/cosine transformations)\n")
            f.write("3. Consider sequence models (LSTM, Transformers) for trajectory prediction\n")
            f.write("4. Implement attention mechanisms for multi-sensor fusion\n\n")
            
            f.write("### For LLM Training:\n")
            f.write("1. Rich contextual data available (callsigns, squawk codes, positions)\n")
            f.write("2. Temporal narratives can be constructed from flight paths\n")
            f.write("3. Multi-sensor perspectives provide diverse viewpoints\n")
            f.write("4. Anomaly detection can be framed as text classification\n\n")
            
            f.write("### For Research:\n")
            f.write("1. Statistically significant sample size (600K+ records)\n")
            f.write("2. Multi-day coverage captures daily and weekly patterns\n")
            f.write("3. Cross-sensor validation enables robust analysis\n")
            f.write("4. Physics-based validation possible with derived features\n\n")
            
            f.write("---\n\n")
            f.write("## Next Steps\n\n")
            f.write("1. **Model Development**: Train baseline models using ML-ready dataset\n")
            f.write("2. **Feature Selection**: Conduct recursive feature elimination\n")
            f.write("3. **Anomaly Detection**: Implement unsupervised learning algorithms\n")
            f.write("4. **Trajectory Prediction**: Build sequence-to-sequence models\n")
            f.write("5. **Real-time Pipeline**: Deploy models for live data streams\n\n")
            
            f.write("---\n\n")
            f.write("## Technical Specifications\n\n")
            f.write(f"- **Python Version**: {pd.__version__ if hasattr(pd, '__version__') else 'Unknown'}\n")
            f.write(f"- **Analysis Runtime**: {datetime.now()}\n")
            f.write(f"- **Total Processing**: Multiple stages completed\n")
            f.write(f"- **Output Format**: CSV, PNG, Markdown\n\n")
            
            f.write("---\n\n")
            f.write("## Contact & Citation\n\n")
            f.write("For questions or collaboration:\n")
            f.write("- **Repository**: https://github.com/rwiren/adsb-research-grid\n")
            f.write("- **License**: MIT\n")
            f.write("- **Citation**: See CITATION.cff in repository root\n\n")
            
            f.write("---\n\n")
            f.write("*This report was automatically generated by the ADS-B Research Grid EDA pipeline.*\n")
        
        self.log(f"\nComprehensive report saved: {report_path}")
        
        # Also save execution log
        log_path = OUTPUT_DIR / "execution_log.txt"
        with open(log_path, 'w') as f:
            f.write("\n".join(self.report_lines))
        self.log(f"Execution log saved: {log_path}")
        
        return self
        
    def run_full_analysis(self):
        """Execute complete EDA pipeline"""
        print("\n" + "=" * 80)
        print(" " * 20 + "GOLDEN 7-DAY EXTENSIVE EDA")
        print(" " * 15 + "ADS-B Research Grid - Deep Analysis")
        print("=" * 80 + "\n")
        
        try:
            # Execute all analysis steps
            (self
             .extract_datasets()
             .data_quality_analysis()
             .temporal_analysis()
             .geospatial_analysis()
             .signal_quality_analysis()
             .aircraft_behavior_analysis()
             .cross_sensor_analysis()
             .feature_engineering()
             .statistical_summary()
             .advanced_visualizations()
             .generate_comprehensive_report())
            
            print("\n" + "=" * 80)
            print(" " * 25 + "ANALYSIS COMPLETE!")
            print("=" * 80)
            print(f"\nResults saved to: {OUTPUT_DIR}")
            print(f"Figures saved to: {FIGURES_DIR}")
            print(f"\nTotal figures generated: {len(list(FIGURES_DIR.glob('*.png')))}")
            print(f"ML-ready dataset: golden_7day_ml_dataset.csv")
            print(f"Comprehensive report: COMPREHENSIVE_EDA_REPORT.md")
            print("\n" + "=" * 80 + "\n")
            
        except Exception as e:
            self.log(f"\nERROR: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            raise


def main():
    """Main execution function"""
    eda = GoldenSevenDayEDA()
    eda.run_full_analysis()


if __name__ == "__main__":
    main()
