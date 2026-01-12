import requests
import json
import subprocess
import time
import configparser
from datetime import datetime

# ==============================================================================
# Script: check_signal_health.py (v6.1)
# Purpose: Robust Diagnostic Tool.
#          - v6.1 FIX: Added "|| true" to SSH command to prevent Python crash 
#            on GPS timeout. This restores Temp/Disk display for Sensor-North.
# ==============================================================================

ANSIBLE_CFG = "infra/ansible/ansible.cfg"

NODES = {
    "sensor-north": {"ip": "192.168.192.130", "port": 8080, "role": "Base Station"},
    "sensor-west":  {"ip": "192.168.192.110", "port": 8080, "role": "Mobile Scout"},
    "sensor-east":  {"ip": "192.168.192.120", "port": 8080, "role": "Sibbo Unit"}
}

def get_ssh_key_path():
    try:
        config = configparser.ConfigParser()
        config.read(ANSIBLE_CFG)
        if 'defaults' in config and 'private_key_file' in config['defaults']:
            return config['defaults']['private_key_file']
    except: pass
    return None

def get_ssh_metrics(host):
    key_path = get_ssh_key_path()
    key_flag = f"-i {key_path}" if key_path else ""
    
    # v6.1 FIX: Added "|| true" at the end.
    # This prevents subprocess.check_output from raising an exception if 
    # 'timeout' kills gpspipe (exit code 124).
    cmd = (
        f"ssh {key_flag} -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o LogLevel=QUIET pi@{host} "
        "'vcgencmd measure_temp; echo \"__SPLIT__\"; "
        "df -h / | tail -1; echo \"__SPLIT__\"; "
        "timeout 2 gpspipe -w -n 10 2>/dev/null || true'" 
    )
    
    try:
        output = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore')
        parts = output.split('__SPLIT__')
        
        # 1. Parse Temp
        temp = "N/A"
        if len(parts) > 0:
            temp = parts[0].replace("temp=", "").replace("'C", "").strip() + "°C"

        # 2. Parse Disk
        disk = "N/A"
        if len(parts) > 1:
            try:
                disk = parts[1].split()[4]
            except: pass

        # 3. Parse GPS (Python Side)
        gnss_mode = 0
        gnss_sats = 0
        if len(parts) > 2:
            gps_lines = parts[2].strip().split('\n')
            for line in gps_lines:
                try:
                    data = json.loads(line)
                    if data.get('class') == 'TPV':
                        m = data.get('mode', 0)
                        if m > gnss_mode: gnss_mode = m
                    if data.get('class') == 'SKY':
                        s = data.get('nSat', 0)
                        if s == 0 and 'satellites' in data:
                            s = len(data['satellites'])
                        # Only update sats if we found a non-zero count
                        if s > 0: gnss_sats = s
                except:
                    continue

        return {"temp": temp, "disk": disk, "gnss_mode": gnss_mode, "gnss_sats": gnss_sats}

    except Exception as e:
        # If it still fails, it's a real network error
        return None

def get_http_metrics(host, port):
    try:
        r_stats = requests.get(f"http://{host}:{port}/data/stats.json", timeout=2).json()
        local_1min = r_stats.get('last1min', {}).get('local', {})
        r_air = requests.get(f"http://{host}:{port}/data/aircraft.json", timeout=2).json()
        
        return {
            'peak': local_1min.get('peak_signal', -99),
            'noise': local_1min.get('noise', -99),
            'ac_count': len(r_air.get('aircraft', [])),
            'msgs_last_min': local_1min.get('accepted', [0])[0]
        }
    except:
        return None

def suggest_gain(peak):
    if peak > -3: return "CRITICAL: Clipping! Reduce Gain."
    if peak < -30: return "ADVICE: Signal Weak. Increase Gain."
    return "PERFECT: Hold Gain."

def print_dashboard(name, config):
    print(f"\n📡 PROBING: {name.upper()} [{config['role']}]")
    
    sys = get_ssh_metrics(config['ip'])
    rf = get_http_metrics(config['ip'], config['port'])
    
    # Defaults
    temp = disk = "N/A"
    gnss = "UNREACHABLE ❌"
    peak = noise = -99
    ac_count = "?"
    rate_status = "UNKNOWN"

    if sys:
        temp = sys['temp']
        disk = sys['disk']
        
        # GNSS Logic
        m = sys['gnss_mode']
        s = sys['gnss_sats']
        
        if m >= 3: gnss = f"3D FIX ({s} Sats) ✅"
        elif m == 2: gnss = f"2D FIX ({s} Sats) ⚠️"
        else: gnss = "NO FIX ❌"

    if rf:
        peak = rf['peak']
        noise = rf['noise']
        ac_count = rf['ac_count']
        rate_status = "ACTIVE 🟢" if rf['msgs_last_min'] > 0 else "IDLE 🟡"

    # --- RENDER UI ---
    print("   ┌──────────────────────────────────────────────────────────┐")
    print("   │ 🏥 SYSTEM HEALTH                                          │")
    print("   ├──────────────────────────────────────────────────────────┤")
    print(f"   │ 🌡️  Temp         : {temp:<10} 💾 Disk: {disk:<10}      │")
    print(f"   │ 🛰️  GNSS Status  : {gnss:<33}      │")
    print("   │                                                          │")
    print("   │ 🧪 RF DIAGNOSTICS                                         │")
    print("   ├──────────────────────────────────────────────────────────┤")
    print(f"   │ 📶 Peak Signal  : {peak:<5} dBFS   📉 Noise: {noise:<5} dBFS   │")
    print(f"   │ ✈️  Traffic      : {ac_count:<3}   Aircraft                     │")
    print(f"   │ ⏺️  Recorder     : {rate_status:<33}      │")
    print("   ├──────────────────────────────────────────────────────────┤")
    print(f"   │ 👉 {suggest_gain(peak):<53} │")
    print("   └──────────────────────────────────────────────────────────┘")

def main():
    print("===============================================================")
    print(f"      ADS-B DIAGNOSTICS v6.1 | {datetime.now().strftime('%H:%M:%S')}")
    print("===============================================================")
    for name, config in NODES.items():
        print_dashboard(name, config)
    print("")

if __name__ == "__main__":
    main()
