#!/usr/bin/env python3
"""
==============================================================================
FILE: scripts/eda_academic_report.py
DESCRIPTION:
  Generates a multi-page PDF Research Report for ADS-B Sensor Data.
  Page 1: Executive Summary (Tables, Metrics, Insights)
  Page 2: RF & Traffic Analysis (Plots 1-6)
  Page 3: Hardware & GNSS Stability (Plots 7-11)
  
  Updates:
  - Fixed Unix Epoch timestamp scaling (1970 bug).
  - Added text-based insights and summary tables.
==============================================================================
"""

import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import seaborn as sns
import numpy as np
from datetime import datetime
import warnings

# Suppress minor warnings for cleaner output
warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid")

# CONFIGURATION
DATA_DIR = "research_data"

def load_master_data(sensor_path, log_type):
    """Robustly loads the MASTER csv for a specific log type."""
    pattern = os.path.join(sensor_path, f"*_{log_type}_MASTER_*.csv")
    files = glob.glob(pattern)
    if not files:
        return None
    
    try:
        df = pd.read_csv(files[0])
    except Exception as e:
        print(f"      ❌ Error reading {files[0]}: {e}")
        return None
    
    # Attempt to convert various timestamp columns
    time_cols = [c for c in df.columns if 'time' in c.lower() or 'now' in c.lower()]
    if time_cols:
        col = time_cols[0]
        # FIX: Explicitly treat float timestamps as Seconds (Unix Epoch)
        df[col] = pd.to_datetime(df[col], unit='s', errors='coerce')
        
        # Drop rows with invalid times
        df = df.dropna(subset=[col])
        
        # Sort by time
        df = df.sort_values(by=col)
        
        # FIX: Handle Duplicate Timestamps
        df = df.drop_duplicates(subset=[col], keep='first')
        
        df.set_index(col, inplace=True)
    
    return df

def generate_summary_page(pdf, sensor_name, date_str, df_air, df_gnss, df_stats):
    """Creates Page 1: Textual Executive Summary & Tables"""
    fig, ax = plt.subplots(figsize=(11, 15))
    ax.axis('off')
    
    # --- HEADER ---
    plt.text(0.5, 0.98, f"ADS-B SENSOR REPORT: {sensor_name.upper()}", 
             ha='center', fontsize=20, weight='bold', color='navy')
    plt.text(0.5, 0.95, f"Date: {date_str} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 
             ha='center', fontsize=12, color='gray')
    
    # --- METRICS CALCULATION ---
    # Air Metrics
    total_msgs = len(df_air) if df_air is not None else 0
    unique_planes = df_air['hex'].nunique() if (df_air is not None and 'hex' in df_air.columns) else 0
    avg_rssi = df_air['rssi'].mean() if (df_air is not None and 'rssi' in df_air.columns) else 0
    
    # GNSS Metrics
    avg_sats = df_gnss['used'].astype(float).mean() if (df_gnss is not None and 'used' in df_gnss.columns) else 0
    gps_fix_count = len(df_gnss) if df_gnss is not None else 0
    
    # Stats Metrics
    avg_temp = 0
    if df_stats is not None and 'cpu_temp' in df_stats.columns:
         # Clean temp string
         temps = df_stats['cpu_temp'].astype(str).str.replace("'C", "", regex=False).str.replace("C", "", regex=False)
         avg_temp = pd.to_numeric(temps, errors='coerce').mean()

    # --- INSIGHTS SECTION ---
    report_text = f"""
    EXECUTIVE SUMMARY
    -----------------
    This report summarizes the operational performance of sensor '{sensor_name}'.
    
    1. TRAFFIC INTELLIGENCE
       • Total ADS-B Messages Captured:  {total_msgs:,}
       • Unique Aircraft Identified:     {unique_planes}
       • Average Signal Strength:        {avg_rssi:.1f} dBFS
       
    2. HARDWARE STATUS
       • Average CPU Temperature:        {avg_temp:.1f} °C
       • GNSS Data Points Collected:     {gps_fix_count}
       • Average Satellites Used:        {avg_sats:.1f}
       
    3. AUTOMATED INSIGHTS
       • Signal Quality: {"✅ Strong" if avg_rssi > -25 else "⚠️ Moderate" if avg_rssi > -35 else "🔴 Weak"}
       • Traffic Volume: {"✅ High" if total_msgs > 50000 else "⚠️ Moderate" if total_msgs > 10000 else "🔴 Low"}
       • System Health:  {"✅ Nominal" if avg_temp < 60 else "⚠️ Running Hot" if avg_temp < 75 else "🔴 CRITICAL TEMP"}
    """
    
    plt.text(0.1, 0.85, report_text, fontsize=12, family='monospace', va='top')
    
    # --- DATA TABLE ---
    # Create a small summary table of hourly stats
    if df_air is not None:
        hourly = df_air.resample('1h').size().reset_index(name='Msg Count')
        hourly['Hour'] = hourly.iloc[:, 0].dt.hour
        hourly = hourly[['Hour', 'Msg Count']].head(24) # Show first 24h
        
        # Add table to plot
        if not hourly.empty:
            table_data = []
            for _, row in hourly.iterrows():
                table_data.append([f"{row['Hour']:02d}:00", f"{row['Msg Count']:,}"])
            
            # Split into two columns if long, or just show top 12 active hours
            table_data = table_data[:15] # Limit rows for space
            
            plt.text(0.1, 0.45, "HOURLY TRAFFIC BREAKDOWN (Top 15 Hours)", fontsize=12, weight='bold')
            table = plt.table(cellText=table_data, colLabels=["Hour", "Messages"], 
                              loc='bottom', bbox=[0.1, 0.1, 0.4, 0.3])
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1, 1.5)

    pdf.savefig(fig)
    plt.close()

