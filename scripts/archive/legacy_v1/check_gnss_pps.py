#!/usr/bin/env python3
"""
check_gnss_pps.py
"""
import matplotlib
matplotlib.use('Agg') # Essential for running on headless Pi
import matplotlib.pyplot as plt
import socket
import json
import time
import statistics
import math
import argparse
from datetime import datetime

# Configuration
GPSD_HOST = '127.0.0.1'
GPSD_PORT = 2947
PPS_PATH = '/sys/class/pps/pps0/assert'
OUTPUT_IMG = '/tmp/gnss_report.png'

def get_pps():
    try:
        with open(PPS_PATH, 'r') as f:
            return float(f.read().strip().split('#')[0])
    except:
        return None

def collect(duration):
    print(f"[*] Collecting GNSS/PPS data for {duration} seconds...")
    data = {'lat':[], 'lon':[], 'alt':[], 'pps':[], 'mode':[]}
    start = time.time()
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((GPSD_HOST, GPSD_PORT))
        sock.sendall(b'?WATCH={"enable":true,"json":true}\n')
        gps_file = sock.makefile('r', encoding='utf-8')
    except Exception as e:
        print(f"[!] GPSD Connection Error: {e}")
        return None

    last_pps = 0
    while (time.time() - start) < duration:
        # Read PPS
        pps = get_pps()
        if pps and pps != last_pps:
            data['pps'].append(pps)
            last_pps = pps
        
        # Read GNSS
        try:
            line = gps_file.readline()
            if not line: break
            msg = json.loads(line)
            if msg.get('class') == 'TPV' and msg.get('mode', 0) >= 2:
                data['lat'].append(msg.get('lat'))
                data['lon'].append(msg.get('lon'))
                data['alt'].append(msg.get('alt'))
                data['mode'].append(msg.get('mode'))
        except:
            pass
            
    sock.close()
    return data

def plot(data):
    if not data or not data['lat']:
        print("[!] No GNSS fix found during capture.")
        return

    # Statistics
    avg_lat = statistics.mean(data['lat'])
    avg_lon = statistics.mean(data['lon'])
    lat_m = [(l - avg_lat)*111000 for l in data['lat']]
    lon_m = [(l - avg_lon)*111000*math.cos(math.radians(avg_lat)) for l in data['lon']]
    
    jitter_us = 0
    if len(data['pps']) > 1:
        diffs = [b-a for a,b in zip(data['pps'][:-1], data['pps'][1:])]
        jitter_us = statistics.stdev(diffs) * 1e6

    print(f"[*] Captured {len(data['lat'])} samples.")
    print(f"[*] PPS Jitter: {jitter_us:.2f} microseconds")

    # Visualization
    fig, axs = plt.subplots(2, 2, figsize=(10, 8))
    fig.suptitle(f"GNSS/PPS Check: {datetime.now().strftime('%H:%M:%S')}")
    
    axs[0,0].scatter(lon_m, lat_m, alpha=0.5)
    axs[0,0].set_title(f"Drift (m) - Std: {statistics.stdev(lat_m):.3f}m")
    axs[0,0].axis('equal'); axs[0,0].grid(True)
    
    axs[0,1].plot(data['alt'])
    axs[0,1].set_title(f"Altitude (m) - Mean: {statistics.mean(data['alt']):.1f}m")
    
    if len(data['pps']) > 1:
        axs[1,0].plot(diffs)
        axs[1,0].set_title(f"PPS Intervals (Jitter: {jitter_us:.2f} µs)")
    
    axs[1,1].hist(data['mode'])
    axs[1,1].set_title("Fix Mode (4=DGPS, 5=Float, 6=Fix)")
    
    plt.tight_layout()
    plt.savefig(OUTPUT_IMG)
    print(f"[*] Report saved to {OUTPUT_IMG}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--duration', type=int, default=60)
    args = parser.parse_args()
    
    d = collect(args.duration)
    if d: plot(d)
