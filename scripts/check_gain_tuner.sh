#!/bin/bash
# Quick check of gain tuner status across all sensors
echo "=== Gain Tuner Status ($(date)) ==="
echo ""
for sensor in "pi@192.168.195.110:NORTH" "pi@192.168.195.120:WEST" "pi@192.168.195.130:EAST"; do
  host="${sensor%%:*}"
  name="${sensor##*:}"
  echo "--- $name ($host) ---"
  ssh $host "cat /var/lib/gain_tuner/state.json 2>/dev/null | python3 -c \"
import json,sys
s=json.load(sys.stdin)
w=s.get('window',[])
print(f'  Samples: {len(w)}/8')
if w:
    print(f'  Last signal: {w[-1].get(\"signal\")} dB')
    print(f'  Last strong: {w[-1].get(\"strong_signals\")}')
print(f'  Hysteresis: {s.get(\"hysteresis_direction\")} ({s.get(\"hysteresis_count\")}/2)')
\" 2>/dev/null || echo '  No state yet (waiting for first cron run)'"
  echo ""
done
