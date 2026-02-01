import numpy as np
import pandas as pd
import sys

# --- CONFIGURATION ---
DATA_DIR = "/home/admin/ouroboros/research_data/science_run_20260201_1303"
FS = 2000000
COARSE_OFFSET_WEST = -3691.9
TARGET_COUNT = 30 
SCAN_DURATION_SEC = 60

print("🚜 RELAXED HARVESTER (V14)")
print(f"   Logic: Valid Preamble + DF17 Header. NO GEOMETRY CHECKS.")

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

while len(results) < TARGET_COUNT and total_scanned < SCAN_DURATION_SEC * FS:
    print(f"   Scanning {total_scanned/FS:.1f}s... Found {len(results)}")
    
    mag = load_chunk(filename_n, total_scanned, chunk_size)
    if len(mag) == 0: break
    
    # 1. PREAMBLE SCAN (Vectorized)
    # Look for High (i, i+2) and Low (i+1, i+3)
    # Thresholds: High > 0.5, Low < 0.45 (Relaxed)
    candidates = np.where((mag[:-300] > 0.5) & (mag[2:-298] > 0.5))[0]
    
    for i in candidates:
        if len(results) >= TARGET_COUNT: break
        if mag[i+1] > 0.45 or mag[i+3] > 0.45: continue # Gap check
        
        # 2. HEADER CHECK (Bits 1-5)
        # Payload starts at i+16. 
        # Extract first 5 bits to check DF type
        header_samples = mag[i+16 : i+16+16] # 8 bits
        header_bits = ""
        for b in range(0, 10, 2): # Just 5 bits needed
            header_bits += "1" if header_samples[b] > header_samples[b+1] else "0"
            
        try:
            type_code = int(header_bits, 2)
        except:
            continue

        if type_code != 17: continue # Only accept DF17 (Extended Squitter)
        
        # 3. EXTRACT HEX
        full_bits = ""
        sl = mag[i+16 : i+16+224] # 112 bits
        for b in range(0, len(sl), 2):
            full_bits += "1" if sl[b] > sl[b+1] else "0"
        hex_msg = f"{int(full_bits, 2):X}".zfill(28)

        # 4. CROSS CORRELATION (Get the timing)
        global_idx = total_scanned + i
        offset_samples = int(abs(COARSE_OFFSET_WEST/1000) * FS)
        expected_west_idx = global_idx + offset_samples
        
        start_w = max(0, expected_west_idx - 5000)
        west_chunk = load_chunk(f"{DATA_DIR}/science_run_west.bin", start_w, 10000)
        fingerprint = mag[i : i+2000]
        
        if len(west_chunk) == 0: continue
        
        corr = np.correlate(west_chunk, fingerprint, mode='valid')
        if len(corr) == 0: continue
        
        score = np.max(corr)
        if score > 15.0: # Only keep strong TDOA locks
            best_idx = np.argmax(corr)
            actual_west_idx = start_w + best_idx
            tdoa_ms = ((actual_west_idx - global_idx) / FS) * 1000
            
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
csv_file = f"{DATA_DIR}/calibration_dataset_final.csv"
df.to_csv(csv_file, index=False)
print(f"\n💾 Saved {len(results)} targets to: {csv_file}")
