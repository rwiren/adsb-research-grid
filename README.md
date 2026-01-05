# Securing the Skies: ADS-B Spoofing Detection Grid

[![License: Academic](https://img.shields.io/badge/License-Academic_Research-blue.svg)](#)
[![Version](https://img.shields.io/badge/Version-v0.1.1-green.svg)](#)

## 📋 Table of Contents
1. [Research Goal](#-research-goal)
2. [The Model Zoo (12 Architectures)](#-the-model-zoo-12-architecture-ensemble)
3. [Architecture (Hardware Grid)](#-architecture-distributed-sensor-grid)
4. [Project Heritage](#-project-heritage)
5. [Usage](#-usage)
6. [License](#-license)

---

## 🔬 Research Goal
To detect and mitigate GNSS spoofing attacks on civilian aviation tracking systems (ADS-B) using a distributed sensor grid and a **Hybrid AI Model Zoo**. This project moves beyond simple thresholding to a multi-layered defense strategy capable of identifying sophisticated trajectory modification attacks.

## 🧠 The "Model Zoo": 12-Architecture Ensemble
The detection engine utilizes a comparative ensemble of 12 distinct methods, layered by computational complexity and abstraction level:

### Tier 1: Edge Baselines (Explainable AI)
* **1. Random Forest (RF):** "Sanity Check" filtering based on physical feature extraction (RSSI vs. Distance consistency).
* **2. XGBoost / LightGBM:** High-speed, Treelite-compiled inference optimized for the Raspberry Pi edge.
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

## 🏗 Architecture (Distributed Sensor Grid)
* **Controller:** Workstation (Ansible)
* **Tower Core (Aggregation Node):** Raspberry Pi 5. Hostname: `tower-core`.
* **Sensor North (Reference Node):** Raspberry Pi 4. **Stratum-1 Timing + High-Fidelity SDR**. Hostname: `sensor-north`.
* **Sensor East (Remote Node):** Raspberry Pi 4. Hostname: `sensor-east`.
* **Sensor West (Remote Node):** Raspberry Pi 4. Hostname: `sensor-west`.

## 📜 Project Heritage
This project supersedes the original **Central Brain PoC**. 
* **Theory:** See the [Legacy Wiki](https://github.com/rwiren/central-brain/wiki) for detection logic.
* **Datasets:** Early baseline datasets are archived in the legacy repo.

## 🚀 Usage
1. **Deploy Grid:** `ansible-playbook infra/ansible/playbooks/site.yml`
2. **Start Agent:** `systemctl start adsb-agent`
3. **Analyze:** Run Jupyter Notebooks in `src/core_brain/analysis/`

## 🛡 License
Academic Research License - Do not distribute without citation.
