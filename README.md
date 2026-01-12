# Securing the Skies: ADS-B Spoofing Detection Grid

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-v0.6.5-green.svg)](#)
[![Status](https://img.shields.io/badge/Status-Phase%203%3A%20Validation-success.svg)](#)
[![Wiki](https://img.shields.io/badge/Docs-Project%20Wiki-purple?style=flat-square)](https://github.com/rwiren/adsb-research-grid/wiki)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](#)
![Last Updated](https://img.shields.io/github/last-commit/rwiren/adsb-research-grid?label=Last%20Updated&color=orange)

## 📋 Table of Contents
1. [Research Goal](#-research-goal)
2. [The Model Zoo (12 Architectures)](#-the-model-zoo-12-architecture-ensemble)
3. [Architecture (Hardware Grid)](#-architecture-distributed-sensor-grid)
4. [Research Workflow (Usage)](#-research-workflow-usage)
5. [Repository Structure](#-repository-structure)
6. [Project Heritage](#-project-heritage)
7. [License & Citation](#-license--citation)

---

## 🔬 Research Goal
To detect and mitigate GNSS spoofing attacks on civilian aviation tracking systems (ADS-B) using a distributed sensor grid and a **Hybrid AI Model Zoo**. This project moves beyond simple signal strength thresholding to a multi-layered defense strategy capable of identifying sophisticated trajectory modification attacks and "ghost" aircraft injections.

---

## 🧠 The "Model Zoo": 12-Architecture Ensemble
The detection engine utilizes a comparative ensemble of 12 distinct methods, layered by computational complexity and abstraction level:

### Tier 1: Edge Baselines (Explainable AI)
* **1. Random Forest (RF):** "Sanity Check" filtering based on physical feature extraction (RSSI vs. Distance consistency).
* **2. XGBoost / LightGBM:** High-speed, Treelite-compiled inference optimized for the Raspberry Pi edge agent.
* **3. Reinforcement Learning (RL):** Single-agent active sensor tuning (Gain/Threshold optimization) to maximize Signal-to-Noise Ratio.
* **4. Multi-Agent RL (MARL):** Decentralized coordination allowing sensor nodes to cooperatively optimize grid-wide coverage.

### Tier 2: Spatial & Temporal Deep Learning
* **5. Graph Neural Networks (GNN):** Modeling the sensor grid as a geometric graph to detect spatial anomalies (e.g., signal seen by Node A but physically impossible to be missed by Node B).
* **6. Graph Attention Networks (GAT):** Dynamic weighting of sensor reliability, allowing the grid to "ignore" noisy or jammed nodes.
* **7. Transformers (FlightBERT++):** Long-range trajectory forecasting using self-attention to detect subtle "meandering" drift.
* **8. xLSTM:** Extended Long Short-Term Memory networks for recurrent anomaly detection with improved memory retention.
* **9. Liquid Neural Networks (LNN):** Time-continuous neural networks designed for adaptive signal processing on irregular time-series data.

### Tier 3: Physics & Generative Validation
* **10. Physics-Informed Neural Networks (PINN):** Embedding Equations of Motion (EoM) directly into the loss function to penalize physically impossible maneuvers.
* **11. Kolmogorov-Arnold Networks (KAN):** Symbolic regression for real-time estimation of aerodynamic coefficients (Lift/Drag).
* **12. Generative Adversarial Networks (GAN):** "Red Teaming" the system by generating synthetic zero-day attack signatures to harden the classifiers.

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
  make check      - 🏥 Real-time Sensor Health Dashboard

  --- SCIENCE (Data) ---
  make fetch      - 📥 Download, Heal & Merge logs from grid
  make consolidate- 🧹 Manually fix fragmented logs (1-min -> Daily)
  make ml         - 🧪 Run Anomaly Detection (Isolation Forest)
  make ghosts     - 👻 Generate Forensic Maps (Ghost Hunt)
  make report     - 📊 Generate Academic Audit Report
  make all        - 🔁 Run Full Pipeline (Fetch->Heal->ML->Report)
```

### 2. Scientific Workflows

#### **A. The "Gold Standard" Run**
To perform a complete scientific audit (Ingest data $\rightarrow$ Heal fragmentation $\rightarrow$ Detect Anomalies $\rightarrow$ Generate Report):
```bash
make all
```
* **Output:** `docs/showcase/latest_audit/REPORT.md` and `research_data/ml_ready/`

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
