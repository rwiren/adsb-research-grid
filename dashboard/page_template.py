# ==============================================================================
# File: html.py
# Version: 5.0.0
# Date: 2026-04-26
# Maintainer: Team-9 Secure Skies
# Description: The single-page HTML/JS/CSS template string served by Flask.
#              Kept in a dedicated file so editors can fold/syntax-highlight the
#              front-end code independently from the Python back-end.
# ==============================================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>SECURESKIES ⬡ MLAT TACTICAL HUB v5.0.0</title>
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='14' fill='none' stroke='%2300c878' stroke-width='2'/%3E%3Cpath d='M10 26 L16 6 L22 26 L16 18 Z' fill='%2300c878' opacity='0.8'/%3E%3C/svg%3E"/>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <!-- Three.js r128 (last stable release with non-module OrbitControls) -->
    <script src="https://unpkg.com/three@0.128.0/build/three.min.js"></script>
    <script src="https://unpkg.com/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    <style>
        * { box-sizing: border-box; }
        body { margin:0; background:#060a0f; color:#a8bcc8; font-family:'Courier New',monospace; overflow:hidden; }

        /* ── Core layout ── */
        #map        { height:75vh; width:100%; border-bottom:1px solid rgba(0,200,120,0.2); position:relative; }
        #dashboard  { height:25vh; display:flex; flex-wrap:wrap; gap:8px; background:#04080d; padding:10px; overflow-y:auto; border-top:1px solid rgba(0,200,120,0.15); transition:height 0.3s ease; }
        #dashboard.collapsed { height:0; padding:0 10px; overflow:hidden; border-top:none; }
        #dashboard.collapsed ~ #collapse-btn { bottom:8px; }
        #collapse-btn { position:fixed; bottom:25vh; right:12px; z-index:1100; background:rgba(4,8,13,0.9); border:1px solid rgba(0,200,120,0.3); color:#11caa0; padding:4px 10px; border-radius:4px; cursor:pointer; font-family:'Courier New',monospace; font-size:0.75em; transition:bottom 0.3s ease; }

        .panel         { background:#08111a; border:1px solid rgba(0,200,120,0.18); border-radius:2px; padding:10px; display:flex; flex-direction:column; position:relative; overflow:hidden; }
        .panel::before { content:''; position:absolute; top:0; left:0; right:0; height:1px; background:linear-gradient(90deg,rgba(0,200,120,0.55) 0%,transparent 80%); pointer-events:none; }
        .panel-sync    { flex:0.8; align-items:center; justify-content:center; text-align:center; }
        .panel-sensors { flex:2; }
        .panel-legend  { flex:1.2; }

        .label     { font-size:0.72em; color:#6a9f90; text-transform:uppercase; margin-bottom:4px; letter-spacing:1.2px; border-bottom:1px solid rgba(0,200,120,0.1); padding-bottom:3px; }
        .value-big { font-size:2.4em; font-weight:bold; color:#e8b84b; line-height:1; margin-bottom:5px; }
        .value-sub { font-size:0.85em; color:#7ab090; margin-top:2px; }

        /* Sensor health grid */
        .sensor-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; height:100%; }
        .sensor-card { background:#060e18; border:1px solid rgba(0,200,120,0.12); border-radius:2px; padding:6px; display:flex; flex-direction:column; gap:2px; position:relative; }
        .sensor-card .name { font-size:0.94em; font-weight:bold; margin-bottom:2px; letter-spacing:0.8px; }
        .sensor-card .row  { display:flex; justify-content:space-between; font-size:0.74em; }
        .sensor-card .row .k { color:#2e6050; }
        .sensor-card .row .v { color:#bee8d0; }
        .snr-bar      { height:3px; background:rgba(0,200,120,0.08); border-radius:1px; margin-top:auto; }
        .snr-bar-fill { height:100%; border-radius:1px; transition:width 0.5s; }

        /* Coverage legend */
        .legend-grid { display:grid; grid-template-columns:1fr 1fr; gap:4px; font-size:0.78em; margin-top:5px; }
        .legend-item { display:flex; align-items:center; color:#a8e6c8; }
        .dot { width:8px; height:8px; border-radius:50%; margin-right:7px; border:1px solid rgba(255,255,255,0.1); flex-shrink:0; }

        /* Popups */
        .leaflet-popup-content-wrapper, .leaflet-popup-tip { background:#04090f; color:#b0e8d0; border:1px solid rgba(0,200,120,0.3); box-shadow:0 0 20px rgba(0,200,120,0.12),0 0 40px rgba(0,0,0,0.9); }
        .leaflet-popup-content { margin:10px; line-height:1.5; font-family:'Courier New',monospace; font-size:0.9em; }

        /* Flight labels */
        .flight-label { background:none; border:none; color:#d0e8d0; font-family:'Courier New',monospace;
                        font-size:11px; font-weight:bold; white-space:nowrap;
                        text-shadow:1px 1px 3px #000, -1px -1px 3px #000, 0 0 6px rgba(0,200,120,0.25); }

        /* ── UAV banner ── */
        #uav-banner {
            display:none; position:absolute; top:0; left:0; right:0; z-index:1950;
            background:rgba(0,80,120,0.92); color:#5dd8ff; padding:6px 12px; font-size:0.82em;
            font-weight:bold; text-align:center; border-bottom:2px solid #39c5cf;
            pointer-events:none; letter-spacing:1px;
        }

        /* UAV marker ring animation */
        @keyframes uav-pulse {
            0%   { opacity:0.9; }
            50%  { opacity:0.35; }
            100% { opacity:0.9; }
        }
        .uav-ring { animation:uav-pulse 2s ease-in-out infinite; }

        /* ── Audio toggle button ── */
        #audio-btn {
            position:absolute; top:48px; right:130px; z-index:1000;
            background:rgba(4,8,13,0.88); border:1px solid rgba(0,200,120,0.22); border-radius:2px;
            color:#3d6050; font-size:0.7em; padding:3px 8px; cursor:pointer;
            font-family:'Courier New',monospace; white-space:nowrap; letter-spacing:0.8px;
            transition:color 0.2s, border-color 0.2s;
        }
        #audio-btn.active { color:#e8b84b; border-color:rgba(232,184,75,0.55); }

        /* ── Feature 4: Connection status badge ── */
        #conn-badge {
            position:absolute; top:48px; right:10px; z-index:1000;
            padding:3px 10px; border-radius:2px; font-size:0.7em; font-weight:bold;
            letter-spacing:1.2px; border:1px solid rgba(255,255,255,0.2); pointer-events:none;
            transition:background 0.5s, color 0.5s;
        }
        #conn-badge.live         { background:rgba(0,200,80,0.1);  color:#00c878; border-color:rgba(0,200,80,0.5); }
        #conn-badge.stale        { background:rgba(232,184,75,0.1); color:#e8b84b; border-color:rgba(232,184,75,0.5); }
        #conn-badge.disconnected { background:rgba(248,81,73,0.1);  color:#f85149; border-color:rgba(248,81,73,0.5); }

        /* ── v3.4: Jamming alert banner ── */
        #jamming-banner {
            display:none; position:absolute; top:0; left:0; right:0; z-index:1900;
            background:rgba(125,64,0,0.92); color:#ffcc00; padding:6px 12px; font-size:0.82em;
            font-weight:bold; text-align:center; border-bottom:2px solid #e8b84b;
            pointer-events:none; letter-spacing:1px;
        }
        /* Emergency banner sits above jamming banner */
        #emergency-banner { z-index:2000; }

        /* ── v3.4: Spoof score ring animation ── */
        @keyframes spoof-pulse {
            0%   { opacity:0.9; }
            50%  { opacity:0.3; }
            100% { opacity:0.9; }
        }
        .spoof-ring { animation:spoof-pulse 1.5s ease-in-out infinite; }

        /* ── Feature 2: Emergency banner ── */
        #emergency-banner {
            display:none; position:absolute; top:0; left:0; right:0; z-index:2000;
            background:rgba(125,0,0,0.92); color:#ff8080; padding:6px 12px; font-size:0.82em;
            font-weight:bold; text-align:center; border-bottom:2px solid #f85149;
            pointer-events:none; letter-spacing:1px;
        }

        /* Emergency marker pulse animation */
        @keyframes emergency-pulse {
            0%   { filter:drop-shadow(0 0 6px #f85149); }
            50%  { filter:drop-shadow(0 0 1px #f85149); opacity:0.6; }
            100% { filter:drop-shadow(0 0 6px #f85149); }
        }
        .emergency-marker { animation:emergency-pulse 1s ease-in-out infinite; }

        /* ── Feature 6: Altitude filter ── */
        #alt-filter {
            position:absolute; bottom:8px; left:50%; transform:translateX(-50%);
            z-index:1000; background:rgba(4,8,13,0.88); border:1px solid rgba(0,200,120,0.2);
            border-radius:2px; padding:4px 12px;
            display:flex; align-items:center; gap:8px; font-size:0.72em;
        }
        #alt-filter label  { color:#6a9f90; white-space:nowrap; letter-spacing:0.8px; }
        #alt-filter input[type=range] { width:80px; accent-color:#00c878; cursor:pointer; }
        #alt-filter span   { color:#e8b84b; min-width:34px; text-align:right; }

        /* ── Feature 9: Ring toggle buttons ── */
        #ring-controls {
            position:absolute; top:48px; left:50px; z-index:1000;
            display:flex; flex-direction:column; gap:4px;
        }
        .ring-btn {
            background:rgba(4,8,13,0.88); border:1px solid rgba(0,200,120,0.18); border-radius:2px;
            color:#5a9080; font-size:0.7em; padding:3px 7px; cursor:pointer;
            font-family:'Courier New',monospace; white-space:nowrap; letter-spacing:0.5px;
        }
        .ring-btn.active { color:#e8b84b; border-color:rgba(0,200,120,0.45); }

        /* ── v4.0: View toggle (2D MAP / 3D SKY) tab bar ── */
        #view-toggle {
            position:fixed; top:46px; left:50%; transform:translateX(-50%);
            z-index:1200; display:flex; gap:3px; pointer-events:auto;
        }
        .view-tab {
            background:rgba(4,8,13,0.92); border:1px solid rgba(0,200,120,0.22); border-radius:2px;
            color:#3d6050; font-size:0.68em; padding:4px 12px; cursor:pointer;
            font-family:'Courier New',monospace; letter-spacing:1px; text-transform:uppercase;
            transition:color 0.2s, border-color 0.2s;
        }
        .view-tab.active { color:#e8b84b; border-color:rgba(232,184,75,0.55); }
        .view-tab:hover  { color:#a8e6c8; border-color:rgba(0,200,120,0.5); }

        /* ── v4.0: 3D Sky View canvas ── */
        #canvas-3d {
            display:none; width:100%; height:75vh;
            background:#060a0f; border-bottom:1px solid rgba(0,200,120,0.2);
        }

        /* ── v4.0: Sky controls overlay (alt exaggeration) ── */
        #sky-controls {
            display:none; position:fixed; bottom:calc(25vh + 8px); left:50%;
            transform:translateX(-50%); z-index:1100;
            background:rgba(4,8,13,0.88); border:1px solid rgba(0,200,120,0.2);
            border-radius:2px; padding:4px 14px;
            align-items:center; gap:8px; font-size:0.72em;
        }
        #sky-controls label { color:#6a9f90; white-space:nowrap; letter-spacing:0.8px; }
        #sky-controls input[type=range] { width:80px; accent-color:#00c878; cursor:pointer; }
        #sky-controls span.val { color:#e8b84b; min-width:34px; text-align:right; }
        #sky-controls span.hint { color:#2a5040; font-size:0.9em; letter-spacing:0.3px; }

        /* ── Cursor coordinates display ── */
        #cursor-coords {
            position:absolute; bottom:40px; right:10px; z-index:1000;
            background:rgba(4,8,13,0.82); border:1px solid rgba(0,200,120,0.2);
            border-radius:2px; padding:2px 8px; font-size:0.7em;
            color:#7ab090; pointer-events:none; letter-spacing:0.5px;
        }

        /* ── Feature 10: Mobile layout ── */
        @media (max-width:768px) {
            body { overflow:auto; }
            #map { height:60vh; }
            #dashboard { height:40vh; }
            .panel { min-width:140px; flex:1 1 140px; }
            #dashboard {
                height:auto; flex-direction:column; position:relative;
                overflow:hidden; max-height:42px; transition:max-height 0.3s ease;
            }
            #dashboard.expanded { max-height:600px; }
            #mobile-bar {
                display:flex; align-items:center; justify-content:space-between;
                padding:6px 10px; background:#04080d; cursor:pointer;
                border-bottom:1px solid rgba(0,200,120,0.15); flex-shrink:0; min-height:42px; color:#7ecda0;
            }
            #mobile-chevron { transition:transform 0.3s; display:inline-block; }
            #dashboard.expanded #mobile-chevron { transform:rotate(180deg); }
            .panel { flex:unset; }
        }
        @media (min-width:769px) {
            #mobile-bar { display:none; }
        }
        /* Z Fold foldable optimization: handle tall narrow aspect ratio */
        @media (max-width:768px) and (min-aspect-ratio: 1/2) {
            #map { height:52vh; }
            #dashboard { max-height:48vh; }
            #dashboard.expanded { max-height:85vh; overflow-y:auto !important; }
            .sensor-card { padding:3px 5px; min-width:80px; gap:1px; }
            .sensor-card .row { font-size:0.68em; gap:1px; }
            .sensor-card .row .k { font-size:0.72em; }
            .sensor-card .row .v { font-size:0.72em; }
            .sensor-card .name { font-size:0.8em; margin-bottom:1px; }
            .snr-bar { margin-top:2px; height:2px; }
        }
        /* Z Fold inner screen: force all rows visible */
        @media (min-height:600px) and (max-width:900px) {
            #dashboard.expanded { 
                max-height:90vh !important;
                overflow-y:scroll !important;
            }
            .sensor-grid { min-height:auto; }
        }
        /* Folded outer cover screen: ~25:9 ratio */
        @media (max-width:350px) and (max-height:800px) {
            .sensor-card .sensor-name { font-size:0.75em; }
            .sensor-row { font-size:0.7rem; }
            #dashboard.expanded .sensor-row:last-child {
                display:flex !important; /* force show temp row */
            }
        }
        /* Unfolded inner screen: ensure 3 columns fit */
        @media (min-width:700px) and (max-width:900px) {
            .panel { flex:1; min-width:140px; }
            .sensor-card { min-width:100px; }
        }

        /* Footer with contact info */
        #footer {
            position:fixed; bottom:0; left:0; right:0; z-index:2000;
            background:#04080d; border-top:1px solid rgba(0,200,120,0.15);
            padding:4px 10px; font-size:0.7em; color:#5a9080;
            text-align:center; font-family:'Courier New',monospace;
        }
        #footer a { color:#7ecda0; text-decoration:none; }
        #footer a:hover { color:#a8e6c8; }
    
        /* Trilateration lock pulse */
        @keyframes trilat-pulse {
            0%, 100% { box-shadow: 0 0 4px 2px rgba(255,255,255,0.3); }
            50% { box-shadow: 0 0 10px 4px rgba(255,255,255,0.6); }
        }
        .trilat-glow {
            animation: trilat-pulse 2s ease-in-out infinite;
            border-radius: 50%;
        }

        /* Anomaly toast notification */
        #anomaly-toast {
            position:fixed; top:60px; right:12px; z-index:2000;
            background:rgba(248,81,73,0.15); border:1px solid rgba(248,81,73,0.5);
            border-radius:6px; padding:8px 14px; color:#f85149;
            font-family:'Courier New',monospace; font-size:0.8em;
            opacity:0; transform:translateX(100px); transition:all 0.4s ease;
            pointer-events:none; backdrop-filter:blur(4px);
        }
        #anomaly-toast.show {
            opacity:1; transform:translateX(0);
        }
</style>
</head>
<body>
    <!-- Feature 2: Emergency banner (shown above the map) -->
    <div id="emergency-banner"></div>
    <!-- UAV/unmanned aircraft banner -->
    <div id="uav-banner"></div>
    <!-- v3.4: Jamming alert banner -->
    <div id="jamming-banner"></div>

    <!-- v4.0: 2D MAP / 3D SKY view toggle (fixed, centered at top) -->
    <div id="view-toggle">
        <button id="btn-2d" class="view-tab active" onclick="setView('2d')">⊞ 2D MAP</button>
        <button id="btn-3d" class="view-tab"        onclick="setView('3d')">⟁ 3D SKY</button>
    </div>

    <div id="map" style="position:relative;">
    <!-- Info popup for first-time visitors -->
    <button id="info-btn" onclick="toggleInfo()" style="position:absolute;top:50px;left:12px;z-index:1000;background:rgba(4,8,13,0.85);border:1px solid rgba(0,200,120,0.3);color:#11caa0;width:28px;height:28px;border-radius:50%;cursor:pointer;font-size:16px;font-weight:bold;line-height:26px;text-align:center;">?</button>
    <div id="info-popup" style="display:none;position:absolute;top:88px;left:12px;z-index:1000;background:rgba(4,8,13,0.95);border:1px solid rgba(0,200,120,0.25);border-radius:8px;padding:16px 20px;max-width:360px;color:#c9d1d9;font-size:12px;line-height:1.6;box-shadow:0 4px 20px rgba(0,0,0,0.5);">
        <div style="font-size:14px;font-weight:bold;color:#11caa0;margin-bottom:10px;">SecuringSkies MLAT Hub</div>
        <p style="margin-bottom:8px;">Real-time ADS-B surveillance from a 3-node distributed sensor network in the Helsinki metropolitan area.</p>
        <p style="margin-bottom:8px;"><span style="color:#58a6ff;">▲</span> <b>North</b> (Helsinki-Vantaa) &middot; <span style="color:#3fb950;">◀</span> <b>West</b> (Jorvas) &middot; <span style="color:#f85149;">▶</span> <b>East</b> (Sipoo)</p>
        <p style="margin-bottom:8px;"><b>Colors:</b> Aircraft color shows which sensors detect it. White = all 3 sensors (trilateration lock).</p>
        <p style="margin-bottom:8px;"><b>Sync ΔT:</b> Sub-millisecond clock alignment between sensors (PPS-disciplined via u-blox F9P RTK).</p>
        <p style="margin-bottom:8px;"><b>Anomalies:</b> Physics-based spoofing detection &mdash; flags aircraft violating momentum, RF propagation, or kinematic constraints.</p>
        <p style="margin-bottom:8px;"><b>GPS Health:</b> Monitors ground sensor EPH (estimated position error). Green = all sensors &lt;20m. Yellow = degraded. Red = possible jamming.</p>
        <p style="margin-bottom:4px;color:#8b949e;"><b>+ EXPERT</b> reveals GNSS accuracy, CPU temp, and system load per sensor.</p>
        <div style="margin-top:10px;padding-top:8px;border-top:1px solid #30363d;color:#8b949e;font-size:11px;">Team 9 · AI Neural Networks 2026 · AI Academy</div>
        <button onclick="toggleInfo()" style="position:absolute;top:8px;right:12px;background:none;border:none;color:#8b949e;cursor:pointer;font-size:16px;">✕</button>
    </div>

        <!-- Feature 4: Connection status badge -->
        <div id="conn-badge" class="live">● LIVE</div>
        <!-- Audio callout toggle -->
        <button id="audio-btn" title="Toggle audio callouts" onclick="toggleAudio()">🔇 AUDIO</button>
        <!-- Cursor coordinate display -->
        <div id="cursor-coords">—</div>

        <!-- Feature 9: Coverage ring toggle buttons -->
        <div id="ring-controls">
            <button class="ring-btn active" id="btn-inner" onclick="toggleRings('inner')">◯ 100 km</button>
            <button class="ring-btn active" id="btn-outer" onclick="toggleRings('outer')">◯ 200 km</button>
        </div>

        <!-- Feature 6: Altitude filter -->
        <div id="alt-filter">
            <label>ALT</label>
            <input type="range" id="alt-min" min="0" max="45000" step="1000" value="0">
            <span id="alt-min-lbl">GND</span>
            <label>–</label>
            <input type="range" id="alt-max" min="0" max="45000" step="1000" value="45000">
            <span id="alt-max-lbl">45k</span>
            <label>ft</label>
        </div>
    </div>

    <!-- v4.0: Three.js 3D Sky View canvas (hidden until activated) -->
    <canvas id="canvas-3d"></canvas>
    <!-- v4.0: Sky controls overlay — visible only in 3D mode -->
    <div id="sky-controls">
        <label>ALT EXAG</label>
        <input type="range" id="alt-exag" min="1" max="50" step="1" value="10">
        <span class="val" id="alt-exag-lbl">10×</span>
        <span class="hint">&nbsp;|&nbsp; T: toggle view &nbsp; R: reset camera</span>
    </div>

    <div id="dashboard">
        <!-- Feature 10: Mobile summary bar (hidden on desktop) -->
        <div id="mobile-bar" onclick="toggleMobileDashboard()">
            <span>◈ <span id="mob-ac">0</span> TRACKS &nbsp;·&nbsp; ΔT <span id="mob-sync">0.00</span> ms</span>
            <span id="mobile-chevron">∧</span>
        </div>

        <div class="panel panel-sync">
            <div class="label">SYS SYNC ΔT</div>
            <div id="sync-delta" class="value-big">0.00</div>
            <div style="font-size:0.9em;color:#3d8060;letter-spacing:1px;">MS</div>
            <div id="sync-detail" class="value-sub"></div>
            <div style="margin-top:20px;">
                <div class="label">TRACKS</div>
                <div id="ac-count" class="value-big" style="font-size:2em;">0</div>
                <div id="last-update" style="font-size:0.65em;color:#8b949e;margin-top:2px;">—</div>
                <div id="gps-health" style="font-size:0.7em;margin-top:4px;padding:2px 6px;border-radius:3px;background:rgba(63,185,80,0.15);color:#3fb950;border:1px solid rgba(63,185,80,0.3);">GPS: OK</div>
            </div>
        </div>

        <div class="panel panel-sensors">
            <div class="label">NODE HEALTH <button id="expert-btn" onclick="toggleExpert()" style="background:none;border:1px solid #30363d;color:#8b949e;font-size:1em;padding:4px 10px;cursor:pointer;border-radius:3px;margin-left:8px;font-family:monospace;">+ EXPERT</button> <span id="accuracy-score" style="font-size:0.85em;margin-left:6px;color:#8b949e;"></span></div>
            <div class="sensor-grid">
                <div class="sensor-card" id="card-north">
                    <div class="name" style="color:#58a6ff;">▲ NORTH</div>
                    <div class="row"><span class="k">Signal</span><span class="v" id="n-sig">—</span></div>
                    <div class="row"><span class="k">SNR</span><span class="v" id="n-snr">—</span></div>
                    <div class="row"><span class="k">Gain</span><span class="v" id="n-gain">—</span></div>
                    <div class="row"><span class="k">Msg/min</span><span class="v" id="n-msg">—</span></div>
                    <div class="row"><span class="k">Max Range</span><span class="v" id="n-range">—</span></div>
                    <div class="row"><span class="k">AC (pos/all)</span><span class="v" id="n-ac">—</span></div>
                    <div class="row expert-row" style="display:none;"><span class="k">CPU</span><span class="v" id="n-temp">—</span></div>
                    <div class="row expert-row" style="display:none;"><span class="k">Load</span><span class="v" id="n-load">—</span></div>
                    <div class="row expert-row" style="display:none;"><span class="k">GNSS std</span><span class="v" id="n-gnss-std">&mdash;</span></div>
                    <div class="row expert-row" style="display:none;"><span class="k">GNSS eph</span><span class="v" id="n-gnss-eph">&mdash;</span></div>
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
                    <div class="row expert-row" style="display:none;"><span class="k">CPU</span><span class="v" id="w-temp">—</span></div>
                    <div class="row expert-row" style="display:none;"><span class="k">Load</span><span class="v" id="w-load">—</span></div>
                    <div class="row expert-row" style="display:none;"><span class="k">GNSS std</span><span class="v" id="w-gnss-std">&mdash;</span></div>
                    <div class="row expert-row" style="display:none;"><span class="k">GNSS eph</span><span class="v" id="w-gnss-eph">&mdash;</span></div>
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
                    <div class="row expert-row" style="display:none;"><span class="k">CPU</span><span class="v" id="e-temp">—</span></div>
                    <div class="row expert-row" style="display:none;"><span class="k">Load</span><span class="v" id="e-load">—</span></div>
                    <div class="row expert-row" style="display:none;"><span class="k">GNSS std</span><span class="v" id="e-gnss-std">&mdash;</span></div>
                    <div class="row expert-row" style="display:none;"><span class="k">GNSS eph</span><span class="v" id="e-gnss-eph">&mdash;</span></div>
                    <div class="snr-bar"><div class="snr-bar-fill" id="e-bar" style="width:0%;background:#f85149;"></div></div>
                </div>
            </div>
        </div>

        <div class="panel panel-legend">
            <div class="label">SA COVERAGE // SENSOR LOCK</div>
            <div class="legend-grid">
                <div class="legend-item"><span class="dot" style="background:#58a6ff"></span>North <span id="cnt-n" style="color:#3d6050;margin-left:auto;">0</span></div>
                <div class="legend-item"><span class="dot" style="background:#39c5cf"></span>N+W   <span id="cnt-nw" style="color:#3d6050;margin-left:auto;">0</span></div>
                <div class="legend-item"><span class="dot" style="background:#3fb950"></span>West  <span id="cnt-w" style="color:#3d6050;margin-left:auto;">0</span></div>
                <div class="legend-item"><span class="dot" style="background:#d2a8ff"></span>N+E   <span id="cnt-ne" style="color:#3d6050;margin-left:auto;">0</span></div>
                <div class="legend-item"><span class="dot" style="background:#f85149"></span>East  <span id="cnt-e" style="color:#3d6050;margin-left:auto;">0</span></div>
                <div class="legend-item"><span class="dot" style="background:#d29922"></span>W+E   <span id="cnt-we" style="color:#3d6050;margin-left:auto;">0</span></div>
                <div class="legend-item" style="grid-column:span 2;margin-top:4px;padding-top:4px;border-top:1px solid rgba(0,200,120,0.15);">
                    <span class="dot" style="background:#fff;box-shadow:0 0 8px #fff;"></span>
                    <b style="color:#e8b84b;">TRILATERATION LOCK</b>
                    <span id="cnt-all" style="color:#e8b84b;margin-left:auto;">0</span>
                </div>
                <!-- Feature 7: Anomaly count row -->
                <div class="legend-item" style="grid-column:span 2;margin-top:2px;">
                    <span style="margin-right:8px;color:#d29922;">⚑</span>ANOMALIES
                    <span id="cnt-anomaly" style="color:#d29922;font-weight:bold;margin-left:auto;">0</span>
                </div>
                <!-- v3.4: Spoofing suspects row -->
                <div class="legend-item" style="grid-column:span 2;margin-top:2px;">
                    <span style="margin-right:8px;color:#f85149;">◈</span>SPOOF SUSPECTS
                    <span id="cnt-spoof" style="color:#f85149;font-weight:bold;margin-left:auto;">0</span>
                </div>
                <!-- UAV/unmanned aircraft row -->
                <div class="legend-item" style="grid-column:span 2;margin-top:2px;">
                    <span style="margin-right:8px;color:#5dd8ff;">⬡</span>UAV / UNMANNED
                    <span id="cnt-uav" style="color:#5dd8ff;font-weight:bold;margin-left:auto;">0</span>
                </div>
            </div>

        </div>
    </div>

<button id="collapse-btn" onclick="toggleDashboard()">▲ PANELS</button>
    <div id="anomaly-toast"></div>
<script>
function toggleDashboard() {
    var d = document.getElementById('dashboard');
    var btn = document.getElementById('collapse-btn');
    d.classList.toggle('collapsed');
    if (d.classList.contains('collapsed')) {
        document.getElementById('map').style.height = '100vh';
        btn.textContent = '▼ PANELS';
        btn.style.bottom = '8px';
    } else {
        document.getElementById('map').style.height = '';
        btn.textContent = '▲ PANELS';
        btn.style.bottom = '';
    }
    if (window.map) setTimeout(function(){ map.invalidateSize(); }, 350);
}
// ── DMS toggle for popup ─────────────────────────
var dmsMode = false;
function dmsBtnHTML(latDD, lonDD, latDMS, lonDMS, hex) {
    return '<button id="dms-btn-'+hex+'" style="font-size:0.8em;padding:1px 6px;margin:2px 0 4px;'
        + 'background:rgba(4,8,13,0.9);border:1px solid rgba(0,200,120,0.3);color:#a8e6c8;'
        + 'cursor:pointer;font-family:monospace;border-radius:2px;"'
        + ' onclick="toggleDMS(event,&#39;'+hex+'&#39;)">&#x21C5; DDM ↔ DMS</button>'
        + '<div class="latlon" id="latlon-'+hex+'">'
        + '<span class="dd" style="display:block">'+latDD+'</span>'
        + '<span class="dms" style="display:none">'+latDMS+'</span>'
        + '<span class="dd" style="display:block">'+lonDD+'</span>'
        + '<span class="dms" style="display:none">'+lonDMS+'</span>'
        + '</div>';
}
window.toggleDMS = function(ev, hex) {
    ev && ev.stopPropagation();
    var el = document.getElementById('latlon-'+hex);
    if (!el) return;
    var dd = el.querySelectorAll('.dd');
    var dm = el.querySelectorAll('.dms');
    var show = dd[0].style.display === 'none';
    dd.forEach(function(s){s.style.display = show ? 'block' : 'none';});
    dm.forEach(function(s){s.style.display = show ? 'none' : 'block';});
};

// ── Feature 8: ICAO ADS-B category lookup table ────────────────────────────
var CAT_LABELS = {
    "A0":"Unknown","A1":"Light (<15 500 lbs)","A2":"Small (15 500–75 000 lbs)",
    "A3":"Large (75 000–300 000 lbs)","A4":"B757","A5":"Heavy (>300 000 lbs)",
    "A6":"High Performance","A7":"Rotorcraft",
    "B0":"Unknown","B1":"Glider/Sailplane","B2":"Lighter-than-air",
    "B3":"Parachutist","B4":"UAV/Drone","B5":"Space","B6":"UAV","B7":"UAV",
    "C0":"Unknown","C1":"Emergency Surface","C2":"Service Surface",
    "C3":"Fixed Ground Obstruction","C4":"Cluster Obstacle","C5":"Line Obstacle",
    "C6":"Spare","C7":"Spare"
};
// ── Tooltip helper ─────────────────────────────────
function showTooltip(el, text) {
    var tip = document.getElementById('map-tooltip');
    if (!tip) {
        tip = document.createElement('div');
        tip.id = 'map-tooltip';
        tip.style.cssText = 'position:fixed;background:rgba(4,8,13,0.92);border:1px solid rgba(0,200,120,0.35);'
            + 'color:#a8e6c8;padding:4px 10px;border-radius:2px;font-size:0.78em;'
            + 'font-family:"Courier New",monospace;pointer-events:none;z-index:3000;'
            + 'box-shadow:0 0 12px rgba(0,200,120,0.15);white-space:nowrap;transition:opacity 0.15s;';
        document.body.appendChild(tip);
    }
    if (!text) { tip.style.opacity = '0'; return; }
    tip.textContent = text;
    var rect = el.getBoundingClientRect();
    tip.style.left = (rect.left + rect.width/2 - tip.offsetWidth/2) + 'px';
    tip.style.top  = (rect.bottom + 8) + 'px';
    tip.style.opacity = '1';
}

// ── Temperature thresholds for sensor health colour coding ─────────────────
var TEMP_WARN_C = 60;   // °C — amber above this
var TEMP_CRIT_C = 75;   // °C — red above this

// ── Map setup ──────────────────────────────────────────────────────────────
var map = L.map('map', {zoomControl:false});
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{attribution:''}).addTo(map);

