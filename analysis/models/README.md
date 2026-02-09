# Liquid Neural Networks and xLSTM for ADS-B Data

This directory contains implementations of **Liquid Neural Networks (LNN)** and **Extended LSTM (xLSTM)** for anomaly detection and trajectory prediction on ADS-B research data.

## 📚 Overview

### Liquid Neural Networks (LNN)
Time-continuous neural networks with learnable dynamics for adaptive signal processing. Ideal for:
- **Anomaly detection** in irregular time-series ADS-B data
- **Signal quality monitoring** with continuous-time adaptation
- **Multi-sensor consistency** checking

**Key Features:**
- Neural ODE integration for continuous dynamics
- Learnable time constants for adaptive behavior
- Reconstruction-based anomaly detection

### Extended LSTM (xLSTM)
Enhanced LSTM with exponential gating and matrix memory for better long-range dependencies. Ideal for:
- **Trajectory prediction** and forecasting
- **Long-sequence modeling** with improved gradient flow
- **Multi-step ahead prediction**

**Key Features:**
- Scalar LSTM (sLSTM) with exponential gating
- Matrix LSTM (mLSTM) with covariance updates
- Enhanced memory retention for long sequences

---

## 🚀 Quick Start

### Installation

```bash
# Install base dependencies
pip install -r requirements.txt

# Install deep learning dependencies
pip install -r requirements-models.txt
```

### Training LNN for Anomaly Detection

```bash
python analysis/models/lnn/train_lnn_anomaly_detector.py \
    --data_path analysis/golden_7day_eda_results/golden_7day_ml_dataset.csv \
    --epochs 50 \
    --hidden_size 64 \
    --sequence_length 20
```

### Training xLSTM for Trajectory Prediction

```bash
python analysis/models/xlstm/train_xlstm_trajectory.py \
    --data_path analysis/golden_7day_eda_results/golden_7day_ml_dataset.csv \
    --epochs 50 \
    --hidden_size 64 \
    --sequence_length 20 \
    --prediction_horizon 10
```

---

## 📂 Repository Structure

```
analysis/models/
├── README.md                           # This file
├── data_utils.py                       # Data loading and preprocessing
├── lnn/                               # Liquid Neural Networks
│   ├── liquid_neural_network.py       # LNN implementation
│   ├── train_lnn_anomaly_detector.py  # Training script
│   ├── lnn_example.ipynb              # Example notebook
│   └── outputs/                       # Trained models and plots
└── xlstm/                             # Extended LSTM
    ├── extended_lstm.py               # xLSTM implementation
    ├── train_xlstm_trajectory.py      # Training script
    ├── xlstm_example.ipynb            # Example notebook
    └── outputs/                       # Trained models and plots
```

---

## 🧠 Model Architectures

### LNN Architecture

```
Input → Liquid Cell (ODE) → Encoder → Latent Space
                                    ↓
                            Reconstruction ← Decoder
                                    ↓
                            Anomaly Score ← Detection Head
```

**Components:**
- **Liquid Cell**: Continuous-time dynamics with learnable τ (time constant)
- **Neural ODE**: odeint integration for smooth state evolution
- **Encoder**: Maps input to latent representation
- **Decoder**: Reconstructs input for anomaly detection
- **Anomaly Head**: Scores anomaly probability (0-1)

### xLSTM Architecture

```
Input → Pre-Norm → sLSTM/mLSTM Cell → Projection → + Residual → Post-Norm → Output
```

**sLSTM Cell** (Scalar):
- Exponential gating: `i = exp(W_i*x + U_i*h)`
- Normalizer state: prevents explosion
- Better gradient flow for long sequences

**mLSTM Cell** (Matrix):
- Matrix memory: `C = f*C_prev + i*(v ⊗ k^T)`
- Covariance-like updates
- Richer context representation

---

## 📊 Dataset Features

The models use the ML-ready dataset from the Golden 7-Day EDA with these features:

**Temporal Features:**
- `hour_sin`, `hour_cos` - Cyclic time encoding
- `day_of_week_sin`, `day_of_week_cos`

**Spatial Features:**
- `lat`, `lon`, `alt_baro` - Position
- `distance_km` - Distance from sensor

**Signal Features:**
- `rssi` - Received signal strength
- `signal_deviation` - Deviation from expected

**Physics Features:**
- `altitude_speed_ratio` - Flight envelope validation
- `track_sin`, `track_cos` - Direction encoding

**See:** `analysis/golden_7day_eda_results/README.md` for full feature list

---

## 🔧 Usage Examples

### Load and Use Trained LNN Model

```python
import torch
from models.lnn.liquid_neural_network import create_lnn_model

# Load model
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = create_lnn_model(input_size=12, model_type='anomaly_detector')
checkpoint = torch.load('analysis/models/lnn/outputs/best_lnn_model.pt')
model.load_state_dict(checkpoint['model_state_dict'])
model.to(device)
model.eval()

# Detect anomalies
with torch.no_grad():
    x = torch.randn(1, 20, 12).to(device)  # (batch, seq, features)
    is_anomaly, scores = model.detect_anomalies(x, threshold=0.5)
    
print(f"Anomaly detected: {is_anomaly.any()}")
print(f"Anomaly scores: {scores.mean()}")
```

