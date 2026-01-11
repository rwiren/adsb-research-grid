#!/usr/bin/env python3
"""
# ==============================================================================
# FILE: scripts/optimize_grid.py
# VERSION: 1.1.0 (Stable/Production)
# DATE: 2026-01-11
# MAINTAINER: DevOps / Data Science Team
#
# DESCRIPTION:
#   Automated Gain Optimization Engine for the Distributed ADS-B Grid.
#   Implements a "Scientific Sweep" protocol to determine the optimal
#   Signal-to-Noise Ratio (SNR) "Knee Point" for SDR hardware.
#
# ARCHITECTURE:
#   1. CONNECTIVITY: auto-detects JSON endpoints (/data/ vs /tar1090/data/).
#   2. TUNING: Iterates standard RTL-SDR gain steps (49.6dB -> 33.8dB).
#   3. EXECUTION: Updates 'docker-compose.yml' and recycles containers remotely.
#   4. SCORING: Calculates a 'Performance Score' = Message Rate * Clipping Penalty.
#
# USAGE:
#   python3 scripts/optimize_grid.py
#
# REQUIREMENTS:
#   - Remote user 'pi' must own the /opt/adsb-grid directory.
#     Run: ssh pi@<ip> "sudo chown -R pi:pi /opt/adsb-grid"
# ==============================================================================
"""

import time
import requests
import subprocess
import sys
import json
from datetime import datetime

# ==============================================================================
# 1. GRID CONFIGURATION (The "Source of Truth")
# ==============================================================================

# Define the operational role for each sensor node.
# 'TUNE': Perform active gain sweep (Restart services).
# 'CHECK': Perform passive health check (No restart).

NODES = {
    "sensor-east": {
        "host": "pi@192.168.192.120",
        "action": "TUNE",           # TARGET: FlightAware Blue Stick (Sibbo)
        "docker_path": "/opt/adsb-grid",
        "container": "ultrafeeder",
        "desc": "Sibbo Field Unit (Blue Stick)"
    },
    "sensor-north": {
        "host": "pi@192.168.192.130",
        "action": "CHECK",          # Stable Base Station
        "docker_path": "/opt/adsb-grid",
        "container": "ultrafeeder",
        "desc": "Base Station (Blue Stick)"
    },
    "sensor-west": {
        "host": "pi@192.168.192.110",
        "action": "CHECK",          # Generic Hardware (Do not tune)
        "docker_path": "/opt/adsb-grid",
        "container": "ultrafeeder",
        "desc": "Mobile Scout (Jetvision)"
    }
}

# Standard Gain Steps (Descending Order)
# Focusing on the high-end range where FlightAware Blue sticks operate best.
GAIN_STEPS = [49.6, 48.0, 44.5, 43.9, 42.1, 40.2, 38.6, 36.4, 33.8]

API_PORT = 8080
DURATION_PER_STEP = 45  # Seconds to dwell on each gain setting for stability

# ==============================================================================
# 2. CORE FUNCTIONS
# ==============================================================================

def get_api_endpoint(host_ip):
    """
    Robustly detects the correct JSON data endpoint.
    Handles variations between readsb, tar1090, and dump1090-fa paths.
    """
    base_url = f"http://{host_ip}:{API_PORT}"
    candidates = [
        f"{base_url}/data",           # Standard readsb
        f"{base_url}/tar1090/data",   # Nginx proxy mapping
        f"{base_url}/dump1090-fa/data",
        f"{base_url}/readsb/data"
    ]
    
    for url in candidates:
        try:
            r = requests.get(f"{url}/stats.json", timeout=2)
            if r.status_code == 200:
                return url
        except:
            continue
    return None

def set_remote_gain(node_conf, gain):
    """
    Updates docker-compose.yml via SSH and recycles the container.
    NOTE: Relies on user ownership (no sudo) for file editing.
    """
    host = node_conf['host']
    path = node_conf['docker_path']
    container = node_conf['container']
    
    # CMD 1: Update Config (Regex Replace)
    # Replaces 'READSB_GAIN=...' with the new test value.
    sed_cmd = f"sed -i 's/READSB_GAIN=[0-9.]*/READSB_GAIN={gain}/' {path}/docker-compose.yml"
    
    # CMD 2: Smart Restart
    # 'up -d' is preferred over 'restart' as it handles environment variable updates cleaner.
    compose_cmd = f"docker compose -f {path}/docker-compose.yml up -d {container}"
    
    # Combine commands for atomic execution
    full_cmd = f"ssh {host} \"{sed_cmd} && {compose_cmd}\""
    
    try:
        # We suppress stdout to keep the console clean, but capture stderr for debugging.
        subprocess.run(full_cmd, shell=True, check=True, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL)
        
        # Critical Wait: Allow Docker to stop, start, and the decoder to initialize.
        time.sleep(15) 
        return True
    except subprocess.CalledProcessError as e:
        print(f"      [ERR] Remote Update Failed: {e}")
        print(f"      [HINT] Did you run 'sudo chown -R pi:pi {path}' on the remote node?")
        return False

