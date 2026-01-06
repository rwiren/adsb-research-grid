# Securing the Skies: ADS-B Spoofing Detection Grid

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-v0.3.0-green.svg)](#)
[![Status](https://img.shields.io/badge/Status-Phase%203%3A%20Validation-success.svg)](#)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](#)

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
To detect and mitigate GNSS spoofing attacks on civilian aviation tracking systems (ADS-B) using a distributed sensor grid and a **Hybrid AI Model Zoo**. This project moves beyond simple signal 
strength thresholding to a multi-layered defense strategy capable of identifying sophisticated trajectory modification attacks and "ghost" aircraft injections.

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

## 🏗 Architecture (Distributed Sensor Grid)
* **Controller:** Research Workstation (MacOS/Ansible).
* **Tower Core (Aggregation Node):** Raspberry Pi 5. Hostname: `tower-core`.
    * *Role:* Central InfluxDB storage and Grafana visualization.
* **Sensor North (Reference Node):** Raspberry Pi 4. Hostname: `sensor-north`.
    * *Role:* **Stratum-1 Precision Timing**.
    * *Hardware:* **FlightAware Pro Stick (Blue)** + SimpleRTK2B (PPS).
* **Sensor East (Remote Node):** Raspberry Pi 4. Hostname: `sensor-east`.
* **Sensor West (Remote Node):** Raspberry Pi 4. Hostname: `sensor-west`.

---

## 🧪 Research Workflow (Usage)
This repository includes automated tooling (`Makefile`) for infrastructure management, data ingestion, and scientific analysis.

### 1. Quick Start
Run these commands from the repository root:

| Command | Description |
| :--- | :--- |
| `make deploy` | Deploy the latest Ansible configuration to the active sensor grid. |
| `make sync` | **Fetch the latest raw binary data** from `sensor-north` to `data/raw/` (using SCP/Rsync). |
| `make analyze` | **Run the Scientific Audit (v0.3.0)**. Processes raw Beast Binary data using the "Byte-Seeker" algorithm. |
| `make clean` | Remove old analysis artifacts and dashboards. |

### 2. Manual Deployment
To update the grid infrastructure manually without the Makefile:
```bash
ansible-playbook infra/ansible/playbooks/site.yml
```

### 3. Scientific Analysis (The Audit)
To run the full physics validation and generate the "Principal Investigator" dashboard:

```bash
make analyze
```

**Output (`analysis/latest/`):**
* **`AUDIT_REPORT.md`**: Executive summary of traffic volume, data quality, and security threats.
* **`A_Operational.png`**: Grid stability, message rates, and protocol distribution.
* **`B_Physics.png`**: Vertical rates, ground speed, and track angle distributions (Gaussian checks).
* **`C_Spatial.png`**: Coverage maps and Altitude vs. Distance radio horizon analysis.
* **`D_Signals.png`**: RSSI signal strength distribution and correlation matrices (Inverse Square Law validation).

---

## 📂 Repository Structure
* **`infra/`**: Ansible playbooks for Infrastructure as Code (IaC).
* **`data/raw/`**: Binary recordings from the sensor nodes (Beast format).
* **`scripts/`**: Python analysis tools.
    * `eda_check.py`: The Master Analysis Suite (v0.3.0).
    * `archive/`: Deprecated prototype scripts and experiments.
* **`analysis/`**: Generated charts and reports.
    * `latest/`: Results from the most recent run.
    * `archive/`: Historical data validation runs.

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
3.  **Test:** Run `make analyze` (Must pass locally!)
4.  **Commit:** Use [Conventional Commits](https://www.conventionalcommits.org/) (e.g., `feat:`, `fix:`, `docs:`).
5.  **Merge:** Open a Pull Request.

### 3. Setup
- Run `make setup` to initialize the environment.
- Fetch data manually from `sensor-north` (data is not in git).
