# SecuringSkies MLAT Dashboard v4.1

Real-time ADS-B surveillance dashboard for the 3-node sensor array (North/West/East).

**Live instance:** [http://www.securingskies.eu:8080/](http://www.securingskies.eu:8080/)

## Features

- Real-time aircraft tracking via MQTT (`aircraft.json` + `stats.json` per sensor)
- **Array Lock coloring** — RGB scheme shows which sensor combination sees each target
- **Heading arrows** — SVG markers rotated to aircraft track for airborne targets
- **Flight labels** — callsign text on map (auto-hidden below zoom 10 to prevent clutter)
- **Sensor health panel** — live signal, SNR, gain, message rate, max range, aircraft count per node
- **Sync delta** — sub-second jitter measurement across the 3-node array with per-sensor offsets
- **Coverage counts** — legend shows how many aircraft in each sensor combination
- **Aircraft trail history** — last 60 position fixes per aircraft rendered as a fading dashed polyline
- **Emergency squawk alarm** — squawks 7500 / 7600 / 7700 trigger a persistent banner and a CSS pulse animation on the marker
- **TDOA uncertainty circle** — for every full-lock (N+W+E) aircraft, an amber dashed circle visualises the TDOA position-uncertainty radius driven by the measured inter-sensor clock sync error (`r ≈ c × Δt / 2`)
- **Connection status badge** — top-right indicator: green LIVE / amber STALE / red DISCONNECTED
- **Aircraft age fade-out** — marker opacity decays linearly from 100 % to 20 % over the last 5 s before server-side removal
- **Altitude filter slider** — dual-thumb range slider at the bottom of the map; filters aircraft by altitude client-side with no server round-trip
- **Anomaly score overlay** — subscribes to `sensor-core/anomalies` MQTT topic published by the ML pipeline; flagged aircraft (`score = -1`) get an amber outer ring and increment an Anomaly count in the legend
- **Popup enrichment** — ICAO ADS-B category codes (`A1`–`C7`) decoded to human-readable labels in the click popup
- **Coverage rings toggle** — two buttons let you show/hide the 100 km and 200 km sensor-range rings independently
- **Mobile-responsive layout** — on screens narrower than 768 px the dashboard panel collapses to a one-line summary bar with a tap-to-expand chevron
- **3D Sky View (v4.0)** — a `⟁ 3D SKY` tab switches from the Leaflet 2D map to a native Three.js 3D scene.  Press `T` to toggle, `R` to reset camera.  Features aircraft cones with altitude stems, ground track trails, TDOA uncertainty spheres, and pulsing spoof rings.  An "ALT EXAG" slider (1×–50×, default 10×) exaggerates vertical separation so FL100/FL200/FL350 traffic layers become clearly visible.  No tile server or external account required — Three.js loads from CDN (~170 KB).
- **Audio callouts (v4.1)** — a `🔇 AUDIO` toggle button activates browser-native speech synthesis (Web Speech API, no external service).  Audio fires **only on state transitions** — a new emergency squawk or a newly-detected unmanned aircraft — so the same target never triggers repeated announcements.  Phrases: *"Emergency squawk 7700 CALLSIGN"* and *"Unmanned aircraft CALLSIGN"*.
- **UAV / unmanned aircraft detection (v4.1)** — aircraft are flagged as unmanned when either:
  1. Their squawk code is in `UAV_SQUAWKS` (default: `7400` — UAS lost C2 link per ICAO Doc 10019), **or**
  2. Their ADS-B emitter category is `B4` (UAV/Drone), `B6` (UAV), or `B7` (UAV).
  Detected UAVs show a pulsing cyan ring on the map, a `⬡ UNMANNED AIRCRAFT` badge in the popup, an entry in the status banner above the map, and a UAV count in the legend.  The `UAV_SQUAWKS` set is centralised in `dashboard.py` and is easy to extend.

## Architecture

```
Sensor Nodes (RPi4)          Helsinki Server
┌──────────────┐             ┌──────────────────────────────────────────────┐
│ sensor-north ├──MQTT──┐    │  Mosquitto :1883 (local) / :8443 (WSS)      │
│ sensor-west  ├──MQTT──┼───►│  dashboard.py  (Flask + SocketIO) ──► :8080  │
│ sensor-east  ├──MQTT──┘    │  anomaly_bridge_v2.py (heuristic scoring)    │
│              │             │  ml_inference_service.py (autoencoder, below) │
└──────────────┘             └──────────────────────────────────────────────┘
```

### ML Inference Service (`ml_inference_service.py`)

Runs in parallel with the heuristic anomaly bridge. Performs real-time autoencoder
inference using the GRU model trained on the 144h multi-sensor dataset.

**Pipeline:**
1. Subscribes to `sensor-{north,west,east}/aircraft` (1 Hz)
2. Maintains a T=30 sliding window buffer per aircraft (ICAO hex)
3. Computes 7 engineered features per timestep (velocity_calculated, velocity_error,
   velocity_drift, distance_to_sensor, rssi_expected, rssi_error, rssi_error_normalized)
4. Applies the fitted StandardScaler (Z-score normalization)
5. Runs GRU Autoencoder forward pass → reconstruction error
6. Decomposes error per feature dimension (Paper Eq. 2)
7. Publishes anomalies (score > τ) to `sensor-core/ml-anomaly`

**Model:** GRU Autoencoder, 79K params, hidden=64, latent=8, τ=0.005050
**Checkpoint:** `models/adsb_gru_w30_144h_7feat.pth`

### Dashboard Integration (Phase 3)

The dashboard backend (`mqtt_handler.py`) subscribes to `sensor-core/ml-anomaly`
and attaches ML scores to each aircraft in the SocketIO `map_update` payload:
- `ml_score`: overall reconstruction error (float)
- `ml_threshold`: anomaly threshold τ (float)
- `ml_is_anomaly`: score > τ (bool)
- `ml_features`: per-feature MSE decomposition (dict)

The frontend (`page_template.py`) uses ML data to drive:
- **Feature Attribution panel**: shows "⚙ ML FEATURE ATTRIBUTION" with per-feature bars
- **Persistence gauge (k=5)**: increments on ML anomalies
- **ML status badge**: "ML: N scored" indicator in the sync panel

## Dependencies

```
pip install flask flask-socketio eventlet paho-mqtt
```

## Usage

```bash
python dashboard.py
# Serves on http://0.0.0.0:8080
```

If the broker requires authentication, provide the password outside the repo via
`MQTT_PASS` or a secret file pointed to by `MQTT_PASS_FILE`
(default: `/etc/securing_skies/mqtt_secret`).

Defaults to `mqtt.securingskies.eu:8883`, configurable via `MQTT_HOST` and
`MQTT_PORT`. Topics consumed:

| Topic | Content |
|---|---|
| `sensor-north/aircraft` | readsb `aircraft.json` payload |
| `sensor-north/stats` | readsb `stats.json` payload |
| `sensor-west/aircraft` | readsb `aircraft.json` payload |
| `sensor-west/stats` | readsb `stats.json` payload |
| `sensor-east/aircraft` | readsb `aircraft.json` payload |
| `sensor-east/stats` | readsb `stats.json` payload |
| `sensor-core/anomalies` | ML pipeline anomaly scores `{icao_hex: score}` |

## TDOA Uncertainty Explanation

For every aircraft seen by all three sensors (FULL LOCK) the dashboard draws an
amber dashed circle whose radius equals the TDOA position uncertainty introduced
by the current inter-sensor clock sync error:

```
r = c × Δt_sync / 2
```

where `c` is the speed of light and `Δt_sync` is the measured clock delta shown
in the Array Sync panel.  A tight NTP / PPS sync (< 1 ms) keeps the circle
small enough to be operationally useful; drift > 10 ms pushes the uncertainty
past 1 500 km, making TDOA localisation impractical — exactly what this
visualisation is designed to catch.