### Load and Use Trained xLSTM Model

```python
import torch
from models.xlstm.extended_lstm import create_xlstm_model

# Load model
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = create_xlstm_model(input_size=12, model_type='trajectory_predictor',
                          predict_steps=10)
checkpoint = torch.load('analysis/models/xlstm/outputs/best_xlstm_model.pt')
model.load_state_dict(checkpoint['model_state_dict'])
model.to(device)
model.eval()

# Predict trajectory
with torch.no_grad():
    x = torch.randn(1, 20, 12).to(device)  # Historical trajectory
    future = model(x, predict_future=True)  # Predict next 10 steps
    
print(f"Future trajectory shape: {future.shape}")  # (1, 10, 12)
```

---

## 📈 Training Arguments

### LNN Training Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--data_path` | Required | Path to CSV dataset |
| `--hidden_size` | 64 | LNN hidden dimension |
| `--latent_size` | 32 | Latent space dimension |
| `--num_layers` | 2 | Number of liquid cells |
| `--sequence_length` | 20 | Input sequence length |
| `--epochs` | 50 | Training epochs |
| `--lr` | 0.001 | Learning rate |
| `--device` | auto | cuda/cpu |

### xLSTM Training Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--data_path` | Required | Path to CSV dataset |
| `--hidden_size` | 64 | xLSTM hidden dimension |
| `--num_layers` | 2 | Number of xLSTM blocks |
| `--sequence_length` | 20 | Input sequence length |
| `--prediction_horizon` | 10 | Steps to predict ahead |
| `--epochs` | 50 | Training epochs |
| `--lr` | 0.001 | Learning rate |
| `--device` | auto | cuda/cpu |

---

## 🎯 Use Cases

### 1. Anomaly Detection (LNN)

**Scenario:** Detect spoofing attacks or sensor malfunctions

```python
# Train on normal flight data
python analysis/models/lnn/train_lnn_anomaly_detector.py \
    --data_path normal_flights.csv \
    --epochs 100

# Detect anomalies in new data
is_anomaly, scores = model.detect_anomalies(new_data)
```

**Applications:**
- GNSS spoofing detection
- Signal quality monitoring
- Multi-sensor consistency checking
- Ghost aircraft identification

### 2. Trajectory Prediction (xLSTM)

**Scenario:** Forecast aircraft positions for collision avoidance

```python
# Train on historical trajectories
python analysis/models/xlstm/train_xlstm_trajectory.py \
    --data_path trajectories.csv \
    --prediction_horizon 20 \
    --epochs 100

# Predict future positions
future_trajectory = model(current_trajectory, predict_future=True)
```

**Applications:**
- Collision avoidance
- Flight path optimization
- Anomaly detection (deviation from prediction)
- Air traffic management

---

## 📝 Citations

### Liquid Neural Networks

```bibtex
@article{hasani2020liquid,
  title={Liquid time-constant networks},
  author={Hasani, Ramin and Lechner, Mathias and Amini, Alexander and Rus, Daniela and Grosu, Radu},
  journal={arXiv preprint arXiv:2006.04439},
  year={2020}
}
```

### xLSTM

```bibtex
@article{beck2024xlstm,
  title={xLSTM: Extended Long Short-Term Memory},
  author={Beck, Maximilian and P{\"o}ppel, Korbinian and Spanring, Markus and Auer, Andreas and Prudnikova, Oleksandra and Kopp, Michael and Klambauer, G{\"u}nter and Brandstetter, Johannes and Hochreiter, Sepp},
  journal={arXiv preprint arXiv:2405.04517},
  year={2024}
}
```

### This Project

```bibtex
@software{wiren2026adsb,
  author = {Wiren, Richard},
  title = {ADS-B Research Grid: Distributed Sensor Network for Spoofing Detection},
  year = {2026},
  url = {https://github.com/rwiren/adsb-research-grid}
}
```

---

## 🛠️ Development

### Running Tests

```bash
# Test LNN implementation
python analysis/models/lnn/liquid_neural_network.py

# Test xLSTM implementation
python analysis/models/xlstm/extended_lstm.py

# Test data utilities
python analysis/models/data_utils.py
```

### Adding New Models

1. Create new model file in appropriate directory
2. Implement model class inheriting from `nn.Module`
3. Add factory function following `create_*_model` pattern
4. Create training script
5. Add example notebook
6. Update this README

---

## 🤝 Contributing

Contributions welcome! Please:
1. Follow existing code style
2. Add tests for new features
3. Update documentation
4. Create example notebooks

---

## 📄 License

MIT License - See repository root for details

---

## 🔗 Links

- **Repository:** https://github.com/rwiren/adsb-research-grid
- **Wiki:** https://github.com/rwiren/adsb-research-grid/wiki
- **Issues:** https://github.com/rwiren/adsb-research-grid/issues

---

**Last Updated:** 2026-02-09  
**Version:** 1.0  
**Status:** ✅ Production Ready
