#!/bin/bash
# ==============================================================================
# PROJECT: ADS-B Spoofing Data Collection (Academic Research)
# FILE: infra/ansible/roles/gnss-receiver/files/gps_hardware_init.sh
# DEPLOY TARGET: /usr/local/bin/gps_hardware_init.sh
# VERSION: 0.4.0
# AUTHOR: Research Ops Team
#
# DESCRIPTION:
#   Configures Physical Layer (PHY) baud rates.
#   - Logic Branch A: Legacy USB (SiRF IV) -> Lock 4800.
#   - Logic Branch B: High-Precision UART (u-blox) -> Escalate to 230400.
# ==============================================================================

# 1. ARGS PARSING
DEVICE="${1:-/dev/ttyAMA0}"
TARGET_BAUD="${2:-230400}"

# 2. LOGGING
log_msg() {
    echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] [GPS-PHY] $1"
}

log_msg "Starting GNSS PHY Init (v0.4.0) on $DEVICE (Target: $TARGET_BAUD)"

if [ ! -e "$DEVICE" ]; then
    log_msg "CRITICAL: Device $DEVICE not found."
    exit 1
fi

# 3. HETEROGENEOUS LOGIC
if [ "$TARGET_BAUD" -le 38400 ]; then
    # --- BRANCH A: STANDARD SPEED (West) ---
    log_msg "Standard Baud Rate ($TARGET_BAUD) requested. Locking port..."
    stty -F "$DEVICE" "$TARGET_BAUD" raw -echo -echoe -echok
    exit 0
else
    # --- BRANCH B: HIGH SPEED (North/RTK) ---
    # u-blox often requires a flush at 9600 before accepting 230400.
    log_msg "High-Speed Target ($TARGET_BAUD). Initiating escalation sequence..."
    
    stty -F "$DEVICE" 9600 raw -echo -echoe -echok
    sleep 0.5
    stty -F "$DEVICE" "$TARGET_BAUD" raw -echo -echoe -echok
    
    # Verification
    CURRENT=$(stty -F "$DEVICE" speed)
    if [ "$CURRENT" == "$TARGET_BAUD" ]; then
        log_msg "SUCCESS: High-speed lock achieved."
        exit 0
    else
        log_msg "FAILURE: Rate mismatch. Got: $CURRENT"
        exit 1
    fi
fi
