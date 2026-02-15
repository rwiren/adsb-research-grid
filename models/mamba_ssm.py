"""
Mamba (State Space Model) for Long-Context Trajectory Tracking

Mamba is an efficient state space model that provides an alternative to
Transformers for long-sequence modeling. It uses selective state spaces
to capture long-range dependencies in aircraft trajectories.

References:
    Gu & Dao (2023). "Mamba: Linear-Time Sequence Modeling with Selective State Spaces"
"""

import numpy as np
from typing import Dict, Optional, Tuple, Any
import warnings

# Conditional PyTorch imports
TORCH_AVAILABLE = False
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    # Create dummy classes for type hints
    class nn:
        class Module:
            pass
    torch = None
    F = None

# Only define PyTorch models if available
if TORCH_AVAILABLE:
        class MambaBlock(nn.Module):
        """
        Single Mamba block implementing selective state space mechanism.
    
        The block consists of:
        1. Input projection
        2. Selective state space operation (S6)
        3. Gated output projection
    
        Args:
        d_model: Model dimension
        d_state: State space dimension (typically 16)
        d_conv: Convolution dimension for local context (typically 4)
        expand: Expansion factor (typically 2)
        """
    
        def __init__(
        self,
        d_model: int = 64,
        d_state: int = 16,
        d_conv: int = 4,
        expand: int = 2,
        ):
        super().__init__()
        
        self.d_model = d_model
        self.d_state = d_state
        self.d_conv = d_conv
        self.d_inner = d_model * expand
        
        # Input projection
        self.in_proj = nn.Linear(d_model, self.d_inner * 2, bias=False)
        
        # Convolution for local context
        self.conv1d = nn.Conv1d(
            in_channels=self.d_inner,
            out_channels=self.d_inner,
            kernel_size=d_conv,
            groups=self.d_inner,
            padding=d_conv - 1,
        )
        
        # State space parameters (selective)
        self.x_proj = nn.Linear(self.d_inner, d_state + d_state + self.d_inner, bias=False)
        self.dt_proj = nn.Linear(d_state, self.d_inner, bias=True)
        
        # Initialize state space matrices (A, B, C, D)
        A = torch.randn(self.d_inner, d_state)
        self.A_log = nn.Parameter(torch.log(A))
        self.D = nn.Parameter(torch.ones(self.d_inner))
        
        # Output projection
        self.out_proj = nn.Linear(self.d_inner, d_model, bias=False)
        
        def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through Mamba block.
        
        Args:
            x: Input tensor [batch, seq_len, d_model]
            
        Returns:
            Output tensor [batch, seq_len, d_model]
        """
        batch, seq_len, _ = x.shape
        
        # Input projection with gating
        x_and_res = self.in_proj(x)  # [batch, seq_len, 2 * d_inner]
        x, res = x_and_res.split([self.d_inner, self.d_inner], dim=-1)
        
        # Apply convolution for local context
        x = x.transpose(1, 2)  # [batch, d_inner, seq_len]
        x = self.conv1d(x)[:, :, :seq_len]  # Trim padding
        x = x.transpose(1, 2)  # [batch, seq_len, d_inner]
        
        # Activation
        x = F.silu(x)
        
        # Selective SSM
        y = self.selective_scan(x)
        
        # Gated output
        y = y * F.silu(res)
        
        # Output projection
        output = self.out_proj(y)
        
        return output
    
        def selective_scan(self, x: torch.Tensor) -> torch.Tensor:
        """
        Selective state space scan (S6 operation).
        
        Args:
            x: Input tensor [batch, seq_len, d_inner]
            
        Returns:
            Output tensor [batch, seq_len, d_inner]
        """
        batch, seq_len, d_inner = x.shape
        
        # Generate selective parameters
        x_dbl = self.x_proj(x)  # [batch, seq_len, d_state + d_state + d_inner]
        delta, B, C = torch.split(
            x_dbl,
            [self.d_state, self.d_state, self.d_inner],
            dim=-1
        )
        
        # Delta (timestep) projection
        delta = F.softplus(self.dt_proj(delta))  # [batch, seq_len, d_inner]
        
        # Compute A matrix (from log space for stability)
        A = -torch.exp(self.A_log.float())  # [d_inner, d_state]
        
        # Discretization: A_bar = exp(delta * A)
        # Simplified approximation for efficiency
        deltaA = torch.einsum('bld,dn->bldn', delta, A)
        
        # State space recurrence (simplified for demonstration)
        # Full implementation would use parallel scan for efficiency
        y = torch.zeros_like(x)
        h = torch.zeros(batch, self.d_inner, self.d_state, device=x.device)
        
        for t in range(seq_len):
            # Update state: h = A*h + B*x
            h = h + deltaA[:, t] * h + torch.einsum('bd,bds->bds', x[:, t], B[:, t:t+1])
            # Output: y = C*h + D*x
            y[:, t] = torch.einsum('bds,bs->bd', h, C[:, t]) + self.D * x[:, t]
        
        return y


    class MambaSSM(nn.Module):
        """
        Mamba State Space Model for long-context trajectory tracking.
    
        This model uses stacked Mamba blocks to efficiently process long
        sequences of aircraft trajectories with linear time complexity.
    
        Key features:
        - Linear time complexity O(L) vs O(L^2) for Transformers
        - Selective state space for adaptive information flow
        - Efficient for long-range dependency modeling
    
        Attributes:
        num_layers: Number of Mamba blocks
        d_model: Model dimension
        d_state: State space dimension
        
        Example:
        >>> model = MambaSSM(input_dim=8, d_model=64, num_layers=4)
        >>> trajectory = torch.randn(2, 1000, 8)  # Long sequence
        >>> output = model(trajectory)
        >>> print(output['anomaly_score'])
        """
    
        def __init__(
        self,
        input_dim: int = 8,
        d_model: int = 64,
        d_state: int = 16,
        d_conv: int = 4,
        expand: int = 2,
        num_layers: int = 4,
        output_dim: int = 32,
        ):
        super().__init__()
        
        self.input_dim = input_dim
        self.d_model = d_model
        self.num_layers = num_layers
        
        # Input embedding
        self.embedding = nn.Linear(input_dim, d_model)
        
        # Stacked Mamba blocks
        self.layers = nn.ModuleList([
            MambaBlock(
                d_model=d_model,
                d_state=d_state,
                d_conv=d_conv,
                expand=expand,
            )
            for _ in range(num_layers)
        ])
        
        # Layer normalization
        self.norm = nn.LayerNorm(d_model)
        
        # Output projection for anomaly detection
        self.output_proj = nn.Linear(d_model, output_dim)
        self.anomaly_head = nn.Sequential(
            nn.Linear(output_dim, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid(),
        )
        
        def forward(
        self,
        x: torch.Tensor,
        return_hidden: bool = True,
        ) -> Dict[str, torch.Tensor]:
        """
        Forward pass through Mamba SSM.
        
        Args:
            x: Input trajectory sequence [batch, seq_len, input_dim]
            return_hidden: Whether to return hidden states
            
        Returns:
            Dictionary containing:
                - 'hidden': Hidden states [batch, seq_len, d_model]
                - 'output': Output features [batch, seq_len, output_dim]
                - 'anomaly_score': Per-timestep anomaly scores [batch, seq_len]
                - 'trajectory_score': Aggregated trajectory-level score [batch]
        """
        # Input embedding
        x = self.embedding(x)  # [batch, seq_len, d_model]
        
        # Pass through Mamba blocks
        hidden = x
        for layer in self.layers:
            hidden = layer(hidden) + hidden  # Residual connection
            hidden = self.norm(hidden)
        
        # Output projection
        output = self.output_proj(hidden)  # [batch, seq_len, output_dim]
        
        # Anomaly detection
        anomaly_scores = self.anomaly_head(output).squeeze(-1)  # [batch, seq_len]
        
        # Aggregate trajectory-level score (mean over time)
        trajectory_scores = anomaly_scores.mean(dim=1)  # [batch]
        
        result = {
            'anomaly_score': trajectory_scores,
            'per_timestep_score': anomaly_scores,
            'output': output,
        }
        
        if return_hidden:
            result['hidden'] = hidden
            
        return result
    
        def export_to_onnx(self, output_path: str, batch_size: int = 1, seq_len: int = 100):
        """
        Export model to ONNX format for deployment.
        
        Args:
            output_path: Path to save ONNX model
            batch_size: Batch size for export
            seq_len: Sequence length for export
        """
        dummy_input = torch.randn(batch_size, seq_len, self.input_dim)
        torch.onnx.export(
            self,
            dummy_input,
            output_path,
            export_params=True,
            opset_version=14,
            do_constant_folding=True,
            input_names=['trajectory'],
            output_names=['anomaly_score', 'hidden', 'output'],
            dynamic_axes={
                'trajectory': {0: 'batch', 1: 'seq_len'},
                'anomaly_score': {0: 'batch'},
                'hidden': {0: 'batch', 1: 'seq_len'},
                'output': {0: 'batch', 1: 'seq_len'},
            }
        )

else:
    # Placeholders when PyTorch not available
    MambaBlock = None
    MambaSSM = None
    warnings.warn("PyTorch not available. Mamba SSM will not be functional.")


# NumPy fallback for environments without PyTorch
class MambaSSMNumPy:
    """
    Simplified NumPy implementation of Mamba SSM for CPU-only environments.
    
    This is a lightweight fallback that provides basic functionality
    without PyTorch dependencies. Performance is limited compared to
    the full PyTorch implementation.
    """
    
    def __init__(self, input_dim: int = 8, hidden_dim: int = 64):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        
        # Simple linear transformation weights
        self.W_in = np.random.randn(input_dim, hidden_dim) * 0.01
        self.W_out = np.random.randn(hidden_dim, 1) * 0.01
        
    def __call__(self, x: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Forward pass using NumPy.
        
        Args:
            x: Input trajectory [batch, seq_len, input_dim]
            
        Returns:
            Dictionary with anomaly scores
        """
        # Simple feedforward approximation
        batch, seq_len, _ = x.shape
        
        # Project to hidden dimension
        hidden = np.dot(x, self.W_in)  # [batch, seq_len, hidden_dim]
        hidden = np.tanh(hidden)
        
        # Compute anomaly scores
        scores = np.dot(hidden, self.W_out).squeeze(-1)  # [batch, seq_len]
        scores = 1.0 / (1.0 + np.exp(-scores))  # Sigmoid
        
        # Aggregate over time
        trajectory_scores = scores.mean(axis=1)  # [batch]
        
        return {
            'anomaly_score': trajectory_scores,
            'per_timestep_score': scores,
            'hidden': hidden,
        }
