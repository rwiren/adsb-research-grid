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

# Try to import PyTorch-based models
try:
    from .deepseek_mchc import DeepSeekMCHC
    from .lnn import LiquidNeuralNetwork
    from .xlstm import xLSTM
    from .mamba_ssm import MambaSSM, MambaSSMNumPy
    from .kan import KAN, KANNumPy
    from .pinn import PINN, PINNNumPy
    from .gan import SpoofingGAN, SpoofingGANNumPy
    from .marl import MARLCoordination, MARLCoordinationNumPy
    PYTORCH_MODELS_AVAILABLE = True
except ImportError as e:
    # PyTorch not available - use NumPy fallbacks
    DeepSeekMCHC = None
    LiquidNeuralNetwork = None
    xLSTM = None
    MambaSSM = None
    KAN = None
    PINN = None
    SpoofingGAN = None
    MARLCoordination = None
    from .mamba_ssm import MambaSSMNumPy
    from .kan import KANNumPy
    from .pinn import PINNNumPy
    from .gan import SpoofingGANNumPy
    from .marl import MARLCoordinationNumPy
    PYTORCH_MODELS_AVAILABLE = False
    warnings.warn(f"PyTorch models not available: {e}. Using NumPy fallbacks where possible.")

from .tree_models import TreeBasedEnsemble

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
        mamba_hidden_dim: int = 64,
        kan_hidden_dims: List[int] = [32, 16],
        pinn_hidden_dim: int = 64,
        gan_hidden_dim: int = 256,
        marl_num_agents: int = 4,
        enable_all_models: bool = False,
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
            mamba_hidden_dim: Hidden dimension for Mamba SSM.
            kan_hidden_dims: Hidden layer dimensions for KAN.
            pinn_hidden_dim: Hidden dimension for PINN.
            gan_hidden_dim: Hidden dimension for GAN.
            marl_num_agents: Number of agents for MARL coordination.
            enable_all_models: If True, enables all 16 models. If False, uses core models only.
            ensemble_weights: Optional custom weights for ensemble voting.
                             Keys: 'sinkhorn', 'rf_xgb', 'marl', 'lnn', 'xlstm', 'mamba',
                                   'pinn', 'kan', 'mchc', 'gan'
            device: Device for PyTorch models ('cpu', 'cuda', or 'hailo').
        """
        self.enable_all_models = enable_all_models
        
        # Initialize Sinkhorn-Knopp (NumPy-based, always available)
        self.sinkhorn = SinkhornKnoppProjection(epsilon=sinkhorn_epsilon)
        
        # Initialize tree-based models (sklearn-based, CPU only)
        try:
            self.tree_ensemble = TreeBasedEnsemble()
            self.tree_available = True
        except ImportError:
            self.tree_ensemble = None
            self.tree_available = False
            warnings.warn("Tree-based models (RF/XGBoost) not available.")
        
        # Initialize neural networks (PyTorch-based, requires torch)
        if TORCH_AVAILABLE:
            self.device = torch.device(device if device != 'hailo' else 'cpu')
            
            # Core models (always initialized if PyTorch available)
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
            
            # New models (initialized only if enable_all_models is True)
            if enable_all_models:
                self.mamba = MambaSSM(
                    input_dim=8,
                    d_model=mamba_hidden_dim,
                    num_layers=4,
                    output_dim=32,
                ).to(self.device)
                
                self.kan = KAN(
                    input_dim=8,
                    hidden_dims=kan_hidden_dims,
                    output_dim=2,
                ).to(self.device)
                
                self.pinn = PINN(
                    input_dim=8,
                    hidden_dim=pinn_hidden_dim,
                    output_dim=9,
                ).to(self.device)
                
                self.gan = SpoofingGAN(
                    latent_dim=128,
                    trajectory_dim=8,
                    seq_len=50,
                    hidden_dim=gan_hidden_dim,
                ).to(self.device)
                
                self.marl = MARLCoordination(
                    num_agents=marl_num_agents,
                    state_dim=16,
                    action_dim=4,
                    hidden_dim=128,
                ).to(self.device)
            else:
                self.mamba = None
                self.kan = None
                self.pinn = None
                self.gan = None
                self.marl = None
            
            self.torch_available = True
        else:
            self.lnn = None
            self.xlstm = None
            self.mchc = None
            self.mamba = None
            self.kan = None
            self.pinn = None
            self.gan = None
            self.marl = None
            self.torch_available = False
            warnings.warn(
                "PyTorch not available. Only Sinkhorn-Knopp and tree-based models will be active."
            )
        
        # Ensemble voting weights
        if ensemble_weights is None:
            if enable_all_models:
                # Full 16-model ensemble
                self.ensemble_weights = {
                    'sinkhorn': 0.10,     # Tier 1: Mathematical gatekeeper
                    'rf_xgb': 0.10,       # Tier 1: Tree-based baseline
                    'marl': 0.05,         # Tier 1: Multi-agent coordination
                    'lnn': 0.10,          # Tier 2: Time-continuous
                    'xlstm': 0.10,        # Tier 2: Recurrent patterns
                    'mamba': 0.10,        # Tier 2: Long-context tracking
                    'pinn': 0.15,         # Tier 3: Physics constraints
                    'kan': 0.10,          # Tier 3: Aerodynamic regression
                    'mchc': 0.15,         # Tier 3: Topology validation
                    'gan': 0.05,          # Tier 3: Adversarial detection
                }
            else:
                # Core models only
                self.ensemble_weights = {
                    'sinkhorn': 0.25,     # Mathematical gatekeeper
                    'rf_xgb': 0.15,       # Tree-based baseline
                    'lnn': 0.15,          # Time-continuous
                    'xlstm': 0.15,        # Recurrent patterns
                    'mchc': 0.30,         # Topology validation
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
        # TIER 1: Tree-Based Models (RF/XGBoost)
        # ========================================
        if self.tree_available and trajectory_sequence is not None:
            try:
                tree_result = self.tree_ensemble(trajectory_sequence)
                model_scores['rf_xgb'] = float(tree_result['anomaly_score'].mean())
            except Exception as e:
                warnings.warn(f"Tree ensemble failed: {e}")
                model_scores['rf_xgb'] = 0.0
        else:
            model_scores['rf_xgb'] = 0.0
        
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
            
            # ========================================
            # NEW TIER 2 MODELS (if enabled)
            # ========================================
            if self.enable_all_models and self.mamba is not None:
                # Mamba: Long-Context Trajectory Tracking
                with torch.no_grad():
                    mamba_output = self.mamba(trajectory_tensor)
                    mamba_score = mamba_output['anomaly_score'].mean().item()
                    model_scores['mamba'] = float(mamba_score)
            else:
                model_scores['mamba'] = 0.0
            
            # ========================================
            # NEW TIER 3 MODELS (if enabled)
            # ========================================
            if self.enable_all_models and self.kan is not None:
                # KAN: Aerodynamic Coefficient Regression
                with torch.no_grad():
                    kan_output = self.kan(trajectory_tensor)
                    kan_score = kan_output['anomaly_score'].mean().item()
                    model_scores['kan'] = float(kan_score)
            else:
                model_scores['kan'] = 0.0
            
            if self.enable_all_models and self.pinn is not None:
                # PINN: Physics Constraints
                with torch.no_grad():
                    pinn_output = self.pinn(trajectory_tensor, dt_tensor)
                    pinn_score = pinn_output['anomaly_score'].mean().item()
                    model_scores['pinn'] = float(pinn_score)
            else:
                model_scores['pinn'] = 0.0
            
            if self.enable_all_models and self.gan is not None:
                # GAN: Adversarial Detection
                with torch.no_grad():
                    gan_output = self.gan(trajectory_tensor)
                    gan_score = gan_output['anomaly_score'].mean().item()
                    model_scores['gan'] = float(gan_score)
            else:
                model_scores['gan'] = 0.0
            
            if self.enable_all_models and self.marl is not None:
                # MARL: Multi-Agent Coordination
                # Reshape trajectory data to create agent states
                # Each aircraft is treated as an agent, and we aggregate features into state_dim=16
                with torch.no_grad():
                    batch_size = trajectory_tensor.shape[0]
                    n_timesteps = trajectory_tensor.shape[1]
                    
                    # If we have enough aircraft to form agents
                    if trajectory_tensor.shape[1] >= self.marl.num_agents:
                        # Take first num_agents aircraft and compute their aggregated states
                        # State includes: mean position, velocity, heading, signal strength
                        agent_trajectories = trajectory_tensor[:, :self.marl.num_agents, :]  # [batch, num_agents, features]
                        
                        # Create state_dim=16 by aggregating trajectory statistics
                        # [mean_features(8), std_features(8)]
                        agent_states = torch.cat([
                            agent_trajectories.mean(dim=1),  # Mean over time: [batch, num_agents, 8]
                            agent_trajectories.std(dim=1),   # Std over time: [batch, num_agents, 8]
                        ], dim=-1)  # [batch, num_agents, 16]
                        
                        # Ensure shape is correct
                        if agent_states.shape[-1] < 16:
                            # Pad to 16 dimensions if needed
                            padding = torch.zeros(batch_size, self.marl.num_agents, 16 - agent_states.shape[-1], device=self.device)
                            agent_states = torch.cat([agent_states, padding], dim=-1)
                        elif agent_states.shape[-1] > 16:
                            # Truncate if too large
                            agent_states = agent_states[:, :, :16]
                        
                        marl_output = self.marl(agent_states)
                        marl_score = marl_output['coordination_score'].mean().item()
                        model_scores['marl'] = float(marl_score)
                    else:
                        # Not enough agents - skip MARL
                        model_scores['marl'] = 0.0
            else:
                model_scores['marl'] = 0.0
            
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
                    "Trajectory sequence not provided. Using limited detection."
                )
            model_scores['lnn'] = 0.0
            model_scores['xlstm'] = 0.0
            model_scores['mchc'] = 0.0
            model_scores['mamba'] = 0.0
            model_scores['kan'] = 0.0
            model_scores['pinn'] = 0.0
            model_scores['gan'] = 0.0
            model_scores['marl'] = 0.0
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