def generate_sensor_report(sensor_name, date_str, sensor_path):
    output_pdf = os.path.join(sensor_path, f"Report_{sensor_name}_{date_str}.pdf")
    print(f"   📊 Generating PDF Report: {output_pdf}")

    # Load Data
    df_air = load_master_data(sensor_path, "aircraft")
    df_gnss = load_master_data(sensor_path, "gnss")
    df_stats = load_master_data(sensor_path, "stats")

    with PdfPages(output_pdf) as pdf:
        
        # PAGE 1: Executive Summary
        generate_summary_page(pdf, sensor_name, date_str, df_air, df_gnss, df_stats)

        # PAGE 2: RF & TRAFFIC INTELLIGENCE
        fig1, axes1 = plt.subplots(3, 2, figsize=(11, 15))
        fig1.suptitle(f"RF Intelligence: {sensor_name} ({date_str})", fontsize=16, weight='bold')

        # Plot 1: Message Rate
        if df_air is not None and not df_air.empty:
            msg_rate = df_air.resample('1min').size()
            axes1[0, 0].plot(msg_rate.index, msg_rate.values, color='royalblue', linewidth=2)
            axes1[0, 0].set_title("1. Message Capture Rate (msgs/min)")
            axes1[0, 0].set_ylabel("Messages")
            axes1[0, 0].tick_params(axis='x', rotation=45)
        else:
            axes1[0, 0].text(0.5, 0.5, "No Aircraft Data", ha='center')

        # Plot 2: RSSI Distribution
        if df_air is not None and 'rssi' in df_air.columns:
            sns.histplot(data=df_air, x='rssi', bins=30, kde=True, ax=axes1[0, 1], color='darkorange')
            axes1[0, 1].set_title("2. Signal Strength (RSSI) Distribution")
            axes1[0, 1].set_xlabel("RSSI (dBFS)")
        
        # Plot 3: Altitude
        if df_air is not None and 'alt_baro' in df_air.columns:
            alts = pd.to_numeric(df_air['alt_baro'], errors='coerce').dropna()
            if not alts.empty:
                sns.histplot(alts, bins=30, kde=True, ax=axes1[1, 0], color='seagreen')
                axes1[1, 0].set_title("3. Aircraft Altitude Distribution")
                axes1[1, 0].set_xlabel("Altitude (ft)")

        # Plot 4: RSSI vs Altitude
        if df_air is not None and 'rssi' in df_air.columns and 'alt_baro' in df_air.columns:
            plot_data = df_air.copy().reset_index()
            plot_data['alt_baro'] = pd.to_numeric(plot_data['alt_baro'], errors='coerce')
            plot_data['rssi'] = pd.to_numeric(plot_data['rssi'], errors='coerce')
            plot_data = plot_data.dropna(subset=['alt_baro', 'rssi'])
            
            if len(plot_data) > 5000: plot_data = plot_data.sample(5000)
            if not plot_data.empty:
                sns.scatterplot(data=plot_data, x='alt_baro', y='rssi', alpha=0.3, ax=axes1[1, 1], color='purple')
                axes1[1, 1].set_title("4. Signal Range: RSSI vs Altitude")
                axes1[1, 1].set_ylabel("RSSI (dBFS)")

        # Plot 5: Unique Aircraft Cumulative
        if df_air is not None and 'hex' in df_air.columns:
            df_air['new_aircraft'] = ~df_air['hex'].duplicated()
            cumulative_planes = df_air['new_aircraft'].cumsum()
            axes1[2, 0].plot(df_air.index, cumulative_planes, color='firebrick')
            axes1[2, 0].set_title("5. Unique Aircraft Spotted (Cumulative)")
            axes1[2, 0].tick_params(axis='x', rotation=45)

        # Plot 6: Hourly Activity
        if df_air is not None:
            hourly = df_air.index.hour.value_counts().sort_index()
            sns.barplot(x=hourly.index, y=hourly.values, ax=axes1[2, 1], palette="Blues_d")
            axes1[2, 1].set_title("6. Hourly Activity Profile")
            axes1[2, 1].set_xlabel("Hour of Day")

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        pdf.savefig(fig1)
        plt.close()

        # PAGE 3: HARDWARE
        fig2, axes2 = plt.subplots(3, 2, figsize=(11, 15))
        fig2.suptitle(f"Hardware Diagnostics: {sensor_name} ({date_str})", fontsize=16, weight='bold')

        # Plot 7: GNSS Satellites
        if df_gnss is not None and 'used' in df_gnss.columns:
            df_gnss['used'] = pd.to_numeric(df_gnss['used'], errors='coerce')
            df_gnss['visible'] = pd.to_numeric(df_gnss.get('visible', 0), errors='coerce')
            axes2[0, 0].plot(df_gnss.index, df_gnss['visible'], label='Visible', color='lightgray', linestyle='--')
            axes2[0, 0].plot(df_gnss.index, df_gnss['used'], label='Used (Fix)', color='green', linewidth=2)
            axes2[0, 0].set_title("7. GNSS Satellite Lock Stability")
            axes2[0, 0].legend()
            axes2[0, 0].tick_params(axis='x', rotation=45)
        else:
             axes2[0, 0].text(0.5, 0.5, "No GNSS Data", ha='center')

        # Plot 8: CPU Temp
        if df_stats is not None and 'cpu_temp' in df_stats.columns:
            val = df_stats['cpu_temp'].astype(str).str.replace("'C", "", regex=False).str.replace("C", "", regex=False)
            df_stats['cpu_temp_clean'] = pd.to_numeric(val, errors='coerce')
            axes2[0, 1].plot(df_stats.index, df_stats['cpu_temp_clean'], color='red')
            axes2[0, 1].set_title("8. CPU Temperature Profile")
            axes2[0, 1].set_ylabel("Temp (°C)")
            axes2[0, 1].tick_params(axis='x', rotation=45)

        # Plot 9: GNSS Drift
        if df_gnss is not None and 'lat' in df_gnss.columns:
            lat = pd.to_numeric(df_gnss['lat'], errors='coerce')
            lon = pd.to_numeric(df_gnss['lon'], errors='coerce')
            lat_mean, lon_mean = lat.mean(), lon.mean()
            lat_diff = (lat - lat_mean) * 111139
            lon_diff = (lon - lon_mean) * 111139
            axes2[1, 0].scatter(lon_diff, lat_diff, alpha=0.5, s=10)
            axes2[1, 0].set_title("9. GNSS Position Drift (Meters)")
            axes2[1, 0].set_xlabel("Longitude Drift (m)")
            axes2[1, 0].set_ylabel("Latitude Drift (m)")

        # Plot 10: CPU Load
        if df_stats is not None and 'cpu_load_percent' in df_stats.columns:
             load = pd.to_numeric(df_stats['cpu_load_percent'], errors='coerce')
             axes2[1, 1].plot(df_stats.index, load, color='black')
             axes2[1, 1].set_title("10. System CPU Load %")
             axes2[1, 1].set_ylim(0, 100)
             axes2[1, 1].tick_params(axis='x', rotation=45)

        # Plot 11: Memory
        if df_stats is not None and 'memory_used_percent' in df_stats.columns:
            mem = pd.to_numeric(df_stats['memory_used_percent'], errors='coerce')
            axes2[2, 0].fill_between(df_stats.index, mem, color='blue', alpha=0.2)
            axes2[2, 0].set_title("11. Memory Usage %")
            axes2[2, 0].set_ylim(0, 100)
            axes2[2, 0].tick_params(axis='x', rotation=45)

        axes2[2, 1].axis('off')

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        pdf.savefig(fig2)
        plt.close()
        print(f"      ✅ Report Saved.")

def main():
    print("🔬 INITIALIZING ACADEMIC VISUALIZATION ENGINE (v2.0)...")
    
    for date_folder in sorted(os.listdir(DATA_DIR)):
        date_path = os.path.join(DATA_DIR, date_folder)
        if not os.path.isdir(date_path) or date_folder.startswith('.'): continue

        for sensor in sorted(os.listdir(date_path)):
            sensor_path = os.path.join(date_path, sensor)
            if not os.path.isdir(sensor_path): continue
            
            if glob.glob(os.path.join(sensor_path, "*_MASTER_*.csv")):
                generate_sensor_report(sensor, date_folder, sensor_path)
            else:
                print(f"   ⚠️  Skipping {sensor}/{date_folder} (No Master Data found)")

if __name__ == "__main__":
    main()
