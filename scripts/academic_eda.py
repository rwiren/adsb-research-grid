import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import subprocess
import os
import shutil
from datetime import datetime
from glob import glob
from math import radians, cos, sin, asin, sqrt

# ==============================================================================
# CLASS: ADSB_Academic_EDA (v6.1 - Fault Tolerant Edition)
# PURPOSE: Full sensor fusion with safety checks for missing columns (Squawk/GNSS).
# ==============================================================================

SENSORS = {
    "sensor-north": {"lat": 60.319555, "lon": 24.830816, "color": "#1f77b4"},
    "sensor-east":  {"lat": 60.306702, "lon": 24.590622, "color": "#d62728"},
    "sensor-west":  {"lat": 59.149320, "lon": 22.497916, "color": "#2ca02c"}
}

class ADSB_Academic_EDA:
    def __init__(self, raw_dir="research_data"):
        self.raw_dir = raw_dir
        self.run_id = datetime.now().strftime("%Y-%m-%d_%H%M")
        self.showcase_dir = f"docs/showcase/run_{self.run_id}"
        self.fig_dir = f"{self.showcase_dir}/figures"
        
        os.makedirs(self.fig_dir, exist_ok=True)
        self.df_ac = pd.DataFrame()   # Aircraft Data
        self.df_gnss = pd.DataFrame() # GNSS Health Data
        self.metadata = self._get_git_metadata()
        self.report_path = f"{self.showcase_dir}/REPORT.md"
        
        # Academic Plotting Aesthetics
        sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)

    def _get_git_metadata(self):
        try:
            hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).strip().decode()
            return f"Git: {hash} | {datetime.now().strftime('%Y-%m-%d')}"
        except: return "Git: Unknown"

    def haversine(self, lat1, lon1, lat2, lon2):
        R = 6372.8
        dLat = np.radians(lat2 - lat1)
        dLon = np.radians(lon2 - lon1)
        lat1 = np.radians(lat1)
        lat2 = np.radians(lat2)
        a = np.sin(dLat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dLon/2)**2
        c = 2*np.arcsin(np.sqrt(a))
        return R * c

    def load_data(self, target_date):
        print(f"[{self.metadata}] 📥 Loading Complete Dataset for {target_date}...")
        
        # 1. LOAD AIRCRAFT LOGS
        ac_files = glob(f"{self.raw_dir}/{target_date}/sensor-*/sensor-*_aircraft_log*.csv")
        ac_list = []
        for f in ac_files:
            try:
                sid = f.split('/')[-2]
                # Try loading with squawk as string; if fails, standard load
                try:
                    tmp = pd.read_csv(f, on_bad_lines='skip', dtype={'squawk': str, 'hex': str})
                except ValueError:
                    tmp = pd.read_csv(f, on_bad_lines='skip', dtype={'hex': str})

                tmp['timestamp'] = pd.to_datetime(tmp['timestamp'], format='mixed', utc=True)
                tmp['sensor_id'] = sid
                
                # Normalization
                if 'alt_baro' in tmp.columns: tmp.rename(columns={'alt_baro': 'alt'}, inplace=True)
                if 'gs' in tmp.columns: tmp.rename(columns={'gs': 'ground_speed'}, inplace=True)
                
                # Physics
                if sid in SENSORS:
                    tmp['distance_km'] = self.haversine(SENSORS[sid]['lat'], SENSORS[sid]['lon'], tmp['lat'], tmp['lon'])
                else: tmp['distance_km'] = np.nan
                
                ac_list.append(tmp)
            except Exception as e: print(f"⚠️ AC Load Error {f}: {e}")
            
        self.df_ac = pd.concat(ac_list, ignore_index=True)
        # Type enforcement
        for col in ['rssi', 'alt', 'ground_speed', 'track']:
            if col in self.df_ac.columns:
                self.df_ac[col] = pd.to_numeric(self.df_ac[col], errors='coerce')
        
        self.df_ac = self.df_ac.sort_values(by=['sensor_id', 'timestamp'])
        print(f"✅ Aircraft Data: {len(self.df_ac):,} rows")

        # 2. LOAD GNSS LOGS
        gnss_files = glob(f"{self.raw_dir}/{target_date}/sensor-*/sensor-*_gnss_log*.csv")
        gnss_list = []
        for f in gnss_files:
            try:
                sid = f.split('/')[-2]
                tmp = pd.read_csv(f, on_bad_lines='skip') 
                tmp['sensor_id'] = sid
                gnss_list.append(tmp)
            except: pass
        
        if gnss_list:
            self.df_gnss = pd.concat(gnss_list, ignore_index=True)
            print(f"✅ GNSS Data: {len(self.df_gnss):,} rows")
        else:
            print("⚠️ No GNSS logs found in local repo (Run 'make fetch' or check playbook)")

    def generate_dashboards(self):
        print("🎨 Generating 5x Scientific Dashboards...")
        palette_map = {k: v['color'] for k,v in SENSORS.items() if k in self.df_ac['sensor_id'].unique()}
        
        # --- D1: OPERATIONAL ---
        fig, axs = plt.subplots(2, 2, figsize=(16, 10))
        fig.suptitle(f"D1: Operational Health\n{self.metadata}", fontsize=16)
        
        sns.countplot(data=self.df_ac, x='sensor_id', hue='sensor_id', ax=axs[0,0], palette=palette_map)
        axs[0,0].set_title("Packet Capture Volume")
        
        sns.kdeplot(data=self.df_ac, x='rssi', hue='sensor_id', fill=True, ax=axs[0,1], common_norm=False, palette=palette_map)
        axs[0,1].set_title("Receiver Sensitivity Profile")
        axs[0,1].axvline(-3, color='r', linestyle='--')
        
        # Message Rate
        self.df_ac['minute'] = self.df_ac['timestamp'].dt.floor('min')
        rate = self.df_ac.groupby(['minute', 'sensor_id']).size().reset_index(name='count')
        sns.lineplot(data=rate, x='minute', y='count', hue='sensor_id', ax=axs[1,0], palette=palette_map)
        axs[1,0].set_title("Message Rate Stability")
        axs[1,0].tick_params(axis='x', rotation=45)
        
        # Squawk Distribution (Safe Mode)
        if 'squawk' in self.df_ac.columns:
            top_squawks = self.df_ac['squawk'].value_counts().head(10).index
            sq_data = self.df_ac[self.df_ac['squawk'].isin(top_squawks)]
            sns.countplot(data=sq_data, y='squawk', hue='sensor_id', ax=axs[1,1], order=top_squawks, palette=palette_map)
            axs[1,1].set_title("Top 10 Transponder Codes (Squawks)")
        else:
            axs[1,1].text(0.5, 0.5, "Squawk Data Not captured by Sensors", ha='center', va='center', fontsize=12)
            axs[1,1].set_title("Transponder Codes (Missing)")
        
        plt.tight_layout()
        plt.savefig(f"{self.fig_dir}/D1_Operational.png", dpi=100)
        plt.close()

        # --- D2: PHYSICS ---
        fig, axs = plt.subplots(2, 2, figsize=(16, 10))
        fig.suptitle("D2: Physics Validation", fontsize=16)
        
        sns.scatterplot(data=self.df_ac[::50], x='distance_km', y='rssi', hue='sensor_id', alpha=0.2, ax=axs[0,0], palette=palette_map)
        axs[0,0].set_title("Signal Decay (RSSI vs Range)")
        axs[0,0].set_ylim(-45, 0)
        
        sns.scatterplot(data=self.df_ac[::50], x='ground_speed', y='alt', hue='sensor_id', alpha=0.2, ax=axs[0,1], palette=palette_map)
        axs[0,1].set_title("Flight Envelope (Alt vs Speed)")
        
        sns.histplot(data=self.df_ac, x='alt', hue='sensor_id', element="step", ax=axs[1,0], palette=palette_map)
        axs[1,0].set_title("Altitude Distribution")
        
        if 'track' in self.df_ac.columns:
            sns.histplot(data=self.df_ac, x='track', hue='sensor_id', element="poly", fill=False, ax=axs[1,1], palette=palette_map)
        axs[1,1].set_title("Heading/Track Distribution")
        
        plt.tight_layout()
        plt.savefig(f"{self.fig_dir}/D2_Physics.png", dpi=100)
        plt.close()

        # --- D3: SPATIAL ---
        fig, axs = plt.subplots(1, 1, figsize=(12, 10))
        sns.scatterplot(data=self.df_ac[::20], x='lon', y='lat', hue='sensor_id', alpha=0.5, s=5, ax=axs, palette=palette_map)
        for s_id, s_data in SENSORS.items():
            axs.plot(s_data['lon'], s_data['lat'], marker='P', color='black', markersize=15)
        axs.set_title("Geospatial Coverage & Sensor Geometry")
        plt.savefig(f"{self.fig_dir}/D3_Spatial.png", dpi=100)
        plt.close()

        # --- D4: FORENSICS ---
        fig, axs = plt.subplots(1, 2, figsize=(16, 6))
        fig.suptitle("D4: Forensic Correlation", fontsize=16)
        
        self.df_ac['time_bucket'] = self.df_ac['timestamp'].dt.round('1s')
        pivot = self.df_ac.pivot_table(index=['hex', 'time_bucket'], columns='sensor_id', values='rssi', aggfunc='mean').dropna()
        
        if 'sensor-north' in pivot.columns and 'sensor-west' in pivot.columns:
            sns.regplot(data=pivot, x='sensor-north', y='sensor-west', ax=axs[0], scatter_kws={'alpha':0.1}, line_kws={'color':'red'})
            axs[0].set_title("RSSI Correlation: North vs West")
            
            pivot['delta'] = pivot['sensor-north'] - pivot['sensor-west']
            sns.histplot(pivot['delta'], kde=True, ax=axs[1], color="purple")
            axs[1].set_title("Differential Signal Histogram (N-W)")
        else:
             axs[0].text(0.5, 0.5, "Insufficient Overlap", ha='center')
        
        plt.tight_layout()
        plt.savefig(f"{self.fig_dir}/D4_Forensics.png", dpi=100)
        plt.close()

        # --- D5: GNSS HEALTH ---
        if not self.df_gnss.empty and 'lat' in self.df_gnss.columns:
            fig, axs = plt.subplots(1, 2, figsize=(16, 6))
            fig.suptitle("D5: GNSS Sensor Stability", fontsize=16)
            
            sns.scatterplot(data=self.df_gnss, x='lon', y='lat', hue='sensor_id', ax=axs[0])
            axs[0].set_title("Sensor Position Drift (Scatter)")
            
            if 'satellites' in self.df_gnss.columns:
                sns.lineplot(data=self.df_gnss, x=self.df_gnss.index, y='satellites', hue='sensor_id', ax=axs[1])
                axs[1].set_title("Satellite Lock Count")
                
            plt.savefig(f"{self.fig_dir}/D5_GNSS_Health.png", dpi=100)
            plt.close()

    def generate_report(self):
        print("📝 Compiling Comprehensive Data Dictionary...")
        
        # Calculate Stats
        cols_to_stat = ['rssi', 'alt', 'distance_km']
        existing_cols = [c for c in cols_to_stat if c in self.df_ac.columns]
        
        stats = self.df_ac.groupby('sensor_id')[existing_cols].agg(['mean', 'min', 'max', 'count']).round(2)
        
        with open(self.report_path, "w") as f:
            f.write(f"# 🛰️ ADS-B Grid Research Audit\n")
            f.write(f"**Run ID:** {self.run_id} | **Git:** {self.metadata}\n\n")
            
            f.write("## 1. 📊 The Data Dictionary\n")
            f.write(stats.to_markdown())
            f.write("\n\n")
            
            if 'squawk' in self.df_ac.columns:
                emergency_sq = self.df_ac[self.df_ac['squawk'].isin(['7500', '7600', '7700'])]
                f.write("### 1.1 Transponder Codes (Squawks)\n")
                f.write(f"- **Unique Squawk Codes:** {self.df_ac['squawk'].nunique()}\n")
                f.write(f"- **Emergency Codes Detected:** {len(emergency_sq)}\n")
            else:
                f.write("### 1.1 Transponder Codes\n> *Squawk codes were not present in the ingested dataset.*\n\n")
            
            f.write("## 2. 🖼️ Visual Evidence\n")
            f.write("### D1: Operational Health\n![D1](figures/D1_Operational.png)\n\n")
            f.write("### D2: Physics & Kinematics\n![D2](figures/D2_Physics.png)\n\n")
            f.write("### D3: Spatial Coverage\n![D3](figures/D3_Spatial.png)\n\n")
            f.write("### D4: Forensic Correlation\n![D4](figures/D4_Forensics.png)\n\n")
            
            if not self.df_gnss.empty:
                f.write("### D5: GNSS Stability\n![D5](figures/D5_GNSS_Health.png)\n\n")

if __name__ == "__main__":
    eda = ADSB_Academic_EDA()
    eda.load_data(target_date="2026-01-12")
    eda.generate_dashboards()
    eda.generate_report()
    print(f"\n🎉 V6 SHOWCASE READY: {eda.showcase_dir}")
