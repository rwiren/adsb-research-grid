import os
import csv
import datetime
import socket

# Configuration
NODE_NAME = socket.gethostname()
LOG_FILE = "/var/lib/adsb_storage/storage_history.csv"
DATA_DIR = "/var/lib/adsb_storage"

def get_disk_usage():
    try:
        stat = os.statvfs(DATA_DIR)
        return (stat.f_blocks - stat.f_bfree) * stat.f_frsize // 1024
    except:
        return 0

def get_recording_size():
    total_size = 0
    for root, dirs, files in os.walk(DATA_DIR):
        for f in files:
            if f.endswith('.bin') or f.endswith('.json'):
                try:
                    total_size += os.path.getsize(os.path.join(root, f))
                except:
                    pass
    return total_size // 1024

def main():
    timestamp = datetime.datetime.now().astimezone().isoformat()
    disk_used = get_disk_usage()
    rec_size = get_recording_size()
    
    # Ensure file exists and has correct header
    file_exists = os.path.isfile(LOG_FILE)
    
    # Check if we need to rewrite the file (if header is wrong)
    if file_exists:
        with open(LOG_FILE, 'r') as f:
            header = f.readline().strip()
        if "node_name" not in header:
            file_exists = False # Force overwrite if header is old
            
    mode = 'a' if file_exists else 'w'
    
    with open(LOG_FILE, mode, newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "node_name", "disk_used_kb", "recording_size_kb"])
        writer.writerow([timestamp, NODE_NAME, disk_used, rec_size])
    
    print(f"✅ Logged: {timestamp} | {NODE_NAME}")

if __name__ == "__main__":
    main()
