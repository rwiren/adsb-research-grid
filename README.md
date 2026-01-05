# Securing the Skies: ADS-B Spoofing Detection Grid

## 🔬 Research Goal
To detect and mitigate GNSS spoofing attacks on civilian aviation tracking systems (ADS-B) using a distributed sensor grid and a **Hybrid AI Model Zoo**.

The detection engine utilizes a comparative ensemble of 12 distinct architectures, including:
* **Physics-Informed Neural Networks (PINNs)** for kinematic validation.
* **Liquid Neural Networks (LNNs)** for time-continuous signal processing.
* **xLSTM & Transformers** for long-sequence anomaly detection.

## 🏗 Architecture (The Keimola Grid)
* **Controller:** MacBook Pro (Ansible)
* **Tower Core (Brain):** Raspberry Pi 5. Hostname: `tower-core`.
* **Sensor North (Reference):** Raspberry Pi 4. **Stratum-1 Timing + High-Fidelity SDR**. Hostname: `sensor-north`.
* **Sensor East (Remote):** Raspberry Pi 4 (Sibbo). Hostname: `sensor-east`.
* **Sensor West (Remote):** Raspberry Pi 4 (Jorvas). Hostname: `sensor-west`.

## 📜 Project Heritage
This project supersedes the original **[Central Brain PoC](https://github.com/rwiren/central-brain)**. 
* **Theory:** See the [Legacy Wiki](https://github.com/rwiren/central-brain/wiki) for detection logic.
* **Datasets:** Early baseline datasets are archived in the legacy repo.

## 🚀 Usage
1. **Deploy Grid:** `ansible-playbook infra/ansible/playbooks/site.yml`
2. **Start Agent:** `systemctl start adsb-agent`
3. **Analyze:** Run Jupyter Notebooks in `src/core_brain/analysis/`

## 🛡 License
Academic Research License - Do not distribute without citation.
