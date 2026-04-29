# 📝 Project Changelog

All notable changes to the **ADS-B Research Grid** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-04-29: The "ML Inference" Update

### Added
- **ML Inference Service** (`ml_inference_service.py`): Real-time GRU Autoencoder inference on live ADS-B traffic. Maintains T=30 sliding window per aircraft, computes 7 engineered features, publishes per-feature reconstruction errors to `sensor-core/ml-anomaly`.
- **Feature Attribution UI**: Live decomposition panel showing which feature dimension (velocity_error, rssi_error, etc.) contributes most to a detection (Paper Eq. 2).
- **Persistence Filter Visual (k=5)**: Threat Confidence gauge that fills over 5 consecutive anomalous windows before escalating to CONFIRMED THREAT (Paper Section 4.3).
- **Hardware Calibrations**: Per-sensor GNSS hardware labels and RSSI calibration multipliers in Expert panel.
- **GPS Health Badge**: Monitors ground sensor EPH; green (<50m), yellow (50-200m), red (>200m).
- **Anomaly Alert Toast**: Slide-in notification when new spoof suspects appear.
- **Sensor Pulsing Dots**: Map markers pulse on data receive, dim when stale.
- **Inject Spoof Demo Button**: Expert-mode button injects fake aircraft for 30s to demonstrate detection.
- **Responsive Panels**: flex-wrap layout + collapse/expand toggle for projector demos.
- **HTTPS on port 9443**: Caddy reverse proxy with Let's Encrypt cert.

### Changed
- **Position smoothing**: Strict sensor lock — aircraft position locked to one sensor, eliminates cross-sensor jumping.
- **Spoof scoring**: Raised climb rate threshold to 8000 fpm, GS discrepancy to 1.5×, minimum 5s altitude delta.
- **Trail rendering**: Min distance 200m, maxlen 30 points (reduces visual noise).
- **Sensor-east position**: Corrected to GNSS-verified coordinates (60.374069, 25.249015).
- **Sensor-north gain**: Fixed at 15.7 dB (autogain disabled).

### Fixed
- Extra `</div>` tag that caused blank page rendering.
- Broken if/else chain from `ac._trilat` insertion.
- GPS Health badge was using RSSI anomalies instead of actual EPH values.

## [0.9.0] - 2026-04-13: The "Sky View" Update
**Feature Release: Native 3D ADS-B Visualization (Three.js).**

### 🛰 3D Sky View
* **`⟁ 3D SKY` tab:** A new tab bar at the top of the page switches between the existing Leaflet 2D map and a native Three.js 3D scene.  Switching costs zero additional server requests — both views share the same `map_update` SocketIO stream.
* **Aircraft cones:** 4-sided cones pointing in the direction of travel (heading derived from `track`), coloured by the existing sensor-coverage scheme (white = trilateration lock).
* **Altitude stems:** Each aircraft has a vertical line from its ground-projection dot to its altitude-exaggerated 3D position — makes altitude discrepancies and "teleportation" spoofing immediately visible.
* **Ground track trails:** Last 60 position fixes rendered as a polyline at ground level, matching the 2D dashed-trail feature.
* **TDOA uncertainty spheres:** For full-lock (N+W+E) aircraft the 2D amber circle becomes a semi-transparent 3D sphere, radius driven by `tdoa_uncertainty_m`.
* **Spoof rings:** Pulsing flat rings around aircraft with `spoof_score ≥ 0.35` (red for ≥ 0.5, amber otherwise), matching the 2D spoof-ring style.
* **FL reference planes:** Subtle translucent horizontal slabs at FL100, FL200, and FL350 provide altitude context without cluttering the scene.
* **Sensor node pyramids:** North (blue) / West (green) / East (red) upright pyramids with 100 km and 200 km coverage rings matching the 2D map toggles.
* **Altitude exaggeration slider:** "ALT EXAG" overlay (1× – 50×, default 10×) scales the Y axis live so traffic layers at FL100/200/350 become clearly separated; updates instantly without waiting for the next SocketIO event.
* **OrbitControls:** Left-drag to orbit, right-drag/two-finger to pan, scroll to zoom. `T` toggles 2D ↔ 3D; `R` resets camera to top-down tactical view (~350 km altitude).
* **Engine choice — Three.js vs CesiumJS:** Three.js (~170 KB CDN, MIT) was chosen over CesiumJS (~3.5 MB + tile server/Ion token) because the Helsinki FIR sensor triangle spans only ~300 km — a flat XZ plane with ~10 lines of lat/lon projection maths is sufficient and keeps the dashboard fully self-contained with no external account required.

