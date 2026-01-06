# Securing the Skies: ADS-B Spoofing Detection Grid

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-v0.2.2-green.svg)](#)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](#)

## 📋 Table of Contents
1. [Research Goal](#-research-goal)
2. [The Model Zoo (12 Architectures)](#-the-model-zoo-12-architecture-ensemble)
3. [Architecture (Hardware Grid)](#-architecture-distributed-sensor-grid)
4. [Research Workflow (Usage)](#-research-workflow-usage)
5. [Project Heritage](#-project-heritage)
6. [License & Citation](#-license--citation)

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
* **Controller:** Research Workstation (MacOS/Ansible)
* **Tower Core (Aggregation Node):** Raspberry Pi 5. Hostname: `tower-core`.
* **Sensor North (Reference Node):** Raspberry Pi 4. **Stratum-1 Timing + High-Fidelity SDR**. Hostname: `sensor-north`.
* **Sensor East (Remote Node):** Raspberry Pi 4. Hostname: `sensor-east`.
* **Sensor West (Remote Node):** Raspberry Pi 4. Hostname: `sensor-west`.

---

## 🧪 Research Workflow (Usage)
This repository includes automated tooling (`Makefile`) for infrastructure management, data ingestion, and analysis.

### 1. Quick Start
Run these commands from the repository root:

| Command | Description |
| :--- | :--- |
| `make setup` | Install Python research dependencies (pandas, pyModeS, seaborn). |
| `make deploy` | Deploy the latest Ansible configuration to the active sensor grid. |
| `make download` | **Fetch the latest raw binary data** from `sensor-north` to `data/raw/`. |
| `make analyze` | **Run the EDA script** to generate health-check plots in `analysis/`. |

### 2. Manual Deployment
To update the grid infrastructure manually without the Makefile:
```bash
ansible-playbook infra/ansible/playbooks/site.yml
```

### 3. Data Analysis Output
Running `make analyze` will process the raw Beast Binary data and generate:
- **Signal Quality:** RSSI distribution plots (Hardware Gain Check).
- **Traffic Density:** Message rate over time (Stability Check).
- **Protocol Breakdown:** ADS-B Message Type statistics (Data Quality Check).

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
