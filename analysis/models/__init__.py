# Deep Learning Models for ADS-B Research

"""
This package contains implementations of advanced neural network architectures
for ADS-B data analysis, including:

- Liquid Neural Networks (LNN) for anomaly detection
- Extended LSTM (xLSTM) for trajectory prediction
"""

from .lnn import (
    LiquidNeuralNetwork,
    LNNAnomalyDetector,
    create_lnn_model
)

from .xlstm import (
    xLSTM,
    xLSTMTrajectoryPredictor,
    create_xlstm_model
)

from .data_utils import (
    ADSBDataset,
    AnomalyDataset,
    load_adsb_data
)

__version__ = '1.0.0'

__all__ = [
    # LNN
    'LiquidNeuralNetwork',
    'LNNAnomalyDetector',
    'create_lnn_model',
    # xLSTM
    'xLSTM',
    'xLSTMTrajectoryPredictor',
    'create_xlstm_model',
    # Data
    'ADSBDataset',
    'AnomalyDataset',
    'load_adsb_data',
]
