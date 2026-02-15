"""
Physics-Informed Neural Network (PINN) Constraints

PINNs embed physical laws (Equations of Motion) directly into the loss function
to ensure predictions respect physics. For ADS-B spoofing detection, this
enforces aircraft dynamics constraints.

Key physics constraints:
1. Newton's Laws: F = ma
2. Maximum acceleration limits
3. Altitude-velocity relationships
4. Minimum turn radius constraints

References:
    Raissi et al. (2019). "Physics-informed neural networks"
"""

import numpy as np
from typing import Dict, Optional, Tuple, Any, List
import warnings

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    nn = None
    warnings.warn("PyTorch not available. PINN will not be functional.")


class PhysicsConstraints:
    """
    Collection of physics constraints for aircraft dynamics.
    
    These constraints are used to compute physics-based loss terms
    that penalize physically impossible trajectories.
    """
    
    # Physical constants
    G = 9.81  # Gravitational acceleration (m/s^2)
    MAX_ACCEL_G = 3.0  # Maximum acceleration for civilian aircraft (in G)
    MAX_VERTICAL_SPEED = 15.0  # m/s (about 3000 ft/min)
    MIN_TURN_RADIUS = 1000.0  # meters
    AIR_DENSITY_SEA_LEVEL = 1.225  # kg/m^3
    
    @staticmethod
    def compute_physics_loss(
        positions: torch.Tensor,
        velocities: torch.Tensor,
        accelerations: torch.Tensor,
        dt: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute physics-based loss terms.
        
        Args:
            positions: [batch, seq_len, 3] (lat, lon, alt in meters)
            velocities: [batch, seq_len, 3] (vx, vy, vz in m/s)
            accelerations: [batch, seq_len, 3] (ax, ay, az in m/s^2)
            dt: [batch, seq_len] time deltas in seconds
            
        Returns:
            Dictionary of loss terms
        """
        # 1. Maximum acceleration constraint
        accel_magnitude = torch.norm(accelerations, dim=-1)  # [batch, seq_len]
        max_allowed_accel = PhysicsConstraints.MAX_ACCEL_G * PhysicsConstraints.G
        accel_violation = F.relu(accel_magnitude - max_allowed_accel)
        accel_loss = accel_violation.mean()
        
        # 2. Vertical speed constraint
        vertical_velocity = velocities[:, :, 2]  # z-component
        vertical_violation = F.relu(
            torch.abs(vertical_velocity) - PhysicsConstraints.MAX_VERTICAL_SPEED
        )
        vertical_loss = vertical_violation.mean()
        
        # 3. Continuity constraint (position derivative should match velocity)
        # dp/dt = v
        position_derivative = (positions[:, 1:] - positions[:, :-1]) / dt[:, :-1, None]
        velocity_diff = torch.abs(position_derivative - velocities[:, :-1])
        continuity_loss = velocity_diff.mean()
        
        # 4. Velocity derivative constraint
        # dv/dt = a
        velocity_derivative = (velocities[:, 1:] - velocities[:, :-1]) / dt[:, :-1, None]
        accel_diff = torch.abs(velocity_derivative - accelerations[:, :-1])
        velocity_continuity_loss = accel_diff.mean()
        
        # 5. Turn radius constraint
        # For horizontal turns: r = v^2 / a_centripetal
        horizontal_velocity = torch.norm(velocities[:, :, :2], dim=-1)
        horizontal_accel = torch.norm(accelerations[:, :, :2], dim=-1)
        turn_radius = (horizontal_velocity ** 2) / (horizontal_accel + 1e-6)
        turn_violation = F.relu(PhysicsConstraints.MIN_TURN_RADIUS - turn_radius)
        turn_loss = turn_violation.mean()
        
        return {
            'accel_loss': accel_loss,
            'vertical_loss': vertical_loss,
            'continuity_loss': continuity_loss,
            'velocity_continuity_loss': velocity_continuity_loss,
            'turn_loss': turn_loss,
            'total_physics_loss': (
                accel_loss +
                vertical_loss +
                continuity_loss * 0.5 +
                velocity_continuity_loss * 0.5 +
                turn_loss * 0.1
            )
        }


class PINN(nn.Module):
    """
    Physics-Informed Neural Network for ADS-B Trajectory Validation.
    
    This network predicts future aircraft states while respecting physical
    constraints through physics-informed loss functions.
    
    Architecture:
    1. Encode current state
    2. Predict future states
    3. Compute physics-based constraints
    4. Use constraints to detect physically impossible trajectories
    
    Key features:
    - Embeds Equations of Motion in training
    - Detects physics violations as anomalies
    - Provides interpretable physics-based scores
    
    Attributes:
        input_dim: Dimension of input state
        hidden_dim: Hidden layer dimension
        output_dim: Dimension of predicted state
        
    Example:
        >>> pinn = PINN(input_dim=8, hidden_dim=64, output_dim=9)
        >>> trajectory = torch.randn(2, 50, 8)
        >>> result = pinn(trajectory)
        >>> print(f"Physics violation score: {result['anomaly_score']}")
    """
    
    def __init__(
        self,
        input_dim: int = 8,
        hidden_dim: int = 64,
        output_dim: int = 9,  # position (3) + velocity (3) + acceleration (3)
        num_layers: int = 3,
    ):
        super().__init__()
        
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        
        # Encoder network
        encoder_layers = []
        encoder_layers.append(nn.Linear(input_dim, hidden_dim))
        encoder_layers.append(nn.Tanh())
        
        for _ in range(num_layers - 1):
            encoder_layers.append(nn.Linear(hidden_dim, hidden_dim))
            encoder_layers.append(nn.Tanh())
        
        self.encoder = nn.Sequential(*encoder_layers)
        
        # Prediction head
        self.predictor = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, output_dim),
        )
        
        # Anomaly detection head
        self.anomaly_detector = nn.Sequential(
            nn.Linear(hidden_dim + output_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )
        
        # Physics constraints
        self.physics_constraints = PhysicsConstraints()
        
    def forward(
        self,
        x: torch.Tensor,
        dt: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass with physics constraints.
        
        Args:
            x: Input trajectory [batch, seq_len, input_dim]
               Features: [lat, lon, alt, vx, vy, vz, heading, rssi]
            dt: Time deltas [batch, seq_len] (optional)
            
        Returns:
            Dictionary containing:
                - 'predicted_state': Predicted next state [batch, seq_len, output_dim]
                - 'anomaly_score': Physics violation score [batch]
                - 'physics_losses': Dictionary of individual physics loss terms
        """
        batch_size, seq_len, _ = x.shape
        
        # Default dt if not provided
        if dt is None:
            dt = torch.ones(batch_size, seq_len, device=x.device)
        
        # Encode trajectory
        x_flat = x.reshape(-1, self.input_dim)
        encoded = self.encoder(x_flat)
        encoded = encoded.reshape(batch_size, seq_len, self.hidden_dim)
        
        # Predict next state (position, velocity, acceleration)
        encoded_flat = encoded.reshape(-1, self.hidden_dim)
        predicted_state = self.predictor(encoded_flat)
        predicted_state = predicted_state.reshape(batch_size, seq_len, self.output_dim)
        
        # Extract components
        predicted_position = predicted_state[:, :, :3]
        predicted_velocity = predicted_state[:, :, 3:6]
        predicted_acceleration = predicted_state[:, :, 6:9]
        
        # Compute physics constraints
        # Note: In training, we would have ground truth to compare against
        # For inference, we check self-consistency
        physics_losses = self.physics_constraints.compute_physics_loss(
            positions=predicted_position,
            velocities=predicted_velocity,
            accelerations=predicted_acceleration,
            dt=dt,
        )
        
        # Anomaly detection based on physics violations
        # Combine encoded representation with predicted state
        combined = torch.cat([
            encoded.reshape(-1, self.hidden_dim),
            predicted_state.reshape(-1, self.output_dim)
        ], dim=-1)
        
        anomaly_logits = self.anomaly_detector(combined)
        anomaly_logits = anomaly_logits.reshape(batch_size, seq_len)
        
        # Aggregate anomaly score (mean over time, weighted by physics loss)
        physics_weight = physics_losses['total_physics_loss'].detach()
        base_anomaly = anomaly_logits.mean(dim=1)
        
        # Combine neural network score with physics violation score
        anomaly_score = (base_anomaly + physics_weight.unsqueeze(0)) / 2.0
        anomaly_score = torch.clamp(anomaly_score, 0.0, 1.0)
        
        return {
            'predicted_state': predicted_state,
            'predicted_position': predicted_position,
            'predicted_velocity': predicted_velocity,
            'predicted_acceleration': predicted_acceleration,
            'anomaly_score': anomaly_score,
            'physics_losses': physics_losses,
            'per_timestep_score': anomaly_logits,
        }
    
    def compute_training_loss(
        self,
        x: torch.Tensor,
        y_true: torch.Tensor,
        dt: Optional[torch.Tensor] = None,
        physics_weight: float = 0.3,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute training loss with physics constraints.
        
        Args:
            x: Input trajectory
            y_true: Ground truth next state
            dt: Time deltas
            physics_weight: Weight for physics loss term
            
        Returns:
            (total_loss, loss_dict)
        """
        output = self.forward(x, dt)
        
        # Prediction loss (MSE)
        pred_loss = F.mse_loss(output['predicted_state'], y_true)
        
        # Physics loss
        physics_loss = output['physics_losses']['total_physics_loss']
        
        # Total loss
        total_loss = pred_loss + physics_weight * physics_loss
        
        loss_dict = {
            'total_loss': total_loss.item(),
            'prediction_loss': pred_loss.item(),
            'physics_loss': physics_loss.item(),
            **{k: v.item() for k, v in output['physics_losses'].items()}
        }
        
        return total_loss, loss_dict
    
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
            output_names=['predicted_state', 'anomaly_score'],
            dynamic_axes={
                'trajectory': {0: 'batch', 1: 'seq_len'},
                'predicted_state': {0: 'batch', 1: 'seq_len'},
                'anomaly_score': {0: 'batch'},
            }
        )


# NumPy fallback
class PINNNumPy:
    """
    Simplified NumPy implementation of PINN for CPU-only environments.
    """
    
    def __init__(self, input_dim: int = 8, hidden_dim: int = 64):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        
        self.W1 = np.random.randn(input_dim, hidden_dim) * 0.01
        self.W2 = np.random.randn(hidden_dim, 9) * 0.01
        
    def __call__(self, x: np.ndarray, dt: Optional[np.ndarray] = None) -> Dict[str, np.ndarray]:
        """
        Forward pass using NumPy.
        
        Args:
            x: Input trajectory [batch, seq_len, input_dim]
            dt: Time deltas [batch, seq_len]
            
        Returns:
            Dictionary with predictions and anomaly scores
        """
        batch, seq_len, _ = x.shape
        x_flat = x.reshape(-1, self.input_dim)
        
        # Simple feedforward
        h = np.tanh(np.dot(x_flat, self.W1))
        out = np.dot(h, self.W2)
        out = out.reshape(batch, seq_len, 9)
        
        # Extract state components
        position = out[:, :, :3]
        velocity = out[:, :, 3:6]
        acceleration = out[:, :, 6:9]
        
        # Simple physics check
        accel_mag = np.linalg.norm(acceleration, axis=-1)
        max_accel = 3.0 * 9.81  # 3G
        violation = np.maximum(0, accel_mag - max_accel)
        anomaly_score = np.clip(violation.mean(axis=1) / max_accel, 0, 1)
        
        return {
            'predicted_state': out,
            'predicted_position': position,
            'predicted_velocity': velocity,
            'predicted_acceleration': acceleration,
            'anomaly_score': anomaly_score,
        }
