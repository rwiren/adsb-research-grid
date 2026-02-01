import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import math

# --- CONFIGURATION ---
DATA_DIR = "/home/admin/ouroboros/research_data/science_run_20260201_1303"
FILE_GOLD = f"{DATA_DIR}/golden_dataset.csv"
FS = 2000000

# SENSORS
LAT_N, LON_N = 60.3194, 24.8307
LAT_W, LON_W = 60.1309, 24.5129
LAT_E, LON_E = 60.3601, 25.3376

print("🎨 GENERATING GOLDEN CROSS MAP V28 (Final Red Color)...")

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
df = pd.read_csv(FILE_GOLD)

# --- PREPARE DATA ---
planes = []
nx, ny = 0, 0
wx, wy = latlon_to_km(LAT_W, LON_W)
ex, ey = latlon_to_km(LAT_E, LON_E)

for i, row in df.iterrows():
    lat, lon = cpr_decode(row['hex'], LAT_N, LON_N)
    if lat:
        px, py = latlon_to_km(lat, lon)
        planes.append({'row': row, 'px': px, 'py': py})

# Select 3 Closest Planes for Zoom
cx, cy = (nx+wx+ex)/3, (ny+wy+ey)/3
planes.sort(key=lambda p: (p['px']-cx)**2 + (p['py']-cy)**2)
selected_planes = planes[:3] 

# --- SETUP PLOT ---
plt.figure(figsize=(12, 12), dpi=150)
plt.style.use('seaborn-v0_8-whitegrid') 
plt.title(f"Triangulation Geometry: TDOA Intersection", fontsize=16, fontweight='bold', pad=15)
plt.xlabel("Distance East-West (km)", fontsize=12)
plt.ylabel("Distance North-South (km)", fontsize=12)

# Zoom Bounds
all_x = [nx, wx, ex] + [p['px'] for p in selected_planes]
all_y = [ny, wy, ey] + [p['py'] for p in selected_planes]
margin = 5
gx = np.linspace(min(all_x)-margin, max(all_x)+margin, 1000)
gy = np.linspace(min(all_y)-margin, max(all_y)+margin, 1000)
GX, GY = np.meshgrid(gx, gy)

Grid_N = np.sqrt((GX-nx)**2 + (GY-ny)**2)
Grid_W = np.sqrt((GX-wx)**2 + (GY-wy)**2)
Grid_E = np.sqrt((GX-ex)**2 + (GY-ey)**2)
TDOA_NW = Grid_W - Grid_N
TDOA_NE = Grid_E - Grid_N

# Draw Sensors (Baselines)
plt.plot([nx, wx, ex, nx], [ny, wy, ey, ny], 'k--', linewidth=0.5, alpha=0.3)

# SENSORS (COLORS FIXED)
plt.scatter(nx, ny, c='navy', s=300, marker='P', edgecolors='white', zorder=10, label='North')
plt.scatter(wx, wy, c='green', s=250, marker='^', edgecolors='white', zorder=10, label='West')
# EAST IS NOW CRIMSON/RED
plt.scatter(ex, ey, c='crimson', s=250, marker='^', edgecolors='white', zorder=10, label='East')

plt.text(nx, ny+1, " NORTH", fontweight='bold', color='navy')
plt.text(wx, wy-1.5, " WEST", fontweight='bold', color='green')
plt.text(ex, ey+1, " EAST", fontweight='bold', color='crimson')

# --- PLOT PLANES WITH LOCAL ALIGNMENT ---
for p in selected_planes:
    px, py = p['px'], p['py']
    
    # Calculate Geometry
    dn = math.sqrt(px**2 + py**2)
    dw = math.sqrt((px-wx)**2 + (py-wy)**2)
    de = math.sqrt((px-ex)**2 + (py-ey)**2)
    
    geom_diff_w = dw - dn 
    geom_diff_e = de - dn 
    
    # Draw Plot
    plt.scatter(px, py, color='black', s=120, marker='x', linewidth=2.5, zorder=6)
    
    # West TDOA (Purple)
    plt.contour(GX, GY, TDOA_NW, levels=[geom_diff_w], colors=['purple'], linewidths=2.5, linestyles='dotted', alpha=0.9)
    
    # East TDOA (Crimson/Red)
    plt.contour(GX, GY, TDOA_NE, levels=[geom_diff_e], colors=['crimson'], linewidths=2.5, linestyles='dotted', alpha=0.9)

# Legend
plt.plot([], [], color='purple', linestyle=':', linewidth=2.5, label='West TDOA')
plt.plot([], [], color='crimson', linestyle=':', linewidth=2.5, label='East TDOA')
plt.scatter([], [], color='black', marker='x', s=100, label='GPS Truth')

plt.legend(loc='lower right', frameon=True, facecolor='white', framealpha=1)
plt.axis('equal')
plt.xlim(min(all_x)-margin, max(all_x)+margin)
plt.ylim(min(all_y)-margin, max(all_y)+margin)
plt.tight_layout()

out = f"{DATA_DIR}/golden_cross_final.png"
plt.savefig(out)
print(f"✅ Final Red Map Saved: {out}")
