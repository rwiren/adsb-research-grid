# ==============================================================================
# File: dashboard.py
# Version: 3.2.0 (Slim UI & Strict MLAT Coloring)
# Date: 2026-04-09
# Maintainer: Team-9 Secure Skies
# Description: Removed altitude scale to focus strictly on Array Lock colors.
#              Expanded map height, compressed dashboard panel height.
# ==============================================================================
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt
import json
import time
import logging

logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')

state = {
    "aircraft": {},
    "sensors": {
        "sensor-north": {"now": 0, "signal": 0, "noise": 0, "msg_rate": 0, "max_range_km": 0, "gain_db": 0, "ac_with_pos": 0, "ac_total": 0},
        "sensor-west":  {"now": 0, "signal": 0, "noise": 0, "msg_rate": 0, "max_range_km": 0, "gain_db": 0, "ac_with_pos": 0, "ac_total": 0},
        "sensor-east":  {"now": 0, "signal": 0, "noise": 0, "msg_rate": 0, "max_range_km": 0, "gain_db": 0, "ac_with_pos": 0, "ac_total": 0},
    },
    "sync": {"delta_ms": 0.0, "per_sensor": {}}
}

def on_message(client, userdata, message):
    try:
        parts = message.topic.split('/')
        sensor, dtype = parts[0], parts[1]
        payload = json.loads(message.payload)

        if dtype == "stats":
            s = state["sensors"].setdefault(sensor, {})
            s["now"] = float(payload.get("now", 0))
            s["gain_db"] = payload.get("gain_db", 0)
            s["ac_with_pos"] = payload.get("aircraft_with_pos", 0)
            s["ac_total"] = s["ac_with_pos"] + payload.get("aircraft_without_pos", 0)
            l1 = payload.get("last1min", {}).get("local", {})
            s["signal"] = l1.get("signal", 0)
            s["noise"] = l1.get("noise", 0)
            s["msg_rate"] = payload.get("last1min", {}).get("messages_valid", 0)
            s["max_range_km"] = round(payload.get("last15min", {}).get("max_distance", 0) / 1000, 1)

        elif dtype == "aircraft":
            if "now" not in payload:
                return

            # Sync math
            state["sensors"].setdefault(sensor, {})["now"] = float(payload["now"])
            nows = {k: v["now"] for k, v in state["sensors"].items() if v.get("now", 0) > 0}
            state["sync"]["per_sensor"] = nows
            vals = list(nows.values())
            if len(vals) > 1:
                sub = (max(vals) - min(vals)) % 1.0
                if sub > 0.5:
                    sub = 1.0 - sub
                state["sync"]["delta_ms"] = sub * 1000

            # Aircraft tracking
            for ac in payload.get("aircraft", []):
                hex_id = ac.get("hex")
                if not hex_id or "lat" not in ac:
                    continue
                entry = state["aircraft"].setdefault(hex_id, {"seen_by": set()})
                entry.update({
                    "lat": ac["lat"], "lon": ac["lon"],
                    "flight": (ac.get("flight") or "").strip() or None,
                    "squawk": ac.get("squawk"),
                    "alt": ac.get("alt_baro", "ground"),
                    "gs": ac.get("gs"),
                    "track": ac.get("track"),
                    "rssi": ac.get("rssi"),
                    "type": ac.get("type"),
                    "category": ac.get("category"),
                    "last_seen": time.time()
                })
                entry["seen_by"].add(sensor)

            # Stale cleanup
            now = time.time()
            state["aircraft"] = {k: v for k, v in state["aircraft"].items() if now - v["last_seen"] < 15}

            socketio.emit('map_update', {
                "sync": state["sync"],
                "sensors": state["sensors"],
                "aircraft": [{**v, "hex": k, "seen_by": list(v["seen_by"])} for k, v in state["aircraft"].items()]
            })

    except Exception as e:
        log.warning("MQTT parse error on %s: %s", message.topic, e)

client = mqtt.Client()
client.username_pw_set("team9", "ResearchView2026!")
client.on_message = on_message

