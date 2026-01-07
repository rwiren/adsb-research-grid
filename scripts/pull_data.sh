#!/bin/bash
# Securely sync data from Sensor Node to Analysis Station
# USAGE: ./pull_data.sh

# --- Configuration ---
PI_USER="pi"
PI_HOST="192.168.1.30"
REMOTE_DIR="~/adsb_data/"
LOCAL_DIR="./research_data/raw_logs/"

# Create local dir if missing
mkdir -p "$LOCAL_DIR"

echo "[*] Syncing logs from ${PI_HOST}..."
echo "[*] Mode: COPY (Files remain on Pi)"

# RSYNC with JSON support
rsync -avz --progress \
    -e "ssh" \
    --include='raw_gnss_*.log' \
    --include='raw_gnss_*.json' \
    --include='raw_adsb_*.bin' \
    --exclude='*' \
    "${PI_USER}@${PI_HOST}:${REMOTE_DIR}" "$LOCAL_DIR"

echo "[*] Sync Complete. Data is in $LOCAL_DIR"
