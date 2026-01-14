import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import glob
import os
import argparse
import sys
from datetime import datetime, timezone

# ==============================================================================
# 📂 File: scripts/infra_health.py
# [VERSION] v3.3 (Clean - No Copy Warnings)
# ==============================================================================

sns.set_theme(style="whitegrid")
plt.rcParams['figure.figsize'] = [12, 12]
plt.rcParams['figure.dpi'] = 150

RAW_PATH = "infra/ansible/playbooks/research_data/raw"

def log_msg(msg, level="INFO"):
    prefix = {"INFO": "ℹ️", "WARN": "⚠️", "ERR": "❌", "OK": "✅"}.get(level, "")
    print(f"[INFRA] {prefix} {msg}")

def normalize_cols(df):
    if not df.empty:
        df.columns = df.columns.str.strip().str.lower()
        rename_map = {'temp': 'temp_c', 'uptime': 'uptime_sec'}
        df.rename(columns=rename_map, inplace=True)
    return df

def load_data(raw_dir):
    log_msg(f"Scanning logs in {raw_dir}...", "INFO")
    
    health_files = glob.glob(f"{raw_dir}/**/hardware_health.csv", recursive=True)
    store_files = glob.glob(f"{raw_dir}/**/storage_history.csv", recursive=True)
    
    # --- HEALTH ---
    df_health = pd.DataFrame()
    if health_files:
        df_list = []
        for f in health_files:
            try:
                temp = pd.read_csv(f, on_bad_lines='skip', engine='python')
                temp = normalize_cols(temp)
                if 'timestamp' not in temp.columns: continue
                
                if 'node' not in temp.columns:
                    parts = f.split(os.sep)
                    sid = next((p for p in reversed(parts) if p.startswith('sensor-')), 'unknown')
                    temp['node'] = sid
                df_list.append(temp)
            except: pass
        if df_list: df_health = pd.concat(df_list, ignore_index=True)

    # --- STORAGE ---
    df_store = pd.DataFrame()
    if store_files:
        df_list = []
        for f in store_files:
            try:
                temp = pd.read_csv(f, on_bad_lines='skip', engine='python')
                temp = normalize_cols(temp)
                if 'timestamp' not in temp.columns: continue
                
                if 'node' not in temp.columns:
                    parts = f.split(os.sep)
                    sid = next((p for p in reversed(parts) if p.startswith('sensor-')), 'unknown')
                    temp['node'] = sid
                df_list.append(temp)
            except: pass
        if df_list: df_store = pd.concat(df_list, ignore_index=True)
    
    return process_data(df_health, df_store)

def process_data(df_health, df_store):
    now_utc = datetime.now(timezone.utc)

    # --- HEALTH ---
    if not df_health.empty:
        # Fix CopyWarning by explicit copy
        df_health = df_health.copy()
        
        df_health['timestamp'] = pd.to_datetime(df_health['timestamp'], errors='coerce')
        df_health = df_health.dropna(subset=['timestamp'])
        
        if df_health['timestamp'].dt.tz is None:
            df_health['timestamp'] = df_health['timestamp'].dt.tz_localize('UTC')
        else:
            df_health['timestamp'] = df_health['timestamp'].dt.tz_convert('UTC')

        cutoff = now_utc - pd.Timedelta(days=2)
        df_health = df_health[df_health['timestamp'] > cutoff]

    # --- STORAGE ---
    if not df_store.empty:
        df_store = df_store.copy()
        
        df_store['timestamp'] = pd.to_datetime(df_store['timestamp'], errors='coerce')
        df_store = df_store.dropna(subset=['timestamp'])
        
        if df_store['timestamp'].dt.tz is None:
            df_store['timestamp'] = df_store['timestamp'].dt.tz_localize('UTC')
        else:
            df_store['timestamp'] = df_store['timestamp'].dt.tz_convert('UTC')

        cutoff = now_utc - pd.Timedelta(days=2)
        df_store = df_store[df_store['timestamp'] > cutoff]

    if not df_health.empty:
        log_msg(f"Loaded {len(df_health)} valid health records.", "OK")
    return df_health, df_store

def plot_health(df_h, df_s, out_dir):
    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True)
    
    # Thermal
    if not df_h.empty and 'temp_c' in df_h.columns:
        sns.lineplot(data=df_h, x='timestamp', y='temp_c', hue='node', ax=ax1, palette="magma", marker=".")
        ax1.axhline(60, color='red', linestyle='--', alpha=0.7, label='Warning (60°C)')
        ax1.legend(loc='upper left', fontsize='small')
    else:
        ax1.text(0.5, 0.5, "No Data", ha='center', transform=ax1.transAxes)
    ax1.set_title("CPU Thermal Performance"); ax1.set_ylabel("Temp (°C)")

    # Storage
    if not df_s.empty and 'disk_used_kb' in df_s.columns:
        df_s['Disk Used (GB)'] = df_s['disk_used_kb'] / 1e6
        sns.lineplot(data=df_s, x='timestamp', y='Disk Used (GB)', hue='node', ax=ax2, palette="colorblind", linewidth=2)
        ax2.axhline(32, color='#4e606e', linestyle=':', label='32GB Limit')
        ax2.legend(loc='upper left', fontsize='small')
    else:
        ax2.text(0.5, 0.5, "No Data", ha='center', transform=ax2.transAxes)
    ax2.set_title("Storage Consumption"); ax2.set_ylabel("Disk Used (GB)")
    
    date_form = mdates.DateFormatter("%m-%d\n%H:%M")
    ax2.xaxis.set_major_formatter(date_form)
    
    plt.suptitle(f"D5: Infrastructure Health\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", weight='bold')
    plt.tight_layout()
    plt.savefig(f"{out_dir}/D5_Infrastructure_Health.png")
    plt.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    
    try:
        h, s = load_data(RAW_PATH)
        plot_health(h, s, args.out_dir)
        log_msg(f"Saved {args.out_dir}/D5_Infrastructure_Health.png", "OK")
    except Exception as e:
        log_msg(f"FAILURE: {e}", "ERR")
        sys.exit(1)