// Per-aircraft layer stores
var markers = {}, labels = {}, arrows = {}, trails = {}, tdoaCircles = {}, anomalyRings = {}, spoofRings = {}, uavRings = {};

// Client-side last-seen timestamps (Date.now()/1000) for opacity fade
var markerLastSeen = {};

// ── Audio callout system ────────────────────────────────────────────────────
// Uses the Web Speech API (built into all modern browsers, no external deps).
// Audio fires only on STATE TRANSITIONS — entering emergency/UAV status — so
// the same aircraft does not trigger repeated announcements every update cycle.
var audioEnabled = false;
// Previous per-aircraft state for change detection: hex → {emergency, uav}
var acPrevState  = {};
// Speech queue: spoken one at a time to avoid overlap.
var speechQueue  = [];
var speechBusy   = false;

function toggleAudio() {
    audioEnabled = !audioEnabled;
    var btn = document.getElementById('audio-btn');
    if (audioEnabled) {
        btn.textContent = '🔊 AUDIO';
        btn.classList.add('active');
    } else {
        btn.textContent = '🔇 AUDIO';
        btn.classList.remove('active');
        window.speechSynthesis.cancel();
        speechQueue  = [];
        speechBusy   = false;
    }
}

// Speech-synthesis tuning (adjust to taste).
var SPEECH_RATE  = 1.05;   // slightly faster than default (1.0) for conciseness
var SPEECH_PITCH = 1.0;

