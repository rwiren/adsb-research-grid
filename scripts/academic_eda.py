#!/usr/bin/env python3
# ------------------------------------------------------------------
# [FILE] scripts/academic_eda.py
# [AUTHOR] Richard Wirén
# [DATE] 2026-01-12
# [VERSION] 1.2.1 (Full Schema Release)
# [DESCRIPTION] 
#   Generates the "Academic Showcase" report. Ingests raw CSV logs,
#   performs cleaning and type enforcement, merges with ML training 
#   data, and produces statistical visualizations and a full Markdown
#   report including the Research Data Schema.
# 
# [DEPENDENCIES] pandas, numpy, matplotlib, seaborn, scikit-learn
# ------------------------------------------------------------------

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import subprocess
import os
import glob
from datetime import datetime
# Import ML Libs for On-Demand Calculation
from sklearn.ensemble import IsolationForest

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------
SENSORS = {
    "sensor-north": {"lat": 60.319555, "lon": 24.830816, "color": "#003f5c", "name": "North (Ref)", "marker": "^"}, 
    "sensor-east":  {"lat": 60.3621, "lon": 25.3375, "color": "#bc5090", "name": "East (Sipoo)", "marker": "s"}, 
    "sensor-west":  {"lat": 60.1478, "lon": 24.5264, "color": "#ffa600", "name": "West (Jorvas)", "marker": "o"} 
}

ML_DATASET = "research_data/ml_ready/training_dataset_v3.csv"