### 🗑 Removed
* All Aviar Labs / external 3D platform references removed from `dashboard.py`, `README.md`, `dashboard/README.md`, and `CHANGELOG.md`.  The dashboard no longer links to or depends on any third-party commercial aviation platform.

### 📖 Documentation
* **`dashboard/README.md`**: bumped to v4.0; replaced the third-party integration bullet with the full 3D Sky View feature description.
* **`README.md`**: replaced the "Companion Visualization" section with a "🛰 3D Sky View" section including a Three.js vs CesiumJS comparison table, scene element inventory, and control reference.

### 🔄 Dashboard
* **`dashboard.py`** bumped to v4.0.0.  All spoofing heuristics, TDOA uncertainty visualisation, anomaly overlay, jamming detection, and TAK/Palantir tactical styling from v3.5.0 are fully preserved.  No new Python dependencies.

---

## [0.8.1] - 2026-02-01: The "Elastic Grid" Milestone
**Major Feature Release: TDOA Synchronization, Clock Drift Compensation, and Multi-Sensor Triangulation.**

### 🚀 Physics & Synchronization (Scientific Proof)
* **Elastic Grid Algorithm:** Implemented a linear heartbeat model ($True\_Time = t_{raw} - (Bias + Drift \times dt)$) to compensate for non-coherent SDR clock drift across the grid.
* **Drift Quantification:** Successfully measured and corrected for individual hardware crystal errors:
    * **Sensor-West (Jorvas):** **+273 PPM** (Fast clock).
    * **Sensor-East (Sibbo):** **-51 PPM** (Slow clock).
* **Golden Packet Harvester:** Added `analyze_tdoa_v23_golden_harvester.py` to identify simultaneous 3-node detections for definitive triangulation proof.
* **Robust Solver:** Integrated a 4-variable Robust Least Squares optimizer (`v15_elastic_solver.py`) to solve for Lat/Lon offsets and drift rates simultaneously using commercial aircraft as "Signals of Opportunity."

### 📊 Visualization (Scientific Evidence)
* **Golden Cross Map:** Developed `v28_golden_cross_final.py` for high-precision validation. Features **Purple (N-W)** and **Red (N-E)** dotted TDOA hyperbolas intersecting at GPS ground truth.
* **Color Standardization:** Anchored the visual schema for all research artifacts:
    * **🟦 North (Master):** Blue (PPS-disciplined anchor).
    * **🟩 West (Slave):** Green (+273 PPM).
    * **🟥 East (Slave):** Red (-51 PPM).
* **Full-Scale Projections:** Updated mapping logic (`v21_master_final.py`) to visualize full hyperbolic curves across 200km+ baselines without clipping.

### 🔬 Documentation & Wiki
* **Project Wiki Update:** Completed **Chapter 15 (Hardware Considerations)**, providing a technical comparison between DS3231 (TCXO) stability vs. GNSS PPS clock disciplining.
* **LaTeX Standards:** Hardened math documentation with double-escaped underscores (`\\_`) to ensure universal MathJax/Markdown rendering for the synchronization formula.
* **Procedural Guide:** Documented the "Triple-Baseline Calibration" workflow (Harvest -> Solve -> Validate).

### 🐛 Fixes
* **Clock Skew:** Resolved the "300km Drift Error" where uncompensated SDR crystals caused TDOA lines to miss targets by massive margins within 10 seconds of capture.
* **Visualization Bounds:** Fixed `v17_elastic_map_fixed.py` where distant aircraft (>100km) were previously cut off by hardcoded axis limits.
* **Ambiguity Error:** Resolved `ValueError` in Python analysis scripts caused by ambiguous truth values during Pandas Series comparisons in the map generator.

---


## [0.8.0] - 2026-01-15: The "Panopticon" Update
**Major Feature Release: Full Observability, Ensemble ML, and DevOps Automation**

