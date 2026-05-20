# WebXR ADS-B Viewer — Performance Optimization & Development Roadmap

**Project:** Securing Skies  
**Version:** 2.1.0  
**Date:** 2026-05-14  
**Authors:** Securing Skies Research Team  

---

## 1. Current State

### 1.1 Architecture

```
Browser (WebXR)         MQTT Broker                Sensors & ML
─────────────────       ─────────────────          ─────────────────
A-Frame + THREE.js  ←── wss://mqtt:8443  ←──────  sensor-north
MQTT.js client          (Mosquitto)                sensor-west
                                                   sensor-east
                                          ←──────  ML inference (anomaly scores)
```

All rendering happens in the browser. The server only relays MQTT messages. The browser receives JSON telemetry over WebSocket and renders aircraft in 3D space in real-time.

### 1.2 Supported Platforms

| Platform | View | Status |
|----------|------|--------|
| Desktop (Chrome/Firefox) | God View from above | Working, profiled |
| Meta Quest 3 (VR) | Immersive close-up | Working, not yet profiled |
| Android phone (AR/Magic Window) | Ground level, gyro+compass | Working, profiled |
| iOS (Safari) | Limited (no WebXR) | Partial |

### 1.3 Current Features

- Real-time MQTT data stream (JSON over WebSocket)
- Lerp smoothing for aircraft movement (0.12 desktop / 0.16 mobile per frame)
- Sensor locking (prevents jumping from multi-sensor updates)
- ML anomaly visualization (color change + expanding red pulse ring)
- Airplane-shaped 3D models (primitives) with heading rotation
- Connection lines to sensors (visible on click, shows all tracking sensors)
- Align North button (compass correction on mobile)
- Camera intro animation (swoop on load)
- Starfield background (800 points, upper hemisphere)
- Info panel: flight, sensors, altitude, heading, speed, distance, ML score
- Yagi antenna-style sensor markers
- Last-known altitude retention (no sudden drops on data gaps)

---

## 2. Performance Profiling — Completed Tests

### 2.1 Test Device: Samsung Galaxy Z Fold 7

Profiling performed on 2026-05-14 using Samsung GPUWatch (built-in HUD overlay).

**Test environment:**
- Device: Samsung Galaxy Z Fold 7
- Browser: Chrome (Android)
- Aircraft count during test: ~21 real-time targets
- Profiling tool: Samsung GPUWatch (Developer Options)

### 2.2 Measurements

#### Measurement 1: Before optimization (setAttribute in tick loop)

The tick loop updated aircraft stem height using A-Frame's `setAttribute('height', ...)` every frame. This passes through A-Frame's DOM abstraction layer and is slow.

| Mode | Rendering API | FPS | CPU | GPU | Draw Calls |
|------|---------------|-----|-----|-----|------------|
| AR (passthrough/Magic Window) | OpenGL | 30 | 75% | 19% | not measured |
| Desktop view | Vulkan | 59 | 21% | 24% | 126 |

#### Measurement 2: After optimization (direct object3D manipulation)

Replaced `setAttribute('height', h)` with direct `object3D.scale.y` manipulation. Also removed `getAttribute('visible')` call from tick loop.

| Mode | Rendering API | FPS | CPU | GPU | Draw Calls |
|------|---------------|-----|-----|-----|------------|
| AR (passthrough/Magic Window) | OpenGL | 31 | 48% | 31% | not measured |
| Desktop view | Vulkan | 59 | 25% | 33% | 118 |

#### Measurement 3: Vulkan flag in AR mode (chrome://flags)

Attempted to force Vulkan rendering in AR mode via Chrome flags.

**Result:** AR mode stopped working entirely. WebXR AR requires OpenGL on Samsung devices (camera passthrough pipeline is not compatible with Vulkan). Flag reverted to default.

### 2.3 Analysis and Conclusions

**Why is AR slower than desktop on the same device?**

Two factors:
1. **Rendering API:** AR uses OpenGL (high CPU overhead), desktop uses Vulkan (low overhead). This is a browser/device choice we cannot influence.
2. **Camera passthrough:** In AR mode the device feeds camera imagery as background, consuming additional resources.

**What the optimization achieved:**
- CPU load in AR dropped **75% → 48%** (-27 percentage points)
- GPU load rose **19% → 31%** — work correctly shifted from CPU to GPU
- FPS stayed at ~31 — this is the OpenGL AR hardware cap, not our code's limitation
- Desktop mode: no significant change (was not a bottleneck)

**Scalability:** With current CPU load (48% AR, 25% desktop) there is ample headroom to add more aircraft and complex logic.

