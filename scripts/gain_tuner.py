#!/usr/bin/env python3
# ==============================================================================
# File: /opt/adsb-sensor/gain_tuner.py
# Version: 1.0.0
# Date: 2026-05-03
# Maintainer: Richard Wirén
# ==============================================================================
# Description:
#   Adaptive SDR gain tuner for ADS-B sensors. Uses a 2-hour rolling window
#   (8 × 15-min samples) to make conservative gain adjustments. Designed to
#   replace readsb's built-in autogain which reacts to instantaneous conditions.
#
#   Decision logic:
#     - strong_signals > threshold → gain too high, step down
#     - mean signal < floor → gain too low, step up
#     - SNR < minimum → noise floor rising, step down
#     - Otherwise → hold
#
#   Safety:
#     - Hysteresis: requires 2 consecutive 2-hour windows recommending same
#       direction before acting (minimum 2h15m to change)
#     - Single step per change (one RTL-SDR gain increment)
#     - Logs all decisions to /var/log/gain_tuner.log
#     - Dry-run mode for validation
#
#   Deployment:
#     Runs via cron every 15 minutes on each sensor node.
#     Crontab: */15 * * * * /usr/bin/python3 /opt/adsb-sensor/gain_tuner.py
#
#   Gain change mechanism:
#     Updates READSB_GAIN in docker-compose.yml and recreates the container.
#     Container restart takes ~5 seconds; data gap is minimal.
# ==============================================================================

import json
import logging
import os
import re
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

# ==============================================================================
# Configuration
# ==============================================================================

# RTL-SDR available gain values (dB)
GAIN_TABLE = [
    0.0, 0.9, 1.4, 2.7, 3.7, 7.7, 8.7, 12.5, 14.4, 15.7,
    16.6, 19.7, 20.7, 22.9, 25.4, 28.0, 29.7, 32.8, 33.8,
    36.4, 37.2, 38.6, 40.2, 42.1, 43.4, 43.9, 44.5, 48.0, 49.6,
]

# Stats source (readsb JSON)
STATS_URL = "http://localhost:8080/data/stats.json"

# Rolling window: 8 samples × 15 min = 2 hours
WINDOW_SIZE = 8

# State file (persists rolling window and hysteresis counter between runs)
STATE_FILE = Path("/var/lib/gain_tuner/state.json")

# Docker compose file location
COMPOSE_FILE = Path("/opt/adsb-grid/docker-compose.yml")

# Decision thresholds
STRONG_SIGNAL_THRESHOLD = 200     # strong_signals per 15min → too many = step down
SIGNAL_FLOOR_DB = -30.0          # mean signal below this → step up
MIN_SNR_DB = 12.0                # SNR below this → step down (noise too high)
PEAK_CEILING_DB = -1.0           # peak signal above this → near ADC saturation

# Hysteresis: require N consecutive same-direction recommendations
HYSTERESIS_COUNT = 2

# Minimum gain floor per sensor (prevents runaway reduction)
# Determined by hardware sensitivity and proximity to flight paths.
# Key in GAIN_FLOOR is matched against hostname.
GAIN_FLOOR = {
    "sensor-north": 12.5,   # FlightAware Pro+, near Helsinki-Vantaa
    "sensor-east": 19.7,    # FlightAware Pro+, suburban Sibbo
    "sensor-west": 40.2,    # RTL-SDR unfiltered, needs high gain
}

# Logging
LOG_FILE = "/var/log/gain_tuner.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("gain_tuner")


# ==============================================================================
# Functions
# ==============================================================================

def fetch_stats():
    """Fetch last15min stats from readsb."""
    import urllib.request
    try:
        with urllib.request.urlopen(STATS_URL, timeout=5) as resp:
            data = json.loads(resp.read())
        last15 = data.get("last15min", {})
        local = last15.get("local", {})
        return {
            "gain_db": data.get("gain_db"),
            "signal": local.get("signal"),
            "noise": local.get("noise"),
            "peak_signal": local.get("peak_signal"),
            "strong_signals": local.get("strong_signals", 0),
            "messages": last15.get("messages", 0),
            "timestamp": time.time(),
        }
    except Exception as e:
        log.error(f"Failed to fetch stats: {e}")
        return None


def load_state():
    """Load persistent state (rolling window + hysteresis)."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"window": [], "hysteresis_direction": None, "hysteresis_count": 0}


def save_state(state):
    """Save persistent state."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_current_gain():
    """Read current gain from docker-compose.yml."""
    text = COMPOSE_FILE.read_text()
    match = re.search(r"READSB_GAIN=([0-9.]+)", text)
    if match:
        return float(match.group(1))
    return None


def step_gain(current, direction):
    """Get next gain value in the given direction (+1 = up, -1 = down)."""
    try:
        idx = GAIN_TABLE.index(current)
    except ValueError:
        # Find closest
        idx = min(range(len(GAIN_TABLE)), key=lambda i: abs(GAIN_TABLE[i] - current))

    new_idx = idx + direction
    if new_idx < 0 or new_idx >= len(GAIN_TABLE):
        return None  # Already at min/max
    return GAIN_TABLE[new_idx]


