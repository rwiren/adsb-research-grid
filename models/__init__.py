"""
Advanced ML Models for ADS-B Spoofing Detection

This package contains the 16-Model Zoo architecture including:
- Tier 1: Random Forest, XGBoost, Reinforcement Learning, MARL, Sinkhorn-Knopp
- Tier 2: GNN, GAT, Transformers, xLSTM, LNN, Mamba (SSM)
- Tier 3: PINN, KAN, DeepSeek MCHC, GAN, ManifoldGuard
"""

__version__ = "2.0.0"

from .sinkhorn_knopp import SinkhornKnoppProjection
from .deepseek_mchc import DeepSeekMCHC
from .lnn import LiquidNeuralNetwork
from .xlstm import xLSTM
from .manifold_guard import ManifoldGuard

# New models
from .mamba_ssm import MambaSSM, MambaSSMNumPy
from .kan import KAN, KANNumPy
from .pinn import PINN, PINNNumPy
from .gan import SpoofingGAN, SpoofingGANNumPy
from .marl import MARLCoordination, MARLCoordinationNumPy
from .tree_models import RandomForestDetector, XGBoostDetector, TreeBasedEnsemble

__all__ = [
    # Core models
    "SinkhornKnoppProjection",
    "DeepSeekMCHC",
    "LiquidNeuralNetwork",
    "xLSTM",
    "ManifoldGuard",
    # New Tier 2 models
    "MambaSSM",
    "MambaSSMNumPy",
    # New Tier 3 models
    "KAN",
    "KANNumPy",
    "PINN",
    "PINNNumPy",
    "SpoofingGAN",
    "SpoofingGANNumPy",
    # Coordination
    "MARLCoordination",
    "MARLCoordinationNumPy",
    # Tree-based (Tier 1)
    "RandomForestDetector",
    "XGBoostDetector",
    "TreeBasedEnsemble",
]
