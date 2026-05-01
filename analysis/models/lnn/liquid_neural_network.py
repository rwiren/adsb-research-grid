#!/usr/bin/env python3
"""
==============================================================================
LIQUID NEURAL NETWORK (LNN) FOR ADS-B ANOMALY DETECTION
==============================================================================
Purpose: Time-continuous neural network for adaptive signal processing
         on irregular time-series ADS-B data

Based on: "Liquid Time-constant Networks" (Hasani et al., 2020)
          Neural ODEs for continuous-time modeling

Use Case: Detect anomalies in aircraft signals, trajectories, and behaviors
          that may indicate spoofing or system malfunctions

Author: ADS-B Research Grid Project
License: MIT
==============================================================================
"""

import torch
import torch.nn as nn
import numpy as np
from torchdiffeq import odeint
from pathlib import Path


class LiquidCell(nn.Module):
    """
    Liquid Time-Constant (LTC) Cell
    
    Implements continuous-time dynamics with learnable time constants.
    The cell evolves according to:
        dh/dt = (1/τ) * (-h + f(Wx*x + Wh*h + b))
    
    where τ is a learnable time constant.
    """
    
    def __init__(self, input_size, hidden_size, nonlinearity='tanh'):
        super(LiquidCell, self).__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        
        # Input weights
        self.W_x = nn.Linear(input_size, hidden_size, bias=False)
        
        # Recurrent weights
        self.W_h = nn.Linear(hidden_size, hidden_size, bias=False)
        
        # Bias
        self.bias = nn.Parameter(torch.zeros(hidden_size))
        
        # Learnable time constants (positive)
        self.tau = nn.Parameter(torch.ones(hidden_size))
        
        # Nonlinearity
        if nonlinearity == 'tanh':
            self.activation = torch.tanh
        elif nonlinearity == 'relu':
            self.activation = torch.relu
        else:
            self.activation = lambda x: x
            
    def forward(self, x, h):
        """
        Forward pass through the liquid cell
        
        Args:
            x: Input tensor (batch_size, input_size)
            h: Hidden state (batch_size, hidden_size)
            
        Returns:
            dh/dt: Time derivative of hidden state
        """
        # Ensure tau is positive
        tau = torch.abs(self.tau) + 1e-3
        
        # Compute activation
        z = self.W_x(x) + self.W_h(h) + self.bias
        f_z = self.activation(z)
        
        # Compute time derivative
        dh = (1.0 / tau) * (-h + f_z)
        
        return dh


class LiquidNeuralNetwork(nn.Module):
    """
    Liquid Neural Network for time-series processing
    
    Uses Neural ODE integration to evolve hidden states continuously
    over time, making it suitable for irregular time-series data.
    """
    
    def __init__(self, input_size, hidden_size, output_size, 
                 num_layers=1, solver='dopri5', rtol=1e-3, atol=1e-4):
        super(LiquidNeuralNetwork, self).__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        self.num_layers = num_layers
        self.solver = solver
        self.rtol = rtol
        self.atol = atol
        
        # Create liquid cells
        self.cells = nn.ModuleList()
        for i in range(num_layers):
            in_size = input_size if i == 0 else hidden_size
            self.cells.append(LiquidCell(in_size, hidden_size))
        
        # Output layer
        self.output_layer = nn.Linear(hidden_size, output_size)
        
    def _ode_func(self, t, state, x):
        """
        ODE function for continuous-time evolution
        
        Args:
            t: Time (not used directly, but required by odeint)
            state: Current hidden state
            x: Input at current time
            
        Returns:
            Time derivative of state
        """
        h = state
        for i, cell in enumerate(self.cells):
            input_i = x if i == 0 else h
            h = cell(input_i, h)
        return h
    
    def forward(self, x, timestamps=None, h0=None):
        """
        Forward pass through the LNN
        
        Args:
            x: Input tensor (batch_size, seq_len, input_size)
            timestamps: Time points for each step (batch_size, seq_len)
                       If None, assumes uniform spacing
            h0: Initial hidden state (batch_size, hidden_size)
            
        Returns:
            output: Predictions (batch_size, seq_len, output_size)
            hidden_states: Evolution of hidden states
        """
        batch_size, seq_len, _ = x.shape
        device = x.device
        
        # Initialize hidden state
        if h0 is None:
            h = torch.zeros(batch_size, self.hidden_size, device=device)
        else:
            h = h0
        
        # Create timestamps if not provided
        if timestamps is None:
            timestamps = torch.arange(seq_len, dtype=torch.float32, device=device)
            timestamps = timestamps.unsqueeze(0).repeat(batch_size, 1)
        
        outputs = []
        hidden_states = []
        
        # Process sequence step by step
        for t in range(seq_len):
            x_t = x[:, t, :]
            
            # Integrate ODE for one time step
            if t < seq_len - 1:
                t_span = torch.tensor([timestamps[0, t], timestamps[0, t+1]], 
                                     device=device, dtype=torch.float32)
            else:
                t_span = torch.tensor([timestamps[0, t], timestamps[0, t] + 1.0],
                                     device=device, dtype=torch.float32)
            
            # Evolve hidden state
            h_evolved = odeint(
                lambda t, h: self._ode_func(t, h, x_t),
                h,
                t_span,
                rtol=self.rtol,
                atol=self.atol,
                method=self.solver
            )
            
            h = h_evolved[-1]  # Take final state
            
            # Compute output
            out = self.output_layer(h)
            outputs.append(out)
            hidden_states.append(h)
        
        # Stack outputs
        outputs = torch.stack(outputs, dim=1)
        hidden_states = torch.stack(hidden_states, dim=1)
        
        return outputs, hidden_states


