# Securing the Skies: ADS-B Spoofing Detection Grid

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-v0.9.0-green.svg)](#)
[![Status](https://img.shields.io/badge/Status-Phase%203%3A%20Validation-success.svg)](#)
[![Wiki](https://img.shields.io/badge/Docs-Project%20Wiki-purple?style=flat-square)](https://github.com/rwiren/adsb-research-grid/wiki)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](#)
![Last Updated](https://img.shields.io/github/last-commit/rwiren/adsb-research-grid?label=Last%20Updated&color=orange)

[![Audit Report](https://img.shields.io/badge/View-Latest%20Report-blue?style=for-the-badge&logo=github)](docs/showcase/latest/REPORT.md)

## 📋 Table of Contents
1. [Research Goal](#-research-goal)
2. [The Model Zoo (18 Architectures)](#-the-model-zoo-18-architecture-ensemble)
3. [Architecture (Hardware Grid)](#-architecture-distributed-sensor-grid)
4. [Research Workflow (Usage)](#-research-workflow-usage)
5. [Repository Structure](#-repository-structure)
6. [Project Heritage](#-project-heritage)
7. [License & Citation](#-license--citation)

---

# 🔬 Research Goal: The "Elastic Manifold" Defense

To detect and mitigate GNSS spoofing attacks on civilian aviation tracking systems (ADS-B) using a distributed sensor grid and a **Hybrid AI Model Zoo**. This project moves beyond simple signal strength thresholding to a multi-layered defense strategy capable of identifying sophisticated trajectory modification attacks, "ghost" aircraft injections, and hardware-level signal cloning.

The core innovation is the **Elastic Manifold Architecture**: a system that validates aircraft not just by physics (speed/altitude), but by **topology** (mathematical constraints), **time** (elastic synchronization), and **hardware signatures** (RF fingerprinting).

---

# 🧠 The "Model Zoo": 18-Architecture Ensemble

The detection engine utilizes a comparative ensemble of 18 distinct methods, layered by computational complexity and abstraction level.

**Status Legend:**
✅ **Implemented** | ⚠️ **Planned / In Progress** | 🔄 **Integration Phase**

### Tier 0: The Physical Truth (Hardware & Signal Layer)
*New layer establishing "Ground Truth" independent of decoded data.*

* **1. Elastic Grid TDOA (Physics):** "The Anchor." Uses nanosecond-level Time Difference of Arrival (TDOA) to calculate the *physical* location of a transmitter, independent of the GPS coordinates reported in the data packet. (✅ **Verified in Science Run**)
* **2. RF Fingerprinting (CNN/ResNet):** "The Hardware ID." A Deep Learning model (running on Hailo-8) that analyzes Raw I/Q signal data to identify the unique electronic signature of the transmitter (e.g., distinguishing a HackRF One from a Garmin transponder). (⚠️ *Planned*)

### Tier 1: Edge Baselines (Reflex Layer)
*Fast, low-latency filters running on Raspberry Pi CPU.*

* **3. Sinkhorn-Knopp Algorithm:** Mathematical gatekeeper using Optimal Transport theory to project signal cost matrices onto the **Birkhoff Polytope**. Fails to converge on "impossible" signal clusters. (✅ **Implemented**)
* **4. Random Forest (RF):** "Sanity Check" filtering based on basic feature extraction (RSSI vs. Distance consistency). (✅ **Implemented**)
* **5. XGBoost / LightGBM:** High-speed, Treelite-compiled inference for detecting known spoofing software signatures. (✅ **Implemented**)
* **6. Reinforcement Learning (RL):** "The Auto-Tuner." Single-agent active learning that dynamically optimizes **RF Gain** and **Squelch** to maximize SNR for specific targets. (✅ **Implemented**)
* **7. Multi-Agent RL (MARL):** Decentralized coordination allowing sensor nodes (North/East/West) to cooperatively optimize grid-wide coverage. (✅ **Implemented**)

### Tier 2: Temporal & Stream Intelligence
*Understanding the flow of time and trajectory continuity (Hailo-8 NPU).*

* **8. Mamba (SSM):** State Space Models for efficient long-context trajectory tracking. Detects slow "drift" attacks that standard Transformers miss due to linear scaling efficiency. (✅ **Implemented**)
* **9. xLSTM:** Extended Long Short-Term Memory networks for precise validation of rapid maneuvers and sharp turns. (✅ **Implemented**)
* **10. Liquid Neural Networks (LNN):** Time-continuous neural networks designed to handle irregular ADS-B packet arrival times without losing context. (✅ **Implemented**)
* **11. Transformers (FlightBERT++):** Self-attention based trajectory forecasting to detect subtle "meandering" anomalies. (⚠️ *Planned*)

### Tier 3: Topological & Spatial Reasoning
*Understanding the shape of the swarm and sensor trust.*

* **12. DeepSeek MCHC (Manifold-Constrained Hyper-Connection):** Graph Neural Network with topology-based validation to detect "ghost aircraft" formations that violate manifold constraints. (✅ **Implemented**)
* **13. Graph Neural Networks (GNN):** Modeling the sensor grid as a geometric graph to detect spatial anomalies (e.g., signals visible to Node A but impossibly occluded from Node B). (⚠️ *Planned*)
* **14. Graph Attention Networks (GAT):** Dynamic weighting of sensor reliability based on **Clock Drift (PPM)** stability, allowing the grid to "ignore" jammed nodes. (⚠️ *Planned*)

### Tier 4: Physics, Logic & Generative Validation
*High-level reasoning and adversarial testing (M4 Max / Server).*

* **15. Physics-Informed Neural Networks (PINN):** Embedding Equations of Motion (Navier-Stokes/Kinematics) directly into the loss function to penalize physically impossible maneuvers. (✅ **Implemented**)
* **16. Kolmogorov-Arnold Networks (KAN):** Symbolic regression for real-time estimation of aerodynamic coefficients (Lift/Drag). Flags targets flying with impossible parameters. (✅ **Implemented**)
* **17. RL-Enhanced GAN (RL-GAN):** "The Smart Red Team." Uses Reinforcement Learning to guide the Generator (GAN), rewarding it for successfully bypassing specific Tier 1-3 defenses. (✅ **Implemented as GAN**)
* **18. Ollama Reasoning Swarm (DeepSeek-R1 / Llama 3 / Phi-3):** "The Investigator." Validated ensemble of LLMs analyzing MQTT-based incident logs. Benchmarks confirm efficacy in parsing complex, multi-variable anomaly scenarios (SecuringSkies Benchmarks). (✅ **Benchmarked & Implemented**)

---

### 🛡️ Manifold Defense System (Integration)
The project orchestrates these tiers into a single decision engine, formerly referred to as the **ManifoldGuard Ensemble**.

**Key Features:**
- **Weighted Ensemble Vote:** A voting mechanism where Tier 0 (Physics) has veto power over Tier 2/3 (AI).
- **Lightweight Inference:** Optimized for **Raspberry Pi 5 + Hailo-8 NPU** (~30ms latency with full ensemble).
- **Graceful Fallback:** System degrades safely from "Full Manifold Defense" to "Basic RF Filtering" if hardware resources are constrained.
- **Distributed Trust:** Uses **GAT** and **Elastic TDOA** to dynamically identify and isolate compromised sensors in the grid.
- **ONNX Export:** Tier 1-3 models are ready for NPU acceleration.
  
---

## 📡 Grid Infrastructure
> For detailed hardware specifications, wiring diagrams, and GNSS benchmarks, please consult the **[Project Wiki](https://github.com/rwiren/adsb-research-grid/wiki)**.

* **Controller: Research Workstation**
    * **OS:** MacOS / Ansible Control Node
    * **Role:** Orchestration, Playbook deployment, and Data Analysis.

* **Tower Core (Aggregation Node)**
    * **Hostname:** `tower-core`
    * **Hardware:** Raspberry Pi 5 (16GB) + 1TB NVMe
    * **Role:** Central InfluxDB storage, Grafana visualization, and signal correlation.

* **Sensor North (Reference Node)**
    * **Hostname:** `sensor-north`
    * **Hardware:** Raspberry Pi 4 (4GB) + 32GB SD
    * **Radio/GNSS:** USB SDRs (FlightAware Blue/Jetvision/RTL-SDR) + SimpleRTK2B (PPS)
    * **Role:** Stratum-1 Precision Timing & Reference Geolocation.

* **Sensor West (Remote Node)**
    * **Hostname:** `sensor-west`
    * **Hardware:** Raspberry Pi 4 (4GB) + 64GB SD
    * **Radio/GNSS:** USB SDRs (RTL-SDR "silver") + G-STAR IV GNSS
    * **Location:** Jorvas (Currently acting as hw verification).

* **Sensor East (Remote Node)**
    * **Hostname:** `sensor-east`
    * **Hardware:** Raspberry Pi 4 (4GB) + 16GB SD
    * **Radio/GNSS:** USB SDRs (FlightAware Blue) + G-STAR IV GNSS
    * **Location:** Sibbo.
      
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
* **Output:** `docs/showcase/latest_audit/REPORT.md` and `research_data/ml_ready/`

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

**Output (`docs/showcase/latest_audit/REPORT.md`):**
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
* **`models/`**: Advanced ML models for the 16-Model Zoo (Manifold Defense System).
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
    - `echo 'THE_PASSWORD' > .vault_pass`
- **Environment:** Run `make setup` to initialize the Python environment.