function speakAlert(text) {
    if (!audioEnabled || !window.speechSynthesis) return;
    speechQueue.push(text);
    flushSpeechQueue();
}

function flushSpeechQueue() {
    if (speechBusy || speechQueue.length === 0) return;
    speechBusy = true;
    var msg = new SpeechSynthesisUtterance(speechQueue.shift());
    msg.rate  = SPEECH_RATE;
    msg.pitch = SPEECH_PITCH;
    msg.onend = function() {
        speechBusy = false;
        flushSpeechQueue();
    };
    msg.onerror = function() {
        speechBusy = false;
        flushSpeechQueue();
    };
    window.speechSynthesis.speak(msg);
}

var nodes = {
    "sensor-north": {pos:[60.319555,24.830816], col:"#58a6ff", lbl:"N"},
    "sensor-west":  {pos:[60.130919,24.512869], col:"#3fb950",  lbl:"W"},
    "sensor-east":  {pos:[60.374069,25.249015], col:"#f85149",  lbl:"E"}
};

// ── Feature 9: Ring layer groups ──────────────────────────────────────────
var innerRingLayer = L.layerGroup().addTo(map);
var outerRingLayer = L.layerGroup().addTo(map);
var ringsVisible   = {inner:true, outer:true};

Object.keys(nodes).forEach(function(id) {
    var n = nodes[id];
    L.circleMarker(n.pos, {radius:8, fillColor:n.col, color:"#fff", weight:2, fillOpacity:1, pane:'markerPane'})
     .addTo(map)
     .bindPopup('<b style="font-family:monospace">NODE: '+id.toUpperCase()+'</b>');
    L.circle(n.pos, {radius:100000, color:n.col, weight:1,   fillOpacity:0, dashArray:'3,8'} ).addTo(innerRingLayer);
    L.circle(n.pos, {radius:200000, color:n.col, weight:0.5, fillOpacity:0, dashArray:'2,12'}).addTo(outerRingLayer);
});

