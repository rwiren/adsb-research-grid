"""
Generative Adversarial Network (GAN) for Adversarial Training

GANs generate synthetic spoofing attack patterns to harden the detection
system through "red teaming". The generator creates zero-day attack signatures
while the discriminator learns to detect them.

Architecture:
- Generator: Creates synthetic spoofed trajectories
- Discriminator: Distinguishes real vs spoofed trajectories
- Used for data augmentation and adversarial robustness

References:
    Goodfellow et al. (2014). "Generative Adversarial Networks"
"""

import numpy as np
from typing import Dict, Optional, Tuple, Any
import warnings

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True



class SpoofingGenerator(nn.Module):
    """
    Generator network that creates synthetic spoofed ADS-B trajectories.
    
    The generator learns to create realistic-looking but spoofed trajectories
    that fool the discriminator. These synthetic attacks are used to train
    more robust detection systems.
    
    Args:
        latent_dim: Dimension of random noise input
        trajectory_dim: Dimension of output trajectory features
        seq_len: Length of generated trajectory sequence
    """
    
    def __init__(
        self,
        latent_dim: int = 128,
        trajectory_dim: int = 8,
        seq_len: int = 50,
        hidden_dim: int = 256,
    ):
        super().__init__()
        
        self.latent_dim = latent_dim
        self.trajectory_dim = trajectory_dim
        self.seq_len = seq_len
        
        # Initial projection
        self.fc = nn.Linear(latent_dim, hidden_dim)
        
        # LSTM for temporal coherence
        self.lstm = nn.LSTM(
            input_size=hidden_dim,
            hidden_size=hidden_dim,
            num_layers=2,
            batch_first=True,
        )
        
        # Output projection
        self.output_layer = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, trajectory_dim),
        )
        
    def forward(
        self,
        z: torch.Tensor,
        target_trajectory: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Generate synthetic spoofed trajectory.
        
        Args:
            z: Random noise [batch, latent_dim]
            target_trajectory: Optional real trajectory to perturb [batch, seq_len, trajectory_dim]
            
        Returns:
            Synthetic trajectory [batch, seq_len, trajectory_dim]
        """
        batch_size = z.shape[0]
        
        # Project noise to hidden dimension
        h = self.fc(z)  # [batch, hidden_dim]
        h = F.relu(h)
        
        # Repeat for sequence length
        h = h.unsqueeze(1).repeat(1, self.seq_len, 1)  # [batch, seq_len, hidden_dim]
        
        # Generate temporal sequence
        h, _ = self.lstm(h)  # [batch, seq_len, hidden_dim]
        
        # Generate trajectory
        trajectory = self.output_layer(h)  # [batch, seq_len, trajectory_dim]
        
        # If target trajectory provided, add perturbation
        if target_trajectory is not None:
            # Generate perturbation that's added to real trajectory
            trajectory = target_trajectory + trajectory * 0.1
        
        return trajectory


class SpoofingDiscriminator(nn.Module):
    """
    Discriminator network that detects spoofed trajectories.
    
    The discriminator learns to distinguish between real and generated
    spoofed trajectories. After training, it serves as a robust detector.
    
    Args:
        trajectory_dim: Dimension of trajectory features
        hidden_dim: Hidden layer dimension
    """
    
    def __init__(
        self,
        trajectory_dim: int = 8,
        hidden_dim: int = 256,
    ):
        super().__init__()
        
        self.trajectory_dim = trajectory_dim
        
        # Encoder: Process trajectory sequence
        self.lstm = nn.LSTM(
            input_size=trajectory_dim,
            hidden_size=hidden_dim,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
        )
        
        # Attention layer for important timesteps
        self.attention = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, 1),
            nn.Softmax(dim=1),
        )
        
        # Classifier
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid(),
        )
        
    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Classify trajectory as real (0) or spoofed (1).
        
        Args:
            x: Input trajectory [batch, seq_len, trajectory_dim]
            
        Returns:
            Dictionary with predictions and attention weights
        """
        batch_size, seq_len, _ = x.shape
        
        # Encode sequence
        h, _ = self.lstm(x)  # [batch, seq_len, hidden_dim * 2]
        
        # Compute attention weights
        attention_weights = self.attention(h)  # [batch, seq_len, 1]
        
        # Weighted aggregation
        context = torch.sum(h * attention_weights, dim=1)  # [batch, hidden_dim * 2]
        
        # Classify
        prediction = self.classifier(context)  # [batch, 1]
        
        return {
            'probability': prediction.squeeze(-1),  # [batch]
            'attention_weights': attention_weights.squeeze(-1),  # [batch, seq_len]
            'context': context,
        }


class SpoofingGAN(nn.Module):
    """
    Complete GAN system for adversarial training of spoofing detection.
    
    This system uses adversarial training to generate diverse spoofing
    attack patterns and train robust detectors. The trained discriminator
    can be deployed as a standalone detector.
    
    Training process:
    1. Generator creates synthetic spoofed trajectories
    2. Discriminator tries to distinguish real vs fake
    3. Both networks improve through adversarial training
    4. Discriminator becomes robust spoofing detector
    
    Key features:
    - Generates diverse attack patterns (red teaming)
    - Improves detector robustness
    - Discovers zero-day attack signatures
    - Provides uncertainty estimates
    
    Attributes:
        generator: Network that generates spoofed trajectories
        discriminator: Network that detects spoofing
        
    Example:
        >>> gan = SpoofingGAN(latent_dim=128, trajectory_dim=8)
        >>> # Generate synthetic attack
        >>> z = torch.randn(10, 128)
        >>> fake_trajectory = gan.generate(z)
        >>> # Detect spoofing
        >>> result = gan.detect(trajectory)
        >>> print(f"Spoofing probability: {result['probability']}")
    """
    
    def __init__(
        self,
        latent_dim: int = 128,
        trajectory_dim: int = 8,
        seq_len: int = 50,
        hidden_dim: int = 256,
    ):
        super().__init__()
        
        self.latent_dim = latent_dim
        self.trajectory_dim = trajectory_dim
        self.seq_len = seq_len
        
        # Create generator and discriminator
        self.generator = SpoofingGenerator(
            latent_dim=latent_dim,
            trajectory_dim=trajectory_dim,
            seq_len=seq_len,
            hidden_dim=hidden_dim,
        )
        
        self.discriminator = SpoofingDiscriminator(
            trajectory_dim=trajectory_dim,
            hidden_dim=hidden_dim,
        )
        
    def generate(
        self,
        z: torch.Tensor,
        target_trajectory: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Generate synthetic spoofed trajectories.
        
        Args:
            z: Random noise [batch, latent_dim]
            target_trajectory: Optional real trajectory to perturb
            
        Returns:
            Synthetic spoofed trajectory [batch, seq_len, trajectory_dim]
        """
        return self.generator(z, target_trajectory)
    
    def detect(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Detect spoofing in trajectory.
        
        Args:
            x: Input trajectory [batch, seq_len, trajectory_dim]
            
        Returns:
            Dictionary with detection results
        """
        return self.discriminator(x)
    
    def compute_gan_loss(
        self,
        real_trajectories: torch.Tensor,
        z: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, float]]:
        """
        Compute GAN training losses.
        
        Args:
            real_trajectories: Real trajectory data [batch, seq_len, trajectory_dim]
            z: Random noise for generator (optional, will be sampled if not provided)
            
        Returns:
            (generator_loss, discriminator_loss, metrics_dict)
        """
        batch_size = real_trajectories.shape[0]
        
        # Sample noise if not provided
        if z is None:
            z = torch.randn(batch_size, self.latent_dim, device=real_trajectories.device)
        
        # ========================================
        # Discriminator Loss
        # ========================================
        
        # Real trajectories
        real_pred = self.discriminator(real_trajectories)
        real_loss = F.binary_cross_entropy(
            real_pred['probability'],
            torch.zeros_like(real_pred['probability'])  # Real = 0
        )
        
        # Fake trajectories
        fake_trajectories = self.generator(z).detach()  # Detach to not train generator
        fake_pred = self.discriminator(fake_trajectories)
        fake_loss = F.binary_cross_entropy(
            fake_pred['probability'],
            torch.ones_like(fake_pred['probability'])  # Fake = 1
        )
        
        discriminator_loss = real_loss + fake_loss
        
        # ========================================
        # Generator Loss
        # ========================================
        
        # Generate trajectories (no detach this time)
        fake_trajectories_for_gen = self.generator(z)
        fake_pred_for_gen = self.discriminator(fake_trajectories_for_gen)
        
        # Generator wants to fool discriminator (predict as real)
        generator_loss = F.binary_cross_entropy(
            fake_pred_for_gen['probability'],
            torch.zeros_like(fake_pred_for_gen['probability'])  # Want to be classified as real
        )
        
        # Metrics
        metrics = {
            'discriminator_loss': discriminator_loss.item(),
            'generator_loss': generator_loss.item(),
            'real_accuracy': (real_pred['probability'] < 0.5).float().mean().item(),
            'fake_accuracy': (fake_pred['probability'] > 0.5).float().mean().item(),
        }
        
        return generator_loss, discriminator_loss, metrics
    
    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Forward pass for inference (detection).
        
        Args:
            x: Input trajectory [batch, seq_len, trajectory_dim]
            
        Returns:
            Dictionary with detection results and anomaly score
        """
        result = self.discriminator(x)
        
        # Anomaly score is the discriminator's confidence that trajectory is spoofed
        result['anomaly_score'] = result['probability']
        
        return result
    
    def export_discriminator_onnx(self, output_path: str, batch_size: int = 1, seq_len: int = 50):
        """
        Export trained discriminator to ONNX for deployment.
        
        Args:
            output_path: Path to save ONNX model
            batch_size: Batch size for export
            seq_len: Sequence length for export
        """
        dummy_input = torch.randn(batch_size, seq_len, self.trajectory_dim)
        torch.onnx.export(
            self.discriminator,
            dummy_input,
            output_path,
            export_params=True,
            opset_version=14,
            do_constant_folding=True,
            input_names=['trajectory'],
            output_names=['probability', 'attention_weights'],
            dynamic_axes={
                'trajectory': {0: 'batch', 1: 'seq_len'},
                'probability': {0: 'batch'},
                'attention_weights': {0: 'batch', 1: 'seq_len'},
            }
        )


# NumPy fallback
class SpoofingGANNumPy:
    """
    Simplified NumPy implementation of GAN discriminator for CPU-only environments.
    """
    
    def __init__(self, trajectory_dim: int = 8, hidden_dim: int = 128):
        self.trajectory_dim = trajectory_dim
        self.hidden_dim = hidden_dim
        
        self.W1 = np.random.randn(trajectory_dim, hidden_dim) * 0.01
        self.W2 = np.random.randn(hidden_dim, 1) * 0.01
        
    def detect(self, x: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Detect spoofing using simple discriminator.
        
        Args:
            x: Input trajectory [batch, seq_len, trajectory_dim]
            
        Returns:
            Dictionary with detection results
        """
        batch, seq_len, _ = x.shape
        
        # Average over time
        x_mean = x.mean(axis=1)  # [batch, trajectory_dim]
        
        # Simple feedforward
        h = np.tanh(np.dot(x_mean, self.W1))
        logit = np.dot(h, self.W2).squeeze(-1)
        probability = 1.0 / (1.0 + np.exp(-logit))
        
        return {
            'probability': probability,
            'anomaly_score': probability,
        }
    
    def __call__(self, x: np.ndarray) -> Dict[str, np.ndarray]:
        return self.detect(x)
