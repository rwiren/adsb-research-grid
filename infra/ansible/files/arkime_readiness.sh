#!/bin/bash
# ==============================================================================
# Script: arkime_readiness.sh
# Description: Checks if the node has enough resources for OpenSearch + Arkime.
# Author: Gemini (Assisted)
# Date: 2026-01-13
# Version: v1.0.0
# ==============================================================================

# --- Thresholds (Home Lab / Low Traffic) ---
MIN_RAM_GB=4
REC_RAM_GB=8
MIN_CORES=2
MIN_DISK_FREE_GB=20

# --- Colors ---
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "\n🔍 \033[1mArkime + OpenSearch Readiness Check\033[0m"
echo "========================================="

# 1. CPU Check
CPU_CORES=$(nproc)
echo -n "CPU Cores:  "
if [ "$CPU_CORES" -ge "$MIN_CORES" ]; then
    echo -e "${GREEN}[PASS] ${CPU_CORES} Cores available${NC}"
else
    echo -e "${RED}[FAIL] Only ${CPU_CORES} Core(s). Arkime needs massive multithreading.${NC}"
fi

# 2. RAM Check
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_RAM_GB=$(echo "$TOTAL_RAM_KB / 1024 / 1024" | bc)
AVAILABLE_RAM_KB=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
AVAILABLE_RAM_GB=$(echo "$AVAILABLE_RAM_KB / 1024 / 1024" | bc)

echo -n "Total RAM:  "
if [ "$TOTAL_RAM_GB" -ge "$REC_RAM_GB" ]; then
    echo -e "${GREEN}[PASS] ${TOTAL_RAM_GB} GB (Excellent)${NC}"
elif [ "$TOTAL_RAM_GB" -ge "$MIN_RAM_GB" ]; then
    echo -e "${YELLOW}[WARN] ${TOTAL_RAM_GB} GB (Tight). OpenSearch might struggle.${NC}"
else
    echo -e "${RED}[FAIL] ${TOTAL_RAM_GB} GB. OpenSearch requires Java Heap which needs more RAM.${NC}"
fi

echo -n "Free RAM:   "
echo -e "${NC}${AVAILABLE_RAM_GB} GB currently available${NC}"

# 3. Disk Space Check (Checking /opt where Docker usually lives)
DISK_FREE=$(df -BG /opt | awk 'NR==2 {print $4}' | sed 's/G//')
echo -n "Disk Free:  "
if [ "$DISK_FREE" -ge "$MIN_DISK_FREE_GB" ]; then
    echo -e "${GREEN}[PASS] ${DISK_FREE} GB available in /opt${NC}"
else
    echo -e "${RED}[FAIL] Only ${DISK_FREE} GB free. PCAP storage fills up FAST.${NC}"
fi

# 4. Architecture Check
ARCH=$(uname -m)
echo -n "Arch:       "
if [[ "$ARCH" == "x86_64" ]] || [[ "$ARCH" == "aarch64" ]]; then
    echo -e "${GREEN}[PASS] ${ARCH} is supported${NC}"
else
    echo -e "${RED}[FAIL] ${ARCH} might have Docker compatibility issues${NC}"
fi

echo "========================================="
echo -e "📝 \033[1mRecommendation:\033[0m"

if [ "$TOTAL_RAM_GB" -lt 4 ]; then
    echo "❌ Your hardware is too weak. Do NOT install Arkime/OpenSearch."
    echo "   Stick to InfluxDB + Telegraf."
elif [ "$TOTAL_RAM_GB" -lt 8 ]; then
    echo "⚠️  You can run it, but you must tune Java Heap settings carefully."
    echo "   Expect high memory pressure."
else
    echo "✅ Your hardware is ready for a hybrid InfluxDB + Arkime setup!"
fi
echo ""