function toggleRings(which) {
    ringsVisible[which] = !ringsVisible[which];
    var layer = which === 'inner' ? innerRingLayer : outerRingLayer;
    var btn   = document.getElementById('btn-' + which);
    if (ringsVisible[which]) { layer.addTo(map);    btn.classList.add('active'); }
    else                     { map.removeLayer(layer); btn.classList.remove('active'); }
}

// Auto-fit to sensor triangle
map.fitBounds(L.latLngBounds([
    nodes["sensor-north"].pos,
    nodes["sensor-west"].pos,
    nodes["sensor-east"].pos
]), {padding:[50,50]});

// Hide flight labels when zoomed out
map.on('zoomend', function() {
    var show = map.getZoom() >= 10;
    document.querySelectorAll('.flight-label').forEach(function(el) {
        el.style.display = show ? 'block' : 'none';
    });
});

// ── Cursor coordinates ─────────────────────────────────────────────────────
var coordEl = document.getElementById('cursor-coords');
map.on('mousemove', function(e) {
    var lat = e.latlng.lat, lon = e.latlng.lng;
    var latStr = Math.abs(lat).toFixed(4) + (lat >= 0 ? '°N' : '°S');
    var lonStr = Math.abs(lon).toFixed(4) + (lon >= 0 ? '°E' : '°W');
    coordEl.textContent = latStr + '  ' + lonStr;
});
map.on('mouseout', function() { coordEl.textContent = '—'; });

// ── Feature 6: Altitude filter state ──────────────────────────────────────
var altMin = 0, altMax = 45000;
document.getElementById('alt-min').addEventListener('input', function() {
    altMin = parseInt(this.value);
    if (altMin >= altMax) { altMin = altMax - 1000; this.value = altMin; }
    document.getElementById('alt-min-lbl').textContent = altMin === 0 ? 'GND' : (altMin/1000).toFixed(0)+'k';
});
document.getElementById('alt-max').addEventListener('input', function() {
    altMax = parseInt(this.value);
    if (altMax <= altMin) { altMax = altMin + 1000; this.value = altMax; }
    document.getElementById('alt-max-lbl').textContent = (altMax/1000).toFixed(0)+'k';
});

// ── Color by sensor coverage ──────────────────────────────────────────────
function getColor(sb) {
    var n=sb.includes("sensor-north"), w=sb.includes("sensor-west"), e=sb.includes("sensor-east");
    if(n&&w&&e) return "#fff";
    if(n&&w)    return "#39c5cf";
    if(n&&e)    return "#d2a8ff";
    if(w&&e)    return "#d29922";
    if(n)       return "#58a6ff";
    if(w)       return "#3fb950";
    if(e)       return "#f85149";
    return "#888";
}

// ── Heading arrow SVG (top-down aircraft silhouette) ──────────────────────
function arrowSvg(track, col) {
    var rot = track || 0;
    return '<svg width="26" height="26" viewBox="0 0 26 26" xmlns="http://www.w3.org/2000/svg">' +
        '<g transform="rotate('+rot+',13,13)">' +
        '<path d="M13,1 L11,11 L2,15 L11,15 L10,23 L13,21 L16,23 L15,15 L24,15 L15,11 Z"' +
        ' fill="'+col+'" stroke="#000" stroke-width="0.7" opacity="0.95"/>' +
        '</g></svg>';
}

// ── Sensor health row updater ──────────────────────────────────────────────
function updateSensor(prefix, s) {
    var snr = (s.signal && s.noise) ? (s.signal - s.noise).toFixed(1) : '—';
    document.getElementById(prefix+'-sig').textContent   = s.signal      ? s.signal.toFixed(1)+' dB'  : '—';
    document.getElementById(prefix+'-snr').textContent   = snr !== '—'   ? snr+' dB'                  : '—';
    document.getElementById(prefix+'-gain').textContent  = s.gain_db     ? s.gain_db+' dB'             : '—';
    document.getElementById(prefix+'-msg').textContent   = s.msg_rate    ? s.msg_rate.toLocaleString() : '—';
    document.getElementById(prefix+'-range').textContent = s.max_range_km? s.max_range_km+' km'        : '—';
    document.getElementById(prefix+'-ac').textContent    = (s.ac_with_pos||0)+'/'+(s.ac_total||0);
    var pct = snr !== '—' ? Math.min(Math.max(parseFloat(snr)/30*100, 0), 100) : 0;
    document.getElementById(prefix+'-bar').style.width = pct+'%';

    // System telemetry: temperature and CPU load
    var tempEl = document.getElementById(prefix+'-temp');
    var loadEl = document.getElementById(prefix+'-load');
    if (s.temp_c != null) {
        var t = parseFloat(s.temp_c);
        var tcol = t >= TEMP_CRIT_C ? '#f85149' : t >= TEMP_WARN_C ? '#d29922' : '#3fb950';
        tempEl.textContent = t.toFixed(1)+'°C';
        tempEl.style.color = tcol;
    } else {
        tempEl.textContent = '—';
        tempEl.style.color = '';
    }
    if (s.load_1m != null) {
        loadEl.textContent = parseFloat(s.load_1m).toFixed(2);
        loadEl.style.color = '';
    } else {
        loadEl.textContent = '—';
        loadEl.style.color = '';
    }
}

// ── Feature 4: Connection state indicator ─────────────────────────────────
var lastUpdateTime = Date.now();  // initialise so stale-check doesn't trigger immediately on connect
var connBadge = document.getElementById('conn-badge');

// Helper: escape HTML special characters for safe insertion
function escapeHtml(text) {
    if (!text) return '';
    return text.toString()
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}


function toggleExpert() {
    var rows = document.querySelectorAll(".expert-row");
    var btn = document.getElementById("expert-btn");
    var mapEl = document.getElementById("map");
    var dashEl = document.getElementById("dashboard");
    var showing = rows[0] && rows[0].style.display !== "none";
    rows.forEach(function(r) { r.style.display = showing ? "none" : "flex"; });
    btn.textContent = showing ? "+ EXPERT" : "- EXPERT";
    btn.style.color = showing ? "#8b949e" : "#11caa0";
    // Resize panels
    if (showing) {
        mapEl.style.height = "75vh";
        dashEl.style.height = "25vh";
        dashEl.style.overflow = "hidden";
    } else {
        mapEl.style.height = "60vh";
        dashEl.style.height = "40vh";
        dashEl.style.overflow = "auto";
    }
    // Trigger map resize
    if (window.map) window.map.invalidateSize();
}


function toggleInfo() {
    var popup = document.getElementById("info-popup");
    popup.style.display = popup.style.display === "none" ? "block" : "none";
}

