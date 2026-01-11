#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# ==============================================================================
# FILE: scripts/check_signal_health.py
# VERSION: 3.7.0 (Cool Down Configuration)
# DATE: 2026-01-11
# MAINTAINER: DevOps / Data Science Team
#
# DESCRIPTION:
#   Scientific validation tool for ADS-B Sensor Nodes.
#   - v3.7.0: Updated gain targets to match 'Cool Down' deployment.
#     (North: 15.7, East: 20.7, West: 40.2)
#   - v3.6.0: Increased sampling window to 5.5s to fix "0 msg/s" artifact.
# ==============================================================================
"""

import requests
import time
import math
from datetime import datetime

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
# Standard RTL-SDR Gain Steps (0.0 to 49.6 dB)
VALID_GAINS = [49.6, 48.0, 44.5, 43.9, 43.4, 42.1, 40.2, 38.6, 38.0, 37.2, 36.4, 
               33.8, 32.8, 29.7, 28.0, 25.4, 22.9, 20.7, 19.7, 16.6, 15.7, 
               14.4, 12.5, 8.7, 7.7, 3.7, 0.0]

NODES = {
    "sensor-north": {
        "url": "http://192.168.192.130:8080",
        "role": "Base Station (Blue Stick)",
        "target_gain": 15.7,   # <--- NEW TARGET (Safety Margin)
        "lat": 60.319555,
        "lon": 24.830816
    },
    "sensor-west": {
        "url": "http://192.168.192.110:8080",
        "role": "Mobile Scout (Silver Stick)",
        "target_gain": 40.2,   # <--- NEW TARGET (CPU Load Fix)
        "lat": 60.319555,   
        "lon": 24.830816
    },
    "sensor-east": {
        "url": "http://192.168.192.120:8080",
        "role": "Sibbo Unit (Blue Stick)",
        "target_gain": 20.7,   # <--- NEW TARGET (Clipping Fix)
        "lat": 60.374127,
        "lon": 25.249095
    }
}

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates distance between two WGS84 points in Nautical Miles (NM)."""
    if lat2 is None or lon2 is None: return 0.0
    R = 3440.065 # Radius of Earth in NM
    
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_message_count(data_json):
    """Extracts total message count robustly."""
    try:
        local = data_json.get('total', {}).get('local', {})
        if 'messages' in local: return int(local['messages'])
        elif 'accepted' in local: return sum(local['accepted'])
        return 0
    except: return 0

def suggest_gain(current_gain, peak_signal):
    """Returns recommended gain tuning advice based on signal headroom."""
    if current_gain is None:
        if peak_signal > -3.0: return "CRITICAL: Signal Clipping! Lower Gain."
        return "Unknown Gain"

    if current_gain not in VALID_GAINS:
        return f"Gain {current_gain} not standard."

    idx = VALID_GAINS.index(current_gain)
    
    # Optimization Logic:
    # Target window: -3 dBFS (Max) to -25 dBFS (Min)
    if peak_signal > -3.0:
        new_idx = min(len(VALID_GAINS)-1, idx + 2)
        return f"CRITICAL: Reduce to {VALID_GAINS[new_idx]}"
    elif peak_signal > -5.0:
        new_idx = min(len(VALID_GAINS)-1, idx + 1)
        return f"ADVICE: Reduce to {VALID_GAINS[new_idx]}"
    elif peak_signal < -25.0:
        new_idx = max(0, idx - 1)
        return f"ADVICE: Increase to {VALID_GAINS[new_idx]}"
    else:
        return "PERFECT: Hold Gain"

