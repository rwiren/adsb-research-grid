import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import subprocess
import os
from datetime import datetime
from glob import glob
from math import radians, cos, sin, asin, sqrt

# ==============================================================================
# CLASS: ADSB_Academic_EDA (v8 - Final Professional)
# PURPOSE: Publication-ready plots with enforced geospatial zooming.
# ==============================================================================

SENSORS = {
    "sensor-north": {"lat": 60.319555, "lon": 24.830816, "color": "#003f5c", "name": "North (Ref)", "marker": "^"}, 
    "sensor-east":  {"lat": 60.250000, "lon": 25.350000, "color": "#bc5090", "name": "East (Sipoo)", "marker": "s"}, 
    "sensor-west":  {"lat": 60.120000, "lon": 24.400000, "color": "#ffa600", "name": "West (Kirkko)", "marker": "o"} 
}

class ADSB_Academic_EDA:
    def __init__(self, raw_dir="research_data"):
        self.raw_dir = raw_dir
        self.run_id = datetime.now().strftime("%Y-%m-%d_%H%M")
        self.showcase_dir = f"docs/showcase/run_{self.run_id}"
        self.fig_dir = f"{self.showcase_dir}/figures"
        os.makedirs(self.fig_dir, exist_ok=True)
        self.df_ac = pd.DataFrame()
        self.metadata = self._get_git_metadata()
        self.report_path = f"{self.showcase_dir}/REPORT.md"
        
        # STRICT PROFESSIONAL STYLE
        plt.style.use('seaborn-v0_8-paper')
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['figure.dpi'] = 150
        plt.rcParams['savefig.dpi'] = 300
        plt.rcParams['axes.grid'] = True
        plt.rcParams['grid.alpha'] = 0.3

    def _get_git_metadata(self):
        try:
            return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).strip().decode()
        except: return "LOCAL"

    def haversine(self, lat1, lon1, lat2, lon2):
        R = 6372.8
        dLat, dLon = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
        lat1, lat2 = np.radians(lat1), np.radians(lat2)
        a = np.sin(dLat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dLon/2)**2
        return R * 2 * np.arcsin(np.sqrt(a))

    def load_data(self, target_date):
        print(f"[{self.metadata}] 📥 Loading Data...")
        ac_files = glob(f"{self.raw_dir}/{target_date}/sensor-*/sensor-*_aircraft_log*.csv")
        ac_list = []
        for f in ac_files:
            try:
                sid = f.split('/')[-2]
                tmp = pd.read_csv(f, on_bad_lines='skip', dtype={'hex': str})
                tmp['timestamp'] = pd.to_datetime(tmp['timestamp'], format='mixed', utc=True)
                tmp['sensor_id'] = sid
                if 'alt_baro' in tmp.columns: tmp.rename(columns={'alt_baro': 'alt'}, inplace=True)
                if 'gs' in tmp.columns: tmp.rename(columns={'gs': 'ground_speed'}, inplace=True)
                if sid in SENSORS:
                    tmp['distance_km'] = self.haversine(SENSORS[sid]['lat'], SENSORS[sid]['lon'], tmp['lat'], tmp['lon'])
                ac_list.append(tmp)
            except: pass
            
        self.df_ac = pd.concat(ac_list, ignore_index=True)
        for c in ['rssi', 'alt', 'ground_speed', 'track']: 
            self.df_ac[c] = pd.to_numeric(self.df_ac[c], errors='coerce')
        
        # TIME FILTER (Post-2025)
        self.df_ac = self.df_ac[self.df_ac['timestamp'] > '2025-01-01']
        print(f"✅ Valid Rows: {len(self.df_ac):,}")

    def generate_dashboards(self):
        print("🎨 Generating Professional Plots...")
        pal = {k: v['color'] for k,v in SENSORS.items()}
        
        # D1: OPERATIONAL
        fig, axs = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle(f"D1: Network Operations Status ({self.metadata})", fontweight='bold')
        
        sns.countplot(data=self.df_ac, x='sensor_id', ax=axs[0,0], palette=pal)
        axs[0,0].set_title("Packet Volume")
        
        sns.kdeplot(data=self.df_ac, x='rssi', hue='sensor_id', fill=True, ax=axs[0,1], palette=pal)
        axs[0,1].set_title("Signal Sensitivity (RSSI)")
        
        self.df_ac['min'] = self.df_ac['timestamp'].dt.floor('min')
        rate = self.df_ac.groupby(['min', 'sensor_id']).size().reset_index(name='count')
        sns.lineplot(data=rate, x='min', y='count', hue='sensor_id', ax=axs[1,0], palette=pal, linewidth=1)
        axs[1,0].set_title("Message Rate (Hz)")
        
        axs[1,1].text(0.5, 0.5, "Squawk Analysis Omitted", ha='center') # Placeholder
        
        plt.tight_layout()
        plt.savefig(f"{self.fig_dir}/D1_Operational.png")
        plt.close()

        # D2: PHYSICS
        fig, axs = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle("D2: Physics Validation", fontweight='bold')
        sample = self.df_ac.sample(n=min(50000, len(self.df_ac)))
        
        sns.scatterplot(data=sample, x='distance_km', y='rssi', hue='sensor_id', s=10, alpha=0.3, ax=axs[0,0], palette=pal)
        axs[0,0].set_title("Path Loss (Friis)")
        axs[0,0].set_ylim(-45, 0)
        
        sns.scatterplot(data=sample, x='ground_speed', y='alt', hue='sensor_id', s=10, alpha=0.3, ax=axs[0,1], palette=pal)
        axs[0,1].set_title("Kinematic Envelope")
        
        sns.histplot(data=self.df_ac, x='alt', hue='sensor_id', element="step", ax=axs[1,0], palette=pal)
        axs[1,0].set_title("Altitude Distribution")
        
        sns.kdeplot(data=self.df_ac, x='track', hue='sensor_id', ax=axs[1,1], palette=pal)
        axs[1,1].set_title("Heading Profile")
        
        plt.tight_layout()
        plt.savefig(f"{self.fig_dir}/D2_Physics.png")
        plt.close()

        # D3: SPATIAL (ZOOMED)
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.set_title("D3: Sensor Grid Geometry (Zoomed)", fontweight='bold')
        
        # Plot Tracks
        sns.scatterplot(data=sample, x='lon', y='lat', hue='sensor_id', s=2, alpha=0.2, palette=pal, ax=ax, legend=False)
        
        # Plot Stations
        for sid, meta in SENSORS.items():
            ax.plot(meta['lon'], meta['lat'], marker=meta['marker'], markersize=15, 
                    color='black', markeredgecolor='white', markeredgewidth=2, label=meta['name'])
            # Offset labels to avoid clutter
            offset_y = 0.02 if sid == 'sensor-north' else -0.03
            ax.text(meta['lon'], meta['lat'] + offset_y, meta['name'].upper(), 
                    fontsize=10, fontweight='bold', ha='center',
                    bbox=dict(facecolor='white', alpha=0.9, edgecolor='black', boxstyle='round,pad=0.2'))

        # FORCE ZOOM on the Triangle
        ax.set_xlim(24.3, 25.5)  # Longitude Range (Kirkko to Sipoo)
        ax.set_ylim(60.1, 60.45) # Latitude Range (Sea to Vantaa)
        ax.grid(True, linestyle='--', alpha=0.5)
        
        plt.savefig(f"{self.fig_dir}/D3_Spatial.png")
        plt.close()

        # D4: FORENSICS
        fig, axs = plt.subplots(1, 2, figsize=(12, 5))
        fig.suptitle("D4: Multi-Sensor Correlation", fontweight='bold')
        
        self.df_ac['bucket'] = self.df_ac['timestamp'].dt.round('30s')
        piv = self.df_ac.pivot_table(index=['hex', 'bucket'], columns='sensor_id', values='rssi', aggfunc='mean')
        
        valid_cols = [c for c in piv.columns if c in SENSORS]
        if len(valid_cols) >= 2:
            s1, s2 = valid_cols[0], valid_cols[1]
            dat = piv[[s1, s2]].dropna()
            
            sns.regplot(data=dat, x=s1, y=s2, ax=axs[0], scatter_kws={'s': 5, 'alpha': 0.3}, line_kws={'color': 'red'})
            axs[0].set_title(f"Correlation: {s1} vs {s2}")
            
            diff = dat[s1] - dat[s2]
            sns.histplot(diff, kde=True, ax=axs[1], color='purple')
            axs[1].set_title("Signal Delta Distribution")
        else:
            axs[0].text(0.5, 0.5, "Insufficient Overlap", ha='center')
            
        plt.tight_layout()
        plt.savefig(f"{self.fig_dir}/D4_Forensics.png")
        plt.close()

    def generate_report(self):
        with open(self.report_path, "w") as f:
            f.write(f"# ADS-B Grid Audit: {self.run_id}\n\n")
            f.write("## Visual Evidence\n")
            f.write("![D1](figures/D1_Operational.png)\n")
            f.write("![D2](figures/D2_Physics.png)\n")
            f.write("![D3](figures/D3_Spatial.png)\n")
            f.write("![D4](figures/D4_Forensics.png)\n")

if __name__ == "__main__":
    eda = ADSB_Academic_EDA()
    eda.load_data(target_date="2026-01-12")
    eda.generate_dashboards()
    eda.generate_report()
    print(f"Showcase: {eda.showcase_dir}")