var socket = io();

socket.on('connect', function() {
    connBadge.className = 'live';
    connBadge.textContent = '● LIVE';
    lastUpdateTime = Date.now();
});
socket.on('disconnect', function() {
    connBadge.className = 'disconnected';
    connBadge.textContent = '● DISCONNECTED';
});

setInterval(function() {
    if (!socket.connected) {
        connBadge.className = 'disconnected';
        connBadge.textContent = '● DISCONNECTED';
        return;
    }
    var age = (Date.now() - lastUpdateTime) / 1000;
    if      (age < 3)  { connBadge.className = 'live';  connBadge.textContent = '● LIVE'; }
    else if (age < 10) { connBadge.className = 'stale'; connBadge.textContent = '● STALE ('+age.toFixed(0)+'s)'; }
    else               { connBadge.className = 'stale'; connBadge.textContent = '● STALE ('+age.toFixed(0)+'s)'; }
}, 1000);

// ── Feature 5: Opacity fade for ageing aircraft ───────────────────────────
// Aircraft are removed server-side at 15 s.  Start fading at 10 s so the
// disappearance feels smooth rather than a hard cut.
setInterval(function() {
    var now = Date.now() / 1000;
    Object.keys(markers).forEach(function(h) {
        var ls = markerLastSeen[h];
        if (!ls) return;
        var age = now - ls;
        var opacity = age > 10 ? Math.max(0.2, 1 - (age - 10) / 5) : 1.0;
        try { markers[h].setStyle({fillOpacity: opacity * 0.9}); } catch(ignored) {}
    });
    Object.keys(arrows).forEach(function(h) {
        var ls = markerLastSeen[h];
        if (!ls) return;
        var age = now - ls;
        var opacity = age > 10 ? Math.max(0.2, 1 - (age - 10) / 5) : 1.0;
        try { arrows[h].setOpacity(opacity); } catch(ignored) {}
    });
}, 500);

// ── Feature 10: Mobile dashboard toggle ───────────────────────────────────
function toggleMobileDashboard() {
    document.getElementById('dashboard').classList.toggle('expanded');
}