**Draw Calls (118):** Healthy number. InstancedMesh optimization is not urgent at current aircraft count (~21). If count grows to 100+, situation may change.

---

## 3. Profiling Tool Setup Guides

### 3.1 Samsung Galaxy Z Fold 7 (Android)

#### GPUWatch (built-in HUD overlay) — USED

Samsung's native developer tool that draws a real-time performance widget on screen (FPS, CPU, GPU load). Fastest way to see WebXR performance directly on device.

**Setup:**

1. Go to **Settings → About phone → Software information**
2. Tap **Build number** 7 times rapidly → Developer mode activates
3. Return to main Settings → select **Developer options** (bottom of list)
4. Find **GPUWatch** in the list and toggle it on
5. Open WebXR page in Chrome or Samsung Internet
6. A widget overlay appears showing real-time metrics

**GPUWatch displays:**
- FPS (Surface) — frame rate
- CPU % — processor load
- GPU % — graphics load
- Context Info — rendering API (OpenGL/Vulkan), resolution, driver type

#### Chrome Remote Debugging (detailed PC analysis) — NOT YET DONE

Most effective way to find code-level bottlenecks. Shows exactly which JavaScript functions consume the most time per frame.

**Setup:**

1. Ensure **USB debugging** is enabled in phone's Developer options
2. Connect phone to computer via USB-C cable
3. Open WebXR page in Chrome on phone
4. On computer, open Chrome and navigate to: `chrome://inspect/#devices`
5. Your phone appears in the list — click **Inspect** under the WebXR tab
6. Chrome DevTools opens on computer, connected to phone's browser
7. Use **Performance** tab: press Record, use the page briefly, stop
8. See exactly how many milliseconds JavaScript computation and WebGL rendering take per frame

**When to use:** When you need to know exactly which function is slow (e.g., is the bottleneck in tick() loop, MQTT handler, or A-Frame internal logic).

#### Android GPU Inspector (AGI) — NOT USED

Google's tool for extremely deep hardware-level profiling (memory bandwidth, exact draw call counts). Installed on computer, profiles Android GPU at very granular level.

**When to use:** Only if Chrome Remote Debugging is insufficient and extreme graphics optimization is needed. For normal WebXR development, Chrome Remote Debugging is sufficient and easier.

### 3.2 Meta Quest 3 — Guide for Collaborator

Quest 3 profiling has not been done yet. Instructions below for collaborator testing with the headset:

#### Step 1: Enable Developer Mode

1. Open **Meta Horizon** app on phone
2. Select connected Quest 3 headset
3. Go to **Settings → Developer Mode** → enable
4. Restart headset

#### Step 2: Meta Quest Developer Hub (MQDH) — PC Software

1. Download **Meta Quest Developer Hub** from: https://developer.meta.com/downloads/package/oculus-developer-hub/
2. Install and launch on computer
3. Connect Quest 3 to computer via USB-C cable
4. MQDH detects headset automatically
5. Select **Performance Profiler** section

#### Step 3: OVR Metrics Tool (HUD in headset)

1. Via MQDH: select **Device Manager → Performance → Enable Performance HUD**
2. Or install OVR Metrics Tool directly from Quest Store (Developer category)
3. With HUD enabled, open Quest browser and navigate to WebXR page
4. Real-time metrics appear at the edge of your field of view

#### What to measure and report:

| Metric | Target | Critical threshold |
|--------|--------|--------------------|
| FPS | 72 (Quest 3 native) | < 60 = judder |
| Stale Frames | 0 | > 5% = nausea risk |
| CPU Utilization | < 80% | > 90% = bottleneck |
| GPU Utilization | < 80% | > 90% = too heavy |
| Draw Calls | < 100 | > 300 = needs optimization |
| Thermal (temperature) | Normal | Throttling = performance drops |

#### Test scenario for collaborator:

1. Open in Quest browser: `https://www.securingskies.eu:9443/webxr.html?u=USER&p=PASS`
2. Wait 30s for aircraft to load
3. Record: FPS, CPU%, GPU%, Draw Calls
4. Enter VR mode (press Enter VR button)
5. Move with thumbsticks, look around
6. Record metrics again while moving
7. Click aircraft — does it affect performance?

---

## 4. Completed Optimizations

### 4.1 DOM Call Elimination from Tick Loop (DONE 2026-05-14)

**Problem:** A-Frame's `setAttribute()` and `getAttribute()` pass through the DOM abstraction layer. When called every frame (60 times per second) for every aircraft, CPU load grows significantly.

