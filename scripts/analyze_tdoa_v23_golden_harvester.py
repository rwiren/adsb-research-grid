import numpy as np
import pandas as pd
import sys

# --- CONFIGURATION ---
DATA_DIR = "/home/admin/ouroboros/research_data/science_run_20260201_1303"
FS = 2000000
OFFSET_W = -3689.8
OFFSET_E = -3927.2
SCAN_DURATION = 60 # Scan first minute to find overlaps

print("🚜 GOLDEN TRIANGLE HARVESTER")
print("   Searching for SIMULTANEOUS detections on North, West, and East...")

def load_chunk(filename, offset, size):
    try:
        raw = np.fromfile(filename, dtype=np.uint8, count=size*2, offset=offset*2)
        data = (raw.astype(np.float32) - 127.5) / 127.5
        mag = np.sqrt(data[0::2]**2 + data[1::2]**2)
        return mag
    except:
        return np.array([])

# Load North stream continuously
chunk_size = 2 * FS 
total_scanned = 0
found_count = 0
results = []

while total_scanned < SCAN_DURATION * FS:
    print(f"   Scanning {total_scanned/FS:.0f}s... (Found {found_count})")
    north_chunk = load_chunk(f"{DATA_DIR}/science_run_north.bin", total_scanned, chunk_size)
    if len(north_chunk) == 0: break

    # Detect Preambles (Relaxed)
    candidates = np.where((north_chunk[:-300] > 0.5) & (north_chunk[2:-298] > 0.5))[0]
    
    for i in candidates:
        if found_count >= 5: break
        # Quick Gap Check
        if north_chunk[i+1] > 0.45 or north_chunk[i+3] > 0.45: continue
        
        # DF17 Type Check (Bits 1-5)
        header_s = north_chunk[i+16 : i+16+10] 
        bits = ""
        for b in range(0, 10, 2):
            bits += "1" if header_s[b] > header_s[b+1] else "0"
        try:
            if int(bits, 2) != 17: continue 
        except: continue
        
        # Found a DF17! Check West AND East
        global_idx = total_scanned + i
        fingerprint = north_chunk[i : i+1000] # 0.5ms fingerprint
        
        # 1. Check West
        off_w = int(abs(OFFSET_W/1000) * FS)
        start_w = max(0, (global_idx + off_w) - 3000)
        chunk_w = load_chunk(f"{DATA_DIR}/science_run_west.bin", start_w, 6000)
        
        if len(chunk_w) == 0: continue
        corr_w = np.correlate(chunk_w, fingerprint, mode='valid')
        if len(corr_w) == 0 or np.max(corr_w) < 12.0: continue 
        
        # 2. Check East (Only if West found it)
        off_e = int(abs(OFFSET_E/1000) * FS)
        start_e = max(0, (global_idx + off_e) - 3000)
        chunk_e = load_chunk(f"{DATA_DIR}/science_run_east.bin", start_e, 6000)
        
        if len(chunk_e) == 0: continue
        corr_e = np.correlate(chunk_e, fingerprint, mode='valid')
        if len(corr_e) == 0 or np.max(corr_e) < 12.0: continue 
        
        # BINGO! TRIANGULATION!
        # Decode Hex
        full_bits = ""
        sl = north_chunk[i+16 : i+16+224]
        for b in range(0, len(sl), 2):
            full_bits += "1" if sl[b] > sl[b+1] else "0"
        hex_msg = f"{int(full_bits, 2):X}".zfill(28)
        
        # Calculate TDOAs
        best_w = np.argmax(corr_w)
        tdoa_w = ((start_w + best_w - global_idx) / FS) * 1000
        
        best_e = np.argmax(corr_e)
        tdoa_e = ((start_e + best_e - global_idx) / FS) * 1000
        
        results.append({
            "ref_idx_north": global_idx,
            "hex": hex_msg,
            "tdoa_w": tdoa_w,
            "tdoa_e": tdoa_e
        })
        print(f"   🌟 MATCH #{len(results)}: {hex_msg}")
        print(f"      TDOA West: {tdoa_w:.2f}ms | East: {tdoa_e:.2f}ms")
        found_count += 1
    
    total_scanned += chunk_size

# Save
df = pd.DataFrame(results)
df.to_csv(f"{DATA_DIR}/golden_dataset.csv", index=False)
print(f"💾 Saved {len(results)} Golden Packets to {DATA_DIR}/golden_dataset.csv")
