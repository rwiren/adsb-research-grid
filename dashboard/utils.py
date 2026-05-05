# ==============================================================================
# File: utils.py
# Version: 5.0.0
# Date: 2026-04-26
# Maintainer: Team-9 Secure Skies
# Description: Stateless helper functions — geodesy, spoof scoring, jamming
#              detection, and MQTT credential loading.  No Flask or MQTT side
#              effects live here.
# ==============================================================================
import math
import os
import time
import logging
from collections import deque

from config import (
    SENSOR_POS,
    MAX_CREDIBLE_CLIMB_FPM,
    MAX_GS_DISCREPANCY,
    MQTT_PASS_FILE,
    MQTT_USER,
)

log = logging.getLogger(__name__)


def decdeg_to_dms(dd, is_lat=True):
    """Convert decimal degrees to DMS string, e.g. 60°19'10.4"N."""
    direction = "N" if is_lat else "E"
    if dd < 0:
        dd = -dd
        direction = "S" if is_lat else "W"
    d = int(dd)
    m_float = (dd - d) * 60
    m = int(m_float)
    s = (m_float - m) * 60
    return f"{d}°{m:02d}'{s:05.2f}\"{direction}"


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres between two WGS-84 points."""
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(min(a, 1.0)))


def tdoa_uncertainty_radius_m(sync_delta_ms):
    """Convert inter-sensor clock-sync error (ms) into a TDOA uncertainty radius (m)."""
    return (sync_delta_ms / 1000.0) * 299_792_458.0 / 2.0


def compute_spoof_score(entry):
    """Heuristic spoofing score in [0.0, 1.0] with descriptive flags."""
    score = 0.0
    flags = []

    # Check 0: suspicious ICAO address
    hex_id = str(entry.get("hex", ""))
    try:
        if hex_id and (int(hex_id, 16) < 0x100 or hex_id in ("000000", "ffffff")):
            score += 0.5
            flags.append("suspicious-ICAO")
    except ValueError:
        pass

    alt = entry.get("alt")
    seen_by = entry.get("seen_by", set())

    # Check 1: single-sensor high-altitude WITHOUT valid squawk or flight
    # (Normal airlines at edge of range are single-sensor but have valid IDs)
    flight = entry.get("flight")
    squawk = entry.get("squawk")
    if len(seen_by) == 1 and isinstance(alt, (int, float)) and alt > 25000:
        if not flight and not squawk:
            score += 0.4
            flags.append("1-sensor>25kft+no-id")

    # Check 2: impossible climb / descent rate
    ah = list(entry.get("alt_history", []))
    if len(ah) >= 2:
        t1, a1 = ah[-2]
        t2, a2 = ah[-1]
        if isinstance(a1, (int, float)) and isinstance(a2, (int, float)) and t2 > t1:
            dt_min = (t2 - t1) / 60.0
            if dt_min > 0.083:  # at least 5 seconds
                fpm = abs(a2 - a1) / dt_min
                if fpm > MAX_CREDIBLE_CLIMB_FPM:
                    score += 0.35
                    flags.append(f"climb>{fpm:.0f}fpm")

    # Check 3: groundspeed inconsistency
    trail = list(entry.get("trail", []))
    last_seen = entry.get("last_seen", 0)
    prev_seen = entry.get("prev_seen", 0)
    if len(trail) >= 2 and 0 < prev_seen < last_seen:
        d_m = haversine_m(trail[-2][0], trail[-2][1], trail[-1][0], trail[-1][1])
        dt_s = last_seen - prev_seen
        if dt_s >= 5:
            computed_kt = (d_m / dt_s) * 1.94384
            reported_gs = entry.get("gs")
            if reported_gs and reported_gs > 20 and computed_kt > 20:
                ratio = abs(computed_kt - reported_gs) / max(reported_gs, 1.0)
                if ratio > MAX_GS_DISCREPANCY:
                    score += 0.3
                    flags.append(f"GS{reported_gs:.0f}vs{computed_kt:.0f}kt")

    return min(score, 1.0), flags


def check_jamming_alerts(sensors_dict):
    """Detect sensors whose message rate has suddenly collapsed.

    Parameters
    ----------
    sensors_dict : dict
        The live ``state["sensors"]`` mapping.

    Returns
    -------
    list[str]
        Names of sensors showing jamming signatures.
    """
    now_ts = time.time()
    alerts = []
    for name, s in sensors_dict.items():
        hist = list(s.get("msg_rate_history", []))
        if len(hist) < 4:
            continue
        recent = [r for t, r in hist if now_ts - t < 15]
        older = [r for t, r in hist if 15 <= now_ts - t < 75]
        if not recent or not older:
            continue
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        if older_avg > 10 and recent_avg < older_avg * 0.4:
            alerts.append(name)
    return alerts


def _load_mqtt_password():
    """Read MQTT password from env or on-disk secret file."""
    mqtt_pass = os.getenv("MQTT_PASS")
    if mqtt_pass:
        return mqtt_pass
    try:
        with open(MQTT_PASS_FILE, "r", encoding="utf-8") as fh:
            return fh.read(1024).strip()
    except OSError as exc:
        log.warning("MQTT password file unavailable: %s", exc)
        return ""
