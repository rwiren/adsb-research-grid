#!/bin/bash
# Version: 8.0.0 (The Proven Manual Fix)
# Description: Configures u-blox F9P via TCP (since socat is running).

# Wait for socat to be ready
sleep 15

echo "Starting GNSS Configuration..."

# 1. Silence NMEA (Critical)
/usr/bin/ubxtool -P 27.31 -d NMEA -f tcp://127.0.0.1:2000

# 2. Enable UBX Binary
/usr/bin/ubxtool -P 27.31 -e BINARY -f tcp://127.0.0.1:2000

# 3. Enable Nav Rate (1Hz)
/usr/bin/ubxtool -P 27.31 -z CFG-RATE -f tcp://127.0.0.1:2000 --set 1000

# 4. Save to Flash
/usr/bin/ubxtool -P 27.31 -p SAVE -f tcp://127.0.0.1:2000

echo "Configuration Saved."