// ── Main map_update handler ───────────────────────────────────────────────
socket.on('map_update', function(data) {
    lastUpdateTime = Date.now();

    // Sync panel
    var dEl = document.getElementById('sync-delta');
    dEl.textContent  = data.sync.delta_ms.toFixed(2);
    dEl.style.color  = data.sync.delta_ms < 50 ? '#3fb950' : data.sync.delta_ms < 200 ? '#d29922' : '#f85149';

    var ps = data.sync.per_sensor || {};
    var psVals = Object.values(ps).filter(function(v){ return v > 0; });
    var refTime = psVals.length ? Math.min.apply(null, psVals) : 0;
    var detail = Object.entries(ps).map(function(e) {
        var short = e[0].replace('sensor-','').charAt(0).toUpperCase();
        var off = ((e[1] - refTime) % 1.0) * 1000;
        if (off > 500) off = off - 1000;
        return short+':'+off.toFixed(0)+'ms';
    }).join(' ');
    document.getElementById('sync-detail').textContent = detail;

    // Sensor health
    if (data.sensors) {
        if (data.sensors["sensor-north"]) updateSensor('n', data.sensors["sensor-north"]);
        if (data.sensors["sensor-west"])  updateSensor('w', data.sensors["sensor-west"]);
        if (data.sensors["sensor-east"])  updateSensor('e', data.sensors["sensor-east"]);

        // ── GNSS Accuracy panel update ──
        try {
        if (data.accuracy && data.accuracy.gnss) {
            var g = data.accuracy.gnss;
            if (g["sensor-north"]) {
                document.getElementById("n-gnss-std").textContent = g["sensor-north"].horizontal_std_m.toFixed(2);
                document.getElementById("n-gnss-eph").textContent = (g["sensor-north"].eph_m || "—");
            }
            if (g["sensor-west"]) {
                document.getElementById("w-gnss-std").textContent = g["sensor-west"].horizontal_std_m.toFixed(2);
                document.getElementById("w-gnss-eph").textContent = (g["sensor-west"].eph_m || "—");
            }
            if (g["sensor-east"]) {
                document.getElementById("e-gnss-std").textContent = g["sensor-east"].horizontal_std_m.toFixed(2);
                document.getElementById("e-gnss-eph").textContent = (g["sensor-east"].eph_m || "—");
            }
        }
        if (data.accuracy && data.accuracy.aggregate) {
            var agg = data.accuracy.aggregate;
            var score = agg.consistency_score;
            var el = document.getElementById("accuracy-score");
            el.textContent = "⚡ " + (score * 100).toFixed(0) + "%";
            el.style.color = score > 0.8 ? "#3fb950" : score > 0.5 ? "#d29922" : "#f85149";
            // GPS Health indicator — based on ground sensor EPH
            var gpsEl = document.getElementById("gps-health");
            if (gpsEl && data.accuracy && data.accuracy.gnss) {
                var gnss = data.accuracy.gnss;
                var maxEph = 0;
                var allOk = true;
                for (var s in gnss) {
                    var eph = gnss[s].eph_m || 0;
                    if (eph > maxEph) maxEph = eph;
                    if (eph > 50) allOk = false;
                }
                if (maxEph < 200) {
                    gpsEl.textContent = "GPS: OK";
                    gpsEl.style.color = "#3fb950";
                    gpsEl.style.borderColor = "rgba(63,185,80,0.3)";
                    gpsEl.style.background = "rgba(63,185,80,0.1)";
                } else if (maxEph < 500) {
                    gpsEl.textContent = "GPS: DEGRADED";
                    gpsEl.style.color = "#d29922";
                    gpsEl.style.borderColor = "rgba(210,153,34,0.3)";
                    gpsEl.style.background = "rgba(210,153,34,0.1)";
                } else {
                    gpsEl.textContent = "GPS: JAMMED?";
                    gpsEl.style.color = "#f85149";
                    gpsEl.style.borderColor = "rgba(248,81,73,0.3)";
                    gpsEl.style.background = "rgba(248,81,73,0.1)";
                }
            }
            // Expert panel extras
            var ve = document.getElementById("exp-vel-err"); // may not exist
            if (ve) ve.textContent = agg.vel_error_mean_kt.toFixed(1);
            var re = document.getElementById("exp-rssi-err");
            if (re) re.textContent = agg.rssi_error_mean_dB.toFixed(1);
            var mu = document.getElementById("exp-multi");
            if (mu) mu.textContent = agg.multi_sensor_aircraft;
            var tr = document.getElementById("exp-trilat");
            if (tr) tr.textContent = agg.trilateration_aircraft;
        }
        } catch(e) { /* accuracy elements may not exist */ }

    }

    // Aircraft total count + mobile bar
    document.getElementById('ac-count').textContent  = data.aircraft.length;
    document.getElementById('last-update').textContent = 'live';
    document.getElementById('last-update').style.color = '#3fb950';
    clearTimeout(window._staleTimer);
    window._staleTimer = setTimeout(function() {
        document.getElementById('last-update').textContent = 'stale';
        document.getElementById('last-update').style.color = '#f85149';
    }, 5000);
    document.getElementById('mob-ac').textContent    = data.aircraft.length;
    document.getElementById('mob-sync').textContent  = data.sync.delta_ms.toFixed(2);

    // ── Feature 6: Altitude filter ────────────────────────────────────────
    var filtered = data.aircraft.filter(function(ac) {
        if (ac.alt === "ground" || ac.alt === "Ground") return altMin === 0;
        var a = parseInt(ac.alt) || 0;
        return a >= altMin && a <= altMax;
    });

    var activeHexes    = new Set();
    var allServerHexes = new Set(data.aircraft.map(function(a) { return a.hex; }));
    var counts         = {n:0, w:0, e:0, nw:0, ne:0, we:0, all:0};
    var emergencyMsgs  = [];
    var uavMsgs        = [];
    var anomalyCount   = 0;
    var spoofCount     = 0;
    var uavCount       = 0;

    filtered.forEach(function(ac) {
        activeHexes.add(ac.hex);
        var col = getColor(ac.seen_by);
        var loc = L.latLng(ac.lat, ac.lon);
        var callsign = ac.flight || ac.hex.toUpperCase();
        var altStr   = (ac.alt === "ground" || ac.alt === "Ground")
                       ? "GND"
                       : (ac.alt ? parseInt(ac.alt).toLocaleString()+"ft" : "?");

        // Store client-side timestamp for opacity fade (Feature 5)
        markerLastSeen[ac.hex] = Date.now() / 1000;

        // Coverage counts
        var n=ac.seen_by.includes("sensor-north"),
            w=ac.seen_by.includes("sensor-west"),
            e=ac.seen_by.includes("sensor-east");
        ac._trilat = (n&&w&&e);
        if(n&&w&&e) counts.all++;
        else if(n&&w) counts.nw++;
        else if(n&&e) counts.ne++;
        else if(w&&e) counts.we++;
        else if(n)    counts.n++;
        else if(w)    counts.w++;
        else if(e)    counts.e++;

        // Feature 2: collect emergency squawks
        if (ac.emergency) emergencyMsgs.push('⚠ '+callsign+' SQUAWK '+ac.squawk);

        // UAV/unmanned aircraft detection
        var isUav = !!ac.uav;
        if (isUav) {
            uavCount++;
            uavMsgs.push('⬡ '+callsign+' UNMANNED');
        }

        // ── Audio: speak on state transitions only ────────────────────────
        // Compare current emergency/uav flags to what they were last cycle;
        // announce only when an aircraft ENTERS a flagged state.
        var prev = acPrevState[ac.hex] || {};
        if (ac.emergency && !prev.emergency) {
            speakAlert('Emergency squawk ' + (ac.squawk || 'unknown') + ' ' + callsign);
        }
        if (isUav && !prev.uav) {
            speakAlert('Unmanned aircraft ' + callsign);
        }
        acPrevState[ac.hex] = {emergency: !!ac.emergency, uav: isUav};

        // Feature 7: anomaly count
        if (ac.anomaly_score === -1) anomalyCount++;

        // v3.4: spoof count — threshold raised to 0.35 to reduce false positives
        var spoofScore = ac.spoof_score || 0;
        if (spoofScore >= 0.35) spoofCount++;

        // v3.4: ghost aircraft = single-sensor high-altitude (matches server spoof threshold)
        var isGhost = (ac.seen_by.length === 1 && typeof ac.alt === 'number' && ac.alt > 25000);

        // Sensor distances for popup
        var dN = n ? (map.distance(loc, L.latLng(nodes["sensor-north"].pos))/1000).toFixed(1)+' km' : '—';
        var dW = w ? (map.distance(loc, L.latLng(nodes["sensor-west"].pos))/1000).toFixed(1)+' km'  : '—';
        var dE = e ? (map.distance(loc, L.latLng(nodes["sensor-east"].pos))/1000).toFixed(1)+' km'  : '—';

        // Feature 8: decoded category label
        var catLabel = ac.category ? (CAT_LABELS[ac.category] || ac.category) : '—';

        // Feature 7: anomaly badge for popup (prefer v2 enriched data)
        var anomalyBadge = '—';
        if (ac.anomaly_score !== null && ac.anomaly_score !== undefined) {
            var v2 = ac.anomaly_v2;
            if (v2 && v2.label !== undefined) {
                var v2Color = v2.label === -1 ? '#d29922' : '#3fb950';
                var v2Label = v2.label === -1 ? '⚠ ANOMALY' : '✓ Normal';
                var v2Conf = v2.confidence !== undefined ? ' [' + (v2.confidence * 100).toFixed(0) + '%]' : '';
                var v2Flags = (v2.flags && v2.flags.length) ? ' [' + v2.flags.join(', ') + ']' : '';
                anomalyBadge = '<span style="color:' + v2Color + ';" title="Score: ' +
                    (v2.score !== undefined ? v2.score.toFixed(3) : '—') + '">' +
                    v2Label + v2Conf + v2Flags + '</span>';
            } else {
                // Fallback to v1 simple score
                anomalyBadge = '<span style="color:' + (ac.anomaly_score === -1 ? '#d29922' : '#3fb950') + ';">'
                    + (ac.anomaly_score === -1 ? '⚠ ANOMALY' : '✓ Normal') + '</span>';
            }
        }

        // Feature 3: TDOA uncertainty info for popup
        var tdoaStr = '';
        if (ac.tdoa_uncertainty_m !== undefined) {
            var um = ac.tdoa_uncertainty_m;
            tdoaStr = '<hr style="border:0;border-top:1px dashed rgba(0,200,120,0.2);margin:6px 0;">'
                    + '<span style="color:#3d8060;font-size:0.9em;">TDOA UNCERTAINTY:</span><br>'
                    + (um < 1000 ? um.toFixed(0)+' m' : (um/1000).toFixed(1)+' km')+' radius<br>';
        }

        // v3.4: spoof score badge for popup
        var spoofBadge = '';
        if (spoofScore > 0) {
            var scol = spoofScore >= 0.5 ? '#f85149' : '#d29922';
            var pct  = Math.round(spoofScore * 100);
            var flagStr = (ac.spoof_flags && ac.spoof_flags.length) ? ac.spoof_flags.join(', ') : '';
            spoofBadge = '<hr style="border:0;border-top:1px dashed rgba(0,200,120,0.2);margin:6px 0;">'
                + '<span style="color:'+scol+';font-weight:bold;">&#9889; SPOOF: '+pct+'%</span>'
                + (flagStr ? '<br><span style="color:#3d8060;font-size:0.85em;">'+flagStr+'</span>' : '');
        }

        // MLAT position block with DMS toggle
        var mlatBlock = '—';
        if (ac.mlat_lat != null && ac.mlat_lon != null) {
            var latDD = ac.mlat_lat.toFixed(4) + '°';
            var lonDD = ac.mlat_lon.toFixed(4) + '°';
            var latDMS = ac.mlat_lat_dms || latDD;
            var lonDMS = ac.mlat_lon_dms || lonDD;
            mlatBlock = dmsBtnHTML(latDD, lonDD, latDMS, lonDMS, ac.hex);
        }
        var staleBadge = ac.mlat_stale ? ' <span style="color:#d29922;font-size:0.85em;">⚠ stale</span>' : '';

        var popupHTML =
            '<div style="font-family:monospace;min-width:175px;">'
            +(ac.emergency ? '<div style="color:#f85149;font-weight:bold;margin-bottom:4px;">⚠ EMERGENCY SQUAWK</div>' : '')
            +(isUav ? '<div style="color:#5dd8ff;font-weight:bold;margin-bottom:4px;">⬡ UNMANNED AIRCRAFT</div>' : '')
            +'<b style="color:'+col+';font-size:1.2em;">'+escapeHtml(callsign)+'</b><br>'
            +'ICAO: '+ac.hex+'<br>'
            +'SQWK: '+(ac.squawk||'—')+(ac.emergency?' <b style="color:#f85149;">⚠</b>':'')+(isUav?' <b style="color:#5dd8ff;">⬡</b>':'')+'<br>'
            +'ALT : '+altStr+'<br>'
            +'GS  : '+(ac.gs ? ac.gs.toFixed(0)+' kt' : '—')+'<br>'
            +'HDG : '+(ac.track != null ? ac.track.toFixed(0)+'°' : '—')+'<br>'
            +'RSSI: '+(ac.rssi ? ac.rssi.toFixed(1)+' dB' : '—')+'<br>'
            +'TYPE: '+(ac.type||'—')+'<br>'
            +'CAT : '+catLabel+'<br>'
            +'MLAT: '+anomalyBadge+staleBadge+'<br>'
            +(ac.mlat_lat!=null ? dmsBtnHTML(ac.mlat_lat.toFixed(4)+'°', ac.mlat_lon.toFixed(4)+'°', ac.mlat_lat_dms||ac.mlat_lat.toFixed(4)+'°', ac.mlat_lon_dms||ac.mlat_lon.toFixed(4)+'°', ac.hex) : 'MLAT: —')
            +'<br>'
            +'<span style="color:'+(ac.mlat_stale?'#d29922':'#3fb950')+';font-size:0.95em;">MLAT_CONF: '+(ac.mlat_confidence!=null?(ac.mlat_confidence*100).toFixed(1)+' %':'—')+'</span><br>'
            +'<hr style="border:0;border-top:1px dashed rgba(0,200,120,0.2);margin:6px 0;">'
            +'<span style="color:#3d8060;font-size:0.9em;">RANGES:</span><br>'
            +'<span style="color:#58a6ff">[N]</span> '+dN+'<br>'
            +'<span style="color:#3fb950">[W]</span> '+dW+'<br>'
            +'<span style="color:#f85149">[E]</span> '+dE+'<br>'
            +tdoaStr
            +'<span style="color:#3d8060;font-size:0.85em;">Sensors: '+ac.seen_by.length+'/3</span>'
            +spoofBadge
            +(isGhost ? '<br><span style="color:#d29922;font-size:0.85em;">&#9655; GHOST candidate</span>' : '')
            +'</div>';

        // ── Feature 1: Trail polyline ─────────────────────────────────────
        if (ac.trail && ac.trail.length > 1) {
            var trailPts = ac.trail.map(function(p) { return L.latLng(p[0], p[1]); });
            if (trails[ac.hex]) {
                trails[ac.hex].setLatLngs(trailPts).setStyle({color: col});
            } else {
                trails[ac.hex] = L.polyline(trailPts, {
                    color: col, weight:1.5, opacity:0.45, dashArray:'4,4', interactive:false
                }).addTo(map);
            }
        }

        // ── Feature 3: TDOA uncertainty circle ────────────────────────────
        if (ac.tdoa_uncertainty_m !== undefined && ac.tdoa_uncertainty_m > 0) {
            // Cap visual radius at 200 km to keep map readable
            var r = Math.min(ac.tdoa_uncertainty_m, 200000);
            if (tdoaCircles[ac.hex]) {
                tdoaCircles[ac.hex].setLatLng(loc).setRadius(r);
            } else {
                tdoaCircles[ac.hex] = L.circle(loc, {
                    radius: r, color:'#f0a000', weight:1,
                    fillOpacity:0.05, dashArray:'3,6', interactive:false
                }).addTo(map);
            }
        }

        // ── Feature 7/7v2: Anomaly outer ring (enriched v2) ────────────────
        if (ac.anomaly_score === -1) {
            var anomColor = '#d29922';   // default amber
            var anomWidth = 2;
            if (ac.anomaly_v2 && ac.anomaly_v2.confidence !== undefined) {
                var conf = ac.anomaly_v2.confidence;
                // High-confidence anomaly → red pulsing ring
                if (conf >= 0.85) { anomColor = '#f85149'; anomWidth = 3; }
                else if (conf >= 0.65) { anomColor = '#d29922'; anomWidth = 2.5; }
                // else keep amber
            }
            if (anomalyRings[ac.hex]) {
                anomalyRings[ac.hex].setLatLng(loc).setStyle({color: anomColor, weight: anomWidth});
            } else {
                anomalyRings[ac.hex] = L.circleMarker(loc, {
                    radius:14, fillColor:'transparent', color: anomColor,
                    weight: anomWidth, fillOpacity:0, pane:'markerPane', interactive:false
                }).addTo(map);
            }
        }

        // ── v3.4: Spoofing score outer ring ───────────────────────────────
        if (spoofScore >= 0.35) {
            var ringColor  = spoofScore >= 0.5 ? '#f85149' : '#d29922';
            var ringRadius = spoofScore >= 0.5 ? 20 : 17;
            if (spoofRings[ac.hex]) {
                spoofRings[ac.hex].setLatLng(loc).setStyle({color: ringColor, radius: ringRadius});
            } else {
                spoofRings[ac.hex] = L.circleMarker(loc, {
                    radius: ringRadius, fillColor:'transparent', color: ringColor,
                    weight: 2.5, fillOpacity:0, pane:'markerPane', interactive:false,
                    className:'spoof-ring'
                }).addTo(map);
            }
        } else if (spoofRings[ac.hex]) {
            map.removeLayer(spoofRings[ac.hex]);
            delete spoofRings[ac.hex];
        }

        // ── v3.4: Ghost aircraft dashed ring ──────────────────────────────
        if (isGhost && !anomalyRings[ac.hex]) {
            // Reuse anomalyRings slot with a distinct dashed style
            if (anomalyRings[ac.hex]) {
                anomalyRings[ac.hex].setLatLng(loc);
            } else {
                anomalyRings[ac.hex] = L.circleMarker(loc, {
                    radius:16, fillColor:'transparent', color:'#d29922',
                    weight:1.5, fillOpacity:0, dashArray:'3,4',
                    pane:'markerPane', interactive:false
                }).addTo(map);
            }
        }

        // ── UAV/unmanned aircraft ring ────────────────────────────────────
        if (isUav) {
            if (uavRings[ac.hex]) {
                uavRings[ac.hex].setLatLng(loc);
            } else {
                uavRings[ac.hex] = L.circleMarker(loc, {
                    radius:12, fillColor:'transparent', color:'#5dd8ff',
                    weight:2, fillOpacity:0, pane:'markerPane', interactive:false,
                    className:'uav-ring'
                }).addTo(map);
            }
        } else if (uavRings[ac.hex]) {
            map.removeLayer(uavRings[ac.hex]);
            delete uavRings[ac.hex];
        }

        // ── Heading arrow / circle marker ─────────────────────────────────
        var markerCol  = ac.emergency ? '#f85149' : col;
        var emClass    = ac.emergency ? ' class="emergency-marker"' : '';

        if (ac.track != null && ac.gs && ac.gs > 10) {
            var iconHtml = '<div'+emClass+'>'+arrowSvg(ac.track, markerCol)+'</div>';
            var icon = L.divIcon({html:iconHtml, className: '', iconSize:[24,24], iconAnchor:[12,12]});
            if (arrows[ac.hex]) {
                arrows[ac.hex].setLatLng(loc).setIcon(icon);
                if (arrows[ac.hex].getPopup()) arrows[ac.hex].getPopup().setContent(popupHTML);
            } else {
                arrows[ac.hex] = L.marker(loc, {icon:icon, pane:'markerPane'}).bindPopup(popupHTML).addTo(map);
            }
            if (markers[ac.hex]) { map.removeLayer(markers[ac.hex]); delete markers[ac.hex]; }
        } else {
            if (markers[ac.hex]) {
                markers[ac.hex].setLatLng(loc).setStyle({fillColor:markerCol, color:"#000"});
                if (markers[ac.hex].getPopup()) markers[ac.hex].getPopup().setContent(popupHTML);
            } else {
                markers[ac.hex] = L.circleMarker(loc, {
                    radius:6, fillColor:markerCol, color:"#000",
                    weight:1, fillOpacity:0.9,
                    className: ac.emergency ? 'emergency-marker' : ''
                }).bindPopup(popupHTML).addTo(map);
            }
            if (arrows[ac.hex]) { map.removeLayer(arrows[ac.hex]); delete arrows[ac.hex]; }
        }

        // Flight label
        var labelIcon = L.divIcon({
            html:'<span>'+escapeHtml(callsign)+'</span>',
            className:'flight-label', iconSize:[80,14], iconAnchor:[-8,7]
        });
        if (labels[ac.hex]) {
            labels[ac.hex].setLatLng(loc).setIcon(labelIcon);
        } else {
            labels[ac.hex] = L.marker(loc, {icon:labelIcon, interactive:false, pane:'tooltipPane'}).addTo(map);
        }
    });

    // ── Feature 2: Emergency banner ───────────────────────────────────────
    var banner = document.getElementById('emergency-banner');
    if (emergencyMsgs.length > 0) {
        banner.style.display = 'block';
        banner.textContent = emergencyMsgs.join('   |   ');
    } else {
        banner.style.display = 'none';
    }

    // ── UAV banner ────────────────────────────────────────────────────────
    var uavBanner = document.getElementById('uav-banner');
    if (uavMsgs.length > 0) {
        uavBanner.style.display = 'block';
        uavBanner.textContent = uavMsgs.join('   |   ');
    } else {
        uavBanner.style.display = 'none';
    }

    // ── v3.4: Jamming alert banner ────────────────────────────────────────
    var jammingBanner = document.getElementById('jamming-banner');
    var jamList = data.jamming || [];
    if (jamList.length > 0) {
        var jamNames = jamList.map(function(s) { return s.replace('sensor-','').toUpperCase(); });
        jammingBanner.style.display = 'block';
        jammingBanner.textContent   = '&#x26A1; JAMMING DETECTED: ' + jamNames.join(', ')
            + ' — message rate dropped >60%';
    } else {
        jammingBanner.style.display = 'none';
    }

    // Legend counts
    document.getElementById('cnt-n').textContent       = counts.n;
    document.getElementById('cnt-w').textContent       = counts.w;
    document.getElementById('cnt-e').textContent       = counts.e;
    document.getElementById('cnt-nw').textContent      = counts.nw;
    document.getElementById('cnt-ne').textContent      = counts.ne;
    document.getElementById('cnt-we').textContent      = counts.we;
    document.getElementById('cnt-all').textContent     = counts.all;
    document.getElementById('cnt-anomaly').textContent = anomalyCount;
    document.getElementById('cnt-spoof').textContent   = spoofCount;
            if (spoofCount > (window._lastSpoofCount || 0)) {
                var toast = document.getElementById('anomaly-toast');
                toast.textContent = '⚠ SPOOF SUSPECT (' + spoofCount + ')';
                toast.classList.add('show');
                clearTimeout(window._toastTimer);
                window._toastTimer = setTimeout(function(){ toast.classList.remove('show'); }, 5000);
            }
            window._lastSpoofCount = spoofCount;
    document.getElementById('cnt-uav').textContent     = uavCount;

    // Clean up markers for aircraft no longer in the current display set
    // Use allServerHexes for markerLastSeen cleanup (keep data for off-screen filtered aircraft)
    // Use activeHexes for map layer cleanup (respect altitude filter)
    var hx;
    for (hx in markers)      { if (!activeHexes.has(hx))    { map.removeLayer(markers[hx]);      delete markers[hx]; } }
    for (hx in arrows)        { if (!activeHexes.has(hx))    { map.removeLayer(arrows[hx]);        delete arrows[hx]; } }
    for (hx in labels)        { if (!activeHexes.has(hx))    { map.removeLayer(labels[hx]);        delete labels[hx]; } }
    for (hx in trails)        { if (!activeHexes.has(hx))    { map.removeLayer(trails[hx]);        delete trails[hx]; } }
    for (hx in tdoaCircles)   { if (!activeHexes.has(hx))    { map.removeLayer(tdoaCircles[hx]);   delete tdoaCircles[hx]; } }
    for (hx in anomalyRings)  { if (!activeHexes.has(hx))    { map.removeLayer(anomalyRings[hx]);  delete anomalyRings[hx]; } }
    for (hx in spoofRings)    { if (!activeHexes.has(hx))    { map.removeLayer(spoofRings[hx]);    delete spoofRings[hx]; } }
    for (hx in uavRings)      { if (!activeHexes.has(hx))    { map.removeLayer(uavRings[hx]);      delete uavRings[hx]; } }
    for (hx in markerLastSeen){ if (!allServerHexes.has(hx)) { delete markerLastSeen[hx]; delete acPrevState[hx]; } }

    // ── v4.0: Feed the 3D scene with the same data ────────────────────────
    lastMapData = data;
    update3DScene(data);
});