class LNNAnomalyDetector(nn.Module):
    """
    Anomaly detection model using Liquid Neural Networks
    
    Detects anomalies by learning normal patterns and identifying
    deviations. Suitable for ADS-B signal irregularities, trajectory
    anomalies, and multi-sensor inconsistencies.
    """
    
    def __init__(self, input_size, hidden_size=64, latent_size=32,
                 num_layers=2, dropout=0.1):
        super(LNNAnomalyDetector, self).__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.latent_size = latent_size
        
        # Encoder: Map input to latent representation
        self.encoder_lnn = LiquidNeuralNetwork(
            input_size=input_size,
            hidden_size=hidden_size,
            output_size=latent_size,
            num_layers=num_layers
        )
        
        # Decoder: Reconstruct input from latent
        self.decoder = nn.Sequential(
            nn.Linear(latent_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, input_size)
        )
        
        # Anomaly score head
        self.anomaly_head = nn.Sequential(
            nn.Linear(latent_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, 1),
            nn.Sigmoid()
        )
        
    def forward(self, x, timestamps=None):
        """
        Forward pass
        
        Args:
            x: Input (batch_size, seq_len, input_size)
            timestamps: Time points (batch_size, seq_len)
            
        Returns:
            reconstruction: Reconstructed input
            anomaly_scores: Anomaly probability (0-1)
            latent: Latent representation
        """
        # Encode to latent space
        latent, _ = self.encoder_lnn(x, timestamps)
        
        # Reconstruct
        reconstruction = self.decoder(latent)
        
        # Compute anomaly scores
        anomaly_scores = self.anomaly_head(latent)
        
        return reconstruction, anomaly_scores, latent
    
    def detect_anomalies(self, x, timestamps=None, threshold=0.5):
        """
        Detect anomalies in input data
        
        Args:
            x: Input tensor
            timestamps: Time points
            threshold: Anomaly score threshold
            
        Returns:
            is_anomaly: Binary mask (1 = anomaly, 0 = normal)
            scores: Anomaly scores
        """
        self.eval()
        with torch.no_grad():
            reconstruction, anomaly_scores, _ = self.forward(x, timestamps)
            
            # Compute reconstruction error
            recon_error = torch.mean((x - reconstruction) ** 2, dim=-1, keepdim=True)
            
            # Combine scores
            combined_scores = (anomaly_scores + recon_error / recon_error.max()) / 2.0
            
            is_anomaly = (combined_scores > threshold).float()
            
        return is_anomaly, combined_scores


def create_lnn_model(input_size, model_type='anomaly_detector', **kwargs):
    """
    Factory function to create LNN models
    
    Args:
        input_size: Number of input features
        model_type: Type of model ('anomaly_detector', 'basic_lnn')
        **kwargs: Additional model parameters
        
    Returns:
        model: Instantiated LNN model
    """
    if model_type == 'anomaly_detector':
        model = LNNAnomalyDetector(
            input_size=input_size,
            hidden_size=kwargs.get('hidden_size', 64),
            latent_size=kwargs.get('latent_size', 32),
            num_layers=kwargs.get('num_layers', 2),
            dropout=kwargs.get('dropout', 0.1)
        )
    elif model_type == 'basic_lnn':
        model = LiquidNeuralNetwork(
            input_size=input_size,
            hidden_size=kwargs.get('hidden_size', 64),
            output_size=kwargs.get('output_size', input_size),
            num_layers=kwargs.get('num_layers', 1)
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")
    
    return model


if __name__ == "__main__":
    # Test the LNN implementation
    print("Testing Liquid Neural Network implementation...")
    
    # Parameters
    batch_size = 4
    seq_len = 10
    input_size = 8
    
    # Create dummy data
    x = torch.randn(batch_size, seq_len, input_size)
    timestamps = torch.linspace(0, 1, seq_len).unsqueeze(0).repeat(batch_size, 1)
    
    # Test basic LNN
    print("\n1. Testing basic LNN...")
    lnn = create_lnn_model(input_size, model_type='basic_lnn', hidden_size=32, output_size=input_size)
    output, hidden = lnn(x, timestamps)
    print(f"   Input shape: {x.shape}")
    print(f"   Output shape: {output.shape}")
    print(f"   Hidden shape: {hidden.shape}")
    
    # Test anomaly detector
    print("\n2. Testing LNN Anomaly Detector...")
    detector = create_lnn_model(input_size, model_type='anomaly_detector', hidden_size=32)
    reconstruction, anomaly_scores, latent = detector(x, timestamps)
    print(f"   Reconstruction shape: {reconstruction.shape}")
    print(f"   Anomaly scores shape: {anomaly_scores.shape}")
    print(f"   Latent shape: {latent.shape}")
    
    # Test anomaly detection
    print("\n3. Testing anomaly detection...")
    is_anomaly, scores = detector.detect_anomalies(x, timestamps, threshold=0.5)
    print(f"   Detected anomalies: {is_anomaly.sum().item()} / {is_anomaly.numel()}")
    print(f"   Mean anomaly score: {scores.mean().item():.4f}")
    
    print("\n✅ All tests passed!")