class ADSB_Academic_EDA:
    def __init__(self, raw_dir="research_data"):
        self.raw_dir = raw_dir
        self.run_id = datetime.now().strftime("%Y-%m-%d_%H%M")
        self.showcase_dir = f"docs/showcase/run_{self.run_id}"
        self.fig_dir = f"{self.showcase_dir}/figures"
        os.makedirs(self.fig_dir, exist_ok=True)
        self.df_ac = pd.DataFrame()
        self.df_ml = pd.DataFrame() 
        self.metadata = self._get_git_metadata()
        self.report_path = f"{self.showcase_dir}/REPORT.md"
        
        # [VISUALIZATION] Academic Style Settings
        plt.style.use('seaborn-v0_8-paper')
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['figure.dpi'] = 150
        plt.rcParams['savefig.dpi'] = 300
        plt.rcParams['axes.grid'] = True
        plt.rcParams['grid.alpha'] = 0.3

    def _get_git_metadata(self):
        """Retrieves the current Git SHA for reproducibility."""
        try: return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).strip().decode()
        except: return "LOCAL"

    def haversine(self, lat1, lon1, lat2, lon2):
        """Calculates Great Circle distance between sensor and aircraft."""
        R = 6372.8 # Earth radius in km
        dLat, dLon = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
        lat1, lat2 = np.radians(lat1), np.radians(lat2)
        a = np.sin(dLat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dLon/2)**2
        return R * 2 * np.arcsin(np.sqrt(a))

    def load_data(self, target_date):
        """
        Ingests raw CSV data with strict type enforcement to prevent DtypeWarnings.
        """
        print(f"[{self.metadata}] 📥 Loading Raw Data...")
        ac_files = glob.glob(f"{self.raw_dir}/{target_date}/sensor-*/sensor-*_aircraft_log*.csv*")
        
        # [DATA SCIENCE] Strict schema to handle mixed types (e.g. Flight ID vs Squawk)
        dtype_schema = {
            'hex': str,
            'flight': str,
            'squawk': str,
            'sensor_id': str
        }
        
        ac_list = []
        for f in ac_files:
            try:
                parts = f.split(os.sep)
                sid = next((p for p in parts if p.startswith('sensor-')), 'unknown')
                comp = 'gzip' if f.endswith('.gz') else None
                
                # [FIX] Added low_memory=False and dtype argument to fix warnings
                tmp = pd.read_csv(
                    f, 
                    compression=comp, 
                    on_bad_lines='skip', 
                    dtype=dtype_schema,
                    low_memory=False 
                )
                
                if 'timestamp' in tmp.columns:
                    tmp['timestamp'] = pd.to_datetime(tmp['timestamp'], format='mixed', utc=True)
                
                tmp['sensor_id'] = sid
                rename_map = {'alt_baro': 'alt', 'gs': 'ground_speed'}
                tmp.rename(columns=rename_map, inplace=True)
                
                # Calculate distance if sensor is known
                if sid in SENSORS:
                    tmp['distance_km'] = self.haversine(SENSORS[sid]['lat'], SENSORS[sid]['lon'], tmp['lat'], tmp['lon'])
                
                ac_list.append(tmp)
            except Exception as e:
                print(f"   ⚠️  Skipping corrupted file {f}: {e}")
            
        if ac_list:
            self.df_ac = pd.concat(ac_list, ignore_index=True)
            for c in ['rssi', 'alt', 'ground_speed', 'track']: 
                self.df_ac[c] = pd.to_numeric(self.df_ac[c], errors='coerce')
            
            # Filter for valid dates (sanity check)
            self.df_ac = self.df_ac[self.df_ac['timestamp'] > '2026-01-01']
            print(f"✅ Raw Rows: {len(self.df_ac):,}")

        # --- SELF-HEALING ML LOADER ---
        if os.path.exists(ML_DATASET):
            print(f"🧠 Loading ML Data from {ML_DATASET}...")
            # Reuse schema for consistency
            self.df_ml = pd.read_csv(ML_DATASET, dtype=dtype_schema, low_memory=False)
            
            # CHECK: Do we have the answers?
            if 'anomaly' not in self.df_ml.columns:
                print("⚙️  'anomaly' column missing. Running On-Demand Isolation Forest...")
                features = ['lat', 'lon', 'alt', 'ground_speed', 'track', 'rssi']
                
                # Impute missing values with median
                X = self.df_ml[features].fillna(self.df_ml[features].median())
                
                # Run the Brain
                iso = IsolationForest(n_estimators=100, contamination=0.01, random_state=42, n_jobs=-1)
                self.df_ml['anomaly'] = iso.fit_predict(X)
                self.df_ml['score'] = iso.decision_function(X) # Raw confidence score
                
                # Normalize Score to 0-100% (Severity)
                min_score = self.df_ml['score'].min()
                self.df_ml['confidence_pct'] = 0.0
                
                # Map negative scores (anomalies) to 0-100 scale
                anom_mask = self.df_ml['score'] < 0
                if anom_mask.any():
                    self.df_ml.loc[anom_mask, 'confidence_pct'] = (self.df_ml.loc[anom_mask, 'score'] / min_score) * 100
                
                print("✅ AI Analysis Complete (On-Demand).")
            
            ghosts = self.df_ml[self.df_ml['anomaly'] == -1]
            print(f"✅ ML Rows: {len(self.df_ml):,} (Anomalies: {len(ghosts)})")

    def generate_dashboards(self):
        if self.df_ac.empty: return
        print("🎨 Generating Professional Plots...")
        pal = {k: v['color'] for k,v in SENSORS.items()}
        
        # D1: Ops
        fig, axs = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle(f"D1: Network Operations Status ({self.metadata})", fontweight='bold')
        sns.countplot(data=self.df_ac, x='sensor_id', hue='sensor_id', ax=axs[0,0], palette=pal, legend=False)
        sns.kdeplot(data=self.df_ac, x='rssi', hue='sensor_id', fill=True, ax=axs[0,1], palette=pal)
        
        self.df_ac['min_bucket'] = self.df_ac['timestamp'].dt.floor('min')
        rate = self.df_ac.groupby(['min_bucket', 'sensor_id']).size().reset_index(name='count')
        sns.lineplot(data=rate, x='min_bucket', y='count', hue='sensor_id', ax=axs[1,0], palette=pal, linewidth=1)
        
        sns.boxplot(data=self.df_ac, x='sensor_id', y='distance_km', hue='sensor_id', ax=axs[1,1], palette=pal, legend=False)
        plt.tight_layout()
        plt.savefig(f"{self.fig_dir}/D1_Operational.png")
        plt.close()

        # D2: Physics
        fig, axs = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle("D2: Physics Validation", fontweight='bold')
        sample = self.df_ac.sample(n=min(50000, len(self.df_ac)))
        
        sns.scatterplot(data=sample, x='distance_km', y='rssi', hue='sensor_id', s=10, alpha=0.3, ax=axs[0,0], palette=pal)
        sns.scatterplot(data=sample, x='ground_speed', y='alt', hue='sensor_id', s=10, alpha=0.3, ax=axs[0,1], palette=pal)
        sns.histplot(data=self.df_ac, x='alt', hue='sensor_id', element="step", ax=axs[1,0], palette=pal)
        sns.kdeplot(data=self.df_ac, x='track', hue='sensor_id', ax=axs[1,1], palette=pal)
        plt.tight_layout()
        plt.savefig(f"{self.fig_dir}/D2_Physics.png")
        plt.close()

        # D3: Spatial
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.set_title("D3: Sensor Grid Geometry", fontweight='bold')
        sns.scatterplot(data=sample, x='lon', y='lat', hue='sensor_id', s=2, alpha=0.2, palette=pal, ax=ax, legend=False)
        for sid, meta in SENSORS.items():
            ax.plot(meta['lon'], meta['lat'], marker=meta['marker'], markersize=15, color='black')
            ax.text(meta['lon'], meta['lat'] + 0.02, meta['name'].upper(), fontweight='bold', ha='center', bbox=dict(facecolor='white', alpha=0.8))
        ax.set_xlim(24.3, 25.5); ax.set_ylim(60.1, 60.45)
        plt.savefig(f"{self.fig_dir}/D3_Spatial.png")
        plt.close()

        # D4: Forensics
        fig, axs = plt.subplots(1, 2, figsize=(12, 5))
        fig.suptitle("D4: Multi-Sensor Correlation", fontweight='bold')
        self.df_ac['bucket'] = self.df_ac['timestamp'].dt.round('30s')
        piv = self.df_ac.pivot_table(index=['hex', 'bucket'], columns='sensor_id', values='rssi', aggfunc='mean')
        valid_cols = [c for c in piv.columns if c in SENSORS]
        if len(valid_cols) >= 2:
            s1, s2 = valid_cols[0], valid_cols[1]
            dat = piv[[s1, s2]].dropna()
            sns.regplot(data=dat, x=s1, y=s2, ax=axs[0], scatter_kws={'s': 5, 'alpha': 0.3}, line_kws={'color': 'red'})
            sns.histplot(dat[s1] - dat[s2], kde=True, ax=axs[1], color='purple')
        plt.tight_layout()
        plt.savefig(f"{self.fig_dir}/D4_Forensics.png")
        plt.close()

    def generate_report(self):
        if self.df_ac.empty: return
        print("📝 Compiling Markdown Report...")
        
        start_ts = self.df_ac['timestamp'].min().strftime('%Y-%m-%d %H:%M UTC')
        end_ts = self.df_ac['timestamp'].max().strftime('%Y-%m-%d %H:%M UTC')
        
        t1 = self.df_ac.groupby('sensor_id').size().reset_index(name='Packets')
        t1['Share %'] = (t1['Packets'] / t1['Packets'].sum() * 100).round(1)
        t2 = self.df_ac.groupby('sensor_id')['rssi'].agg(['mean', 'max', 'min', 'std']).round(2)
        t3 = self.df_ac.groupby('sensor_id').agg({'distance_km': 'max', 'alt': 'mean', 'hex': 'nunique'}).round(1)
        missing = self.df_ac[['lat', 'lon', 'alt', 'rssi']].isnull().sum()
        missing_pct = (missing / len(self.df_ac) * 100).round(2)
        t4 = pd.DataFrame({'Missing Rows': missing, 'Missing %': missing_pct})

        with open(self.report_path, "w") as f:
            f.write(f"# 📡 ADS-B Grid Audit: {self.run_id}\n\n")
            f.write(f"**Metadata:** `Git-SHA: {self.metadata} | Date: {datetime.now().strftime('%Y-%m-%d')}`\n\n")
            
            f.write("## 1. 📋 Executive Summary\n")
            f.write(f"| Metric | Value |\n|---|---|\n")
            f.write(f"| **Data Start** | `{start_ts}` |\n")
            f.write(f"| **Data End** | `{end_ts}` |\n")
            f.write(f"| **Total Valid Samples** | **{len(self.df_ac):,}** |\n")
            f.write(f"| **Active Sensors** | {len(t1)} |\n")
            
            if not self.df_ml.empty:
                ghosts = self.df_ml[self.df_ml['anomaly'] == -1]
                ghost_pct = (len(ghosts) / len(self.df_ml)) * 100
                f.write(f"| **Detected Anomalies** | **{len(ghosts):,}** ({ghost_pct:.2f}%) |\n")

            f.write("\n## 2. 🏥 Data Health Check\n")
            f.write(t4.to_markdown() + "\n\n")

            f.write("## 3. 📊 Fleet Performance Matrix\n")
            f.write("### 3.1 Packet Volume\n")
            f.write(t1.to_markdown(index=False) + "\n\n")
            f.write("### 3.2 Signal Forensics (RSSI)\n")
            f.write(t2.to_markdown() + "\n\n")
            f.write("### 3.3 Spatial Coverage\n")
            f.write(t3.to_markdown() + "\n\n")
            
            f.write("## 4. 🖼️ Visual Evidence\n")
            f.write("![D1](figures/D1_Operational.png)\n![D2](figures/D2_Physics.png)\n")
            f.write("![D3](figures/D3_Spatial.png)\n![D4](figures/D4_Forensics.png)\n\n")

            if not self.df_ml.empty:
                f.write("## 5. 👻 Anomaly Detection (Ghost Hunt)\n")
                f.write("**Algorithm:** Isolation Forest (n=100, contamination=1%)\n\n")
                f.write("### 5.1 Top 5 Highest Confidence Anomalies\n")
                
                score_col = 'confidence_pct' if 'confidence_pct' in self.df_ml.columns else 'score'
                
                if score_col in self.df_ml.columns:
                    top5 = self.df_ml[self.df_ml['anomaly'] == -1].sort_values(score_col, ascending=False).head(5)
                    disp = top5[['hex', 'sensor_id', 'alt', 'ground_speed', 'rssi', score_col]].copy()
                    
                    if score_col == 'confidence_pct':
                        disp[score_col] = disp[score_col].apply(lambda x: f"{x:.1f}%")
                        disp.columns = ['Hex', 'Sensor', 'Alt (ft)', 'Speed (kts)', 'RSSI', 'Confidence']
                    else:
                        disp.columns = ['Hex', 'Sensor', 'Alt (ft)', 'Speed (kts)', 'RSSI', 'Raw Score']
                        
                    f.write(disp.to_markdown(index=False) + "\n\n")
                
                f.write("### 5.2 Forensic Maps\n")
                f.write("*(See `docs/showcase/ghost_hunt/` for high-res forensic maps generated by `visualize_ghosts.py`)*\n\n")

            # --- SECTION 6: RESEARCH DATA SCHEMA (Restored) ---
            f.write("## 6. 📚 Research Data Schema\n")
            f.write("Comprehensive definition of all collected data fields.\n\n")

            f.write("### 6.1 Aircraft Telemetry (`aircraft.json`)\n")
            f.write("| Field | Unit | Description | Relevance |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
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

            f.write("### 6.2 Hardware Stress (`stats.json`)\n")
            f.write("Detailed SDR and decoder performance metrics.\n\n")
            f.write("| Field | Sub-Field | Description | Criticality |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
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

            f.write("### 6.3 GNSS Navigation (`_gnss_log.csv`)\n")
            f.write("Precise positioning data from u-blox/SiRF receivers.\n\n")
            f.write("| Field | Unit | Description |\n")
            f.write("| :--- | :--- | :--- |\n")
            f.write("| `timestamp` | UTC | Time of fix |\n")
            f.write("| `lat`/`lon` | Deg | Sensor WGS84 Position |\n")
            f.write("| `alt` | Meters | Height Above Ellipsoid (HAE) |\n")
            f.write("| `fix` | Enum | 0=No Fix, 1=2D, 2=3D, 4=RTK-Fixed |\n")
            f.write("| `sats` | Int | Number of satellites used |\n")
            f.write("| `hdop` | Float | Horizontal Dilution of Precision |\n\n")

            f.write("### 6.4 System Health & Storage (`hardware_health.csv`)\n")
            f.write("Forensic logs for diagnosing node crashes and outages.\n\n")
            f.write("| Field | Unit | Description |\n")
            f.write("| :--- | :--- | :--- |\n")
            f.write("| `timestamp` | ISO | Log time |\n")
            f.write("| `node` | String | Hostname (e.g., sensor-west) |\n")
            f.write("| `Temp_C` | Celsius | CPU SoC Temperature |\n")
            f.write("| `Throttled_Hex` | Hex | 0x50000 = Under-Voltage Occurred |\n")
            f.write("| `Clock_Arm_Hz` | Hz | Current CPU Frequency (Throttling check) |\n")
            f.write("| `disk_used_kb` | KB | Storage consumed by logs |\n")

if __name__ == "__main__":
    eda = ADSB_Academic_EDA()
    # Default to today's date for daily run
    eda.load_data(target_date=datetime.now().strftime("%Y-%m-%d"))
    eda.generate_dashboards()
    eda.generate_report()
    print(f"✅ Showcase Generated: {eda.showcase_dir}")