def apply_gain(new_gain):
    """Update docker-compose.yml and recreate container."""
    text = COMPOSE_FILE.read_text()
    new_text = re.sub(r"READSB_GAIN=[0-9.]+", f"READSB_GAIN={new_gain}", text)
    COMPOSE_FILE.write_text(new_text)

    log.info(f"Restarting ultrafeeder with gain={new_gain}")
    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "ultrafeeder"],
        capture_output=True, text=True, cwd=str(COMPOSE_FILE.parent),
    )
    if result.returncode != 0:
        log.error(f"Container restart failed: {result.stderr}")
        return False
    return True


def evaluate_window(window):
    """Analyze 2-hour rolling window and recommend action.

    Returns: 'down', 'up', or 'hold'
    """
    if len(window) < WINDOW_SIZE:
        return "hold"  # Not enough data yet

    # Aggregate metrics over the 2-hour window
    avg_signal = sum(s["signal"] for s in window if s["signal"]) / len(window)
    avg_noise = sum(s["noise"] for s in window if s["noise"]) / len(window)
    total_strong = sum(s["strong_signals"] for s in window)
    worst_peak = max(s["peak_signal"] for s in window if s["peak_signal"] is not None)
    snr = avg_signal - avg_noise

    log.info(f"  2h window: signal={avg_signal:.1f} noise={avg_noise:.1f} "
             f"SNR={snr:.1f} strong={total_strong} peak={worst_peak:.1f}")

    # Decision rules (priority order)
    # Rule 1: ADC saturation — peak too close to 0 dB
    if worst_peak > PEAK_CEILING_DB:
        log.info(f"  → STEP DOWN: peak {worst_peak:.1f} > {PEAK_CEILING_DB} (near saturation)")
        return "down"

    # Rule 2: Too many strong signals over 2 hours
    if total_strong > STRONG_SIGNAL_THRESHOLD * WINDOW_SIZE:
        log.info(f"  → STEP DOWN: {total_strong} strong signals in 2h (threshold: {STRONG_SIGNAL_THRESHOLD * WINDOW_SIZE})")
        return "down"

    # Rule 3: SNR too low (noise floor rising relative to signal)
    if snr < MIN_SNR_DB:
        log.info(f"  → STEP DOWN: SNR {snr:.1f} < {MIN_SNR_DB} (amplifier noise)")
        return "down"

    # Rule 4: Signal too weak — might be missing distant aircraft
    if avg_signal < SIGNAL_FLOOR_DB:
        log.info(f"  → STEP UP: signal {avg_signal:.1f} < {SIGNAL_FLOOR_DB} (too weak)")
        return "up"

    log.info("  → HOLD: all metrics within acceptable range")
    return "hold"


def main():
    dry_run = "--dry-run" in sys.argv

    import socket
    hostname = socket.gethostname()
    min_gain = GAIN_FLOOR.get(hostname, 0.0)

    log.info("=" * 50)
    log.info(f"Gain tuner run {'(DRY RUN)' if dry_run else ''} [{hostname}, floor={min_gain}]")

    # Fetch current stats
    stats = fetch_stats()
    if stats is None:
        log.warning("No stats available, skipping")
        return

    current_gain = stats["gain_db"] or get_current_gain()
    log.info(f"Current gain: {current_gain} dB")
    log.info(f"  15min: signal={stats['signal']} noise={stats['noise']} "
             f"peak={stats['peak_signal']} strong={stats['strong_signals']} msgs={stats['messages']}")

    # Load state and append new sample
    state = load_state()
    window = state["window"]
    window.append(stats)

    # Keep only last WINDOW_SIZE samples
    if len(window) > WINDOW_SIZE:
        window = window[-WINDOW_SIZE:]
    state["window"] = window

    # Evaluate
    recommendation = evaluate_window(window)

    # Hysteresis logic
    if recommendation == "hold":
        state["hysteresis_direction"] = None
        state["hysteresis_count"] = 0
    elif recommendation == state.get("hysteresis_direction"):
        state["hysteresis_count"] += 1
    else:
        state["hysteresis_direction"] = recommendation
        state["hysteresis_count"] = 1

    log.info(f"  Hysteresis: direction={state['hysteresis_direction']} "
             f"count={state['hysteresis_count']}/{HYSTERESIS_COUNT}")

    # Act only if hysteresis threshold met
    if state["hysteresis_count"] >= HYSTERESIS_COUNT:
        direction = 1 if recommendation == "up" else -1
        new_gain = step_gain(current_gain, direction)

        if new_gain is None:
            log.info(f"  Already at {'max' if direction > 0 else 'min'} gain, no change")
        elif direction == -1 and new_gain < min_gain:
            log.info(f"  FLOOR: {new_gain} below minimum {min_gain} for {hostname}, no change")
        elif dry_run:
            log.info(f"  DRY RUN: would change gain {current_gain} → {new_gain}")
        else:
            log.info(f"  APPLYING: gain {current_gain} → {new_gain}")
            if apply_gain(new_gain):
                # Reset hysteresis AND clear window after successful change
                # This prevents stale pre-change samples from triggering another step
                state["hysteresis_direction"] = None
                state["hysteresis_count"] = 0
                state["window"] = []
                log.info(f"  SUCCESS: gain changed to {new_gain} (window cleared)")
            else:
                log.error("  FAILED: gain change unsuccessful, will retry next cycle")
    else:
        log.info("  No action (hysteresis not met)")

    save_state(state)


if __name__ == "__main__":
    main()
