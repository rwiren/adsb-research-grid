#!/usr/bin/env python3
"""
FILE: scripts/tune_gain_docker.py
DESCRIPTION:
  Docker-Aware Gain Optimization Sweep.
  Targets 'ultrafeeder' in /opt/adsb-grid/docker-compose.yml.
"""

import time
import requests
import subprocess
import json
import sys

# --- CONFIGURATION ---
TARGET_HOST = "pi@192.168.192.110"  # Sensor-West
DOCKER_PATH = "/opt/adsb-grid"      # Path to docker-compose.yml
API_PORT = 8080
DURATION_PER_STEP = 45

# RTL-SDR Standard Gain Table (Descending)
GAIN_STEPS = [49.6, 48.0, 44.5, 43.9, 42.1, 40.2, 38.6, 36.4, 33.8, 29.7, 25.4, 20.7]

def set_remote_gain(host, gain):
    """Updates docker-compose.yml and recreates the container."""
    print(f"   [CMD] Setting Gain to {gain} dB...")
    
    # 1. Sed command to replace READSB_GAIN line
    # We use -i (in-place) and a regex to find 'READSB_GAIN=...'
    sed_cmd = (
        f"sed -i 's/READSB_GAIN=[0-9.]*/READSB_GAIN={gain}/' {DOCKER_PATH}/docker-compose.yml"
    )
    
    # 2. Docker Compose command to apply changes
    # 'up -d' picks up the file change and recreates only the modified container
    compose_cmd = (
        f"docker compose -f {DOCKER_PATH}/docker-compose.yml up -d ultrafeeder"
    )
    
    # Combine into one SSH call for atomicity
    full_cmd = f"ssh {host} \"{sed_cmd} && {compose_cmd}\""
    
    try:
        subprocess.run(full_cmd, shell=True, check=True, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f"   [ERR] SSH Command Failed: {e}")
        sys.exit(1)

    # 3. Wait for container to boot and readsb to initialize
    time.sleep(15) 

def measure_performance(host_ip):
    """Polls the HTTP API for metrics."""
    # Try the standard ultrafeeder paths
    base_url = f"http://{host_ip}:{API_PORT}"
    
    # NOTE: If getting 404s, your container might serve data at /tar1090/data/
    endpoints = [
        f"{base_url}/data",           # Standard root mapping
        f"{base_url}/tar1090/data",   # Nginx subpath mapping
        f"{base_url}/dump1090-fa/data" # Legacy mapping
    ]

    stats_url = None
    air_url = None

    # Auto-detect correct path
    for ep in endpoints:
        try:
            test = requests.get(f"{ep}/stats.json", timeout=1)
            if test.status_code == 200:
                stats_url = f"{ep}/stats.json"
                air_url = f"{ep}/aircraft.json"
                break
        except:
            continue
            
    if not stats_url:
        print(f"   [ERR] HTTP 404: Could not find stats.json on {base_url}. Check container logs.")
        return None

    try:
        # Rate Calculation (3s delta)
        r1 = requests.get(stats_url, timeout=2).json()
        t1 = time.time()
        c1 = r1['total']['local']['accepted'][0]
        
        time.sleep(3) 
        
        r2 = requests.get(stats_url, timeout=2).json()
        t2 = time.time()
        c2 = r2['total']['local']['accepted'][0]
        
        rate = (c2 - c1) / (t2 - t1)
        
        # Physics & Geometry
        air_data = requests.get(air_url, timeout=2).json()
        aircraft_count = len(air_data['aircraft'])
        
        # Signal Strength (Last 1 min average)
        latest = r2['last1min']['local']
        signal = latest.get('peak_signal', -99)
        noise = latest.get('noise', -99)
        
        return {
            "rate": rate,
            "aircraft": aircraft_count,
            "signal": signal,
            "noise": noise
        }
    except Exception as e:
        print(f"   [ERR] Measurement failed: {e}")
        return None

def main():
    ip = TARGET_HOST.split('@')[1]
    print("===================================================")
    print(f"   DOCKER GAIN TUNER | Target: {TARGET_HOST}")
    print("===================================================")
    
    # Pre-check API
    print("   [INIT] Checking API connectivity...")
    test_data = measure_performance(ip)
    if not test_data:
        print("   ❌ ABORTING: API Unreachable. Fix the 404 error first.")
        sys.exit(1)
    else:
        print("   ✅ API Detected. Starting Sweep...")

    results = []
    try:
        for gain in GAIN_STEPS:
            print(f"\n🔭 TESTING GAIN: {gain} dB")
            
            # 1. Apply Gain via Docker
            set_remote_gain(TARGET_HOST, gain)
            
            # 2. Soak
            print(f"   [WAIT] Stabilizing for {DURATION_PER_STEP}s...")
            time.sleep(DURATION_PER_STEP)
            
            # 3. Measure
            data = measure_performance(ip)
            if data:
                data['gain'] = gain
                results.append(data)
                print(f"   --> RATE: {data['rate']:.1f}/s | PLANES: {data['aircraft']} | RSSI: {data['signal']} dB")
            
    except KeyboardInterrupt:
        print("\n[!] Aborted by user.")

    # --- ANALYSIS ---
    print("\n===================================================")
    print("   RESULTS ANALYSIS")
    print("===================================================")
    print(f"{'GAIN':<6} | {'RATE':<6} | {'ACFT':<6} | {'RSSI':<6} | {'NOISE':<6} | {'SCORE':<6}")
    
    best_score = 0
    best_gain = 0
    
    for r in results:
        # Scoring: Maximize Rate, Brutally penalize clipping (>-3dB)
        penalty = 1.0
        if r['signal'] > -3.0: penalty = 0.01 
        
        score = r['rate'] * penalty
        
        if score > best_score:
            best_score = score
            best_gain = r['gain']
            
        print(f"{r['gain']:<6} | {r['rate']:<6.1f} | {r['aircraft']:<6} | {r['signal']:<6.1f} | {r['noise']:<6.1f} | {score:<6.1f}")

    print("===================================================")
    print(f"🏆 OPTIMAL GAIN: {best_gain} dB")
    print("===================================================")
    print(f"Command to apply: ssh {TARGET_HOST} \"sed -i 's/READSB_GAIN=[0-9.]*/READSB_GAIN={best_gain}/' {DOCKER_PATH}/docker-compose.yml && docker compose -f {DOCKER_PATH}/docker-compose.yml up -d ultrafeeder\"")

if __name__ == "__main__":
    main()
