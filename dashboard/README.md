# SecuringSkies MLAT Dashboard v3.2

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

## Architecture
```
Sensor Nodes (RPi4)          Helsinki Server
┌──────────┐                ┌──────────────────┐
│sensor-north├──MQTT──┐     │  Mosquitto :1883  │
│sensor-west ├──MQTT──┼────►│  dashboard.py     │──► :8080 (WebSocket)
│sensor-east ├──MQTT──┘     │  Flask+SocketIO   │
└──────────┘                └──────────────────┘
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

Expects a local Mosquitto broker on `127.0.0.1:1883` with topics:
- `sensor-north/aircraft`, `sensor-north/stats`
- `sensor-west/aircraft`, `sensor-west/stats`
- `sensor-east/aircraft`, `sensor-east/stats`