### 🚀 Infrastructure & DevOps
* **Makefile "Control Center":** Added shortcuts (`make dashboard`, `make logging`) for rapid iteration.
* **Ansible Dashboarding:** Grafana dashboards are now provisioned via Ansible code (IaC).
* **Logging Overhaul:** Replaced Fluent Bit with **Logstash (v8)** on port 5514 for robust syslog parsing.
* **Security:** Hardened pipeline configuration permissions (`0640`) to prevent credential leakage.

### 📊 Visualization (Grafana)
* **Grid Health V4:** Real-time sensor activity stream with `syslog_hostname` filtering.
* **OwnTracks Chase:** 1s refresh rate tactical map for field agents.
* **System Overview:** Universal TIG stack monitoring (CPU/RAM/Temp/Disk).

### 🧪 Data Science (Tier 1)
* **Ensemble Detection:** Upgraded anomaly detection to a voting system:
    * *Model A:* Isolation Forest (Global geometric anomalies).
    * *Model B:* Local Outlier Factor (LOF) (Local density/cluster anomalies).
* **Windowed Reporting:** Added `--window` argument to EDA pipeline. Reports can now slice data by "Last 24h", "48h", or "Total History".
* **Training Export:** Pipeline now auto-generates `training_dataset_v4_ensemble.csv` for future Supervised Learning (XGBoost).

### 🐛 Fixes
* **Data Ingestion:** Fixed pipeline crash caused by mismatched paths (`infra/ansible` vs root) and GZIP handling.
* **Robustness:** Added fault tolerance to `infra_health.py` to skip corrupted CSV lines instead of crashing.
* **Dashboard Mappings:** Fixed "No Data" bug in Grafana by aligning `host` tag to `syslog_hostname`.



## [0.7.6] - 2026-01-14
### Added
- **GNSS Certification (D12):** New analysis module (`gnss_analysis.py`) to validate sensor hardware precision (Jitter & CEP).
- **Multi-Path Discovery:** Analysis scripts now automatically locate logs in both `research_data/` and Ansible staging areas.
- **Auto-Documentation:** `make report` now updates a `docs/showcase/latest` symlink-style folder for permanent README linking.

### Fixed
- **Path Logic:** Fixed `make gnss` target to output correctly to the report figures directory.
- **Zero-Coordinate Bug:** Filtered invalid `0.0` lat/lon fixes that were skewing centroid calculations for East/West sensors.
- **Sensor North Audit:** Confirmed Sensor North is currently outputting status-only (GNTXT) logs; pipeline now handles "0 position" scenarios gracefully.

## [0.7.5] - 2026-01-14
### Added
- **Infrastructure Dashboard (D5):** Now includes Avg/Max temperature statistics in the legend and a visual "Nominal Range" (green band) for thermal health.
- **Report Enhancements:** Added "Data Window" (Start/End times) and automated "Missing Sensor" warnings to `REPORT.md`.
- **Ghost Hunt:** Renumbered forensic maps (D7-D10) for logical flow.
- **Makefile:** Added `make help`, `setup`, and `deploy` targets; added auto-cleaning for ghost maps.

### Changed
- **Visuals:** Tightened D3 Spatial Zoom to focus strictly on sensor geometry.
- **Health:** Merged Thermal and Storage plots into a single synchronized dashboard.


