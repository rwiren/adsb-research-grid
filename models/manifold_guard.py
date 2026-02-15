"""
ManifoldGuard: Orchestration System for Topological Defense

Central orchestration class that coordinates all components of the 
Manifold Defense System (16-Model Zoo) for ADS-B spoofing detection.

Architecture Flow:
1. Ingest raw ADS-B vectors
2. Sinkhorn-Knopp projection (transport cost as gatekeeper)
3. LNN processing (time-continuous dynamics)
4. xLSTM processing (recurrent patterns)
5. DeepSeek MCHC (topology validation)
6. Weighted ensemble voting
7. Final spoofing probability
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import warnings

from .sinkhorn_knopp import SinkhornKnoppProjection
from .deepseek_mchc import DeepSeekMCHC
from .lnn import LiquidNeuralNetwork
from .xlstm import xLSTM

try:
    import torch
    from torch import Tensor
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    Tensor = Any
    warnings.warn(
        "PyTorch not available. ManifoldGuard will use NumPy-only mode with limited functionality."
    )


class ManifoldGuard:
    """
    ManifoldGuard: Topological & Logical Defense System for ADS-B Spoofing.
    
    This class orchestrates the complete detection pipeline:
    1. **Sinkhorn-Knopp (Tier 1 Math):** Pre-processing gatekeeper using optimal transport.
    2. **LNN (Tier 2):** Time-continuous modeling of irregular ADS-B streams.
    3. **xLSTM (Tier 2):** Recurrent anomaly detection with enhanced memory.
    4. **DeepSeek MCHC (Tier 3):** Topology-based validation via GNN.
    5. **Ensemble Voting:** Weighted combination of all model outputs.
    
    Key Features:
    - Multi-tier defense (mathematical, temporal, topological)
    - Lightweight inference (optimized for Raspberry Pi 5 + Hailo-8)
    - Explainable decisions (per-model scores + ensemble vote)
    - Configurable weights for operational tuning
    
    Attributes:
        sinkhorn: Sinkhorn-Knopp projector for optimal transport.
        lnn: Liquid Neural Network for time-continuous modeling.
        xlstm: Extended LSTM for recurrent pattern detection.
        mchc: DeepSeek MCHC for topology validation.
        ensemble_weights: Weights for combining model scores.
        
    Example:
        >>> guard = ManifoldGuard()
        >>> # Raw ADS-B data
        >>> observed_positions = np.random.rand(10, 3)  # [n_aircraft, (lat, lon, alt)]
        >>> predicted_positions = np.random.rand(10, 3)
        >>> trajectory_sequence = np.random.rand(10, 50, 8)  # [n_aircraft, time, features]
        >>> # Detect spoofing
        >>> result = guard.detect_spoofing(observed_positions, predicted_positions, trajectory_sequence)
        >>> print(f"Spoofing Probability: {result['is_spoof_probability']:.2%}")
    """
    
    def __init__(
        self,
        sinkhorn_epsilon: float = 0.1,
        lnn_hidden_dim: int = 32,
        xlstm_hidden_dim: int = 64,
        mchc_hidden_dim: int = 64,
        ensemble_weights: Optional[Dict[str, float]] = None,
        device: str = "cpu",
    ):
        """
        Initialize ManifoldGuard detection system.
        
        Args:
            sinkhorn_epsilon: Entropy regularization for Sinkhorn-Knopp.
            lnn_hidden_dim: Hidden dimension for Liquid Neural Network.
            xlstm_hidden_dim: Hidden dimension for xLSTM.
            mchc_hidden_dim: Hidden dimension for DeepSeek MCHC.
            ensemble_weights: Optional custom weights for ensemble voting.
                             Keys: 'sinkhorn', 'lnn', 'xlstm', 'mchc'
                             Default: {'sinkhorn': 0.3, 'lnn': 0.2, 'xlstm': 0.2, 'mchc': 0.3}
            device: Device for PyTorch models ('cpu', 'cuda', or 'hailo').
        """
        # Initialize Sinkhorn-Knopp (NumPy-based, always available)
        self.sinkhorn = SinkhornKnoppProjection(epsilon=sinkhorn_epsilon)
        
        # Initialize neural networks (PyTorch-based, requires torch)
        if TORCH_AVAILABLE:
            self.device = torch.device(device if device != 'hailo' else 'cpu')
            
            self.lnn = LiquidNeuralNetwork(
                input_dim=8,  # [lat, lon, alt, velocity, heading, rssi, ...]
                hidden_dim=lnn_hidden_dim,
                output_dim=16,
            ).to(self.device)
            
            self.xlstm = xLSTM(
                input_dim=8,
                hidden_dim=xlstm_hidden_dim,
                num_layers=2,
                output_dim=32,
            ).to(self.device)
            
            self.mchc = DeepSeekMCHC(
                input_dim=8,
                hidden_dim=mchc_hidden_dim,
                num_layers=3,
            ).to(self.device)
            
            self.torch_available = True
        else:
            self.lnn = None
            self.xlstm = None
            self.mchc = None
            self.torch_available = False
            warnings.warn(
                "PyTorch not available. Only Sinkhorn-Knopp layer will be active."
            )
        
        # Ensemble voting weights
        if ensemble_weights is None:
            self.ensemble_weights = {
                'sinkhorn': 0.3,  # Mathematical gatekeeper
                'lnn': 0.2,       # Time-continuous
                'xlstm': 0.2,     # Recurrent patterns
                'mchc': 0.3,      # Topology validation
            }
        else:
            self.ensemble_weights = ensemble_weights
            
        # Normalize weights
        total_weight = sum(self.ensemble_weights.values())
        self.ensemble_weights = {
            k: v / total_weight for k, v in self.ensemble_weights.items()
        }
    
    def detect_spoofing(
        self,
        observed_positions: np.ndarray,
        predicted_positions: np.ndarray,
        trajectory_sequence: Optional[np.ndarray] = None,
        edge_index: Optional[np.ndarray] = None,
        dt: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """
        Detect ADS-B spoofing using multi-tier ensemble.
        
        Args:
            observed_positions: [n_aircraft, 3] array of observed (lat, lon, alt).
            predicted_positions: [n_aircraft, 3] array of physics-predicted positions.
            trajectory_sequence: [n_aircraft, seq_len, feature_dim] historical trajectories.
                                Required for LNN, xLSTM, and MCHC models.
            edge_index: [2, n_edges] edge connectivity for graph structure (optional).
            dt: [n_aircraft, seq_len] time deltas for irregular sampling (optional).
            
        Returns:
            Dictionary containing:
                - 'is_spoof_probability': [float] ensemble probability of spoofing [0, 1]
                - 'is_spoof': [bool] binary decision (threshold at 0.5)
                - 'model_scores': [dict] individual model scores
                - 'transport_cost': [float] Sinkhorn transport cost
                - 'topology_score': [float] MCHC topology violation score
                - 'confidence': [float] ensemble confidence (variance-based)
                
        Raises:
            ValueError: If inputs have incompatible shapes or invalid values.
        """
        if observed_positions.shape != predicted_positions.shape:
            raise ValueError(
                f"Shape mismatch: observed {observed_positions.shape} vs "
                f"predicted {predicted_positions.shape}"
            )
        
        n_aircraft = observed_positions.shape[0]
        model_scores = {}
        
        # ========================================
        # TIER 1: Sinkhorn-Knopp (Mathematical Gatekeeper)
        # ========================================
        # Compute cost matrix (Euclidean distance between observed and predicted)
        cost_matrix = self._compute_cost_matrix(observed_positions, predicted_positions)
        
        # Project onto Birkhoff Polytope
        transport_cost, convergence_rate, transport_plan = self.sinkhorn.project(cost_matrix)
        sinkhorn_score = self.sinkhorn.compute_anomaly_score(cost_matrix)
        model_scores['sinkhorn'] = float(sinkhorn_score)
        
        # ========================================
        # TIER 2 & 3: Neural Network Ensemble
        # ========================================
        if self.torch_available and trajectory_sequence is not None:
            # Convert to PyTorch tensors
            trajectory_tensor = torch.from_numpy(trajectory_sequence).float().to(self.device)
            
            # Add batch dimension if needed
            if trajectory_tensor.dim() == 2:
                trajectory_tensor = trajectory_tensor.unsqueeze(0)
            
            # Convert dt if provided
            dt_tensor = None
            if dt is not None:
                dt_tensor = torch.from_numpy(dt).float().to(self.device)
            
            # LNN: Time-Continuous Dynamics
            with torch.no_grad():
                lnn_output = self.lnn(trajectory_tensor, dt_tensor)
                lnn_score = lnn_output['anomaly_score'].mean().item()
                lnn_hidden = lnn_output['hidden']
                model_scores['lnn'] = float(lnn_score)
            
            # xLSTM: Recurrent Pattern Detection
            with torch.no_grad():
                xlstm_output = self.xlstm(trajectory_tensor)
                xlstm_score = xlstm_output['anomaly_score'].mean().item()
                xlstm_hidden = xlstm_output['hidden']
                model_scores['xlstm'] = float(xlstm_score)
            
            # DeepSeek MCHC: Topology Validation
            # Prepare graph features
            node_features = trajectory_tensor[:, :, -1, :]  # [batch, n_nodes, features]
            manifold_constraints = torch.from_numpy(cost_matrix).float().to(self.device)
            manifold_constraints = manifold_constraints.unsqueeze(0)  # Add batch dim
            
            # Convert edge_index if provided
            edge_index_tensor = None
            if edge_index is not None:
                edge_index_tensor = torch.from_numpy(edge_index).long().to(self.device)
            
            with torch.no_grad():
                mchc_output = self.mchc(
                    node_features,
                    edge_index_tensor,
                    manifold_constraints,
                    lnn_hidden,
                    xlstm_hidden,
                )
                mchc_score = mchc_output['probabilities'].mean().item()
                topology_score = mchc_output['topology_score'].mean().item()
                model_scores['mchc'] = float(mchc_score)
        else:
            # Fallback: Use only Sinkhorn if trajectory data not provided
            if trajectory_sequence is None:
                warnings.warn(
                    "Trajectory sequence not provided. Using Sinkhorn-only detection."
                )
            model_scores['lnn'] = 0.0
            model_scores['xlstm'] = 0.0
            model_scores['mchc'] = 0.0
            topology_score = 0.0
        
        # ========================================
        # ENSEMBLE VOTING
        # ========================================
        ensemble_score = self._weighted_ensemble_vote(model_scores)
        
        # Compute confidence (inverse of score variance)
        scores_array = np.array(list(model_scores.values()))
        score_variance = np.var(scores_array)
        confidence = 1.0 / (1.0 + score_variance)
        
        return {
            'is_spoof_probability': float(ensemble_score),
            'is_spoof': bool(ensemble_score > 0.5),
            'model_scores': model_scores,
            'transport_cost': float(transport_cost),
            'topology_score': float(topology_score) if topology_score else 0.0,
            'confidence': float(confidence),
            'convergence_rate': float(convergence_rate),
        }
    
    def _compute_cost_matrix(
        self,
        observed: np.ndarray,
        predicted: np.ndarray,
    ) -> np.ndarray:
        """
        Compute cost matrix (Euclidean distance) between observed and predicted positions.
        
        Args:
            observed: [n, 3] observed positions (lat, lon, alt).
            predicted: [n, 3] predicted positions.
            
        Returns:
            [n, n] cost matrix.
        """
        # Normalize altitude (convert to similar scale as lat/lon in degrees)
        # Typical: 1 degree ≈ 111 km, 1000 ft ≈ 0.3 km
        observed_normalized = observed.copy()
        predicted_normalized = predicted.copy()
        
        observed_normalized[:, 2] = observed[:, 2] / 1000.0 / 111.0  # feet to ~degrees
        predicted_normalized[:, 2] = predicted[:, 2] / 1000.0 / 111.0
        
        # Compute pairwise Euclidean distances
        # Broadcasting: [n, 1, 3] - [1, n, 3] = [n, n, 3]
        diff = observed_normalized[:, np.newaxis, :] - predicted_normalized[np.newaxis, :, :]
        cost_matrix = np.sqrt(np.sum(diff ** 2, axis=-1))
        
        return cost_matrix
    
    def _weighted_ensemble_vote(self, model_scores: Dict[str, float]) -> float:
        """
        Compute weighted ensemble vote from individual model scores.
        
        Args:
            model_scores: Dictionary of model name -> anomaly score.
            
        Returns:
            Ensemble anomaly probability in [0, 1].
        """
        ensemble_score = 0.0
        for model_name, score in model_scores.items():
            weight = self.ensemble_weights.get(model_name, 0.0)
            ensemble_score += weight * score
        
        # Ensure output is in [0, 1]
        ensemble_score = np.clip(ensemble_score, 0.0, 1.0)
        
        return ensemble_score
    
    def export_models(self, output_dir: str = "./models/exported"):
        """
        Export all neural network models to ONNX format for Hailo-8 NPU deployment.
        
        Args:
            output_dir: Directory to save exported models.
        """
        if not self.torch_available:
            raise RuntimeError("PyTorch not available. Cannot export models.")
        
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        # Export MCHC
        self.mchc.export_to_onnx(
            os.path.join(output_dir, "deepseek_mchc.onnx"),
            batch_size=1,
            num_nodes=10,
        )
        
        print(f"Models exported to {output_dir}")
        print("Note: LNN and xLSTM export requires additional configuration.")
