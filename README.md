# Securing the Skies: ADS-B Spoofing Detection Grid

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/github/v/tag/rwiren/adsb-research-grid?label=Version&color=green)](https://github.com/rwiren/adsb-research-grid/tags)
[![Status](https://img.shields.io/badge/Status-Phase%205%3A%20Production-success.svg)](#)
[![Dashboard](https://img.shields.io/badge/Live%20Dashboard-securingskies.eu-00c878?style=flat-square)](https://www.securingskies.eu:9443/)
[![MQTT](https://img.shields.io/badge/MQTT-3%20Sensors%20Online-blue?style=flat-square)](#-grid-infrastructure)
[![Wiki](https://img.shields.io/badge/Docs-Project%20Wiki-purple?style=flat-square)](https://github.com/rwiren/adsb-research-grid/wiki)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](#)
[![MLAT](https://img.shields.io/badge/MLAT-3--Sensor%20TDOA%20(PPS)-brightgreen?style=flat-square)](#)
![Last Updated](https://img.shields.io/github/last-commit/rwiren/adsb-research-grid?label=Last%20Updated&color=orange)

[![Audit Report](https://img.shields.io/badge/View-Latest%20Report-blue?style=for-the-badge&logo=github)](docs/showcase/latest/REPORT.md)

## 📋 Table of Contents
1. [Research Goal](#-research-goal)
2. [Real-World Validation (May 2026)](#-real-world-validation-may-2026)
3. [The Model Zoo (18 Architectures)](#-the-model-zoo-18-architecture-ensemble)
4. [Architecture (Hardware Grid)](#-architecture-distributed-sensor-grid)
5. [Research Workflow (Usage)](#-research-workflow-usage)
6. [Repository Structure](#-repository-structure)
7. [3D Sky View](#-3d-sky-view-native-three-js-visualization)
8. [Project Heritage](#-project-heritage)
9. [License & Citation](#-license--citation)

---

## 🎯 Real-World Validation (May 2026)

On May 15, 2026, our sensor grid detected a confirmed ADS-B spoofing event in the Gulf of Finland. Four fabricated aircraft tracks were injected into 1090 MHz, confirmed by multi-sensor correlation and OpenSky Network cross-validation.

**Key Result:** A GRU autoencoder trained exclusively on 4 days of normal traffic (Mon–Thu, May 11–14) detected the primary spoofed track with reconstruction error **4,462× above the anomaly threshold** — without any labeled attack data in training.

| What | Details |
|------|---------|
| **Who** | Richard Wirén & SecureSkies Team — AI Academy 2026 |
| **What** | Unsupervised ADS-B spoofing detection using distributed sensor grid + deep autoencoders |
| **How** | 3 Raspberry Pi sensors (SDR 1090 MHz) → MQTT → physics-informed feature engineering → GRU autoencoder with information bottleneck |
| **Why** | ADS-B has no authentication — anyone can inject false aircraft. Civil aviation needs independent detection capability |
| **When** | Sensors operational since April 2026. Real spoofing detected May 15, 2026 |
| **Where** | Helsinki FIR (Finland), sensors across Greater Helsinki (~30 km baselines), spoofing source: eastern Gulf of Finland (~59.65°N, 29.35°E) |

### Detection Results

| ICAO | Callsign | Detection Confidence | Rank |
|------|----------|---------------------|------|
| 151fb6 | AUL505 | **4,462× threshold** | #2/310 aircraft |
| 151e57 | PBD6837 | 2.8× threshold | #8/310 |
| 151e10 | PBD529 | 13.1× (sequence-level) | Detected with persistence filtering |
| 4691c5 | AEE6118 | Borderline | Detected with persistence filtering |

### Production System (operational since April 2026)

- **Live dashboard**: [securingskies.eu:9443](https://www.securingskies.eu:9443/) — 2D map + 3D sky view, real-time ML inference, spoofing replay
- **WebXR 3D view**: [securingskies.eu:9443/webxr.html](https://www.securingskies.eu:9443/webxr.html) (Meta Quest 3, Android AR, Desktop)
- **Deployed model**: GRU autoencoder (1.8 Hz inference), τ=0.136, FP rate 0.12%
- **MLAT**: 3-sensor TDOA multilateration operational (PPS-disciplined timing, 15μs precision on reference node)
- **GNSS monitoring**: Real-time integrity checking across all sensors, spoofing/jamming detection
- **ML pipeline**: Continual evaluation, adaptive thresholds, per-feature anomaly attribution
- **Uptime**: Continuous operation since April 2026 (90+ days)

---

# 🔬 Research Goal: The "Elastic Manifold" Defense

To detect and mitigate GNSS spoofing attacks on civilian aviation tracking systems (ADS-B) using a distributed sensor grid and a **Hybrid AI Model Zoo**. This project moves beyond simple signal strength thresholding to a multi-layered defense strategy capable of identifying sophisticated trajectory modification attacks, "ghost" aircraft injections, and hardware-level signal cloning.

The core innovation is the **Elastic Manifold Architecture**: a system that validates aircraft not just by physics (speed/altitude), but by **topology** (mathematical constraints), **time** (elastic synchronization), and **hardware signatures** (RF fingerprinting).

---

# 🧠 Validated Architectures & Detection Methods

10 neural architectures rigorously evaluated with 20-trial hyperparameter search per architecture, 6 attack magnitudes, and proper aircraft-level data partitioning.

**Status Legend:**
✅ **Validated (with results)** | 🔄 **Implemented (code exists)** | ⚠️ **Roadmap**

### Production (Deployed Live)

| # | Architecture | F1 | AUC | Status | Notes |
|---|-------------|-----|-----|--------|-------|
| 1 | **GRU Autoencoder** | 0.357 | 0.771 | ✅ Deployed | Best aggregate, lowest FP, recommended |
| 2 | LSTM | 0.354 | 0.793 | ✅ Validated | Best on RF shadowing attacks |
| 3 | BiLSTM | 0.342 | 0.763 | ✅ Validated | |
| 4 | Vanilla RNN | 0.339 | 0.792 | ✅ Validated | |
| 5 | CNN | 0.280 | 0.757 | ✅ Validated | Lowest FP rate but worst F1 |

### Research (Evaluated, Not Deployed)

| # | Architecture | F1 | AUC | Status | Notes |
|---|-------------|-----|-----|--------|-------|
| 6 | PINN | 0.315 | 0.790 | ✅ Validated | **Key finding: physics loss is counterproductive** |
| 7 | TCN | 0.262 | 0.783 | ✅ Validated | Dilated convolutions insufficient for drift |
| 8 | xLSTM | 0.295 | 0.772 | ✅ Validated | Matrix memory provides no benefit over LSTM |
| 9 | FlightBERT++ | 0.297 | 0.746 | ✅ Validated | Transformer variant |
| 10 | TOMHT | 0.145 | 0.563 | ✅ Validated | Track-based, poorest performer |

### Key Findings from Architecture Comparison

- **Physics belongs in features, not loss** — PINN's physics loss *degrades* detection by 30%
- **Temporal memory is essential** — CNN and TCN fail despite dilated convolutions
- **Architecture specialisation exists** — GRU→kinematic, LSTM→RF, motivates ensemble
- **Engineered features outperform raw by 188×** — physics-informed feature engineering is essential
- **Single-layer universally wins** — deeper models don't help for ADS-B temporal complexity

### Infrastructure & Cross-Sensor Validation

| Method | Status | Description |
|--------|--------|-------------|
| Cross-sensor position consistency | ✅ Live | Flags aircraft with >1km position spread across sensors |
| TDOA multilateration | ✅ Operational | 3-sensor MLAT with PPS timing (15μs on North) |
| GNSS integrity monitoring | ✅ Live | Spoofing/jamming detection per sensor |
| Anomaly bridge (28 features) | ✅ Live | Cross-sensor conflict detection |
| Adaptive threshold | ✅ Live | Self-calibrating to traffic regime |
| Persistence filtering | ✅ Live | k=5 consecutive windows, FP→~0% |

### Roadmap (Future Work)

| Method | Description | Status |
|--------|-------------|--------|
| RF Fingerprinting | I/Q signal analysis for transmitter identification | ⚠️ Planned |
| Mixture-of-Experts | Route to specialist architecture per attack type | ⚠️ Planned |
| Graph Attention Networks | Dynamic sensor reliability weighting | ⚠️ Planned |
| Hopsworks Feature Store | MLOps pipeline for reproducible training | 🔄 In progress |

---

### 🛡️ Detection Pipeline (What Actually Runs)

```
Sensors (3× RPi4)                    Server (Helsinki VPS)
┌─────────────────┐                  ┌──────────────────────────────────┐
│ ADS-B SDR 1090  │──── MQTT ──────→ │ Feature Engineering (11 features)│
│ GNSS (GPS/RTK)  │                  │ GRU Autoencoder (1.8 Hz)         │
│ System health   │                  │ Cross-sensor validation          │
└─────────────────┘                  │ GNSS integrity monitor           │
                                     │ MLAT server (TDOA)               │
                                     │ Anomaly bridge (28 features)     │
                                     │ Dashboard + WebXR                │
                                     └──────────────────────────────────┘
```
  
---

## 📡 Grid Infrastructure

> For detailed hardware specifications and GNSS benchmarks, see the **[Project Wiki](https://github.com/rwiren/adsb-research-grid/wiki)**.

### Current Status (June 2026)

| Node | Hardware | GNSS | Position Accuracy | Timing | Role |
|------|----------|------|-------------------|--------|------|
| **North** | RPi4 4GB | u-blox ZED-F9P (RTK + PPS) | **0.4m** (sub-meter) | **15μs** (PPS/GPIO) | Stratum-1 reference |
| **West** | RPi4 4GB | GlobalSat BU-353S4 (GPS L1) | 5.5m | ~0.3ms (NTP via North) | Remote sensor |
| **East** | RPi4 4GB | GlobalSat BU-353S4 (GPS L1) | 10.8m | ~0.3ms (NTP via North) | Remote sensor |
| **Server** | VPS (Helsinki) | — | — | NTP | MQTT broker, ML, dashboard |

### Network

- **Transport:** ZeroTier VPN overlay (encrypted P2P mesh)
- **Data:** MQTT (TLS on port 8883, WebSocket on 8443)
- **MLAT:** Private mlat-server on VPS, all 3 nodes as clients
- **Monitoring:** Real-time GNSS health, system temp/load, ML model health
- **Archival:** Daily cron harvest (compressed CSVs, 46+ days retained)
      
---

## 🧪 Research Workflow (Usage)
This repository includes an automated "Control Center" (`Makefile`) for infrastructure management, data ingestion, self-healing maintenance, and scientific analysis.

### 1. Command Reference
To see the full list of available commands, run `make help` from the repository root:

```text
📡 ADS-B Research Grid Control Center
--------------------------------------------------------
  --- OPERATIONS (Infra) ---
  make setup      - 📦 Install dependencies
  make deploy     - 🚀 Configure all sensors (Ansible)

  --- INFRASTRUCTURE (Ops) --
  make check        - 🏥 Check Connectivity
  make dashboard    - 📊 Update Grafana Dashboards
  make logging      - 🪵 Update Logstash Pipeline
  make tower        - 🗼 Provision Tower Core services

  --- DATA SCIENCE (Tier 1) ---
  make fetch        - 📥 Download, Heal & Merge logs from grid
  make ml           - 🧪 Run Ensemble Anomaly Detection (IsoForest + LOF)
  make ghosts       - 👻 Generate Forensic Maps (Ghost Hunt)
  make gnss         - 🛰️  Run Hardware Certification (D12)
  make report       - 📊 Generate Academic Report (Default: Last 24h)
  make clean        - 🧹 Archive old reports
  make all          - 🔁 Run Full Pipeline (Fetch -> ML -> Report)
--------------------------------------------------------
```

### 2. Scientific Workflows

#### **A. The "Gold Standard" Run**
To perform a complete scientific audit (Ingest data $\rightarrow$ Heal fragmentation $\rightarrow$ Detect Anomalies $\rightarrow$ Generate Report):
```bash
make all
```
* **Output:** `docs/showcase/latest/REPORT.md` and `research_data/ml_ready/`

  * **[View Latest Forensic Report](docs/showcase/latest/REPORT.md)**

#### **B. Manual Data Repair**
If `sensor-west` or other nodes generate fragmented 1-minute logs due to instability, run the self-healing utility manually:
```bash
make consolidate
```

#### **C. Forensic Mapping (Ghost Hunt)**
To generate probabilistic heatmaps of potential spoofing sources without running the full pipeline:
```bash
make ghosts
```

### 3. Manual Deployment
To update the grid infrastructure manually without the Makefile:
```bash
ansible-playbook infra/ansible/playbooks/site.yml
```

### 4. Scientific Analysis (Forensic Report)
To run the full physics validation and generate the "Principal Investigator" dashboard:

```bash
make report
```

**Output (`docs/showcase/latest/REPORT.md`):**
* **`REPORT.md`**: Executive Forensic Report including "Data Health Certificate" and missing value analysis.
* **`D1_Operational.png`**: Grid stability, message rates, and sensor sensitivity profiles.
* **`D2_Physics.png`**: Flight Envelopes (Alt vs Speed) and Signal Decay (Inverse-Square Law validation).
* **`D3_Spatial.png`**: Geospatial coverage maps and sensor geometry.
* **`D4_Forensics.png`**: Multi-sensor correlation and differential signal histograms.

### 5. Machine Learning (Anomaly Detection)
To train the unsupervised spoofing detector on fresh data:

```bash
make ml
```

**Output:** Generates `research_data/ml_ready/training_dataset_v3.csv` containing:
* Normalized physics features (Velocity Discrepancy, SNR Proxy).
* `anomaly_score`: -1 (Potential Spoofer) vs 1 (Normal).

---

## 📂 Repository Structure
* **`infra/`**: Ansible playbooks for Infrastructure as Code (IaC).
* **`models/`**: Advanced ML models for the 18-Architecture Ensemble (Manifold Defense System).
    * `sinkhorn_knopp.py`: Optimal transport algorithm (Tier 1 gatekeeper).
    * `lnn.py`: Liquid Neural Networks for time-continuous dynamics.
    * `xlstm.py`: Extended LSTM with exponential gating.
    * `deepseek_mchc.py`: Graph Neural Network for topology validation.
    * `manifold_guard.py`: Ensemble orchestration system.
    * See [`models/README.md`](models/README.md) for detailed documentation.
* **`examples/`**: Usage demonstrations and tutorials.
    * `demo_manifold_guard.py`: Complete demo of spoofing detection with normal and spoofed scenarios.
* **`research_data/`**: Local repository for ingested sensor logs (Ignored by Git).
* **`docs/showcase/`**: Versioned output of scientific runs (The "Evidence").
* **`scripts/`**: Python analysis tools.
    * `academic_eda.py`: Forensic reporting engine (v0.5.0).
    * `ds_pipeline_master.py`: Machine Learning pipeline (v3.0).
    * `check_signal_health.py`: Real-time sensor diagnostics.
    * `archive/`: Deprecated prototype scripts (v0.1 - v0.4).

---

## 🛰 3D Sky View — Native Three.js Visualization

The dashboard includes a built-in **3D Sky View** tab alongside the standard Leaflet 2D map.  It is implemented entirely in [Three.js](https://threejs.org/) (MIT licence, ~170 KB CDN, no tile server, no external account) and reuses the same `map_update` SocketIO stream that powers the 2D view — switching between modes costs zero additional server requests.

**Live dashboard:** [https://www.securingskies.eu:9443/](https://www.securingskies.eu:9443/) (HTTPS)

> **UPDATED (2026-05-05):** Dashboard v5.0.0 modular refactor deployed. MQTT auto-reconnect on all services. Accuracy monitor with per-sensor GNSS stability (std + eph). ML inference: **GRU h128/l4** (305K params, latent=4). MLAT server operational on sensor-north with all 3 sensors feeding TDOA data. TLS cert auto-renewal with deploy hooks. Synthetic injector removed from production. Click **+ EXPERT** to see GNSS std/eph, model info, and the **⚡ INJECT** demo buttons.

### Why Three.js and not CesiumJS?

| | **CesiumJS** | **Three.js (chosen)** |
|---|---|---|
| Bundle size | ~3.5 MB + tile server | ~170 KB CDN core |
| Globe model | Real WGS-84 ellipsoid | Flat XZ plane (sufficient for ~300 km FIR area) |
| External dependency | Cesium Ion token or self-hosted terrain | None — fully offline-capable |
| Coordinate maths | Built-in ECEF helpers | ~10 lines of manual lat/lon → km projection |
| Fit for this project | Overkill for a regional sensor grid | Ideal — lightweight, single-file, zero signup |

CesiumJS excels when you need a planetary-scale globe with streaming terrain and satellite imagery. For the Helsinki FIR sensor triangle (~50–80 km baselines), a flat Three.js scene with a 10 km ground grid is the right tool.

### What the 3D view reveals that 2D cannot

- **Altitude layering** — at 10× exaggeration, FL100 / FL200 / FL350 become clearly separated vertical layers.  A "ghost" aircraft reported at FL350 that is geometrically impossible at that altitude becomes immediately obvious.
- **TDOA uncertainty volumes** — the TDOA error radius becomes a 3D semi-transparent sphere instead of a flat circle, giving a more scientifically honest representation of localisation quality.
- **Altitude stems** — a vertical line from the ground projection to the aircraft position makes altitude discrepancies visually striking (e.g., an aircraft "teleporting" between altitude layers shows as an abrupt stem change).
- **Sensor LoS geometry** — orbiting the camera to a side angle shows which sensor nodes have unobstructed geometric line-of-sight to a target at its reported altitude.

### Controls

| Control | Action |
|---|---|
| Left drag | Orbit camera |
| Right drag / two-finger pan | Pan |
| Scroll | Zoom |
| `T` | Toggle 2D ↔ 3D |
| `R` | Reset camera to top-down tactical view |
| ALT EXAG slider | Live altitude exaggeration 1× – 50× (default 10×) |

### Scene elements

- **Ground grid** — 600 km × 600 km, 10 km cells, TAK dark palette
- **Sensor nodes** — coloured upright pyramids (blue North / green West / red East)
- **Coverage rings** — 100 km and 200 km rings per node (matching 2D toggles)
- **FL reference planes** — translucent horizontal slabs at FL100, FL200, FL350
- **Aircraft cones** — 4-sided cones pointing in the direction of travel, coloured by sensor coverage (white = trilateration lock)
- **Altitude stems** — vertical line from ground shadow to aircraft position
- **Ground track trails** — polyline of last 60 position fixes at ground level
- **TDOA uncertainty spheres** — amber semi-transparent sphere for full-lock aircraft
- **Spoof rings** — pulsing red/amber flat rings around suspect aircraft, driven by `spoof_score`

### 🔊 Audio Callouts (v4.1)

The dashboard now includes an **AUDIO** toggle that enables browser-native speech synthesis (Web Speech API). Announcements are emitted only on **state transitions** (for example, newly detected emergency squawk or unmanned aircraft), preventing repeated audio spam for the same target.

### 🥽 WebXR 3D Viewer (v2.1.0)

A separate immersive VR/AR visualization of live ADS-B traffic with ML anomaly scoring.

**Live:** [https://www.securingskies.eu:9443/webxr.html](https://www.securingskies.eu:9443/webxr.html) (requires MQTT credentials via `?u=USER&p=PASS`)

| Platform | Mode |
|----------|------|
| Meta Quest 3 | Full VR + AR, gaze cursor, thumbstick movement |
| Android phone | AR magic window, gyro + compass orientation |
| Desktop browser | Mouse drag to look, WASD/QE to move, click to select |

Key features: airplane-shaped aircraft with heading rotation, ML anomaly pulse rings, sensor locking, connection lines to tracking sensors, Align North compass button, real-time info panel (speed, heading, distance, ML score).

Built with A-Frame 1.4.2 + MQTT.js. Single self-contained HTML file, no build step.

See [`dashboard/README.md`](dashboard/README.md#webxr-3d-viewer) for full feature list and [`docs/webxr-optimization-roadmap.md`](docs/webxr-optimization-roadmap.md) for performance profiling data.

---

## 📜 Project Heritage
This project supersedes the original **Central Brain PoC**.
* **Theory:** See the [Legacy Wiki](https://github.com/rwiren/central-brain/wiki) for foundational detection logic.
* **Datasets:** Early baseline datasets are archived in the legacy repo.

---

## 🛡 License & Citation

**MIT License** - Open for academic and research use.

### Citation
If you use this dataset, architecture, or tooling in your research, please cite:

> Wiren, Richard. (2026). *ADS-B Research Grid: Distributed Sensor Network for Spoofing Detection* [Software]. https://github.com/rwiren/adsb-research-grid

See [CITATION.cff](CITATION.cff) for BibTeX format.

---
## 🤝 How to Contribute

We follow a strict DevOps workflow to ensure integrity across Apple Silicon, Intel, and Windows.

### 1. The Golden Rule
**Main is protected.** Never push directly to main. Always use a feature branch.

### 2. Workflow
1.  **Sync:** `git checkout main && git pull origin main`
2.  **Branch:** `git checkout -b feature/your-feature-name`
3.  **Test:** Run `make report` (Must pass locally!)
4.  **Commit:** Use [Conventional Commits](https://www.conventionalcommits.org/) (e.g., `feat:`, `fix:`, `docs:`).
5.  **Merge:** Open a Pull Request.

### 3. Setup
- **Vault Password:** You need the project secret to decrypt configuration files.
    - *Action:* Ask the Maintainer for the password, then run:
    - `read -rs VAULT_PASS && echo "$VAULT_PASS" > .vault_pass`
    - *(Using `read -rs` avoids storing the password in shell history.)*
- **Environment:** Run `make setup` to initialize the Python environment.