## [0.7.1] - 2026-01-13
### Added
- **Log Aggregation:** Implemented \`fetch_logs.sh\` on Tower Core with a daily Cron job (04:00 AM) to harvest and archive sensor logs.
- **Real-Time Logging:** Verified active Rsyslog streaming from all three sensors (North, East, West) to Tower Core storage.

### Changed
- **Grafana Dashboard:** Overhauled "System Overview" (V4) with universal Flux queries, "Smart Disk" detection (handling both \`/\` and \`/hostfs\`), and improved 2x2 layout with sparklines.
- **Sensor Provisioning:** Updated Telegraf Docker permissions to allow access to \`/var/run/docker.sock\` for container metrics on all nodes.

### Fixed
- **Connectivity:** Opened port 8086 on \`sensor-north\` UFW, resolving "Connection Refused" errors to the InfluxDB tower.
- **Ansible Templates:** Fixed empty Flux queries and YAML syntax errors in the \`tower_core\` role that prevented dashboard provisioning.


## [0.7.0] - 2026-01-12
### Added
- **Tower Core:** Full deployment of TIG Stack (Telegraf, InfluxDB v2, Grafana) and Mosquitto MQTT Broker on Raspberry Pi 5.
- **Observability:** Automated provisioning of "System Overview" Dashboard in Grafana with dynamic host filtering.
- **Universal Sensor Role:** New Ansible role (`sensor_node`) that dynamically configures North/West/East based on inventory variables.
- **Hardware Abstraction:** Moved all hardware-specific settings (SDR Gain, GNSS Driver, Serial Paths) into `inventory/hosts.prod` as the Single Source of Truth.

### Changed
- **Inventory:** Refactored `hosts.prod` to support mixed-user fleets (Legacy `pi` user for North, `admin` for Core).
- **Telegraf:** Standardized configuration across all nodes; added `/hostfs` mounting to correctly monitor host storage from within Docker containers.
- **Dashboard:** Refined "System Overview" layout (increased panel height to 14, moved legends to table view) to accommodate multi-sensor NVMe data.

### Fixed
- **Docker Race Condition:** Fixed an issue where Docker created a directory instead of a file for `telegraf.conf` by ensuring config generation happens before container startup.
- **Disk Monitoring:** Solved "No Data" in Disk Usage graphs by explicitly mapping `/:/hostfs:ro` in Docker Compose.


## [0.6.5] - 2026-01-12
### Added
- **Self-Healing Data:** Added `scripts/maintenance/consolidate_fragments.py` to automatically detect and merge fragmented 1-minute sensor logs into daily gzip archives (fixing `sensor-west` instability).
- **Forensics:** Added "Ghost Hunt" probabilistic heatmaps to `docs/showcase/ghost_hunt/`.
- **Documentation:** Added robust relative links to the `README.md` for direct access to forensic reports.

### Changed
- **Pipeline:** Updated `Makefile` to trigger `consolidate` automatically during `fetch` and `all` targets.
- **Reporting:** Restored **Section 6: Research Data Schema** in `academic_eda.py`, providing full academic definitions for `nic`, `sil`, and `rssi`.
- **Showcase:** Consolidated all run artifacts into `docs/showcase/latest_audit/`, removing obsolete timestamped folders to reduce repository bloat.

### Verified
- **Physics:** Validated 6,293 anomalies (0.98% of traffic) in the Jan 12th dataset.
- **Data Integrity:** Confirmed `sensor-west` is now generating clean ~3KB daily stats logs instead of thousands of fragments.

## [0.6.0] - 2026-01-12
### 🚀 Infrastructure & Stability
- **Critical Fix:** Deployed NetworkManager configuration to disable WiFi power management on all nodes (prevents "Sleep Coma" on Sensor-East/West).
- **Refactor:** Moved remote health logic from Ansible tasks to a dedicated script (`/opt/adsb/scripts/health_monitor.sh`) for better version control.

### 🛠️ Diagnostics
- **Upgrade:** Updated `check_signal_health.py` to v6.1.
- **Robustness:** Implemented "Best Lock" logic for GNSS. The system now captures raw GPS streams and sorts for the highest quality fix (3D > 2D > No Fix) instead of accepting the first packet.
- **Reliability:** Added fault tolerance to SSH commands to prevent dashboard crashes during GPS timeouts.

### 🔬 Data Science
- **Pipeline:** Validated end-to-end execution of `make all` (Fetch -> ML -> Report).
- **Analysis:** Generated `run_2026-01-12_1342` report showing 5,996 detected anomalies (1.00% contamination rate).


## [0.5.0] - 2026-01-12 (The Data Science Release)
### 🚀 Major Features
- **Forensic EDA Engine (`academic_eda.py`):**
  - **Showcase Generator:** Creates comprehensive "Showcase" reports (Markdown + 4x4 Composite Dashboards) for scientific defense.
  - **Physics Validation:** Implements Inverse-Square Law checks (RSSI vs Distance) and Flight Envelope analysis (Alt vs Speed).
  - **Fault Tolerance:** Robust handling of missing Squawk/GNSS data without pipeline failure.
- **Machine Learning Pipeline (`ds_pipeline_master.py`):**
  - **Anomaly Detection:** Added `IsolationForest` (Unsupervised Learning) to detect spoofing candidates based on 4-dimensional feature vectors.
  - **Feature Engineering:** Automated calculation of Velocity Discrepancy (Physics vs Reported) and SNR Proxies.

### 🛠️ Infrastructure
- **Makefile v3.5.0:** Separated `make report` (Forensic Documentation) from `make ml` (AI Training) workflows.
- **Requirements:** Added `scikit-learn`, `seaborn`, `tabulate` for advanced analytics.
- **Data Hygiene:** Implemented "Showcase Strategy" to keep Git clean while archiving scientific runs in `docs/showcase/`.

### 🐛 Bug Fixes
- Fixed `ImportError: tabulate` during report generation.
- Fixed `ModuleNotFoundError: requests` in health check scripts.
- Resolved timestamp timezone conflicts (ISO-8601 vs Unix Epoch) across heterogenous sensor logs.

---

## [0.4.6] - 2026-01-10 (Scientific Pipeline Release)
### 🚀 Major Features
- **Scientific Data Pipeline:**
    - **Ingest:** Added `fetch.yml` to securely pull CSV logs to `research_data/`.
    - **Consolidate:** Added `scripts/consolidate_data.py` to merge fragmented 2-minute logs into Daily Masters.
    - **Visualize:** Added `scripts/eda_academic_report.py` (v2.0) generating professional PDF research reports.
- **Smart Logging Architecture:**
    - Replaced legacy recording with `smart_adsb_logger.py` in `infra/ansible/roles/recorder/`.
    - Added `gps_hardware_init.sh` for robust U-Blox/SDR hardware initialization.

### 📂 Repository Refactoring
- **Archival:** Moved legacy plots and R-history files to `analysis/archive/` to clean the workspace.
- **Storage Metrics:** Added `scripts/analyze_storage.py` and `scripts/collect_storage_metrics.py` for long-term disk usage tracking.
- **Infrastructure:** Added `setup_data_manager.yml` and `setup_metrics_collector.yml` playbooks.

### 🔧 Fixes & improvements
- **Ansible:** Fixed `fetch` playbook path resolution to ensure data lands in project root.
- **Hardware:** Validated `sensor-west` (Pi 4/SDR) GNSS lock and RF signal integrity (-31.1 dBFS).
- **Visualization:** Fixed "1970 Epoch" timestamp bug in analysis scripts.
- **Timestamp Scaling:** Resolved "1970 Epoch" bug in analysis scripts by forcing `unit='s'` during Pandas datetime conversion.
- **Duplicate Indexing:** Added robustness to analysis scripts to handle duplicate timestamps in overlapping sensor logs.

## [0.3.5] - 2026-01-08
### Changed
- **Sensor Calibration:** Finalized `sensor-north` gain at **16.6 dB** to accommodate high-gain rooftop antenna (reduced from 29.7 dB).
- **Diagnostics:** Updated `scripts/check_signal_health.py` to **v3.2**, adding support for low-gain settings and expanded tuning tables.
- **Documentation:** Updated Project Master File to **v0.3.5** status, reflecting the move to "Operational" for the North Node.

### Added
- **Validation Artifacts:** Added `analysis/latest/` plots confirming 189 NM range and -7.7 dBFS peak signal (zero clipping).
- **Tower Architecture (Draft):** Added initial Ansible inventory for `tower-core` (Raspberry Pi 5).
- **Data Pipeline (Draft):** Added `infra/database/` schema for TimescaleDB and `scripts/ingest_pipeline.py` for future state-vector stitching.
- **Model Zoo:** Created `model_zoo/REGISTRY.md` defining the 12-architecture ensemble roadmap.


## [0.3.4] - 2026-01-07
### Added
- **Scientific Dashboard:** New `gnss_unified.py` script generating Jitter histograms, CEP-50/95 target plots, and temporal correlation timelines.
- **Automation:** New Ansible playbook `check_gnss.yml` for verifying sensor node status.
- **Reporting:** Automatic generation of `REPORT_SUMMARY.md` with statistical baselines (Mean Jitter, CEP radius).

### Changed
- **Data Transport:** Updated `pull_data.sh` to sync hybrid datasets (both legacy `.log` NMEA and new `.json` GPSD files).
- **Recording Architecture:** Switched sensor node recording from raw NMEA to GPSD JSON format to capture nanosecond PPS timing.

### Deprecated
- Legacy NMEA-only recording (replaced by JSON/PPS stream).


## [0.3.3] - 2026-01-07
### Added
- **Recorder:** Implemented dual-stream recording; now capturing raw GNSS (NMEA) alongside ADS-B data.
- **Timing:** Enabled scientific logging in Chrony (`tracking.log`, `statistics.log`) for Stratum 1 drift analysis.
- **Config:** Hardcoded RTK-derived precise coordinates for `sensor-north` to improve MLAT anchor accuracy.

### Fixed
- **GNSS:** Resolved U-blox baud rate mismatch loop by implementing active `gpsctl` switching (9600 -> 230400).
- **Systemd:** Hardened `gnss-receiver` service with `ExecStartPre` hooks and `socat` baud locking.
- **Ansible:** Fixed missing service restart handlers for the recorder role.


## [0.3.2] - 2026-01-06
### Added
- **Cross-Platform Validation:** Successfully benchmarked the analysis pipeline on three hardware architectures:
    - **Apple Silicon (M4 Max):** 26.46s (Baseline)
    - **Windows x86_64 (WSL 2):** 34.13s (~1.3x slower)
    - **Intel Mac (2017):** 60.45s (~2.3x slower)
- **Documentation:** Added "How to Contribute" guide to README.


## [0.3.0] - 2026-01-06
### Added
- **Scientific Audit Suite:** Promoted `scripts/eda_check.py` to "Master Edition".
    - **Byte-Seeker Parser:** Recovers 99% of ADS-B frames previously lost to synchronization errors (Yield improved 0.2% -> 48.9%).
    - **Statistical Sampling:** Optimized physics calculations to run in <2 minutes using a 50k frame sample.
    - **11-Plot Dashboard:** Generates 4-page visualization suite (Operational, Physics, Spatial, Signals).
    - **Automated Reporting:** Generates `AUDIT_REPORT.md` with executive summaries.
- **Archive Structure:** Created `scripts/archive/` and `analysis/archive/` to preserve prototype experiments.

### Changed
- **Makefile:** Updated `make analyze` to use the new `eda_check.py` arguments and directory scanning mode.
- **Project Status:** Moved to **Phase 3: Scientific Validation** (Physics checks passed).


## [0.2.3] - 2026-01-06
### Added
- **License:** Officially added MIT License file.
- **Dependencies:** Froze exact versions in `requirements.txt` (numpy, pyModeS, etc.).
- **Documentation:** Finalized README with "Research Workflow" and citation data.

### Security
- **Git:** Added strict ignore rules for `.vault_pass` and raw data binaries.


## [0.2.2] - 2026-01-06
### Fixed
- **Sensor Node Networking:** Resolved critical issue where `readsb` container ports were closed.
- **Configuration:** Forced `--net` flags using `READSB_EXTRA_ARGS` to bypass container variable parsing issues.
- **Data Recording:** Verified recording of binary data (non-zero byte files confirmed).

### Added
- **Repository Structure:** Added `requirements.txt`, `Makefile`, and `CITATION.cff`.
- **Analysis Tools:** Added `scripts/eda_check.py` for parsing Beast Binary files and generating health-check plots.
- **License:** Added MIT License.

## [0.2.0] - 2026-01-05 (Infrastructure Baseline)
### 🚀 Added
* **Ansible Roles:**
    * `common`: OS hardening, UFW firewall, Fail2Ban, essential tools.
    * `zerotier`: Automated VPN mesh joining and ID reporting.
    * `sensor_node`: Docker Engine, Compose Plugin, and user permission management.
* **Network Topology:** Established "Century Schema" (VPN IPs .100-.130) for grid independence.
* **Security:** Implemented Vault encryption for secrets and SSH key-based authentication.

## [0.1.0] - 2026-01-05 (Research Definition)
### 📄 Added
* Initial README with 12-Model Architecture.
* Project directory structure.
* Research goals and licensing.
