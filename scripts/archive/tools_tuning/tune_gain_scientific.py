#!/usr/bin/env python3
"""
FILE: scripts/tune_gain_scientific.py
DESCRIPTION:
  Automated Gain Optimization Sweep.
  Iterates through valid SDR gain levels, restarts the remote service,
  and records telemetry to find the optimal Signal-to-Noise ratio.
"""

import time
import requests
import subprocess
import json
import numpy as np
import pandas as pd
from datetime import datetime

# CONFIGURATION
TARGET_HOST = "pi@192.168.192.110"  # Default (West), change as needed
API_PORT = 8080
DURATION_PER_STEP = 45  # Seconds to measure each step

# RTL-SDR Standard Gain Table (Descending)
GAIN_STEPS = [49.6, 48.0, 44.5, 43.9, 42.1, 40.2, 38.6, 36.4, 33.8, 29.7, 25.4, 20.7]

def set_remote_gain(host, gain):
    """Uses SSH to modify the readsb config and restart the service."""
    print(f"   [CMD] Setting Gain to {gain} dB...")
    
    # 1. Update Config File (Sed magic)
    # Assumes standard /etc/default/readsb or /etc/default/dump1090-fa location
    # This command looks for '--gain <number>' or '--gain max' and replaces it.
    cmd_update = (
        f"ssh {host} 'sudo sed -i -E \"s/--gain [0-9\.]+/--gain {gain}/\" /etc/default/readsb "
        f"&& sudo sed -i -E \"s/--gain -10/--gain {gain}/\" /etc/default/readsb'"
    )
    subprocess.run(cmd_update, shell=True, check=True)

    # 2. Restart Service
    cmd_restart = f"ssh {host} 'sudo systemctl restart readsb'"
    subprocess.run(cmd_restart, shell=True, check=True)
    
    # 3. Wait for boot
    time.sleep(10) 

def measure_performance(host_ip):
    """Polls the HTTP API for metrics."""
    stats_url = f"http://{host_ip}:{API_PORT}/data/stats.json"
    air_url = f"http://{host_ip}:{API_PORT}/data/aircraft.json"
    
    try:
        # Rate Calculation (2s delta)
        r1 = requests.get(stats_url, timeout=2).json()
        t1 = time.time()
        c1 = r1['total']['local']['accepted'][0]
        
        time.sleep(5) # Short sample
        
        r2 = requests.get(stats_url, timeout=2).json()
        t2 = time.time()
        c2 = r2['total']['local']['accepted'][0]
        
        rate = (c2 - c1) / (t2 - t1)
        
        # Physics & Geometry
        air_data = requests.get(air_url, timeout=2).json()
        aircraft_count = len(air_data['aircraft'])
        
        # Signal Strength (Last 1 min average from stats)
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
    print("===================================================")
    print(f"   SCIENTIFIC GAIN TUNER | Target: {TARGET_HOST}")
    print("===================================================")
    
    results = []
    ip = TARGET_HOST.split('@')[1]

    try:
        for gain in GAIN_STEPS:
            print(f"\n🔭 TESTING GAIN: {gain} dB")
            
            # 1. Apply Gain
            set_remote_gain(TARGET_HOST, gain)
            
            # 2. Soak (Let stats accumulate)
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
        # Scoring Algo: Message Rate * (1 if RSSI < -3 else 0.5 penalty for clipping)
        penalty = 1.0
        if r['signal'] > -3.0: penalty = 0.1  # Severe penalty for clipping
        
        score = r['rate'] * penalty
        
        if score > best_score:
            best_score = score
            best_gain = r['gain']
            
        print(f"{r['gain']:<6} | {r['rate']:<6.1f} | {r['aircraft']:<6} | {r['signal']:<6.1f} | {r['noise']:<6.1f} | {score:<6.1f}")

    print("===================================================")
    print(f"🏆 OPTIMAL GAIN: {best_gain} dB")
    print("===================================================")
    print(f"To apply permanently, run:\nssh {TARGET_HOST} 'sudo sed -i -E \"s/--gain [0-9\.]+/--gain {best_gain}/\" /etc/default/readsb && sudo systemctl restart readsb'")

if __name__ == "__main__":
    main()