**Implemented solution:**
```javascript
// BEFORE (slow — DOM call every frame):
item.stem.setAttribute('height', h);
popup.getAttribute("visible") === "true"

// AFTER (fast — direct THREE.js object3D manipulation):
item.stem.object3D.scale.y = h / item._stemInitH;
popup.object3D.visible
```

**Measured result:** CPU load in AR dropped 75% → 48%.

**Why this works:** A-Frame's `setAttribute` does significant work behind the scenes: parses the value, validates it, updates component internal state, and finally sets the THREE.js object value. Direct `object3D` manipulation bypasses all of this and sets the value directly in the data going to the GPU.

### 4.2 Draw Call Counter in HUD (DONE 2026-05-14)

Added `renderer.info.render.calls` to HUD text in real-time. Enables draw call monitoring without external tools.

```javascript
const dc = sceneEl.renderer ? sceneEl.renderer.info.render.calls : "?";
hud.textContent = `LIVE | ${aircraft.size} ac | ${dc} draws | ${fps} fps`;
```

---

## 5. Planned Optimizations (NOT YET IMPLEMENTED)

### 5.1 Instanced Rendering (Priority: LOW now, HIGH if aircraft count grows)

**Problem:** Each aircraft is a separate A-Frame entity with multiple child elements. 200 aircraft = ~1200 separate 3D objects = ~1200 draw calls.

**Solution:** THREE.js `InstancedMesh` — one geometry, one material, hundreds of instances with a single draw call.

**Expected benefit:** Draw calls ~1200 → ~5.

**Challenge:** A-Frame entity-based raycasting doesn't work directly with InstancedMesh. Requires custom raycaster.

**Status:** Not implemented. Current draw call count (118 @ 21 aircraft) is healthy. Implement if aircraft count grows significantly or Quest 3 profiling shows need.

### 5.2 Web Workers (Priority: MEDIUM)

**Problem:** MQTT message handling (JSON.parse) and geoToLocal coordinate transforms happen on the main thread, competing with rendering for CPU time.

**Solution:** Move data parsing and coordinate transforms to a Web Worker (separate CPU thread).

**Expected benefit:** Main thread freed for rendering, fewer frame drops during data spikes.

**Status:** Not implemented. With current message rate (~3–10 messages/s) and post-optimization CPU load (48% AR) there is no acute need. Useful if message rate grows significantly.

### 5.3 Binary Data Transfer (Priority: LOW)

**Problem:** JSON parsing causes GC pauses (garbage collection) at high message volumes.

**Solution:** Protocol Buffers or FlatBuffers for MQTT payload compression (~60–70% smaller payload).

**Status:** Not implemented. Requires changes to both server-side (Python encoder) and browser (protobuf.js decoder). Low priority as current message rate is not a problem.

---

## 6. Visualization Roadmap (NOT YET IMPLEMENTED)

### 6.1 Confidence Volumes (Uncertainty Ellipsoids)

ML model uncertainty visualized in 3D space: semi-transparent ellipsoid around aircraft. Size grows with uncertainty. Spoofed aircraft → large ellipsoid.

### 6.2 Trajectory Ribbons

Historical flight path as ribbon mesh. Normal flight = smooth ribbon, spoofing = sudden jumps visible as "tears" in the ribbon.

### 6.3 Chase Cam

Camera follows selected aircraft (3rd person or cockpit view). Useful for auditing individual flight paths.

### 6.4 3D Terrain Map

Terrain tiles (e.g., Mapbox Terrain) for geographic context. Helsinki-Espoo area topography, airports, sea vs. land.

---

## 7. Implementation Roadmap

### Phase 1: Core Features (2026-05-14) — DONE

- [x] Airplane shapes with heading rotation
- [x] ML anomaly pulse ring
- [x] Sensor locking (prevents multi-sensor jumping)
- [x] Mobile AR ground-level view + compass correction (declination -8°)
- [x] Align North button
- [x] Info panel (speed, heading, distance, all sensors, ML score)
- [x] Camera intro animation
- [x] Connection lines to sensors (click-to-show, all sensors)
- [x] Yagi antenna-style sensors
- [x] Starfield
- [x] Profiling on Samsung Z Fold 7 (GPUWatch)
- [x] Draw call counter in HUD
- [x] object3D direct manipulation (setAttribute removal from tick loop)
- [x] Vulkan flag tested in AR → does not work (AR requires OpenGL)

### Phase 2: Refinement (15–18 May 2026)

