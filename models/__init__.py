"""
Advanced ML Models for ADS-B Spoofing Detection

This package contains the 16-Model Zoo architecture including:
- Sinkhorn-Knopp Algorithm (Tier 1 Math)
- DeepSeek MCHC (Manifold-Constrained Hyper-Connection)
- Liquid Neural Networks (LNN)
- xLSTM
- ManifoldGuard orchestration system
"""

__version__ = "1.0.0"

from .sinkhorn_knopp import SinkhornKnoppProjection
from .deepseek_mchc import DeepSeekMCHC
from .lnn import LiquidNeuralNetwork
from .xlstm import xLSTM
from .manifold_guard import ManifoldGuard

__all__ = [
    "SinkhornKnoppProjection",
    "DeepSeekMCHC",
    "LiquidNeuralNetwork",
    "xLSTM",
    "ManifoldGuard",
]
