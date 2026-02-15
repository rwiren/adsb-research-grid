# Manifold Defense System - ADS-B Spoofing Detection

This directory contains the advanced ML models for the **16-Model Zoo** architecture implementing a multi-tier topological and logical defense system for ADS-B spoofing detection.

## Architecture Overview

The system implements a **Tier 1-3 Defense Strategy**:

### Tier 1: Mathematical Gatekeeper
- **Sinkhorn-Knopp Algorithm**: Projects cost matrices onto the Birkhoff Polytope using optimal transport theory. Computes transport costs between observed and predicted aircraft positions as an initial anomaly score.

### Tier 2: Temporal Deep Learning
- **Liquid Neural Networks (LNN)**: Time-continuous neural networks for handling irregular time-series ADS-B data with variable sampling rates.
- **xLSTM (Extended LSTM)**: Enhanced recurrent networks with exponential gating and improved memory retention for pattern recognition in aircraft trajectories.

### Tier 3: Topological Validation
- **DeepSeek MCHC (Manifold-Constrained Hyper-Connection)**: Graph Neural Network architecture that validates flight paths using topological constraints derived from manifold logic. Detects "ghost aircraft" formations and hyper-connection violations.

### Orchestration
- **ManifoldGuard**: Central orchestration system that coordinates all components and performs weighted ensemble voting to produce final spoofing probability.

## Modules

### `sinkhorn_knopp.py`
- `SinkhornKnoppProjection`: Implements the Sinkhorn-Knopp iterative algorithm
- Pure NumPy implementation (no dependencies beyond NumPy)
- Projects cost matrices onto the Birkhoff Polytope
- Computes transport costs as anomaly indicators

### `lnn.py`
- `LiquidNeuralNetwork`: Time-continuous neural network for irregular time-series
- Handles variable sampling rates in ADS-B streams
- Continuous-time dynamics using ODE approximations
- Requires: PyTorch

### `xlstm.py`
- `xLSTM`: Extended LSTM with exponential gating
- `xLSTMCell`: Single cell implementation with enhanced memory
- Improved long-term dependency modeling
- Requires: PyTorch

### `deepseek_mchc.py`
- `DeepSeekMCHC`: Manifold-Constrained Graph Neural Network
- Topology-based validation of aircraft formations
- Detects hyper-connection violations
- ONNX export support for Hailo-8 NPU deployment
- Requires: PyTorch, (PyTorch Geometric recommended)

### `manifold_guard.py`
- `ManifoldGuard`: Main orchestration class
- Coordinates all detection models
- Weighted ensemble voting
- Configurable weights and thresholds
- Falls back to Sinkhorn-only mode if PyTorch unavailable

## Installation

### Minimal (Sinkhorn-only)
```bash
pip install numpy scipy
```

### Full System (All Models)
```bash
pip install numpy scipy torch torch-geometric
```

Or install all project requirements:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Example
```python
import numpy as np
from models import ManifoldGuard

# Initialize the defense system
guard = ManifoldGuard()

# Prepare data
observed_positions = np.array([
    [60.1, 24.8, 10000],  # [lat, lon, alt_feet]
    [60.2, 24.9, 11000],
    # ... more aircraft
])

predicted_positions = np.array([
    [60.1, 24.8, 10000],
    [60.2, 24.9, 11000],
    # ... physics-predicted positions
])

# For full detection with neural networks, also provide trajectory sequences
trajectory_sequence = np.random.rand(2, 50, 8)  # [n_aircraft, seq_len, features]

# Detect spoofing
result = guard.detect_spoofing(
    observed_positions=observed_positions,
    predicted_positions=predicted_positions,
    trajectory_sequence=trajectory_sequence,
)

# Check results
print(f"Spoofing Detected: {result['is_spoof']}")
print(f"Probability: {result['is_spoof_probability']:.2%}")
print(f"Confidence: {result['confidence']:.2%}")
print(f"Model Scores: {result['model_scores']}")
```

