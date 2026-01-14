#!/usr/bin/env python3
# ------------------------------------------------------------------
# [FILE] scripts/academic_eda.py
# [VERSION] 5.2.0 (Data Window & Missing Sensor Warnings)
# ------------------------------------------------------------------

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from sklearn.ensemble import IsolationForest

BASE_DIR = Path("research_data")
ML_DATASET = Path("research_data/ml_ready/training_dataset_v3.csv")

SENSORS = {
    "sensor-north": {"lat": 60.319555, "lon": 24.830816, "color": "#003f5c", "name": "North (Ref)", "marker": "^"}, 
    "sensor-east":  {"lat": 60.3621, "lon": 25.3375, "color": "#bc5090", "name": "East (Sipoo)", "marker": "s"}, 
    "sensor-west":  {"lat": 60.1478, "lon": 24.5264, "color": "#ffa600", "name": "West (Jorvas)", "marker": "o"} 
}

class ADSB_Science_EDA:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.run_id = output_dir.name
        self.fig_dir = self.output_dir / "figures"
        self.fig_dir.mkdir(parents=True, exist_ok=True)
        self.report_path = self.output_dir / "REPORT.md"
        self.df_ac = pd.DataFrame()
        self.df_ml = pd.DataFrame()
        self.metadata = self._get_git_metadata()
        plt.style.use('seaborn-v0_8-paper')
        plt.rcParams.update({'figure.dpi': 150, 'savefig.dpi': 300, 'font.family': 'sans-serif'})

    def _get_git_metadata(self):
        try: return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).strip().decode()
        except: return "LOCAL"

    def haversine(self, lat1, lon1, lat2, lon2):
        R = 6372.8 
        dLat, dLon = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
        lat1, lat2 = np.radians(lat1), np.radians(lat2)
        a = np.sin(dLat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dLon/2)**2
        return R * 2 * np.arcsin(np.sqrt(a))
    
    def add_timestamp(self, ax=None):
        t_str = datetime.now().strftime("Generated: %Y-%m-%d %H:%M")
        if ax: ax.text(0.99, 0.01, t_str, transform=ax.transAxes, ha='right', va='bottom', fontsize=8, color='gray', alpha=0.7)
        else: plt.figtext(0.99, 0.01, t_str, ha='right', va='bottom', fontsize=8, color='gray', alpha=0.7)

    def load_science_data(self, target_date_str):
        print(f"[SCIENCE] 🔍 Loading data for: {target_date_str}")
        ac_files = list(BASE_DIR.rglob(f"*aircraft_log_{target_date_str}*.csv*"))
        if not ac_files: ac_files = list(BASE_DIR.rglob("*aircraft_log_*.csv*"))
        
        ac_list = []
        dtype_schema = {'hex': str, 'flight': str, 'squawk': str, 'sensor_id': str}
        for f in ac_files:
            try:
                sid = "unknown"
                for part in f.parts:
                    if part.startswith("sensor-"): sid = part; break
                comp = 'gzip' if f.suffix == '.gz' else None
                tmp = pd.read_csv(f, compression=comp, on_bad_lines='skip', dtype=dtype_schema, low_memory=False)
                if 'timestamp' in tmp.columns: tmp['timestamp'] = pd.to_datetime(tmp['timestamp'], format='mixed', utc=True)
                tmp['sensor_id'] = sid
                tmp.rename(columns={'alt_baro': 'alt', 'gs': 'ground_speed'}, inplace=True)
                if sid in SENSORS: tmp['distance_km'] = self.haversine(SENSORS[sid]['lat'], SENSORS[sid]['lon'], tmp['lat'], tmp['lon'])
                ac_list.append(tmp)
            except: pass

        if ac_list:
            self.df_ac = pd.concat(ac_list, ignore_index=True)
            for c in ['rssi', 'alt', 'ground_speed']: self.df_ac[c] = pd.to_numeric(self.df_ac[c], errors='coerce')
            self.df_ac = self.df_ac[self.df_ac['timestamp'] > '2025-01-01']
            print(f"   ✅ Loaded {len(self.df_ac):,} valid aircraft rows.")

        if ML_DATASET.exists():
            self.df_ml = pd.read_csv(ML_DATASET, dtype=dtype_schema, low_memory=False)
            if 'anomaly' not in self.df_ml.columns:
                features = ['lat', 'lon', 'alt', 'ground_speed', 'track', 'rssi']
                X = self.df_ml[features].fillna(self.df_ml[features].median())
                iso = IsolationForest(n_estimators=100, contamination=0.01, n_jobs=-1)
                self.df_ml['anomaly'] = iso.fit_predict(X)
                self.df_ml['score'] = iso.decision_function(X)
                min_s = self.df_ml['score'].min()
                mask = self.df_ml['score'] < 0
                self.df_ml.loc[mask, 'confidence_pct'] = (self.df_ml.loc[mask, 'score']/min_s)*100
            self.df_ml['anomaly'] = self.df_ml['anomaly'].fillna(1).astype(int)
            print(f"   ✅ ML Loaded: {len(self.df_ml):,} rows")

    def generate_plots(self):
        print("[SCIENCE] 🎨 Generating Plots...")
        pal = {k: v['color'] for k,v in SENSORS.items()}
        if not self.df_ac.empty:
            # D1: Ops
            fig, axs = plt.subplots(2, 2, figsize=(12, 8))
            sns.countplot(data=self.df_ac, x='sensor_id', hue='sensor_id', ax=axs[0,0], palette=pal, legend=False)
            sns.kdeplot(data=self.df_ac, x='rssi', hue='sensor_id', fill=True, ax=axs[0,1], palette=pal)
            self.df_ac['min'] = self.df_ac['timestamp'].dt.floor('min')
            rate = self.df_ac.groupby(['min', 'sensor_id']).size().reset_index(name='count')
            sns.lineplot(data=rate, x='min', y='count', hue='sensor_id', ax=axs[1,0], palette=pal)
            axs[1,0].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            sns.boxplot(data=self.df_ac, x='sensor_id', y='distance_km', hue='sensor_id', ax=axs[1,1], palette=pal, legend=False)
            self.add_timestamp()
            plt.suptitle("D1: Operational Status"); plt.tight_layout(); plt.savefig(self.fig_dir / "D1_Operational.png"); plt.close()

            # D3: Spatial (SENSOR ZOOM)
            fig, ax = plt.subplots(figsize=(10, 8))
            sns.scatterplot(data=self.df_ac.sample(n=min(10000, len(self.df_ac))), x='lon', y='lat', hue='sensor_id', s=2, alpha=0.2, palette=pal, ax=ax, legend=False)
            
            s_lats, s_lons = [], []
            for sid, meta in SENSORS.items():
                ax.plot(meta['lon'], meta['lat'], marker=meta['marker'], markersize=15, color='black')
                ax.text(meta['lon'], meta['lat'] + 0.02, meta['name'].upper(), fontweight='bold', ha='center', bbox=dict(facecolor='white', alpha=0.8))
                s_lats.append(meta['lat'])
                s_lons.append(meta['lon'])
            
            # Zoom Logic: Sensors + 10%
            if s_lats and s_lons:
                min_lat, max_lat = min(s_lats), max(s_lats)
                min_lon, max_lon = min(s_lons), max(s_lons)
                lat_pad = (max_lat - min_lat) * 0.1
                lon_pad = (max_lon - min_lon) * 0.1
                if lat_pad > 0:
                    ax.set_xlim(min_lon - lon_pad, max_lon + lon_pad)
                    ax.set_ylim(min_lat - lat_pad, max_lat + lat_pad)
            
            self.add_timestamp(ax)
            plt.title("D3: Spatial Coverage (Sensor Zoom)"); plt.savefig(self.fig_dir / "D3_Spatial.png"); plt.close()

            # D2: Physics
            plt.figure(figsize=(10,6)); sns.scatterplot(data=self.df_ac.sample(n=min(50000, len(self.df_ac))), x='ground_speed', y='alt', hue='sensor_id', palette=pal, s=10, alpha=0.3); 
            self.add_timestamp(); plt.title("D2: Physics"); plt.savefig(self.fig_dir / "D2_Physics.png"); plt.close()
            
            # D4: Forensics
            plt.figure(figsize=(10,6)); sns.histplot(data=self.df_ac, x='rssi', hue='sensor_id', palette=pal); 
            self.add_timestamp(); plt.title("D4: Forensics"); plt.savefig(self.fig_dir / "D4_Forensics.png"); plt.close()

        # D6: ML
        if not self.df_ml.empty:
            fig, axs = plt.subplots(1, 3, figsize=(15, 5))
            for i, f in enumerate(['rssi', 'alt', 'ground_speed']):
                sns.boxplot(data=self.df_ml, x='anomaly', y=f, hue='anomaly', ax=axs[i], palette={1:'gray', -1:'red'}, legend=False)
                axs[i].set_xticks([-1, 1]); axs[i].set_xticklabels(['Anomaly', 'Normal'])
            self.add_timestamp()
            plt.suptitle("D6: AI Forensics"); plt.tight_layout(); plt.savefig(self.fig_dir / "D6_ML_Analysis.png"); plt.close()

    def write_report(self):
        print("[SCIENCE] 📝 Compiling Full Academic Report...")
        count = len(self.df_ac)
        
        # Calculate Data Window
        start_t, end_t = "N/A", "N/A"
        if not self.df_ac.empty:
            start_t = self.df_ac['timestamp'].min().strftime('%Y-%m-%d %H:%M')
            end_t = self.df_ac['timestamp'].max().strftime('%H:%M UTC')

        t1 = pd.DataFrame()
        active_sensors = []
        if not self.df_ac.empty: 
            t1 = self.df_ac.groupby('sensor_id').size().reset_index(name='Packets')
            active_sensors = t1['sensor_id'].unique()

        with open(self.report_path, "w") as f:
            f.write(f"# 📡 ADS-B Grid Audit: {self.run_id}\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"**Data Window:** {start_t} to {end_t}\n")
            f.write(f"**Total Packets:** {count:,}\n\n")
            
            if not t1.empty: 
                f.write("### 1.1 Fleet Performance Matrix\n" + t1.to_markdown(index=False) + "\n\n")
            
            # Check for Missing Sensors
            missing = set(SENSORS.keys()) - set(active_sensors)
            if missing:
                f.write(f"> ⚠️ **WARNING: Missing Telemetry**\n")
                f.write(f"> The following configured sensors produced NO valid aircraft data in this window: **{', '.join(missing)}**.\n")
                f.write(f"> *Check Infrastructure Dashboard (D5/D7) for possible disk fill or thermal shutdown events.*\n\n")

            f.write("## 2. Visual Evidence\n")
            f.write("![D1](figures/D1_Operational.png)\n![D3](figures/D3_Spatial.png)\n![D2](figures/D2_Physics.png)\n![D4](figures/D4_Forensics.png)\n")
            
            if (self.fig_dir / "D5_Infrastructure_Health.png").exists():
                f.write("### Infrastructure\n![D5](figures/D5_Infrastructure_Health.png)\n")
                
            if not self.df_ml.empty:
                ghosts = self.df_ml[self.df_ml['anomaly'] == -1]
                f.write(f"\n## 3. 👻 Anomaly Detection (Ghost Hunt)\n")
                f.write(f"**Algorithm:** Isolation Forest (n=100, contamination=1%)\n")
                f.write(f"- **Detected Anomalies:** {len(ghosts):,} ({len(ghosts)/len(self.df_ml)*100:.2f}%)\n\n")
                
                if 'confidence_pct' in ghosts.columns:
                    top5 = ghosts.sort_values('confidence_pct', ascending=False).head(5)
                    disp = top5[['hex', 'sensor_id', 'alt', 'ground_speed', 'rssi', 'confidence_pct']].copy()
                    disp['confidence_pct'] = disp['confidence_pct'].apply(lambda x: f"{x:.1f}%")
                    disp.columns = ['Hex', 'Sensor', 'Alt (ft)', 'Speed (kts)', 'RSSI', 'Confidence']
                    f.write("### 3.1 Top 5 Highest Confidence Anomalies\n")
                    f.write(disp.to_markdown(index=False) + "\n\n")

                f.write("### 3.2 Forensic Maps\n")
                f.write("![D6](figures/D6_ML_Analysis.png)\n")
                f.write("![D7](figures/D7_Ghost_Confidence.png)\n")
                f.write("![D8](figures/D8_Ghost_Map_Confidence.png)\n")
                f.write("![D9](figures/D9_Ghost_Map_Spatial.png)\n")
                f.write("![D10](figures/D10_Ghost_Physics.png)\n")
            
            # --- FULL SCHEMA RESTORATION ---
            f.write("\n## 4. 📚 Research Data Schema\n")
            f.write("Comprehensive definition of all collected data fields.\n\n")

            f.write("### 4.1 Aircraft Telemetry (`aircraft.json`)\n")
            f.write("| Field | Unit | Description | Relevance |\n|---|---|---|---|\n")
            f.write("| `hex` | 24-bit | Unique ICAO Address | Target ID |\n")
            f.write("| `flight` | String | Call Sign | Identification |\n")
            f.write("| `squawk` | Octal | Transponder Code | ATC Assignment |\n")
            f.write("| `lat`/`lon` | Deg | WGS84 Position | Geolocation |\n")
            f.write("| `alt_baro` | Feet | Barometric Altitude | Vertical Profile |\n")
            f.write("| `alt_geom` | Feet | GNSS Altitude | Anti-Spoofing (Check vs Baro) |\n")
            f.write("| `gs` | Knots | Ground Speed | Kinematics |\n")
            f.write("| `track` | Deg | True Track | Heading Analysis |\n")
            f.write("| `baro_rate` | ft/min | Climb/Sink Rate | Vertical Dynamics |\n")
            f.write("| `nic` | 0-11 | Nav Integrity Category | Spoofing Indicator (Trust) |\n")
            f.write("| `sil` | 0-3 | Source Integrity Level | Spoofing Indicator (Probability) |\n")
            f.write("| `nac_p` | 0-11 | Nav Accuracy Category | Spoofing Indicator (Precision) |\n")
            f.write("| `rc` | Meters | Radius of Containment | Safety Bubble |\n")
            f.write("| `version` | Int | DO-260 Standard | 0=Old, 2=DO-260B |\n")
            f.write("| `rssi` | dBFS | Signal Strength | Receiver Proximity |\n\n")

            f.write("### 4.2 Hardware Stress (`stats.json`)\n")
            f.write("Detailed SDR and decoder performance metrics.\n\n")
            f.write("| Field | Sub-Field | Description | Criticality |\n|---|---|---|---|\n")
            f.write("| `local` | `samples_processed` | Total RF samples read from SDR | Throughput |\n")
            f.write("| `local` | `samples_dropped` | Samples lost due to CPU/USB lag | **HIGH (Data Loss)** |\n")
            f.write("| `local` | `mode_s` | Valid Mode-S preambles detected | Signal Quality |\n")
            f.write("| `local` | `signal` | Mean Signal Level (dBFS) | Gain Tuning |\n")
            f.write("| `local` | `noise` | Noise Floor (dBFS) | Environment |\n")
            f.write("| `local` | `strong_signals` | Count of signals > -3dBFS | **LNA Overload** |\n")
            f.write("| `remote` | `modes` | Messages received from network neighbors | Grid Health |\n")
            f.write("| `cpr` | `airborne/surface` | Compact Position Reports decoded | Geo-Efficiency |\n")
            f.write("| `cpr` | `global_bad` | CPR packets discarded (Ambiguous) | Decoder Stress |\n")
            f.write("| `cpu` | `demod` | Time spent demodulating RF | CPU Load |\n")
            f.write("| `cpu` | `background` | Time spent in housekeeping | Overhead |\n\n")

            f.write("### 4.3 GNSS Navigation (`_gnss_log.csv`)\n")
            f.write("Precise positioning data from u-blox/SiRF receivers.\n\n")
            f.write("| Field | Unit | Description |\n|---|---|---|\n")
            f.write("| `timestamp` | UTC | Time of fix |\n")
            f.write("| `lat`/`lon` | Deg | Sensor WGS84 Position |\n")
            f.write("| `alt` | Meters | Height Above Ellipsoid (HAE) |\n")
            f.write("| `fix` | Enum | 0=No Fix, 1=2D, 2=3D, 4=RTK-Fixed |\n")
            f.write("| `sats` | Int | Number of satellites used |\n")
            f.write("| `hdop` | Float | Horizontal Dilution of Precision |\n\n")

            f.write("### 4.4 System Health & Storage (`hardware_health.csv`)\n")
            f.write("Forensic logs for diagnosing node crashes and outages.\n\n")
            f.write("| Field | Unit | Description |\n|---|---|---|\n")
            f.write("| `timestamp` | ISO | Log time |\n")
            f.write("| `node` | String | Hostname (e.g., sensor-west) |\n")
            f.write("| `Temp_C` | Celsius | CPU SoC Temperature |\n")
            f.write("| `Throttled_Hex` | Hex | 0x50000 = Under-Voltage Occurred |\n")
            f.write("| `Clock_Arm_Hz` | Hz | Current CPU Frequency (Throttling check) |\n")
            f.write("| `disk_used_kb` | KB | Storage consumed by logs |\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    
    eda = ADSB_Science_EDA(args.out_dir)
    eda.load_science_data(datetime.now().strftime("%Y-%m-%d"))
    eda.generate_plots()
    eda.write_report()
    print(f"[SCIENCE] ✅ Report generated: {args.out_dir}")
