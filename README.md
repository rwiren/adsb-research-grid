# Securing the Skies: ADS-B Spoofing Detection Grid

## 🔬 Research Goal
To detect and mitigate GNSS spoofing attacks on civilian aviation tracking systems (ADS-B) using a distributed sensor grid and a **Hybrid AI 
Model Zoo**.

## 🧠 The "Model Zoo": 12-Architecture Ensemble
The detection engine utilizes a comparative ensemble of 12 distinct methods, layered by computational complexity:

### Tier 1: Edge Baselines (Explainable AI)
1. [cite_start]**Random Forest (RF):** "Sanity Check" filtering based on physical feature extraction (RSSI vs. Distance)[cite: 24].
2. [cite_start]**XGBoost / LightGBM:** High-speed, Treelite-compiled inference for pre-filtering on Raspberry Pi[cite: 66].
3. [cite_start]**Reinforcement Learning (RL):** Single-agent active sensor tuning (Gain/Threshold optimization)[cite: 87].
4. [cite_start]**Multi-Agent RL (MARL):** Decentralized coordination for grid-wide coverage optimization[cite: 129].

### Tier 2: Spatial & Temporal Deep Learning
5. [cite_start]**Graph Neural Networks (GNN):** Modeling the sensor grid as a geometric graph to detect spatial anomalies[cite: 140].
6. [cite_start]**Graph Attention Networks (GAT):** Dynamic weighting of sensor reliability based on noise environments[cite: 174].
7. [cite_start]**Transformers (FlightBERT++):** Long-range trajectory forecasting using self-attention mechanisms[cite: 176].
8. **xLSTM:** Extended Long Short-Term Memory networks for recurrent anomaly detection.
9. **Liquid Neural Networks (LNN):** Time-continuous neural networks for adaptive signal processing.

### Tier 3: Physics & Generative Validation
10. [cite_start]**Physics-Informed Neural Networks (PINN):** Embedding Equations of Motion (EoM) directly into the loss function[cite: 214].
11. [cite_start]**Kolmogorov-Arnold Networks (KAN):** Symbolic regression for real-time aerodynamic coefficient estimation[cite: 235].
12. [cite_start]**Generative Adversarial Networks (GAN):** "Red Teaming" the system with synthetic zero-day attack signatures[cite: 245].

## 🏗 Architecture (Distributed Sensor Grid)
* **Controller:** Workstation (Ansible)
* **Tower Core (Aggregation Node):** Raspberry Pi 5. Hostname: `tower-core`.
* **Sensor North (Reference Node):** Raspberry Pi 4. **Stratum-1 Timing + High-Fidelity SDR**. Hostname: `sensor-north`.
* **Sensor East (Remote Node):** Raspberry Pi 4. Hostname: `sensor-east`.
* **Sensor West (Remote Node):** Raspberry Pi 4. Hostname: `sensor-west`.

## 🚀 Usage
1. **Deploy Grid:** `ansible-playbook infra/ansible/playbooks/site.yml`
2. **Start Agent:** `systemctl start adsb-agent`
3. **Analyze:** Run Jupyter Notebooks in `src/core_brain/analysis/`

## 🛡 License
Academic Research License - Do not distribute without citation.