// ═══════════════════════════════════════════════════════════════════════════
// v4.0 — 3D SKY VIEW  (Three.js r128, CDN, no tile server, no external token)
// ═══════════════════════════════════════════════════════════════════════════

// ── State ──────────────────────────────────────────────────────────────────
var SKY_ACTIVE  = false;
var lastMapData = null;
var renderer3d  = null, camera3d = null, controls3d = null, scene3d = null;
var ac3d        = {};      // hex → {cone, stem, shadow, trailLine, tdoaSphere, spoofRing}
var spoof3dTime = 0;
var altExag     = 10;      // altitude exaggeration factor (default 10x)

// Unit conversion: feet to kilometres
var FT_TO_KM = 0.0003048;

// ── Geographic origin: centroid of sensor triangle ─────────────────────────
var ORIG_LAT        = 60.267;
var ORIG_LON        = 24.898;
var KM_PER_DEG_LAT  = 111.319;
var KM_PER_DEG_LON  = KM_PER_DEG_LAT * Math.cos(ORIG_LAT * Math.PI / 180); // ≈ 55.3

// Convert WGS-84 + altitude to Three.js scene coordinates.
// Convention: X = east, Z = south (−Z = north), Y = up.
// 1 scene unit = 1 km.
function latlonToVec3(lat, lon, altFt) {
    var x = (lon - ORIG_LON) * KM_PER_DEG_LON;
    var z = -(lat - ORIG_LAT) * KM_PER_DEG_LAT;
    var y = (typeof altFt === 'number') ? (altFt * FT_TO_KM * altExag) : 0;
    return new THREE.Vector3(x, y, z);
}

// Sensor-coverage colour as a hex integer (mirrors getColor() for Leaflet).
function hexColor3d(sb) {
    var n = sb.includes("sensor-north"),
        w = sb.includes("sensor-west"),
        e = sb.includes("sensor-east");
    if(n&&w&&e) return 0xffffff;
    if(n&&w)    return 0x39c5cf;
    if(n&&e)    return 0xd2a8ff;
    if(w&&e)    return 0xd29922;
    if(n)       return 0x58a6ff;
    if(w)       return 0x3fb950;
    if(e)       return 0xf85149;
    return 0x888888;
}

// Build a flat ring mesh lying in the XZ plane.
function makeRing3d(cx, cz, rKm, color, opacity) {
    var geo = new THREE.RingGeometry(rKm - 0.5, rKm + 0.5, 72);
    var mat = new THREE.MeshBasicMaterial({
        color: color, side: THREE.DoubleSide, transparent: true, opacity: opacity
    });
    var m = new THREE.Mesh(geo, mat);
    m.position.set(cx, 0.05, cz);
    m.rotation.x = -Math.PI / 2;
    return m;
}