# -----------------------------------------------------------------------------
# MAIN LOGIC
# -----------------------------------------------------------------------------
def fetch_telemetry(node_name, config):
    stats_url = f"{config['url']}/data/stats.json"
    aircraft_url = f"{config['url']}/data/aircraft.json"
    receiver_url = f"{config['url']}/data/receiver.json"
    
    print(f"\n📡 PROBING: {node_name.upper()} [{config['role']}]")

    try:
        # --- PHASE 1: RATE ANALYSIS (Extended Window) ---
        # NOTE: ReadsB writes stats.json every 5s-60s. 
        # Window must be > update_interval to catch changes.
        sample_duration = 5.5 
        
        r1 = requests.get(stats_url, timeout=2.0)
        t1 = time.time()
        c1 = get_message_count(r1.json())
        
        time.sleep(sample_duration)
        
        r2 = requests.get(stats_url, timeout=2.0)
        t2 = time.time()
        c2 = get_message_count(r2.json())
        
        air_data = requests.get(aircraft_url, timeout=2.0).json()

        # Calculation
        time_delta = t2 - t1
        msg_delta = c2 - c1
        instant_rate = msg_delta / time_delta if time_delta > 0 else 0

        # --- PHASE 2: GAIN DETECTION ---
        active_gain = None
        gain_source = "Unknown"
        try:
            r_recv = requests.get(receiver_url, timeout=1.0)
            if r_recv.status_code == 200:
                recv_data = r_recv.json()
                if 'gain' in recv_data:
                    active_gain = float(recv_data['gain'])
                    gain_source = "Verified via API"
        except: pass
        
        if active_gain is None:
            active_gain = config['target_gain']
            gain_source = "Config Target"

        # --- PHASE 3: PHYSICS EXTRACTION ---
        stats_data = r2.json()
        latest = stats_data.get('last1min', {}).get('local', {})
        
        peak_signal = latest.get('peak_signal', -99.9)
        noise_db = latest.get('noise', -99.9)
        signal_avg = latest.get('signal', -99.9)
        
        # Average Rate (1-min avg from JSON)
        avg_count_1min = 0
        if 'messages' in latest: avg_count_1min = latest['messages']
        elif 'accepted' in latest: avg_count_1min = sum(latest['accepted'])
        avg_rate = avg_count_1min / 60.0

        # --- PHASE 4: GEOMETRY ---
        max_range_nm = 0.0
        aircraft_with_pos = 0
        plane_list = air_data.get('aircraft', [])
        for p in plane_list:
            if p.get('lat') and p.get('lon'):
                aircraft_with_pos += 1
                dist = p.get('r')
                if not dist:
                    dist = haversine_distance(config['lat'], config['lon'], p.get('lat'), p.get('lon'))
                if dist and dist > max_range_nm: max_range_nm = dist

        # --- PHASE 5: REPORT ---
        p_val = float(peak_signal)
        if p_val > -3.0:   sig_status = "CLIPPING ⛔"
        elif p_val > -5.0: sig_status = "Limit ⚠️"
        elif p_val < -35.0: sig_status = "Weak 📉"
        else:              sig_status = "Optimal ✅"

        snr = float(signal_avg) - float(noise_db)
        snr_grade = "Excellent 🌟" if snr > 20 else "Fair ⚠️"

        print("   ┌──────────────────────────────────────────────────────────┐")
        print("   │ 🧪 PHYSICS (RF Health)                                  │")
        print("   ├──────────────────────────────────────────────────────────┤")
        
        gain_icon = "✅" if gain_source == "Verified via API" else "⚠️"
        print(f"   │ ⚙️  Gain Setting    : {str(active_gain):<5} dB ({gain_source}) {gain_icon} │")
        print(f"   │ 📶 Peak RSSI       : {p_val:<5} dBFS ({sig_status}){'':<7} │")
        print(f"   │ 📊 SNR             : {snr:.1f} dB ({snr_grade}){'':<13} │")
        print(f"   │ 📉 Noise Floor     : {noise_db:<5} dBFS {'':<19} │")
        
        print("   │                                                          │")
        print("   │ 🚀 PERFORMANCE (Throughput)                              │")
        print("   ├──────────────────────────────────────────────────────────┤")
        print(f"   │ 📡 Max Range       : {max_range_nm:.1f} NM   {'':<20} │")
        print(f"   │ ✈️  Aircraft       : {len(plane_list)} total / {aircraft_with_pos} w/ pos{'':<7} │")
        print(f"   │ ⚡ Instant Rate   : {int(instant_rate):<4} msg/s  (5.5s Sample){'':<2} │")
        print(f"   │ 📉 Average Rate   : {int(avg_rate):<4} msg/s  (60s Avg){'':<6} │")
        
        print("   │                                                          │")
        print("   │ 💡 SMART RECOMMENDATION                                  │")
        print("   ├──────────────────────────────────────────────────────────┤")
        print(f"   │ 👉 {suggest_gain(active_gain, p_val):<53} │")
        print("   └──────────────────────────────────────────────────────────┘")

    except requests.exceptions.ConnectionError:
        print("   ❌ FATAL: Connection Refused (Firewall?). Check port 8080.")
    except requests.exceptions.ReadTimeout:
        print("   ❌ FATAL: Read Timeout. Node is overloaded or dropping packets.")
    except Exception as e:
        print(f"   ❌ EXCEPTION: {e}")

if __name__ == "__main__":
    print("===============================================================")
    print(f"      ADS-B DIAGNOSTICS v3.7 | {datetime.now().strftime('%H:%M:%S')}")
    print("===============================================================")
    for name, config in NODES.items():
        fetch_telemetry(name, config)
    print("")
