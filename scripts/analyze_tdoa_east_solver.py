import numpy as np
import pandas as pd
import math
import sys
from scipy.optimize import minimize

# --- CONFIGURATION ---
DATA_DIR = "/home/admin/ouroboros/research_data/science_run_20260201_1303"
CSV_FILE = f"{DATA_DIR}/calibration_dataset_east.csv"
FS = 2000000
C_MS = 299792.458

# GEOMETRY
LAT_N, LON_N = 60.3194, 24.8307
LAT_E_GUESS, LON_E_GUESS = 60.3601, 25.3376 # Sibbo Guess

print("🧠 EAST ELASTIC SOLVER")
print("   Calculating Drift Rate for Sensor-East...")

# --- HELPERS ---
def gps_to_local_meters(lat, lon, ref_lat, ref_lon):
    R = 6371000
    x = (lon - ref_lon) * (math.pi/180) * R * math.cos(math.radians(ref_lat))
    y = (lat - ref_lat) * (math.pi/180) * R
    return x, y

def cpr_decode(hex_msg, ref_lat, ref_lon):
    try:
        bin_str = bin(int(hex_msg, 16))[2:].zfill(112)
        cpr_lat = int(bin_str[54:71], 2)
        cpr_lon = int(bin_str[71:88], 2)
        cpr_format = int(bin_str[53])
        dlat = 360.0 / (59.0 if cpr_format else 60.0)
        j = math.floor(ref_lat/dlat) + math.floor(0.5 + ((ref_lat%dlat)/dlat) - (cpr_lat/131072.0))
        rlat = dlat * (j + cpr_lat/131072.0)
        def get_nl(lat):
            if abs(lat) >= 87: return 2
            return math.floor(2 * math.pi / math.acos(1 - (1-math.cos(math.pi/30))/(math.cos(math.radians(lat))**2)))
        nl = get_nl(rlat)
        dlon = 360.0 / max(1, nl - cpr_format)
        m = math.floor(ref_lon/dlon) + math.floor(0.5 + ((ref_lon%dlon)/dlon) - (cpr_lon/131072.0))
        rlon = dlon * (m + cpr_lon/131072.0)
        return rlat, rlon
    except: return None, None

# --- LOAD ---
df = pd.read_csv(CSV_FILE)
df['time_sec'] = df['ref_idx_north'] / FS
t0 = df['time_sec'].min()

targets = []
E_guess_x, E_guess_y = gps_to_local_meters(LAT_E_GUESS, LON_E_GUESS, LAT_N, LON_N)

for i, row in df.iterrows():
    lat, lon = cpr_decode(row['hex'], LAT_N, LON_N)
    if lat and 59.0 < lat < 62.0:
        px, py = gps_to_local_meters(lat, lon, LAT_N, LON_N)
        targets.append({
            "px": px, "py": py, 
            "tdoa": row['tdoa_ms'],
            "dt": row['time_sec'] - t0
        })

print(f"✅ Loaded {len(targets)} valid targets.")

# --- SOLVE ---
def loss_func(params):
    dx, dy, bias, drift_slope = params
    sx, sy = E_guess_x + dx, E_guess_y + dy
    error_sum = 0
    for t in targets:
        d_n = math.sqrt(t['px']**2 + t['py']**2)
        d_e = math.sqrt((t['px']-sx)**2 + (t['py']-sy)**2)
        
        geom_tdoa = (d_e - d_n) / C_MS
        pred = geom_tdoa + bias + (drift_slope * t['dt'])
        error_sum += (t['tdoa'] - pred)**2
    return math.sqrt(error_sum / len(targets))

# Initial Guess: 0, 0, 3926.9, 0.0
x0 = [0.0, 0.0, 3926.9, 0.0]
bounds = [(-200, 200), (-200, 200), (3800, 4000), (-1.0, 1.0)]

res = minimize(loss_func, x0, method='L-BFGS-B', bounds=bounds)

print("\n🏆 EAST SENSOR RESULTS:")
print(f"   RMSE: {res.fun:.4f} ms")
print(f"   -----------------------------")
print(f"   Offset: X={res.x[0]:.2f}m, Y={res.x[1]:.2f}m")
print(f"   BIAS:   {res.x[2]:.4f} ms")
print(f"   DRIFT:  {res.x[3]:.6f} ms/sec ({res.x[3]*1000:.2f} PPM)")
print(f"   -----------------------------")
