"""
Kolmogorov-Arnold Networks (KAN) for Symbolic Aerodynamic Regression

KAN replaces traditional MLPs with learnable activation functions on edges,
enabling symbolic regression for aerodynamic coefficient estimation.

This implementation is designed for real-time lift/drag coefficient estimation
from ADS-B trajectory data.

References:
    Liu et al. (2024). "KAN: Kolmogorov-Arnold Networks"
"""

import numpy as np
from typing import Dict, Optional, List, Tuple, Any
import warnings

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    nn = None
    warnings.warn("PyTorch not available. KAN will not be functional.")


class BSplineBasis(nn.Module):
    """
    B-Spline basis functions for learnable activation.
    
    Instead of fixed activations (ReLU, tanh), KAN learns the activation
    function itself using B-spline basis functions.
    
    Args:
        num_bases: Number of B-spline basis functions
        input_range: (min, max) range for input values
        degree: Degree of B-spline (typically 3 for cubic)
    """
    
    def __init__(
        self,
        num_bases: int = 10,
        input_range: Tuple[float, float] = (-1.0, 1.0),
        degree: int = 3,
    ):
        super().__init__()
        
        self.num_bases = num_bases
        self.degree = degree
        self.input_range = input_range
        
        # Create knot vector
        # For cubic B-splines with n bases, we need n + degree + 1 knots
        num_knots = num_bases + degree + 1
        knots = torch.linspace(input_range[0], input_range[1], num_knots)
        self.register_buffer('knots', knots)
        
        # Learnable coefficients for each basis function
        self.coeffs = nn.Parameter(torch.randn(num_bases))
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Evaluate B-spline at input x.
        
        Args:
            x: Input tensor [..., 1]
            
        Returns:
            Output tensor [..., 1]
        """
        # Clamp input to valid range
        x = torch.clamp(x, self.input_range[0], self.input_range[1])
        
        # Compute B-spline basis functions (simplified implementation)
        # Full implementation would use Cox-de Boor recursion
        basis = self._compute_basis(x)
        
        # Linear combination of basis functions
        output = torch.sum(basis * self.coeffs, dim=-1, keepdim=True)
        
        return output
    
    def _compute_basis(self, x: torch.Tensor) -> torch.Tensor:
        """
        Compute B-spline basis function values (simplified).
        
        Args:
            x: Input tensor
            
        Returns:
            Basis function values [batch, num_bases]
        """
        # Simplified radial basis function approximation
        # Full KAN would implement proper B-spline recursion
        centers = torch.linspace(
            self.input_range[0],
            self.input_range[1],
            self.num_bases,
            device=x.device
        )
        
        # Gaussian RBF approximation
        basis = torch.exp(-0.5 * ((x - centers) / 0.2) ** 2)
        
        return basis


class KANLayer(nn.Module):
    """
    Kolmogorov-Arnold Network Layer.
    
    Unlike traditional dense layers with y = W*activation(x),
    KAN uses y = sum(activation_ij(x_i)) where each edge has its own
    learnable activation function.
    
    Args:
        in_features: Input dimension
        out_features: Output dimension
        num_bases: Number of B-spline bases per activation
    """
    
    def __init__(
        self,
        in_features: int,
        out_features: int,
        num_bases: int = 10,
    ):
        super().__init__()
        
        self.in_features = in_features
        self.out_features = out_features
        
        # Each edge (i, j) has its own learnable activation function
        self.activations = nn.ModuleList([
            nn.ModuleList([
                BSplineBasis(num_bases=num_bases)
                for _ in range(out_features)
            ])
            for _ in range(in_features)
        ])
        
        # Optional residual connection with learnable weight
        self.residual_weight = nn.Parameter(torch.ones(1))
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through KAN layer.
        
        Args:
            x: Input tensor [batch, in_features]
            
        Returns:
            Output tensor [batch, out_features]
        """
        batch_size = x.shape[0]
        output = torch.zeros(batch_size, self.out_features, device=x.device)
        
        # For each output neuron j, sum contributions from all input neurons i
        for i in range(self.in_features):
            x_i = x[:, i:i+1]  # [batch, 1]
            
            for j in range(self.out_features):
                # Apply learnable activation function for edge (i, j)
                contribution = self.activations[i][j](x_i).squeeze(-1)
                output[:, j] += contribution
        
        return output


