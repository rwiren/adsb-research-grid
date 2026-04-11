# SecuringSkies MLAT Dashboard v3.3

Real-time ADS-B surveillance dashboard for the 3-node sensor array (North/West/East).

**Live instance:** [http://www.securingskies.eu:8080/](http://www.securingskies.eu:8080/)

## Features (v3.3 additions in bold)

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

## Architecture

```
Sensor Nodes (RPi4)          Helsinki Server
┌──────────────┐             ┌──────────────────────────────────────┐
│ sensor-north ├──MQTT──┐    │  Mosquitto :1883 (local)             │
│ sensor-west  ├──MQTT──┼───►│  dashboard.py  (Flask + SocketIO)   │──► :8080
│ sensor-east  ├──MQTT──┘    │  ML pipeline → sensor-core/anomalies │
└──────────────┘             └──────────────────────────────────────┘
```

## Dependencies

```
pip install flask flask-socketio eventlet paho-mqtt
```

## Usage

```bash
python dashboard.py
# Serves on http://0.0.0.0:8080
```

Expects a local Mosquitto broker on `127.0.0.1:1883`.  Topics consumed:

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
