#!/bin/bash
# ==============================================================================
# SCRIPT: tower_collector.sh
# DESCRIPTION: Automated Scientific Data Retrieval (Tower -> Sensors)
# VERSION: v1.1.0 (Fixed SSH User: admin -> pi)
# ==============================================================================

# --- CONFIGURATION ---
DATE_STR=$(date +%Y-%m-%d)
BASE_DIR="/opt/adsb-grid/research_data"
TARGET_DIR="${BASE_DIR}/${DATE_STR}"

# Define Nodes: "Name|IP"
NODES=(
    "sensor-north|192.168.192.130"
    "sensor-west|192.168.192.110"
    "sensor-east|192.168.192.120"
)

# --- EXECUTION ---
echo "[$(date)] 📡 Starting Grid Data Collection..."
mkdir -p "$TARGET_DIR"

for node in "${NODES[@]}"; do
    IFS="|" read -r NAME IP <<< "$node"
    NODE_DIR="${TARGET_DIR}/${NAME}"
    mkdir -p "$NODE_DIR/json"
    
    echo "  ➡️  Syncing: $NAME ($IP)"

    # 1. FETCH CSV LOGS (Incremental Sync)
    # UPDATED: Connecting as user 'pi' (not admin)
    rsync -avz -e "ssh -o StrictHostKeyChecking=no" \
        --include="*.csv" \
        --include="*.csv.gz" \
        pi@$IP:/var/lib/adsb_storage/csv_data/ \
        "$NODE_DIR/" > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        echo "     ✅ CSV Data Synced"
    else
        echo "     ❌ CSV Sync Failed (Check connectivity)"
    fi

    # 2. FETCH SNAPSHOTS (JSON)
    TIMESTAMP=$(date +%H%M%S)
    scp -o StrictHostKeyChecking=no pi@$IP:/run/readsb/aircraft.json "$NODE_DIR/json/aircraft_${TIMESTAMP}.json" > /dev/null 2>&1
    scp -o StrictHostKeyChecking=no pi@$IP:/run/readsb/stats.json "$NODE_DIR/json/stats_${TIMESTAMP}.json" > /dev/null 2>&1

    # 3. FETCH METRICS
    scp -o StrictHostKeyChecking=no pi@$IP:/var/lib/adsb_storage/storage_history.csv "$NODE_DIR/storage_history.csv" > /dev/null 2>&1

done

echo "[$(date)] ✅ Collection Complete."
# Ensure 'admin' owns the files so you can read them
chown -R admin:admin "$BASE_DIR"
