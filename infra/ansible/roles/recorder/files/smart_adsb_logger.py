import sys
import os
import time
import socket
import json
import threading
import logging
import argparse
import datetime
import urllib.request
from logging.handlers import RotatingFileHandler

# ==============================================================================
# FILE: smart_adsb_logger.py
# VERSION: 1.3.0 (Restored Aircraft Logging via JSON)
# ==============================================================================

# --- CONFIGURATION ---
LOG_FORMAT = '%(asctime)s %(levelname)s: %(message)s'
STATS_INTERVAL = 60      # System health check (seconds)
AIRCRAFT_INTERVAL = 1.0  # Trajectory snapshot rate (seconds)

# Setup Global Logging
sys_log = logging.getLogger("SmartADSBLogger")
sys_log.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter(LOG_FORMAT))
sys_log.addHandler(handler)

class SmartLogger:
    def __init__(self, host, port, log_dir, log_aircraft):
        self.host = host
        self.port = port
        self.log_dir = log_dir
        self.log_aircraft = log_aircraft
        self.running = True
        self.lock = threading.Lock()
        self.sensor_id = os.getenv("SENSOR_ID", "sensor-unknown")
        
        # Ensure output directory
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Metrics
        self.messages_total = 0
        self.aircraft_seen = 0

    def get_filenames(self):
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        return {
            "stats": os.path.join(self.log_dir, f"{self.sensor_id}_stats_log_{today}.csv"),
            "aircraft": os.path.join(self.log_dir, f"{self.sensor_id}_aircraft_log_{today}.csv")
        }

    def write_csv(self, file_type, headers, data):
        filepath = self.get_filenames()[file_type]
        file_exists = os.path.isfile(filepath)
        
        with self.lock:
            try:
                with open(filepath, "a") as f:
                    if not file_exists:
                        f.write(",".join(headers) + "\n")
                    f.write(",".join(map(str, data)) + "\n")
            except Exception as e:
                sys_log.error(f"Failed to write {file_type} log: {e}")

    def run_stats_loop(self):
        """Logs system health every 60s."""
        sys_log.info(f"✅ Started Stats Monitor ({STATS_INTERVAL}s)")
        while self.running:
            try:
                # Read CPU Temp
                temp = "N/A"
                try:
                    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                        temp = float(f.read()) / 1000.0
                except:
                    pass
                
                # Write Stats CSV
                timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
                self.write_csv("stats", 
                             ["timestamp", "messages_total", "aircraft_tracked", "cpu_temp"], 
                             [timestamp, self.messages_total, self.aircraft_seen, temp])
                
                # Update Health Status JSON (For external monitoring)
                status = {
                    "status": "healthy",
                    "timestamp": timestamp,
                    "metrics": {"messages": self.messages_total, "temp": temp}
                }
                with open("/var/lib/adsb_storage/health_status.json", "w") as f:
                    json.dump(status, f)
                    
            except Exception as e:
                sys_log.error(f"Stats loop error: {e}")
            
            time.sleep(STATS_INTERVAL)

    def run_aircraft_loop(self):
        """Fetches decoded aircraft state from local webserver every 1s."""
        if not self.log_aircraft:
            return

        sys_log.info(f"✅ Started Aircraft Logger ({AIRCRAFT_INTERVAL}s)")
        # We assume readsb/dump1090 is running on localhost port 8080
        url = "http://localhost:8080/data/aircraft.json"
        
        while self.running:
            try:
                with urllib.request.urlopen(url, timeout=2) as response:
                    data = json.loads(response.read().decode())
                    
                timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
                self.aircraft_seen = len(data.get("aircraft", []))
                
                for ac in data.get("aircraft", []):
                    # Only log if we have at least a Hex ID
                    if "hex" in ac:
                        row = [
                            timestamp,
                            ac.get("hex", ""),
                            ac.get("flight", "").strip(),
                            ac.get("lat", ""),
                            ac.get("lon", ""),
                            ac.get("alt_baro", ""),
                            ac.get("gs", ""),
                            ac.get("track", ""),
                            ac.get("rssi", "")
                        ]
                        self.write_csv("aircraft", 
                                     ["timestamp", "hex", "flight", "lat", "lon", "alt", "gs", "track", "rssi"], 
                                     row)
                                     
            except Exception as e:
                # Don't spam logs if service is momentarily down
                pass
                
            time.sleep(AIRCRAFT_INTERVAL)

    def run(self):
        sys_log.info(f"🚀 Initializing...")
        
        # 1. Start Stats Thread
        threading.Thread(target=self.run_stats_loop, daemon=True).start()
        
        # 2. Start Aircraft Logging Thread
        threading.Thread(target=self.run_aircraft_loop, daemon=True).start()
        
        # 3. Main Loop: Keep a heartbeat connection to port 30005 (just to count raw frames)
        while self.running:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(10)
                s.connect((self.host, self.port))
                sys_log.info(f"✅ Connected to ADSB Stream ({self.port})")
                
                while self.running:
                    data = s.recv(4096)
                    if not data: break
                    # Just count raw frames for health stats
                    self.messages_total += 1
            except Exception as e:
                time.sleep(5)
            finally:
                s.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=30005)
    parser.add_argument("--log-dir", default=".")
    parser.add_argument("--log-aircraft", action="store_true")
    args = parser.parse_args()

    sensor_app = SmartLogger(args.host, args.port, args.log_dir, args.log_aircraft)
    try:
        sensor_app.run()
    except KeyboardInterrupt:
        sys_log.info("Stopping...")