def start_mqtt():
    try:
        client.connect("127.0.0.1", 1883, 60)
        client.subscribe("+/aircraft")
        client.subscribe("+/stats")
        client.loop_start()
        log.warning("MQTT connected to 127.0.0.1:1883")
    except Exception as e:
        log.error("MQTT Connect Error: %s", e)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>SecuringSkies MLAT Hub v3.2</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        * { box-sizing: border-box; }
        body { margin:0; background:#0d1117; color:#c9d1d9; font-family:'Courier New',monospace; overflow:hidden; }

        /* Layout Adjusted: Map 75vh, Dashboard 25vh */
        #map { height: 75vh; width: 100%; border-bottom: 2px solid #30363d; }
        #dashboard { height: 25vh; display:flex; gap:8px; background:#161b22; padding:10px; }

        .panel { background:#0d1117; border:1px solid #30363d; border-radius:4px; padding:10px; display:flex; flex-direction:column; }
        .panel-sync { flex:0.8; align-items:center; justify-content:center; text-align:center; }
        .panel-sensors { flex:2; }
        .panel-legend { flex:1.2; }

        .label { font-size:0.75em; color:#8b949e; text-transform:uppercase; margin-bottom:4px; letter-spacing:0.5px; }
        .value-big { font-size:3em; font-weight:bold; color:#3fb950; line-height:1; margin-bottom: 5px; }
        .value-sub { font-size:0.85em; color:#8b949e; margin-top:2px; }

        /* Sensor health grid */
        .sensor-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; height:100%; }
        .sensor-card { background:#161b22; border:1px solid #30363d; border-radius:4px; padding:6px; display:flex; flex-direction:column; gap:2px; }
        .sensor-card .name { font-size:0.85em; font-weight:bold; margin-bottom:2px; }
        .sensor-card .row { display:flex; justify-content:space-between; font-size:0.75em; }
        .sensor-card .row .k { color:#8b949e; }
        .sensor-card .row .v { color:#c9d1d9; }
        .snr-bar { height:4px; background:#21262d; border-radius:2px; margin-top:auto; }
        .snr-bar-fill { height:100%; border-radius:2px; transition: width 0.5s; }

        .legend-grid { display:grid; grid-template-columns:1fr 1fr; gap:4px; font-size:0.8em; margin-top: 5px;}
        .legend-item { display:flex; align-items:center; }
        .dot { width:10px; height:10px; border-radius:50%; margin-right:8px; border:1px solid rgba(255,255,255,0.15); flex-shrink:0; }

        .leaflet-popup-content-wrapper,.leaflet-popup-tip { background:#161b22; color:#c9d1d9; border:1px solid #30363d; box-shadow:0 0 15px rgba(0,0,0,0.8); }
        .leaflet-popup-content { margin:10px; line-height:1.5; font-family:'Courier New',monospace; font-size:0.9em; }

        /* Flight labels */
        .flight-label { background:none; border:none; color:#c9d1d9; font-family:'Courier New',monospace;
                        font-size:11px; font-weight:bold; white-space:nowrap; text-shadow:1px 1px 2px #000,-1px -1px 2px #000; }
    </style>
</head>
<body>
    <div id="map"></div>
    <div id="dashboard">
        <div class="panel panel-sync">
            <div class="label">Array Sync Δ</div>
            <div id="sync-delta" class="value-big">0.00</div>
            <div style="font-size:1em;color:#8b949e;">ms</div>
            <div id="sync-detail" class="value-sub"></div>
            <div style="margin-top:auto;">
                <div class="label">Targets</div>
                <div id="ac-count" class="value-big" style="font-size:2em;">0</div>
            </div>
        </div>
        <div class="panel panel-sensors">
            <div class="label">Sensor Health (Live Telemetry)</div>
            <div class="sensor-grid">
                <div class="sensor-card" id="card-north">
                    <div class="name" style="color:#58a6ff;">▲ NORTH</div>
                    <div class="row"><span class="k">Signal</span><span class="v" id="n-sig">—</span></div>
                    <div class="row"><span class="k">SNR</span><span class="v" id="n-snr">—</span></div>
                    <div class="row"><span class="k">Gain</span><span class="v" id="n-gain">—</span></div>
                    <div class="row"><span class="k">Msg/min</span><span class="v" id="n-msg">—</span></div>
                    <div class="row"><span class="k">Max Range</span><span class="v" id="n-range">—</span></div>
                    <div class="row"><span class="k">AC (pos/all)</span><span class="v" id="n-ac">—</span></div>
                    <div class="snr-bar"><div class="snr-bar-fill" id="n-bar" style="width:0%;background:#58a6ff;"></div></div>
                </div>
                <div class="sensor-card" id="card-west">
                    <div class="name" style="color:#3fb950;">◀ WEST</div>
                    <div class="row"><span class="k">Signal</span><span class="v" id="w-sig">—</span></div>
                    <div class="row"><span class="k">SNR</span><span class="v" id="w-snr">—</span></div>
                    <div class="row"><span class="k">Gain</span><span class="v" id="w-gain">—</span></div>
                    <div class="row"><span class="k">Msg/min</span><span class="v" id="w-msg">—</span></div>
                    <div class="row"><span class="k">Max Range</span><span class="v" id="w-range">—</span></div>
                    <div class="row"><span class="k">AC (pos/all)</span><span class="v" id="w-ac">—</span></div>
                    <div class="snr-bar"><div class="snr-bar-fill" id="w-bar" style="width:0%;background:#3fb950;"></div></div>
                </div>
                <div class="sensor-card" id="card-east">
                    <div class="name" style="color:#f85149;">▶ EAST</div>
                    <div class="row"><span class="k">Signal</span><span class="v" id="e-sig">—</span></div>
                    <div class="row"><span class="k">SNR</span><span class="v" id="e-snr">—</span></div>
                    <div class="row"><span class="k">Gain</span><span class="v" id="e-gain">—</span></div>
                    <div class="row"><span class="k">Msg/min</span><span class="v" id="e-msg">—</span></div>
                    <div class="row"><span class="k">Max Range</span><span class="v" id="e-range">—</span></div>
                    <div class="row"><span class="k">AC (pos/all)</span><span class="v" id="e-ac">—</span></div>
                    <div class="snr-bar"><div class="snr-bar-fill" id="e-bar" style="width:0%;background:#f85149;"></div></div>
                </div>
            </div>
        </div>
        <div class="panel panel-legend">
            <div class="label">Coverage Legend</div>
            <div class="legend-grid">
                <div class="legend-item"><span class="dot" style="background:#58a6ff"></span>North <span id="cnt-n" style="color:#8b949e;margin-left:auto;">0</span></div>
                <div class="legend-item"><span class="dot" style="background:#39c5cf"></span>N+W <span id="cnt-nw" style="color:#8b949e;margin-left:auto;">0</span></div>
                <div class="legend-item"><span class="dot" style="background:#3fb950"></span>West <span id="cnt-w" style="color:#8b949e;margin-left:auto;">0</span></div>
                <div class="legend-item"><span class="dot" style="background:#d2a8ff"></span>N+E <span id="cnt-ne" style="color:#8b949e;margin-left:auto;">0</span></div>
                <div class="legend-item"><span class="dot" style="background:#f85149"></span>East <span id="cnt-e" style="color:#8b949e;margin-left:auto;">0</span></div>
                <div class="legend-item"><span class="dot" style="background:#d29922"></span>W+E <span id="cnt-we" style="color:#8b949e;margin-left:auto;">0</span></div>
                <div class="legend-item" style="grid-column:span 2;margin-top:4px;padding-top:4px;border-top:1px solid #30363d;">
                    <span class="dot" style="background:#fff;box-shadow:0 0 8px #fff;"></span><b>FULL LOCK (N+W+E)</b>
                    <span id="cnt-all" style="color:#8b949e;margin-left:auto;">0</span>
                </div>
            </div>
        </div>
    </div>
<script>
var map = L.map('map', {zoomControl:false});
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{attribution:''}).addTo(map);

var markers = {}, labels = {}, arrows = {};

var nodes = {
    "sensor-north": {pos:[60.319555,24.830816], col:"#58a6ff", lbl:"N"},
    "sensor-west":  {pos:[60.130919,24.512869], col:"#3fb950", lbl:"W"},
    "sensor-east":  {pos:[60.350000,25.350000], col:"#f85149", lbl:"E"}
};

Object.keys(nodes).forEach(id => {
    var n = nodes[id];
    L.circleMarker(n.pos, {radius:8, fillColor:n.col, color:"#fff", weight:2, fillOpacity:1, pane:'markerPane'}).addTo(map)
     .bindPopup('<b style="font-family:monospace">NODE: '+id.toUpperCase()+'</b>');
    L.circle(n.pos, {radius:100000, color:n.col, weight:1, fillOpacity:0, dashArray:'3,8'}).addTo(map);
    L.circle(n.pos, {radius:200000, color:n.col, weight:0.5, fillOpacity:0, dashArray:'2,12'}).addTo(map);
});

// Auto-fit to sensor triangle
map.fitBounds(L.latLngBounds([nodes["sensor-north"].pos, nodes["sensor-west"].pos, nodes["sensor-east"].pos]), {padding:[50,50]});

// Hide flight labels when zoomed out to avoid clutter
map.on('zoomend', function() {
    var show = map.getZoom() >= 10;
    document.querySelectorAll('.flight-label').forEach(function(el) { el.style.display = show ? 'block' : 'none'; });
});

function getColor(sb) {
    var n=sb.includes("sensor-north"), w=sb.includes("sensor-west"), e=sb.includes("sensor-east");
    if(n&&w&&e) return "#fff";
    if(n&&w) return "#39c5cf";
    if(n&&e) return "#d2a8ff";
    if(w&&e) return "#d29922";
    if(n) return "#58a6ff";
    if(w) return "#3fb950";
    if(e) return "#f85149";
    return "#888";
}

function arrowSvg(track, col) {
    var rot = track || 0;
    return '<svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">' +
        '<g transform="rotate('+rot+',12,12)">' +
        '<polygon points="12,2 8,18 12,14 16,18" fill="'+col+'" stroke="#000" stroke-width="0.8" opacity="0.9"/>' +
        '</g></svg>';
}

function updateSensor(prefix, s) {
    var snr = (s.signal && s.noise) ? (s.signal - s.noise).toFixed(1) : '—';
    document.getElementById(prefix+'-sig').textContent = s.signal ? s.signal.toFixed(1)+' dB' : '—';
    document.getElementById(prefix+'-snr').textContent = snr !== '—' ? snr+' dB' : '—';
    document.getElementById(prefix+'-gain').textContent = s.gain_db ? s.gain_db+' dB' : '—';
    document.getElementById(prefix+'-msg').textContent = s.msg_rate ? s.msg_rate.toLocaleString() : '—';
    document.getElementById(prefix+'-range').textContent = s.max_range_km ? s.max_range_km+' km' : '—';
    document.getElementById(prefix+'-ac').textContent = (s.ac_with_pos||0)+'/'+(s.ac_total||0);
    var pct = snr !== '—' ? Math.min(Math.max(parseFloat(snr)/30*100,0),100) : 0;
    document.getElementById(prefix+'-bar').style.width = pct+'%';
}

var socket = io();
socket.on('map_update', function(data) {
    // Sync panel
    document.getElementById('sync-delta').textContent = data.sync.delta_ms.toFixed(2);
    var dEl = document.getElementById('sync-delta');
    dEl.style.color = data.sync.delta_ms < 50 ? '#3fb950' : data.sync.delta_ms < 200 ? '#d29922' : '#f85149';

    // Per-sensor sync detail
    var ps = data.sync.per_sensor || {};
    var refTime = Math.min(...Object.values(ps).filter(v=>v>0));
    var detail = Object.entries(ps).map(function(e) {
        var short = e[0].replace('sensor-','').charAt(0).toUpperCase();
        var off = ((e[1] - refTime) % 1.0) * 1000;
        if(off > 500) off = off - 1000;
        return short+':'+off.toFixed(0)+'ms';
    }).join(' ');
    document.getElementById('sync-detail').textContent = detail;

    // Sensor health
    if(data.sensors) {
        if(data.sensors["sensor-north"]) updateSensor('n', data.sensors["sensor-north"]);
        if(data.sensors["sensor-west"])  updateSensor('w', data.sensors["sensor-west"]);
        if(data.sensors["sensor-east"])  updateSensor('e', data.sensors["sensor-east"]);
    }

    // Aircraft
    document.getElementById('ac-count').textContent = data.aircraft.length;
    var activeHexes = new Set();
    var counts = {n:0,w:0,e:0,nw:0,ne:0,we:0,all:0};

    data.aircraft.forEach(function(ac) {
        activeHexes.add(ac.hex);
        var col = getColor(ac.seen_by);
        var loc = L.latLng(ac.lat, ac.lon);
        var callsign = ac.flight || ac.hex.toUpperCase();
        var altStr = (ac.alt==="ground"||ac.alt==="Ground") ? "GND" : (ac.alt ? ac.alt.toLocaleString()+"ft" : "?");

        // Count by coverage
        var n=ac.seen_by.includes("sensor-north"),w=ac.seen_by.includes("sensor-west"),e=ac.seen_by.includes("sensor-east");
        if(n&&w&&e) counts.all++;
        else if(n&&w) counts.nw++;
        else if(n&&e) counts.ne++;
        else if(w&&e) counts.we++;
        else if(n) counts.n++;
        else if(w) counts.w++;
        else if(e) counts.e++;

        // Distances
        var dN=n?(map.distance(loc,L.latLng(nodes["sensor-north"].pos))/1000).toFixed(1)+" km":"—";
        var dW=w?(map.distance(loc,L.latLng(nodes["sensor-west"].pos))/1000).toFixed(1)+" km":"—";
        var dE=e?(map.distance(loc,L.latLng(nodes["sensor-east"].pos))/1000).toFixed(1)+" km":"—";

        var popupHTML = '<div style="font-family:monospace;min-width:160px;">'+
            '<b style="color:'+col+';font-size:1.2em;">'+callsign+'</b><br>'+
            'ICAO: '+ac.hex+'<br>'+
            'SQWK: '+(ac.squawk||'—')+'<br>'+
            'ALT : '+altStr+'<br>'+
            'GS  : '+(ac.gs?ac.gs.toFixed(0)+' kt':'—')+'<br>'+
            'HDG : '+(ac.track!=null?ac.track.toFixed(0)+'°':'—')+'<br>'+
            'RSSI: '+(ac.rssi?ac.rssi.toFixed(1)+' dB':'—')+'<br>'+
            'TYPE: '+(ac.type||'—')+' '+(ac.category||'')+'<br>'+
            '<hr style="border:0;border-top:1px dashed #30363d;margin:6px 0;">'+
            '<span style="color:#8b949e;font-size:0.9em;">RANGES:</span><br>'+
            '<span style="color:#58a6ff">[N]</span> '+dN+'<br>'+
            '<span style="color:#3fb950">[W]</span> '+dW+'<br>'+
            '<span style="color:#f85149">[E]</span> '+dE+'<br>'+
            '<span style="color:#8b949e;font-size:0.85em;">Sensors: '+ac.seen_by.length+'/3</span>'+
            '</div>';

        // Heading arrow marker
        if(ac.track != null && ac.gs && ac.gs > 10) {
            var icon = L.divIcon({html: arrowSvg(ac.track, col), className:'', iconSize:[24,24], iconAnchor:[12,12]});
            if(arrows[ac.hex]) {
                arrows[ac.hex].setLatLng(loc).setIcon(icon);
                if(arrows[ac.hex].getPopup()) arrows[ac.hex].getPopup().setContent(popupHTML);
            } else {
                arrows[ac.hex] = L.marker(loc, {icon:icon, pane:'markerPane'}).bindPopup(popupHTML).addTo(map);
            }
            if(markers[ac.hex]) { map.removeLayer(markers[ac.hex]); delete markers[ac.hex]; }
        } else {
            // Fallback circle strictly follows Array Lock color
            if(markers[ac.hex]) {
                markers[ac.hex].setLatLng(loc).setStyle({fillColor:col, color:"#000"});
                if(markers[ac.hex].getPopup()) markers[ac.hex].getPopup().setContent(popupHTML);
            } else {
                markers[ac.hex] = L.circleMarker(loc, {radius:6, fillColor:col, color:"#000", weight:1, fillOpacity:0.9}).bindPopup(popupHTML).addTo(map);
            }
            if(arrows[ac.hex]) { map.removeLayer(arrows[ac.hex]); delete arrows[ac.hex]; }
        }

        // Flight label
        var labelIcon = L.divIcon({html:'<span>'+callsign+'</span>', className:'flight-label', iconSize:[80,14], iconAnchor:[-8,7]});
        if(labels[ac.hex]) {
            labels[ac.hex].setLatLng(loc).setIcon(labelIcon);
        } else {
            labels[ac.hex] = L.marker(loc, {icon:labelIcon, interactive:false, pane:'tooltipPane'}).addTo(map);
        }
    });

    // Update legend counts
    document.getElementById('cnt-n').textContent = counts.n;
    document.getElementById('cnt-w').textContent = counts.w;
    document.getElementById('cnt-e').textContent = counts.e;
    document.getElementById('cnt-nw').textContent = counts.nw;
    document.getElementById('cnt-ne').textContent = counts.ne;
    document.getElementById('cnt-we').textContent = counts.we;
    document.getElementById('cnt-all').textContent = counts.all;

    // Cleanup stale
    for(var h in markers)  { if(!activeHexes.has(h)) { map.removeLayer(markers[h]);  delete markers[h]; } }
    for(var h in arrows)   { if(!activeHexes.has(h)) { map.removeLayer(arrows[h]);   delete arrows[h]; } }
    for(var h in labels)   { if(!activeHexes.has(h)) { map.removeLayer(labels[h]);   delete labels[h]; } }
});
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    start_mqtt()
    socketio.run(app, host='0.0.0.0', port=8080)
