# ==============================================================================
# File: mlat.py
# Version: 5.0.0
# Date: 2026-04-26
# Maintainer: Team-9 Secure Skies
# Description: TDOA multilateration engine — Chan's least-squares solver and
#              TDOA pair calculator.  Pure math; no Flask or MQTT dependencies.
# ==============================================================================
import math
import logging

from config import C, SENSOR_POS

log = logging.getLogger(__name__)


def solve_mlat_2d(sensor_positions, tdoa_pairs, altitude_m=None):
    """Chan's algorithm for TDOA multilateration with geometric confidence.

    Parameters
    ----------
    sensor_positions : dict
        Mapping sensor_name -> (lat, lon).
    tdoa_pairs : dict
        Mapping (ref_sensor, other_sensor) -> dt seconds.
    altitude_m : float, optional
        Altitude in metres (ignored for 2-D projection).

    Returns
    -------
    tuple | None
        (lat, lon, confidence) or None on failure.
    """
    if len(tdoa_pairs) < 2 or len(sensor_positions) < 3:
        return None

    ref_lat = sum(p[0] for p in sensor_positions.values()) / len(sensor_positions)
    ref_lon = sum(p[1] for p in sensor_positions.values()) / len(sensor_positions)
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(ref_lat))

    sensors_xy = {}
    for name, (lat, lon) in sensor_positions.items():
        x = (lon - ref_lon) * m_per_deg_lon
        y = (lat - ref_lat) * m_per_deg_lat
        sensors_xy[name] = (x, y)

    sensor_names = list(sensors_xy.keys())
    ref_sensor = sensor_names[0]
    ref_xy = sensors_xy[ref_sensor]

    A, b_vals, used_pairs = [], [], []

    for (s1, s2), dt in tdoa_pairs.items():
        if s1 == ref_sensor:
            x1, y1 = ref_xy
            xj, yj = sensors_xy[s2]
            t1, tj = 0.0, dt
        elif s2 == ref_sensor:
            x1, y1 = ref_xy
            xj, yj = sensors_xy[s1]
            t1, tj = 0.0, -dt
        else:
            continue

        A.append([2 * (xj - x1), 2 * (yj - y1)])
        val = (C * C) * (tj * tj - t1 * t1) + (x1 * x1 + y1 * y1) - (xj * xj + yj * yj)
        b_vals.append(val)
        used_pairs.append((s1, s2, dt))

    if len(A) < 2:
        return None

    try:
        import numpy as np
        A_np = np.array(A)
        b_np = np.array(b_vals)
        x_est = np.linalg.lstsq(A_np, b_np, rcond=None)[0]
        x_m, y_m = float(x_est[0]), float(x_est[1])

        # Reconstructed TDOA RMSE (fit quality in metres)
        target_local = np.array([x_m, y_m])
        tdoa_errors = []
        for s1_name, s2_name, dt_obs in used_pairs:
            x1, y1 = sensors_xy[s1_name]
            x2, y2 = sensors_xy[s2_name]
            d1 = float(np.linalg.norm(target_local - np.array([x1, y1])))
            d2 = float(np.linalg.norm(target_local - np.array([x2, y2])))
            dt_calc = (d2 - d1) / C
            tdoa_errors.append((dt_calc - dt_obs) ** 2)
        rmse_s = (
            math.sqrt(sum(tdoa_errors) / len(tdoa_errors))
            if tdoa_errors else 0.0
        )
        rmse_m = rmse_s * C

        # PDOP-like geometry factor
        try:
            ATA = A_np.T @ A_np
            Q = np.linalg.inv(ATA)
            pdop = math.sqrt(float(np.trace(Q)))
        except Exception:
            pdop = 10.0

        calc_lon = ref_lon + x_m / m_per_deg_lon
        calc_lat = ref_lat + y_m / m_per_deg_lat

        # ── Sanity bounds check: reject overflow / divergence ──────────────
        if abs(calc_lat) > 90 or abs(calc_lon) > 180:
            return None

        sensor_count = len(sensor_positions)
        sensor_factor = min(1.0, sensor_count / 4.0)
        accuracy_factor = math.exp(-rmse_m / 800.0)
        geometry_factor = math.exp(-pdop / 2.5)
        confidence = sensor_factor * accuracy_factor * geometry_factor
        confidence = max(0.05, min(0.98, confidence))

        return (calc_lat, calc_lon, confidence)
    except Exception as e:
        log.warning("MLAT solve error: %s", e)
        return None


def calculate_tdoa_pairs(arrival_times, sync_offsets_ms=None):
    """Calculate TDOA from arrival timestamps.

    Parameters
    ----------
    arrival_times : dict
        sensor_name -> timestamp (seconds).
    sync_offsets_ms : dict, optional
        sensor_name -> offset ms.

    Returns
    -------
    dict | None
        {"pairs": dict, "reference_sensor": str, "used_sensors": list,
         "sync_quality_ms": float} or None.
    """
    if len(arrival_times) < 2:
        return None

    sync_offsets_ms = sync_offsets_ms or {}
    corrected_times = {}
    for sensor, t in arrival_times.items():
        offset_sec = sync_offsets_ms.get(sensor, 0) / 1000.0
        corrected_times[sensor] = t - offset_sec

    ref_sensor = min(corrected_times, key=corrected_times.get)
    ref_time = corrected_times[ref_sensor]

    pairs = {}
    sensors_used = [ref_sensor]

    for sensor, t in corrected_times.items():
        if sensor == ref_sensor:
            continue
        dt = t - ref_time
        pairs[(ref_sensor, sensor)] = dt
        sensors_used.append(sensor)

    times_list = list(corrected_times.values())
    sync_quality = max(times_list) - min(times_list) if len(times_list) > 1 else 0

    return {
        "pairs": pairs,
        "reference_sensor": ref_sensor,
        "used_sensors": sensors_used,
        "sync_quality_ms": sync_quality * 1000,
    }
