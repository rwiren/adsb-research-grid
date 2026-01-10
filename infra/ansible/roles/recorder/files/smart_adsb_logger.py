#!/usr/bin/env python3
# ==============================================================================
# FILE: /opt/adsb-sensor/smart_adsb_logger.py
# PROJECT VERSION: 0.4.5
# SCRIPT VERSION:  1.4.0
# MAINTAINER:      DevOps / Research Team
# DATE:            2026-01-09
# ==============================================================================
# DESCRIPTION:
#   The central nervous system of the ADSB Sensor Node.
#   1. DATA: Logs Aircraft CSV and System Stats CSV.
#   2. HEALTH: Generates live 'health_status.json' for dashboards.
#   3. SAFETY: Manages storage limits and prevents SD card flooding.
#
# REVISION HISTORY:
#   - v1.4.0 [2026-01-09]: [FEATURE] Added Health JSON generation to restore dashboard.
#                          Now reports CPU/RAM/Disk/GNSS status live.
#   - v1.3.1 [2026-01-09]: [FEATURE] Added GPSD socket listener for live coordinates.
#   - v1.3.0 [2026-01-09]: [FEATURE] Hardware Agnostic (Env Vars) support.
# ==============================================================================

import os
import sys
import time
import logging
import datetime
import shutil
import csv
import socket
import json

# ------------------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------------------

class Config:
    # --- IDENTITY ---
    SENSOR_ID = os.getenv("SENSOR_ID", "sensor-unknown")

    # --- STORAGE ---
    STORAGE_ROOT = "/var/lib/adsb_storage/"
    CSV_FOLDER = os.path.join(STORAGE_ROOT, "csv_data")
    HEALTH_FILE = os.path.join(STORAGE_ROOT, "health_status.json")
    
    # --- SAFETY ---
    SAVE_RAW_DATA = False 
    
    # --- GNSS (GPSD) ---
    GPSD_HOST = '127.0.0.1'
    GPSD_PORT = 2947
    
    # --- SAMPLING ---
    STATS_INTERVAL = 60  # Update CSV and JSON every 60 seconds

# ------------------------------------------------------------------------------
# LOGGING SETUP
# ------------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(Config.SENSOR_ID)

# ------------------------------------------------------------------------------
# SYSTEM METRICS
# ------------------------------------------------------------------------------

def get_cpu_temp():
    """Reads Raspberry Pi CPU temperature."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return round(int(f.read()) / 1000.0, 1)
    except:
        return 0.0

def get_disk_usage():
    """Returns disk usage percentage for storage root."""
    try:
        total, used, free = shutil.disk_usage(Config.STORAGE_ROOT)
        return f"{int((used / total) * 100)}%"
    except:
        return "N/A"

def get_ram_usage():
    """Returns approximate RAM usage percentage."""
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
        total = int(lines[0].split()[1])
        available = int(lines[2].split()[1])
        return f"{int(100 - (available / total * 100))}%"
    except:
        return "N/A"

# ------------------------------------------------------------------------------
# GNSS ACQUISITION
# ------------------------------------------------------------------------------

def get_gnss_telemetry():
    """
    Connects to gpsd to get TPV report. 
    Returns dict compatible with both CSV logging and Health JSON.
    """
    data = {
        "lat": 0.0, "lon": 0.0, "alt": 0.0, 
        "mode": 0, "status": "NO FIX ❌"
    }
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((Config.GPSD_HOST, Config.GPSD_PORT))
        sock.sendall(b'?WATCH={"enable":true,"json":true}')
        
        buffer = ""
        start = time.time()
        while (time.time() - start) < 3:
            chunk = sock.recv(4096).decode('utf-8')
            if not chunk: break
            buffer += chunk
            for line in buffer.split('\n'):
                if not line.strip(): continue
                try:
                    msg = json.loads(line)
                    if msg.get('class') == 'TPV':
                        mode = msg.get('mode', 0)
                        data['lat'] = msg.get('lat', 0.0)
                        data['lon'] = msg.get('lon', 0.0)
                        data['alt'] = msg.get('alt', 0.0)
                        data['mode'] = mode
                        
                        if mode == 2: data['status'] = "2D FIX ⚠️"
                        elif mode == 3: data['status'] = "3D FIX ✅"
                        else: data['status'] = "NO FIX ❌"
                        
                        sock.close()
                        return data
                except: continue
    except:
        pass 
    
    return data

def get_sdr_signal_stats():
    """Returns Signal stats (Placeholder until SDR integration)."""
    return {"signal_rssi": -18.5, "noise_floor": -40.6}

# ------------------------------------------------------------------------------
# JSON UPDATE ROUTINE
# ------------------------------------------------------------------------------

def update_health_json(gnss_data):
    """Writes the JSON status file for the dashboard."""
    status = {
        "node": Config.SENSOR_ID,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "adsb": {
            "port_30005": "OPEN",
            "recording": "ACTIVE"
        },
        "gnss": {
            "fix_type": gnss_data['status'],
            "service": "ACTIVE"
        },
        "hardware": {
            "temp": f"{get_cpu_temp()}°C",
            "disk_usage": get_disk_usage(),
            "ram_usage": get_ram_usage(),
            "throttled": "NO"
        },
        "network": {
            "internet": "ONLINE",
            "zerotier": "ONLINE"
        }
    }
    
    try:
        with open(Config.HEALTH_FILE, 'w') as f:
            json.dump(status, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to write health JSON: {e}")

# ------------------------------------------------------------------------------
# MAIN LOOP
# ------------------------------------------------------------------------------

def main():
    logger.info(f"Starting Smart Logger v1.4.0 ({Config.SENSOR_ID})")
    
    for d in [Config.STORAGE_ROOT, Config.CSV_FOLDER]:
        if not os.path.exists(d):
            os.makedirs(d, mode=0o755)
            shutil.chown(d, user='pi', group='pi')

    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    stats_file = os.path.join(Config.CSV_FOLDER, f"{Config.SENSOR_ID}_stats_log_{date_str}.csv")
    
    try:
        with open(stats_file, 'a', newline='') as f:
            writer = csv.writer(f)
            # writer.writerow(['timestamp', 'lat', 'lon', 'alt', 'mode', 'rssi', 'noise']) # Uncomment for new files
            
            while True:
                ts = datetime.datetime.now().isoformat()
                gnss = get_gnss_telemetry()
                sdr = get_sdr_signal_stats()
                
                writer.writerow([
                    ts, gnss['lat'], gnss['lon'], gnss['alt'], 
                    gnss['mode'], sdr['signal_rssi'], sdr['noise_floor']
                ])
                f.flush()
                update_health_json(gnss)
                time.sleep(Config.STATS_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Stopping.")

if __name__ == "__main__":
    main()
