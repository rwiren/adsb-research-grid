#!/bin/bash
# ------------------------------------------------------------------
# Filename: ublox_init.sh
# Description: Force U-blox GPS to switch from 9600 -> 230400 baud.
# ------------------------------------------------------------------

DEVICE="/dev/ttyACM0"
TARGET_SPEED="230400"
SAFE_SPEED="9600"

echo "[GNSS-INIT] Starting initialization..."

# 1. Kill any process holding the port so we can configure it
fuser -k -v $DEVICE || true

# 2. Set Host to safe speed (9600) to talk to the chip
stty -F $DEVICE $SAFE_SPEED raw
sleep 1

# 3. Force the switch command. We run it twice to be sure.
#    -f: force low-level access
#    -s: target speed
if command -v gpsctl &> /dev/null; then
    echo "[GNSS-INIT] Commanding chip to switch to $TARGET_SPEED..."
    gpsctl -f -s $TARGET_SPEED $DEVICE
    sleep 1
    gpsctl -f -s $TARGET_SPEED $DEVICE
else
    echo "[ERROR] gpsctl missing."
    exit 1
fi

# 4. Wait for chip restart
sleep 2

# 5. Set Host to Target Speed
echo "[GNSS-INIT] Updating host serial port to $TARGET_SPEED..."
stty -F $DEVICE $TARGET_SPEED raw

# 6. Validate (Optional check)
CURRENT_SPEED=$(stty -F $DEVICE speed)
echo "[GNSS-INIT] Final Host Speed: $CURRENT_SPEED"