def measure_metrics(api_url):
    """
    Samples performance metrics over a short delta window.
    Returns: Rate (msg/s), Aircraft Count, RSSI, Noise.
    """
    try:
        # Snapshot 1
        r1 = requests.get(f"{api_url}/stats.json", timeout=2).json()
        t1 = time.time()
        c1 = r1['total']['local']['accepted'][0]
        
        time.sleep(3) # Measurement Window
        
        # Snapshot 2
        r2 = requests.get(f"{api_url}/stats.json", timeout=2).json()
        t2 = time.time()
        c2 = r2['total']['local']['accepted'][0]
        
        # Physics Data (Signal Strength)
        air = requests.get(f"{api_url}/aircraft.json", timeout=2).json()
        latest = r2['last1min']['local']
        
        return {
            "rate": (c2 - c1) / (t2 - t1),
            "aircraft": len(air['aircraft']),
            "signal": latest.get('peak_signal', -99.9),
            "noise": latest.get('noise', -99.9)
        }
    except Exception as e:
        return None

# ==============================================================================
# 3. OPERATION MODES
# ==============================================================================

def run_health_check(name, conf, ip):
    """Passive monitoring mode for standard/production nodes."""
    print(f"\n🏥 HEALTH CHECK: {name.upper()} ({conf['desc']})")
    url = get_api_endpoint(ip)
    
    if not url:
        print("   ❌ API Unreachable (Check Container/VPN)")
        return

    data = measure_metrics(url)
    if data:
        status = "✅ ONLINE" if data['rate'] > 0 else "⚠️ IDLE"
        print(f"   STATUS:   {status}")
        print(f"   RATES:    {data['rate']:.1f} msg/s")
        print(f"   AIRCRAFT: {data['aircraft']} tracked")
        print(f"   SIGNAL:   {data['signal']} dBFS")
    else:
        print("   ❌ Read Error")

def run_tuning_sweep(name, conf, ip):
    """Active tuning mode for high-performance nodes."""
    print(f"\n🔭 TUNING SWEEP: {name.upper()} ({conf['desc']})")
    url = get_api_endpoint(ip)
    
    if not url:
        print("   ❌ FATAL: API Unreachable. Cannot tune blind.")
        return

    print(f"   [INIT] Baseline check passed. Starting {len(GAIN_STEPS)}-step sweep...")
    print(f"   {'GAIN':<6} | {'RATE':<6} | {'ACFT':<6} | {'RSSI':<6} | {'SCORE':<6}")
    print("   " + "-"*40)

    best_score = -1
    best_gain = 0

    try:
        for gain in GAIN_STEPS:
            # 1. Apply Gain
            if not set_remote_gain(conf, gain):
                continue
                
            # 2. Soak (Wait for AGC/Traffic to stabilize)
            time.sleep(DURATION_PER_STEP)
            
            # 3. Measure
            data = measure_metrics(url)
            if data:
                # Scoring Algorithm:
                # Prioritize Message Rate, but apply heavy penalty for Clipping (>-3dB)
                penalty = 0.1 if data['signal'] > -3.0 else 1.0
                score = data['rate'] * penalty
                
                print(f"   {gain:<6} | {data['rate']:<6.1f} | {data['aircraft']:<6} | {data['signal']:<6.1f} | {score:<6.1f}")
                
                if score > best_score:
                    best_score = score
                    best_gain = gain
                    
    except KeyboardInterrupt:
        print("\n   [!] Interrupted by user.")

    print("   " + "-"*40)
    print(f"   🏆 OPTIMAL GAIN: {best_gain} dB (Score: {best_score:.1f})")
    
    # Restore optimal setting
    print(f"   [RESTORE] Applying optimal gain {best_gain}...")
    set_remote_gain(conf, best_gain)
    print("   ✅ Tuning Complete.")

# ==============================================================================
# 4. MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    print("==========================================================")
    print(f" 📡 SMART GRID OPTIMIZER | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("==========================================================")
    
    for name, conf in NODES.items():
        ip = conf['host'].split('@')[1]
        
        # Execute based on configured Action
        if conf['action'] == "TUNE":
            run_tuning_sweep(name, conf, ip)
        else:
            run_health_check(name, conf, ip)
            
    print("\n==========================================================")
    print(" [INFO] REMINDER: Update 'infra/ansible/host_vars/' with new gains!")
    print("==========================================================")