// ── Scene initialisation (called lazily on first 3D activation) ────────────
function init3DScene() {
    var canvas = document.getElementById('canvas-3d');

    renderer3d = new THREE.WebGLRenderer({canvas: canvas, antialias: true, alpha: false});
    renderer3d.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer3d.setClearColor(0x060a0f);
    renderer3d.setSize(canvas.clientWidth, canvas.clientHeight, false);

    scene3d = new THREE.Scene();
    scene3d.fog = new THREE.FogExp2(0x060a0f, 0.0006);

    camera3d = new THREE.PerspectiveCamera(55, canvas.clientWidth / (canvas.clientHeight || 1), 0.5, 4000);
    // Start top-down tactical view at ~350 km altitude; slight Z offset avoids gimbal lock
    camera3d.position.set(0, 350, 0.1);
    camera3d.lookAt(0, 0, 0);

    controls3d = new THREE.OrbitControls(camera3d, renderer3d.domElement);
    controls3d.enableDamping  = true;
    controls3d.dampingFactor  = 0.06;
    controls3d.screenSpacePanning = true;
    controls3d.minDistance    = 5;
    controls3d.maxDistance    = 2000;
    controls3d.target.set(0, 0, 0);

    // Lighting
    scene3d.add(new THREE.AmbientLight(0xffffff, 0.85));
    var sun = new THREE.DirectionalLight(0xffffff, 0.4);
    sun.position.set(80, 200, 60);
    scene3d.add(sun);

    // Ground grid: 600 km × 600 km, 10 km cells
    scene3d.add(new THREE.GridHelper(600, 60, 0x0e2a3a, 0x091820));

    // Sensor nodes — coloured upright pyramids
    var SNODES = [
        {lat:60.319555, lon:24.830816, col:0x58a6ff},  // North
        {lat:60.130919, lon:24.512869, col:0x3fb950},  // West
        {lat:60.374069, lon:25.249015, col:0xf85149}   // East
    ];
    SNODES.forEach(function(s) {
        var p = latlonToVec3(s.lat, s.lon, 0);
        var geo = new THREE.ConeGeometry(2.5, 7, 4);
        var mat = new THREE.MeshLambertMaterial({color: s.col});
        var m   = new THREE.Mesh(geo, mat);
        m.position.set(p.x, 3.5, p.z);   // sit base on ground
        scene3d.add(m);
        // 100 km and 200 km coverage rings matching the 2D map
        scene3d.add(makeRing3d(p.x, p.z, 100, s.col, 0.28));
        scene3d.add(makeRing3d(p.x, p.z, 200, s.col, 0.11));
    });

    // FL reference planes — subtle translucent slabs at FL100 / FL200 / FL350
    // Positioned by altExag; re-adjusted in update3DScene if slider changes.
    [{fl:100, col:0x1a2a1a}, {fl:200, col:0x1a3a30}, {fl:350, col:0x202050}].forEach(function(ref) {
        var altKm = ref.fl * 100 * FT_TO_KM;
        var geo   = new THREE.PlaneGeometry(600, 600);
        var mat   = new THREE.MeshBasicMaterial({
            color: ref.col, transparent: true, opacity: 0.04, side: THREE.DoubleSide
        });
        var plane = new THREE.Mesh(geo, mat);
        plane.rotation.x    = -Math.PI / 2;
        plane.position.y    = altKm * altExag;
        plane.userData.altKm = altKm;    // store for re-positioning on slider change
        scene3d.add(plane);
    });

    animate3d();
    window.addEventListener('resize', on3dResize);
}

// ── Render loop ────────────────────────────────────────────────────────────
function animate3d() {
    requestAnimationFrame(animate3d);
    if (!SKY_ACTIVE || !renderer3d) return;
    controls3d.update();
    renderer3d.render(scene3d, camera3d);
}

function on3dResize() {
    if (!renderer3d) return;
    var canvas = document.getElementById('canvas-3d');
    var w = canvas.clientWidth, h = canvas.clientHeight || 1;
    camera3d.aspect = w / h;
    camera3d.updateProjectionMatrix();
    renderer3d.setSize(w, h, false);
}

// ── Per-frame scene update (called from socket.on('map_update')) ───────────
function update3DScene(data) {
    if (!scene3d) return;
    spoof3dTime += 0.05;

    var seenHexes = new Set();

    data.aircraft.forEach(function(ac) {
        seenHexes.add(ac.hex);

        var pos3d = latlonToVec3(ac.lat, ac.lon, ac.alt);
        var gnd3d = latlonToVec3(ac.lat, ac.lon, 0);
        var col   = hexColor3d(ac.seen_by);

        var obj = ac3d[ac.hex];
        if (!obj) { obj = {}; ac3d[ac.hex] = obj; }

        // ── Aircraft cone ──────────────────────────────────────────────────
        // ConeGeometry tip is at +Y.  Rx(−90°) rotates it to −Z (north).
        // Ry(-trackRad) then applies clockwise heading: N->E->S->W matches
        // track 0→90→180→270.  (Euler XYZ order, verified analytically.)
        if (!obj.cone) {
            var cGeo = new THREE.ConeGeometry(1.5, 5, 4);
            var cMat = new THREE.MeshLambertMaterial({color: col});
            obj.cone = new THREE.Mesh(cGeo, cMat);
            scene3d.add(obj.cone);
        }
        obj.cone.position.copy(pos3d);
        obj.cone.material.color.setHex(col);
        var trackRad = (ac.track || 0) * Math.PI / 180;
        obj.cone.rotation.set(-Math.PI / 2, -trackRad, 0);

        // ── Altitude stem: vertical line from ground projection to aircraft ─
        if (obj.stem) scene3d.remove(obj.stem);
        var sGeo = new THREE.BufferGeometry().setFromPoints([gnd3d, pos3d]);
        obj.stem = new THREE.Line(sGeo,
            new THREE.LineBasicMaterial({color: col, opacity: 0.32, transparent: true}));
        scene3d.add(obj.stem);

        // ── Ground shadow dot ──────────────────────────────────────────────
        if (!obj.shadow) {
            var shGeo = new THREE.CircleGeometry(0.9, 8);
            var shMat = new THREE.MeshBasicMaterial({color: col, transparent: true, opacity: 0.45});
            obj.shadow = new THREE.Mesh(shGeo, shMat);
            obj.shadow.rotation.x = -Math.PI / 2;
            obj.shadow.position.y = 0.02;
            scene3d.add(obj.shadow);
        }
        obj.shadow.position.x = gnd3d.x;
        obj.shadow.position.z = gnd3d.z;
        obj.shadow.material.color.setHex(col);

        // ── Ground track trail (polyline at Y=0) ───────────────────────────
        if (ac.trail && ac.trail.length > 1) {
            if (obj.trailLine) scene3d.remove(obj.trailLine);
            var tPts = ac.trail.map(function(p) { return latlonToVec3(p[0], p[1], 0); });
            var tGeo = new THREE.BufferGeometry().setFromPoints(tPts);
            obj.trailLine = new THREE.Line(tGeo,
                new THREE.LineBasicMaterial({color: col, opacity: 0.38, transparent: true}));
            scene3d.add(obj.trailLine);
        }

        // ── TDOA uncertainty sphere (full-lock aircraft only) ──────────────
        if (ac.tdoa_uncertainty_m !== undefined && ac.tdoa_uncertainty_m > 0) {
            var rKm = Math.min(ac.tdoa_uncertainty_m / 1000, 200);
            if (!obj.tdoaSphere) {
                var tsGeo = new THREE.SphereGeometry(1, 16, 12);
                var tsMat = new THREE.MeshBasicMaterial({
                    color: 0xf0a000, transparent: true, opacity: 0.06
                });
                obj.tdoaSphere = new THREE.Mesh(tsGeo, tsMat);
                scene3d.add(obj.tdoaSphere);
            }
            obj.tdoaSphere.position.copy(pos3d);
            obj.tdoaSphere.scale.setScalar(rKm);
        } else if (obj.tdoaSphere) {
            scene3d.remove(obj.tdoaSphere);
            obj.tdoaSphere = null;
        }

        // ── Spoof ring — pulsing flat ring around suspect aircraft ─────────
        var spoofScore = ac.spoof_score || 0;
        if (spoofScore >= 0.35) {
            if (obj.spoofRing) scene3d.remove(obj.spoofRing);
            // Phase differs per aircraft so rings don't all pulse in unison
            var pulse   = 0.7 + 0.3 * Math.sin(spoof3dTime * 2.5 + ac.hex.charCodeAt(0) * 0.1);
            var rInner  = (spoofScore >= 0.5 ? 2.8 : 2.0) * pulse;
            var sCol    = spoofScore >= 0.5 ? 0xf85149 : 0xd29922;
            var srGeo   = new THREE.RingGeometry(rInner, rInner + 0.5, 32);
            var srMat   = new THREE.MeshBasicMaterial({
                color: sCol, side: THREE.DoubleSide, transparent: true, opacity: 0.72
            });
            obj.spoofRing = new THREE.Mesh(srGeo, srMat);
            obj.spoofRing.position.copy(pos3d);
            obj.spoofRing.rotation.x = -Math.PI / 2;
            scene3d.add(obj.spoofRing);
        } else if (obj.spoofRing) {
            scene3d.remove(obj.spoofRing);
            obj.spoofRing = null;
        }
    });

    // Remove Three.js objects for aircraft that have left the server state
    Object.keys(ac3d).forEach(function(hex) {
        if (seenHexes.has(hex)) return;
        var obj = ac3d[hex];
        ['cone','stem','shadow','trailLine','tdoaSphere','spoofRing'].forEach(function(k) {
            if (obj[k]) { scene3d.remove(obj[k]); obj[k] = null; }
        });
        delete ac3d[hex];
    });

    // Re-position FL reference planes if altExag was changed via slider
    scene3d.traverse(function(o) {
        if (o.userData.altKm !== undefined) {
            o.position.y = o.userData.altKm * altExag;
        }
    });
}

// ── View toggle ────────────────────────────────────────────────────────────
function setView(mode) {
    SKY_ACTIVE = (mode === '3d');
    document.getElementById('map').style.display          = SKY_ACTIVE ? 'none'  : 'block';
    document.getElementById('canvas-3d').style.display    = SKY_ACTIVE ? 'block' : 'none';
    document.getElementById('sky-controls').style.display = SKY_ACTIVE ? 'flex'  : 'none';
    document.getElementById('btn-2d').classList.toggle('active', !SKY_ACTIVE);
    document.getElementById('btn-3d').classList.toggle('active',  SKY_ACTIVE);
    if (SKY_ACTIVE) {
        if (!renderer3d) {
            init3DScene();
            // Render the last known aircraft positions immediately on first open
            if (lastMapData) update3DScene(lastMapData);
        } else {
            on3dResize();
        }
    }
}

// ── Keyboard shortcuts ─────────────────────────────────────────────────────
document.addEventListener('keydown', function(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if (e.key === 't' || e.key === 'T') {
        setView(SKY_ACTIVE ? '2d' : '3d');
        return;
    }
    if ((e.key === 'r' || e.key === 'R') && SKY_ACTIVE && camera3d) {
        camera3d.position.set(0, 350, 0.1);
        camera3d.lookAt(0, 0, 0);
        controls3d.target.set(0, 0, 0);
        controls3d.update();
    }
});

// ── Altitude exaggeration slider ───────────────────────────────────────────
document.getElementById('alt-exag').addEventListener('input', function() {
    altExag = parseInt(this.value);
    document.getElementById('alt-exag-lbl').textContent = altExag + '×';
    // Re-render immediately so aircraft jump to their new Y positions
    if (lastMapData && scene3d) update3DScene(lastMapData);
});
</script>

<!-- Footer with contact -->
<div id="footer">
    Disclaimer: Made with AI help. Contact: richard (at) wiren (dot) fi
</div>
</body>
</html>

"""