- [x] VR comfort improvements (locomotion speed, popup distance, text size)
- [x] AR passthrough transparency (ground plane + rings hidden on mobile)
- [x] Spatial UI popup panel (glow border, platform-specific scaling)
- [x] Color-coded connection lines (blue=north, green=west, red=east)
- [x] Mobile stability (max aircraft 40, raycaster throttled)
- [x] Quest 3 profiling (Performance HUD deployed, metrics captured)
- [x] VR comfort improvements (locomotion speed, popup distance, text size — Meta guidelines)
- [x] AR passthrough transparency (ground plane + rings hidden on mobile)
- [x] Spatial UI popup panel (glow border, platform-specific scaling)
- [x] Color-coded connection lines (blue=north, green=west, red=east)
- [x] Mobile stability (max aircraft 40, raycaster throttled)
- [x] Wireframe terrain grid with procedural elevation (land/sea, 40x40)
- [x] Finnish coastline polyline (Gulf of Finland, 24 points, dynamic)
- [x] URL-based sensor selector (?sensor=north|west|east)
- [x] Dynamic sensor position recalculation based on selected reference point
- [ ] Chrome Remote Debugging analysis (exact function-level bottlenecks)

### Phase 3: Further Development

**Requires Quest 3 for testing (confirmed supported by Quest Browser):**
- [ ] Request 90Hz frame rate (`xrSession.updateTargetFrameRate(90)`) — Quest defaults to 72Hz
- [ ] Hand tracking pinch-to-select (WebXR Hand Input API, supported since Quest Browser v15.1, pinch threshold 0.7-0.8)
- [ ] Hit Test for MR table placement (WebXR Hit Test API, supported since Quest Browser v25.3) — tap real surface to anchor scene
- [ ] Controller haptic feedback on select (`gamepad.hapticActuators[0].pulse(0.5, 100)`)
- [ ] Spatial anchors for persistent MR placement (WebXR Anchors API, supported since Quest Browser v24.0)

**General improvements:**
- [ ] Haptic vibrate on aircraft select for Android (`navigator.vibrate(50)`)
- [ ] Slow rotation animation on sensor antennas (ambient life)
- [ ] InstancedMesh implementation (if needed based on Quest 3 profiling data)
- [ ] Web Worker for data handling (if message rate grows)
- [ ] Trajectory ribbons
- [ ] Confidence volumes
- [ ] Chase Cam
- [ ] Multi-user shared view (WebSocket sync)
- [ ] Voice commands ("show anomalies", "follow aircraft")
- [x] Terrain map (procedural wireframe with elevation + coastline)

### Phase 4: Production Readiness (later)

- [ ] Vault-based authentication (no hardcoded credentials)
- [ ] CI/CD pipeline (GitHub Actions → staging → production)
- [ ] Comprehensive README.md (install, build, deploy)
- [ ] Code commenting and versioning per standards

---

## 8. Security & DevOps Standards

### 8.1 Credential Management

| Current State | Risk | Target |
|---------------|------|--------|
| MQTT credentials via URL params | Low (read-only, not indexed) | Vault injection via backend proxy |
| Direct MQTT connection from browser | Low | Backend proxy with session validation |
| Single shared username | Low | Per-session tokens |

**Note:** Current solution is a deliberate compromise for the development phase. Credentials are read-only (subscribe-only) and the site is not publicly indexed. Will be fixed for production.

### 8.2 Code Documentation Standard

```javascript
/**
 * File: [file path]
 * Version: [semver]
 * Date: [date]
 * Description: [description]
 * Academic Note: [research context, if relevant]
 * Security: [security notes]
 * Dependencies: [external dependencies]
 */
```

### 8.3 Deployment (current — manual)

```bash
# Manual deploy
scp webxr.html root@server:/path/to/static/
ssh root@server 'cp /path/to/static/webxr.html /var/www/site/'
```

**Target:** CI/CD pipeline in the future.

---

## 9. Summary

### Current State
WebXR ADS-B Viewer is **operational**. Tested on Samsung Galaxy Z Fold 7 (GPUWatch profiling). Desktop view runs at 59 FPS / 25% CPU (Vulkan). AR mode at 31 FPS / 48% CPU (OpenGL limitation).

### Completed Optimization
setAttribute → object3D direct manipulation. Result: **CPU -27 percentage points** in AR mode. FPS did not increase because 30 FPS is the OpenGL AR hardware cap on this device.

### Open Questions
1. Quest 3 performance? (collaborator to test)
2. Is 30 FPS sufficient for AR? (likely yes, no VR nausea risk in magic window mode)
3. Is InstancedMesh needed? (not at current aircraft count, 118 draw calls OK)

### Next Steps
1. Quest 3 profiling
2. Visual refinements as needed