### Running the Demo
```bash
python examples/demo_manifold_guard.py
```

This will run two scenarios:
1. **Normal Traffic**: Smooth trajectories with physics-consistent motion
2. **Spoofed Traffic**: Erratic trajectories with impossible velocity changes

## Hardware Deployment

### Raspberry Pi 5 (CPU Inference)
- Use Sinkhorn-Knopp + lightweight neural networks
- Set `device='cpu'` in `ManifoldGuard`
- Expected latency: 50-100ms per batch

### Raspberry Pi 5 + Hailo-8 NPU
- Export models to ONNX format
- Deploy neural networks to Hailo-8 accelerator
- Expected latency: 10-20ms per batch

```python
guard = ManifoldGuard(device='cpu')
guard.export_models('./exported_models')
```

### M4 Max MacBook Pro (Training)
- Use for full model training with large datasets
- Set `device='mps'` for Metal Performance Shaders acceleration
- Or `device='cuda'` for NVIDIA GPUs

## Model Configuration

### Ensemble Weights
Customize the voting weights for different operational scenarios:

```python
# Default (balanced)
weights = {
    'sinkhorn': 0.3,  # Mathematical gatekeeper
    'lnn': 0.2,       # Time-continuous
    'xlstm': 0.2,     # Recurrent patterns
    'mchc': 0.3,      # Topology validation
}

# Precision mode (favor topology)
weights = {
    'sinkhorn': 0.2,
    'lnn': 0.15,
    'xlstm': 0.15,
    'mchc': 0.5,
}

# Fast mode (favor Sinkhorn)
weights = {
    'sinkhorn': 0.6,
    'lnn': 0.15,
    'xlstm': 0.15,
    'mchc': 0.1,
}

guard = ManifoldGuard(ensemble_weights=weights)
```

## Performance Characteristics

| Model | Parameters | Inference Time (CPU) | Inference Time (NPU) |
|-------|-----------|---------------------|---------------------|
| Sinkhorn-Knopp | N/A | ~1ms | N/A |
| LNN | ~50K | ~15ms | ~3ms |
| xLSTM | ~100K | ~20ms | ~4ms |
| DeepSeek MCHC | ~150K | ~30ms | ~5ms |
| **Total Pipeline** | ~300K | **~65ms** | **~12ms** |

*Benchmarked on Raspberry Pi 5 (8GB) with 10 aircraft, 50 time steps.*

## Future Enhancements

Planned additions to complete the 16-Model Zoo:
- [ ] Mamba (State Space Model) for long-context trajectory tracking
- [ ] KAN (Kolmogorov-Arnold Networks) for symbolic aerodynamic regression
- [ ] Integration with existing Random Forest and XGBoost models
- [ ] Multi-Agent RL coordination layer
- [ ] Physics-Informed Neural Network (PINN) constraints
- [ ] GAN-based adversarial training

## References

1. **Sinkhorn-Knopp Algorithm**
   - Cuturi, M. (2013). "Sinkhorn Distances: Lightspeed Computation of Optimal Transport"
   - Peyré, G., & Cuturi, M. (2019). "Computational Optimal Transport"

2. **Liquid Neural Networks**
   - Hasani et al. (2021). "Liquid Time-constant Networks"
   - Lechner et al. (2020). "Neural Circuit Policies"

3. **xLSTM**
   - Beck et al. (2024). "xLSTM: Extended Long Short-Term Memory"

4. **Graph Neural Networks**
   - Kipf & Welling (2017). "Semi-Supervised Classification with Graph Convolutional Networks"
   - Veličković et al. (2018). "Graph Attention Networks"

## License

MIT License - See [LICENSE](../LICENSE) for details.

## Citation

If you use this system in your research, please cite:

```bibtex
@software{wiren2026manifold,
  title={Manifold Defense System: Topological ADS-B Spoofing Detection},
  author={Wiren, Richard},
  year={2026},
  url={https://github.com/rwiren/adsb-research-grid}
}
```