class KAN(nn.Module):
    """
    Kolmogorov-Arnold Network for Symbolic Aerodynamic Regression.
    
    This network learns to estimate aerodynamic coefficients (Lift, Drag)
    from aircraft trajectory data using symbolic regression via learnable
    activation functions.
    
    Key features:
    - Learns interpretable mathematical relationships
    - Symbolic regression for aerodynamic equations
    - Efficient evaluation for real-time inference
    
    Physical relationships modeled:
    - Lift coefficient: C_L = f(alpha, Mach, Re)
    - Drag coefficient: C_D = f(C_L, Mach, aspect_ratio)
    
    Attributes:
        input_dim: Dimension of input features
        hidden_dims: List of hidden layer dimensions
        output_dim: Output dimension (typically 2 for C_L and C_D)
        
    Example:
        >>> kan = KAN(input_dim=8, hidden_dims=[32, 16], output_dim=2)
        >>> trajectory = torch.randn(10, 50, 8)  # [batch, time, features]
        >>> coeffs = kan(trajectory)
        >>> print(f"Lift coeff: {coeffs['lift_coeff']}")
        >>> print(f"Drag coeff: {coeffs['drag_coeff']}")
    """
    
    def __init__(
        self,
        input_dim: int = 8,
        hidden_dims: List[int] = [32, 16],
        output_dim: int = 2,
        num_bases: int = 10,
    ):
        super().__init__()
        
        self.input_dim = input_dim
        self.output_dim = output_dim
        
        # Build KAN layers
        dims = [input_dim] + hidden_dims + [output_dim]
        self.layers = nn.ModuleList([
            KANLayer(dims[i], dims[i+1], num_bases=num_bases)
            for i in range(len(dims) - 1)
        ])
        
        # Normalization layers
        self.layer_norms = nn.ModuleList([
            nn.LayerNorm(dim) for dim in dims[1:]
        ])
        
        # Physics-based output constraints
        # Lift coefficient typically in range [-2, 2]
        # Drag coefficient typically in range [0, 0.5]
        self.register_buffer('lift_scale', torch.tensor([2.0]))
        self.register_buffer('drag_scale', torch.tensor([0.5]))
        self.register_buffer('drag_offset', torch.tensor([0.0]))
        
    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Forward pass to estimate aerodynamic coefficients.
        
        Args:
            x: Input trajectory features [batch, seq_len, input_dim]
               Features should include: velocity, altitude, acceleration,
               angle of attack (estimated), air density, temperature
               
        Returns:
            Dictionary containing:
                - 'coefficients': Raw output [batch, seq_len, 2]
                - 'lift_coeff': Lift coefficient [batch, seq_len]
                - 'drag_coeff': Drag coefficient [batch, seq_len]
                - 'anomaly_score': Physics-based anomaly score [batch]
        """
        batch_size, seq_len, _ = x.shape
        
        # Process sequence (can be parallelized)
        x_flat = x.reshape(-1, self.input_dim)  # [batch*seq_len, input_dim]
        
        # Pass through KAN layers
        h = x_flat
        for layer, norm in zip(self.layers, self.layer_norms):
            h = layer(h)
            h = norm(h)
        
        # Reshape back to sequence
        h = h.reshape(batch_size, seq_len, self.output_dim)
        
        # Split into lift and drag coefficients
        lift_raw = h[:, :, 0]
        drag_raw = h[:, :, 1]
        
        # Apply physics-based constraints
        lift_coeff = torch.tanh(lift_raw) * self.lift_scale  # [-2, 2]
        drag_coeff = torch.sigmoid(drag_raw) * self.drag_scale + self.drag_offset  # [0, 0.5]
        
        # Compute anomaly score based on physical plausibility
        # High drag with low lift is suspicious (efficiency violation)
        # Sudden coefficient changes indicate spoofing
        lift_std = lift_coeff.std(dim=1)
        drag_std = drag_coeff.std(dim=1)
        
        # Lift/drag ratio should be reasonable for aircraft
        # Typical L/D for civilian aircraft: 15-20 (efficient), military: 10-15
        # Using conservative threshold of 5.0 to catch severely degraded performance
        ld_ratio = lift_coeff.abs() / (drag_coeff + 1e-6)
        ld_anomaly = torch.where(
            ld_ratio < 5.0,  # Conservative threshold - below this indicates severe issues
            1.0,
            0.0
        ).mean(dim=1)
        
        # Coefficient instability (rapid changes)
        instability = (lift_std + drag_std) / 2.0
        instability_score = torch.sigmoid((instability - 0.5) * 10)
        
        # Combined anomaly score
        anomaly_score = (ld_anomaly + instability_score) / 2.0
        
        return {
            'coefficients': h,
            'lift_coeff': lift_coeff,
            'drag_coeff': drag_coeff,
            'anomaly_score': anomaly_score,
            'lift_std': lift_std,
            'drag_std': drag_std,
        }
    
    def export_to_onnx(self, output_path: str, batch_size: int = 1, seq_len: int = 50):
        """
        Export model to ONNX format.
        
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
            output_names=['coefficients', 'lift_coeff', 'drag_coeff', 'anomaly_score'],
            dynamic_axes={
                'trajectory': {0: 'batch', 1: 'seq_len'},
                'coefficients': {0: 'batch', 1: 'seq_len'},
                'lift_coeff': {0: 'batch', 1: 'seq_len'},
                'drag_coeff': {0: 'batch', 1: 'seq_len'},
                'anomaly_score': {0: 'batch'},
            }
        )


# NumPy fallback
class KANNumPy:
    """
    Simplified NumPy implementation of KAN for CPU-only environments.
    """
    
    def __init__(self, input_dim: int = 8, hidden_dim: int = 32, output_dim: int = 2):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        
        # Simple MLP weights as fallback
        self.W1 = np.random.randn(input_dim, hidden_dim) * 0.01
        self.W2 = np.random.randn(hidden_dim, output_dim) * 0.01
        
    def __call__(self, x: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Forward pass using NumPy.
        
        Args:
            x: Input trajectory [batch, seq_len, input_dim]
            
        Returns:
            Dictionary with aerodynamic coefficients
        """
        batch, seq_len, _ = x.shape
        x_flat = x.reshape(-1, self.input_dim)
        
        # Simple feedforward
        h = np.tanh(np.dot(x_flat, self.W1))
        out = np.dot(h, self.W2)
        out = out.reshape(batch, seq_len, self.output_dim)
        
        # Extract coefficients
        lift_coeff = np.tanh(out[:, :, 0]) * 2.0
        drag_coeff = 1.0 / (1.0 + np.exp(-out[:, :, 1])) * 0.5
        
        # Simple anomaly score
        anomaly_score = np.abs(lift_coeff.std(axis=1) + drag_coeff.std(axis=1))
        anomaly_score = 1.0 / (1.0 + np.exp(-(anomaly_score - 0.5) * 10))
        
        return {
            'coefficients': out,
            'lift_coeff': lift_coeff,
            'drag_coeff': drag_coeff,
            'anomaly_score': anomaly_score,
        }
