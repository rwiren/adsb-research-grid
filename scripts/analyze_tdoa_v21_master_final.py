import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import math

# --- CONFIGURATION ---
DATA_DIR = "/home/admin/ouroboros/research_data/science_run_20260201_1303"
FILE_NW = f"{DATA_DIR}/calibration_dataset_final.csv"
FILE_NE = f"{DATA_DIR}/calibration_dataset_east.csv"
C_KM_S = 299792.458 
FS = 2000000

# SENSORS
LAT_N, LON_N = 60.3194, 24.8307
LAT_W, LON_W = 60.1309, 24.5129
LAT_E, LON_E = 60.3601, 25.3376

# ELASTIC PARAMETERS
BIAS_W = 3689.8026; DRIFT_W = 0.272994
BIAS_E = 3927.1688; DRIFT_E = -0.051385

print("🎨 GENERATING MASTER MAP V21 (Bold & Correct)...")

# --- HELPERS ---
def latlon_to_km(lat, lon):
    R = 6371.0
    x = (lon - LON_N) * math.cos(math.radians(LAT_N)) * (math.pi/180) * R
    y = (lat - LAT_N) * (math.pi/180) * R
    return x, y

def cpr_decode(hex_msg, ref_lat, ref_lon):
    try:
        bin_str = bin(int(hex_msg, 16))[2:].zfill(112)
        cpr_lat = int(bin_str[54:71], 2); cpr_lon = int(bin_str[71:88], 2); cpr_format = int(bin_str[53])
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

# --- LOAD DATA ---
df_nw = pd.read_csv(FILE_NW)
df_ne = pd.read_csv(FILE_NE)
df_nw['t'] = df_nw['ref_idx_north'] / FS
df_ne['t'] = df_ne['ref_idx_north'] / FS
t0 = min(df_nw['t'].min(), df_ne['t'].min())

# Get Planes
def get_planes(df):
    planes = []
    for i, row in df.iterrows():
        lat, lon = cpr_decode(row['hex'], LAT_N, LON_N)
        if lat and (59.5<lat<62):
            px, py = latlon_to_km(lat, lon)
            planes.append((row, px, py))
    return planes

planes_nw = get_planes(df_nw)
planes_ne = get_planes(df_ne)

# SELECT TOP EXAMPLES (Far, Mid, Near)
# Sorting by distance from North helps pick distinct planes
planes_nw.sort(key=lambda p: p[1]**2 + p[2]**2)
planes_ne.sort(key=lambda p: p[1]**2 + p[2]**2)

# Pick 3 distinct ones from each set to avoid clutter
selected_nw = [planes_nw[0], planes_nw[len(planes_nw)//2], planes_nw[-1]]
selected_ne = [planes_ne[0], planes_ne[len(planes_ne)//2], planes_ne[-1]]

# --- SETUP PLOT ---
plt.figure(figsize=(16, 12), dpi=100)
plt.style.use('seaborn-v0_8-whitegrid') 
plt.title(f"Elastic Grid Triangulation: TDOA Hyperbolas vs GPS Truth", fontsize=18, fontweight='bold', pad=20)
plt.xlabel("Distance East-West (km)", fontsize=14)
plt.ylabel("Distance North-South (km)", fontsize=14)

# Sensors
nx, ny = 0, 0
wx, wy = latlon_to_km(LAT_W, LON_W)
ex, ey = latlon_to_km(LAT_E, LON_E)

# 1. Draw Sensor Baseline (Geometry)
triangle_x = [nx, wx, ex, nx]
triangle_y = [ny, wy, ey, ny]
plt.fill(triangle_x, triangle_y, color='black', alpha=0.05, label='Sensor Array Baseline')
plt.plot(triangle_x, triangle_y, 'k--', linewidth=1, alpha=0.3)

# 2. Draw Sensors
plt.scatter(nx, ny, c='navy', s=300, marker='P', edgecolors='white', linewidth=2, label='North (Master)', zorder=10)
plt.scatter(wx, wy, c='green', s=250, marker='^', edgecolors='white', linewidth=2, label='West (Slave)', zorder=10)
plt.scatter(ex, ey, c='darkorange', s=250, marker='^', edgecolors='white', linewidth=2, label='East (Slave)', zorder=10)

# Labels
plt.text(nx, ny+2, " NORTH", fontweight='bold', fontsize=11, color='navy')
plt.text(wx, wy-3, " WEST", fontweight='bold', fontsize=11, color='green')
plt.text(ex, ey+2, " EAST", fontweight='bold', fontsize=11, color='darkorange')

# --- CALCULATE GLOBAL GRID ---
all_x = [p[1] for p in selected_nw] + [p[1] for p in selected_ne] + [wx, ex]
all_y = [p[2] for p in selected_nw] + [p[2] for p in selected_ne] + [wy, ey]
margin = 25
min_x, max_x = min(all_x)-margin, max(all_x)+margin
min_y, max_y = min(all_y)-margin, max(all_y)+margin

gx = np.linspace(min_x, max_x, 1000)
gy = np.linspace(min_y, max_y, 1000)
GX, GY = np.meshgrid(gx, gy)

Grid_N = np.sqrt((GX-nx)**2 + (GY-ny)**2)
Grid_W = np.sqrt((GX-wx)**2 + (GY-wy)**2)
Grid_E = np.sqrt((GX-ex)**2 + (GY-ey)**2)
TDOA_NW = Grid_W - Grid_N
TDOA_NE = Grid_E - Grid_N

# --- PLOT HYPERBOLAS ---

# North-West (Purple)
for i, (row, px, py) in enumerate(selected_nw):
    dt = row['t'] - t0
    corr = BIAS_W + (DRIFT_W * dt)
    dist_diff = (row['tdoa_ms'] - corr) * (C_KM_S / 1000.0)
    
    # Plot "X"
    plt.scatter(px, py, color='purple', s=100, marker='x', linewidth=2, zorder=6)
    # Plot Curve
    plt.contour(GX, GY, TDOA_NW, levels=[dist_diff], colors=['purple'], linewidths=2.5, linestyles='solid', alpha=0.8)

# North-East (Red)
for i, (row, px, py) in enumerate(selected_ne):
    dt = row['t'] - t0
    corr = BIAS_E + (DRIFT_E * dt)
    dist_diff = (row['tdoa_ms'] - corr) * (C_KM_S / 1000.0)
    
    # Plot "X"
    plt.scatter(px, py, color='crimson', s=100, marker='x', linewidth=2, zorder=6)
    # Plot Curve
    plt.contour(GX, GY, TDOA_NE, levels=[dist_diff], colors=['crimson'], linewidths=2.5, linestyles='solid', alpha=0.8)

# Fake lines for Legend
plt.plot([], [], color='purple', linewidth=2.5, label='TDOA Hyperbola (N-W Baseline)')
plt.plot([], [], color='crimson', linewidth=2.5, label='TDOA Hyperbola (N-E Baseline)')
plt.scatter([], [], color='black', marker='x', label='GPS Truth Position')

plt.legend(loc='lower right', frameon=True, fontsize=12, facecolor='white', framealpha=1)
plt.axis('equal')
plt.xlim(min_x, max_x)
plt.ylim(min_y, max_y)
plt.tight_layout()

out = f"{DATA_DIR}/master_map_final.png"
plt.savefig(out)
print(f"✅ Master Map Saved: {out}")
