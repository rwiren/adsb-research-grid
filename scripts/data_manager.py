#!/usr/bin/env python3
# Path: scripts/data_manager.py
# Revision: 2.0
# Description: Verifies integrity of raw ADSB/GNSS files and compresses them to save space.
#              This should be run via cron on the sensor nodes.

import os
import glob
import gzip
import json
import shutil
import logging
import datetime

# --- Configuration ---
DATA_DIR = "/var/lib/adsb_storage"
LOG_FILE = "/var/log/data_manager.log"
# Only compress files older than X minutes to avoid touching active recordings
AGE_THRESHOLD_MINUTES = 2 

# Setup Logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def is_file_ready(filepath):
    """Check if file is old enough to be compressed (not currently being written)."""
    try:
        mtime = os.path.getmtime(filepath)
        if (datetime.datetime.now().timestamp() - mtime) > (AGE_THRESHOLD_MINUTES * 60):
            return True
    except OSError:
        return False
    return False

def verify_gnss_integrity(filepath):
    """
    Reads the last few lines of a GNSS file to ensure it ends cleanly.
    Returns: (bool is_valid, str error_message)
    """
    try:
        if os.path.getsize(filepath) == 0:
            return False, "Empty file"

        # Read last 1KB to find the last line
        with open(filepath, 'rb') as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            seek_offset = min(1024, file_size)
            f.seek(-seek_offset, os.SEEK_END)
            lines = f.readlines()
            
            # Get the last non-empty line
            if not lines:
                return False, "No data lines found"
            
            last_line = lines[-1].decode('utf-8', errors='ignore').strip()
            
            # Simple check: Does it look like a JSON object closing?
            if not last_line:
                return False, "Last line is empty"
                
            try:
                # Try to parse the last line as JSON
                json.loads(last_line)
                return True, "Valid JSON tail"
            except json.JSONDecodeError:
                # It might be a partial write if disk was full
                return False, f"Corrupt JSON at end: {last_line[:50]}..."

    except Exception as e:
        return False, str(e)

def verify_adsb_integrity(filepath):
    """
    Verifies ADSB binary files. 
    Binary is harder to validate without a decoder, so we check for non-zero size.
    """
    try:
        size = os.path.getsize(filepath)
        if size == 0:
            return False, "Empty file"
        return True, "Size OK"
    except Exception as e:
        return False, str(e)

def compress_file(filepath):
    """Compresses a file using GZIP and removes the original."""
    gz_path = filepath + ".gz"
    
    try:
        with open(filepath, 'rb') as f_in:
            with gzip.open(gz_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Verify gzip was created and has content
        if os.path.exists(gz_path) and os.path.getsize(gz_path) > 0:
            os.remove(filepath)
            logging.info(f"COMPRESSED: {filepath} -> {gz_path}")
            return True
        else:
            logging.error(f"FAILED: Gzip creation failed for {filepath}")
            return False
            
    except Exception as e:
        logging.error(f"ERROR: Compressing {filepath}: {e}")
        # Clean up partial gzip if it exists
        if os.path.exists(gz_path):
            os.remove(gz_path)
        return False

def main():
    logging.info("--- Starting Data Management Run ---")
    
    # 1. Process GNSS Files (JSON/LOG)
    gnss_files = glob.glob(os.path.join(DATA_DIR, "raw_gnss_*"))
    for f in gnss_files:
        if f.endswith(".gz") or not is_file_ready(f):
            continue
            
        valid, msg = verify_gnss_integrity(f)
        if valid:
            compress_file(f)
        else:
            logging.warning(f"CORRUPT GNSS: {f} - {msg}. Skipping compression.")

    # 2. Process ADSB Files (BIN)
    adsb_files = glob.glob(os.path.join(DATA_DIR, "raw_adsb_*.bin"))
    for f in adsb_files:
        if f.endswith(".gz") or not is_file_ready(f):
            continue
            
        valid, msg = verify_adsb_integrity(f)
        if valid:
            compress_file(f)
        else:
            logging.warning(f"CORRUPT ADSB: {f} - {msg}. Skipping compression.")

if __name__ == "__main__":
    main()
