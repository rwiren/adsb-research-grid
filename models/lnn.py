"""
Liquid Neural Networks (LNN) for Irregular Time-Series

Time-continuous neural networks designed for adaptive signal processing on 
irregular time-series data. Particularly suited for ADS-B streams with 
variable sampling rates.

References:
    - Hasani et al. (2021). Liquid Time-constant Networks.
    - Lechner et al. (2020). Neural Circuit Policies.
"""

import numpy as np
from typing import Dict, Optional, Any

try:
    import torch
    import torch.nn as nn
    from torch import Tensor
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    class nn:
        class Module:
            pass
    Tensor = Any


class LiquidNeuralNetwork(nn.Module if TORCH_AVAILABLE else object):
    """
    Liquid Neural Network (LNN) for Time-Continuous Anomaly Detection.
    
    LNNs use continuous-time dynamics to process irregular time-series data,
    making them ideal for ADS-B signals with variable update rates. The network
    maintains internal "liquid" states that evolve according to learned ODEs.
    
    Key Features:
    - Handles irregular sampling (adaptive to ADS-B message rate variations)
    - Time-continuous dynamics (realistic temporal modeling)
    - Stable long-term predictions
    - Lightweight architecture for edge deployment
    
    Attributes:
        input_dim: Dimension of input features (e.g., position, velocity).
        hidden_dim: Dimension of internal liquid state.
        output_dim: Dimension of output features.
        num_layers: Number of liquid layers.
        time_constant: Time constant for ODE integration (stability parameter).
        
    Example:
        >>> lnn = LiquidNeuralNetwork(input_dim=6, hidden_dim=32, output_dim=16)
        >>> # Sequence: [batch_size, seq_len, input_dim]
        >>> x = torch.randn(4, 100, 6)
        >>> # Delta times: [batch_size, seq_len] (irregular sampling)
        >>> dt = torch.rand(4, 100) * 0.1 + 0.01
        >>> output, hidden = lnn(x, dt)
    """
    
    def __init__(
        self,
        input_dim: int = 6,
        hidden_dim: int = 32,
        output_dim: int = 16,
        num_layers: int = 2,
        time_constant: float = 0.5,
        dropout: float = 0.1,
    ):
        """
        Initialize Liquid Neural Network.
        
        Args:
            input_dim: Dimension of input features per time step.
            hidden_dim: Dimension of liquid state (internal dynamics).
            output_dim: Dimension of output features.
            num_layers: Number of liquid layers (depth).
            time_constant: Time constant τ for ODE stability. Lower = more adaptive.
            dropout: Dropout rate for regularization.
        """
        if not TORCH_AVAILABLE:
            raise ImportError(
                "PyTorch is required for LNN. "
                "Install with: pip install torch"
            )
            
        super(LiquidNeuralNetwork, self).__init__()
        
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        self.num_layers = num_layers
        self.time_constant = time_constant
        self.dropout = dropout
        
        # Input projection
        self.input_projection = nn.Linear(input_dim, hidden_dim)
        
        # Liquid layers (simplified continuous-time RNN)
        # In full implementation, use neural ODEs
        self.liquid_layers = nn.ModuleList([
            nn.Linear(hidden_dim, hidden_dim) for _ in range(num_layers)
        ])
        
        # Time modulation layers
        self.time_gates = nn.ModuleList([
            nn.Linear(hidden_dim + 1, hidden_dim) for _ in range(num_layers)
        ])
        
        # Output projection
        self.output_projection = nn.Linear(hidden_dim, output_dim)
        
        # Layer normalization
        self.layer_norms = nn.ModuleList([
            nn.LayerNorm(hidden_dim) for _ in range(num_layers)
        ])
        
    def forward(
        self,
        x: Tensor,
        dt: Optional[Tensor] = None,
        hidden: Optional[Tensor] = None,
    ) -> Dict[str, Tensor]:
        """
        Forward pass through Liquid Neural Network.
        
        Args:
            x: [batch_size, seq_len, input_dim] input sequence.
            dt: [batch_size, seq_len] time differences between samples (optional).
                If None, assumes uniform sampling with dt=1.0.
            hidden: [batch_size, hidden_dim] initial hidden state (optional).
            
        Returns:
            Dictionary containing:
                - 'output': [batch_size, seq_len, output_dim] output sequence
                - 'hidden': [batch_size, hidden_dim] final hidden state
                - 'anomaly_score': [batch_size] time-based anomaly score
        """
        batch_size, seq_len, _ = x.shape
        
        # Initialize hidden state
        if hidden is None:
            hidden = torch.zeros(batch_size, self.hidden_dim, device=x.device)
            
        # Default time differences if not provided
        if dt is None:
            dt = torch.ones(batch_size, seq_len, device=x.device)
        else:
            # Ensure dt has correct shape
            if dt.dim() == 1:
                dt = dt.unsqueeze(0).expand(batch_size, -1)
        
        # Project input
        x_projected = self.input_projection(x)  # [batch_size, seq_len, hidden_dim]
        x_projected = torch.relu(x_projected)
        
        # Process sequence with liquid dynamics
        outputs = []
        for t in range(seq_len):
            x_t = x_projected[:, t, :]  # [batch_size, hidden_dim]
            dt_t = dt[:, t].unsqueeze(-1)  # [batch_size, 1]
            
            # Liquid state evolution
            for layer_idx, (liquid_layer, time_gate, layer_norm) in enumerate(
                zip(self.liquid_layers, self.time_gates, self.layer_norms)
            ):
                # Continuous-time update approximation (Euler method)
                # dh/dt = f(h, x) / τ
                # h_new = h + dt * (f(h, x) - h) / τ
                
                # Compute time-dependent gate
                h_with_time = torch.cat([hidden, dt_t], dim=-1)
                gate = torch.sigmoid(time_gate(h_with_time))
                
                # State derivative
                h_derivative = liquid_layer(hidden + x_t)
                h_derivative = torch.tanh(h_derivative)
                
                # Continuous update with time constant
                hidden = hidden + (dt_t / self.time_constant) * gate * (h_derivative - hidden)
                
                # Layer normalization
                hidden = layer_norm(hidden)
                
                # Dropout
                hidden = nn.functional.dropout(hidden, p=self.dropout, training=self.training)
            
            outputs.append(hidden)
        
        # Stack outputs
        output_sequence = torch.stack(outputs, dim=1)  # [batch_size, seq_len, hidden_dim]
        
        # Project to output dimension
        output = self.output_projection(output_sequence)
        
        # Compute anomaly score based on state dynamics
        # High variance in hidden state = potential anomaly
        hidden_variance = torch.var(output_sequence, dim=1).mean(dim=-1)
        anomaly_score = torch.sigmoid(hidden_variance)
        
        return {
            'output': output,
            'hidden': hidden,
            'anomaly_score': anomaly_score,
        }
    
    def get_anomaly_features(self, x: Tensor, dt: Optional[Tensor] = None) -> Tensor:
        """
        Extract anomaly detection features from input sequence.
        
        Args:
            x: [batch_size, seq_len, input_dim] input sequence.
            dt: [batch_size, seq_len] time differences (optional).
            
        Returns:
            [batch_size, output_dim] anomaly feature vector.
        """
        result = self.forward(x, dt)
        # Return final output as features
        return result['output'][:, -1, :]
