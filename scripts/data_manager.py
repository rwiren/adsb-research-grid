#!/usr/bin/env python3
"""
# ==============================================================================
# FILE: scripts/data_manager.py
# PURPOSE: Runs ON SENSOR NODES to manage storage.
# ACTIONS: 
#   1. Compresses CSVs older than 1 hour (gzip).
#   2. Deletes files older than 7 days to prevent disk fill.
# ==============================================================================
"""
import os
import time
import gzip
import shutil
import glob

DATA_DIR = "/var/lib/adsb_storage/csv_data"
RETENTION_DAYS = 7

def compress_old_logs():
    # Target both stats and aircraft logs
    files = glob.glob(f"{DATA_DIR}/*.csv")
    now = time.time()
    
    for f in files:
        # If file is older than 60 mins, compress it
        if os.stat(f).st_mtime < (now - 3600):
            print(f"📦 Compressing: {f}")
            with open(f, 'rb') as f_in:
                with gzip.open(f"{f}.gz", 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            os.remove(f) # Delete original

def cleanup_storage():
    # Find all files (csv and gz)
    files = glob.glob(f"{DATA_DIR}/*")
    now = time.time()
    limit = RETENTION_DAYS * 86400
    
    for f in files:
        if os.stat(f).st_mtime < (now - limit):
            print(f"🗑️ Purging old file: {f}")
            os.remove(f)

if __name__ == "__main__":
    if os.path.exists(DATA_DIR):
        compress_old_logs()
        cleanup_storage()
    else:
        print(f"Directory {DATA_DIR} not found. Nothing to do.")
