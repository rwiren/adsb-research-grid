import numpy as np
import pandas as pd
import sys

# --- CONFIGURATION ---
DATA_DIR = "/home/admin/ouroboros/research_data/science_run_20260201_1303"
FS = 2000000
# Coarse Offset for EAST (from Correlation Check)
COARSE_OFFSET = -3926.9 
TARGET_COUNT = 30 
SCAN_DURATION_SEC = 60

print("🚜 EAST HARVESTER (Calibration Generator)")
print(f"   Target: science_run_east.bin | Offset: {COARSE_OFFSET}ms")

def load_chunk(filename, offset, size):
    try:
        raw = np.fromfile(filename, dtype=np.uint8, count=size*2, offset=offset*2)
        data = (raw.astype(np.float32) - 127.5) / 127.5
        mag = np.sqrt(data[0::2]**2 + data[1::2]**2)
        return mag
    except:
        return np.array([])

results = []
chunk_size = 2 * FS 
total_scanned = 0
filename_n = f"{DATA_DIR}/science_run_north.bin"
filename_e = f"{DATA_DIR}/science_run_east.bin"

while len(results) < TARGET_COUNT and total_scanned < SCAN_DURATION_SEC * FS:
    print(f"   Scanning {total_scanned/FS:.1f}s... Found {len(results)}")
    
    mag = load_chunk(filename_n, total_scanned, chunk_size)
    if len(mag) == 0: break
    
    # 1. PREAMBLE SCAN (Relaxed)
    candidates = np.where((mag[:-300] > 0.5) & (mag[2:-298] > 0.5))[0]
    
    for i in candidates:
        if len(results) >= TARGET_COUNT: break
        if mag[i+1] > 0.45 or mag[i+3] > 0.45: continue 
        
        # 2. CHECK DF17
        header_samples = mag[i+16 : i+16+16]
        header_bits = ""
        for b in range(0, 10, 2):
            header_bits += "1" if header_samples[b] > header_samples[b+1] else "0"
        try:
            if int(header_bits, 2) != 17: continue
        except: continue
        
        # 3. EXTRACT HEX
        full_bits = ""
        sl = mag[i+16 : i+16+224]
        for b in range(0, len(sl), 2):
            full_bits += "1" if sl[b] > sl[b+1] else "0"
        hex_msg = f"{int(full_bits, 2):X}".zfill(28)

        # 4. CROSS CORRELATE WITH EAST
        global_idx = total_scanned + i
        offset_samples = int(abs(COARSE_OFFSET/1000) * FS)
        expected_east_idx = global_idx + offset_samples
        
        start_e = max(0, expected_east_idx - 5000)
        east_chunk = load_chunk(filename_e, start_e, 10000)
        fingerprint = mag[i : i+2000]
        
        if len(east_chunk) == 0: continue
        
        corr = np.correlate(east_chunk, fingerprint, mode='valid')
        if len(corr) == 0: continue
        
        score = np.max(corr)
        if score > 15.0: # Strong Lock
            best_idx = np.argmax(corr)
            actual_east_idx = start_e + best_idx
            tdoa_ms = ((actual_east_idx - global_idx) / FS) * 1000
            
            results.append({
                "ref_idx_north": global_idx,
                "tdoa_ms": tdoa_ms,
                "hex": hex_msg,
                "score": score
            })
            print(f"     ✅ #{len(results)} {hex_msg} | TDOA: {tdoa_ms:.2f}ms")

    total_scanned += chunk_size

# SAVE
df = pd.DataFrame(results)
csv_file = f"{DATA_DIR}/calibration_dataset_east.csv"
df.to_csv(csv_file, index=False)
print(f"\n💾 Saved East Calibration Data: {csv_file}")
