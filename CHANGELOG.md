# Changelog

All notable changes to the **ADS-B Research Grid** project will be documented in this file.

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
## [0.4.6b] - 2026-01-10 (Scientific Pipeline Release)
- Added `fetch.yml` for secure log retrieval.
- Added `consolidate_data.py` for daily master log merging.
- Refactored legacy recording to `smart_adsb_logger.py`.



## [0.4.6b] - 2026-01-10 (Scientific Pipeline Release)
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



## [0.4.6] - 2026-01-10
### Added
- **Scientific Pipeline:** Implemented `scripts/consolidate_data.py` to merge fragmented 2-minute sensor logs into clean daily MASTER datasets (`_aircraft`, `_gnss`, `_stats`).
- **Visualization Engine:** Introduced `scripts/eda_academic_report.py` (v2.0) which generates 3-page academic PDF reports containing:
    - Executive Summaries (Uptime, Traffic Volume, Signal Integrity).
    - RF Intelligence Plots (RSSI vs Altitude, Message Rates).
    - Hardware Diagnostics (GNSS Drift, CPU Thermals).
- **Workflow Automation:** Added `make consolidate` and `make analyze` targets to the Makefile.

### Changed
- **Data Ingestion:** Updated `fetch.yml` to v0.4.7; fixed critical path resolution issue to ensure data lands in project root (`research_data/`) regardless of execution directory.
- **Ansible Syntax:** Updated variable injection to use modern `ansible_facts` namespace, eliminating deprecation warnings.
- **Hardware Validation:** Validated `sensor-west` (Raspberry Pi 4 / Silver RTL-SDR) performance:
    - Confirmed GNSS lock with ~30m stationary drift (expected for indoor/test).
    - Validated RF signal integrity (-31.1 dBFS avg).

### Fixed
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

# 📝 Project Changelog


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

## [v0.2.0] - 2026-01-05 (Infrastructure Baseline)
### 🚀 Added
* **Ansible Roles:**
    * `common`: OS hardening, UFW firewall, Fail2Ban, essential tools.
    * `zerotier`: Automated VPN mesh joining and ID reporting.
    * `sensor_node`: Docker Engine, Compose Plugin, and user permission management.
* **Network Topology:** Established "Century Schema" (VPN IPs .100-.130) for grid independence.
* **Security:** Implemented Vault encryption for secrets and SSH key-based authentication.

## [v0.1.0] - 2026-01-05 (Research Definition)
### 📄 Added
* Initial README with 12-Model Architecture.
* Project directory structure.
* Research goals and licensing.
