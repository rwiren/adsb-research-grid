#!/usr/bin/env python3
"""
==============================================================================
EXTENDED LSTM (xLSTM) FOR ADS-B TRAJECTORY PREDICTION
==============================================================================
Purpose: Extended LSTM with exponential gating and enhanced memory
         for long-range trajectory forecasting and anomaly detection

Based on: "xLSTM: Extended Long Short-Term Memory" (Beck et al., 2024)
          - Exponential gating for better gradient flow
          - Memory mixing for enhanced context retention
          - Scalar and matrix memory variants

Use Case: Predict aircraft trajectories, detect trajectory anomalies,
          forecast signal patterns with long-term dependencies

Author: ADS-B Research Grid Project
License: MIT
==============================================================================
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Optional, Tuple


class sLSTMCell(nn.Module):
    """
    Scalar LSTM (sLSTM) Cell with exponential gating
    
    Key improvements over standard LSTM:
    - Exponential gating for better gradient flow
    - Normalizer state to prevent activation explosion
    - Enhanced memory retention for long sequences
    """
    
    def __init__(self, input_size, hidden_size):
        super(sLSTMCell, self).__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        
        # Input transformations
        self.W_i = nn.Linear(input_size, hidden_size)  # Input gate
        self.W_f = nn.Linear(input_size, hidden_size)  # Forget gate
        self.W_o = nn.Linear(input_size, hidden_size)  # Output gate
        self.W_z = nn.Linear(input_size, hidden_size)  # Cell input
        
        # Recurrent transformations
        self.U_i = nn.Linear(hidden_size, hidden_size, bias=False)
        self.U_f = nn.Linear(hidden_size, hidden_size, bias=False)
        self.U_o = nn.Linear(hidden_size, hidden_size, bias=False)
        self.U_z = nn.Linear(hidden_size, hidden_size, bias=False)
        
    def forward(self, x, h_prev, c_prev, n_prev):
        """
        Forward pass through sLSTM cell
        
        Args:
            x: Input (batch_size, input_size)
            h_prev: Previous hidden state (batch_size, hidden_size)
            c_prev: Previous cell state (batch_size, hidden_size)
            n_prev: Previous normalizer state (batch_size, hidden_size)
            
        Returns:
            h: New hidden state
            c: New cell state
            n: New normalizer state
        """
        # Compute gates with exponential gating
        i = torch.exp(self.W_i(x) + self.U_i(h_prev))  # Input gate (exponential)
        f = torch.exp(self.W_f(x) + self.U_f(h_prev))  # Forget gate (exponential)
        o = torch.sigmoid(self.W_o(x) + self.U_o(h_prev))  # Output gate
        
        # Cell input
        z = torch.tanh(self.W_z(x) + self.U_z(h_prev))
        
        # Update cell state (stabilized with normalizer)
        c = f * c_prev + i * z
        n = f * n_prev + i
        
        # Compute hidden state (normalized)
        h = o * (c / (n + 1e-6))
        
        return h, c, n


class mLSTMCell(nn.Module):
    """
    Matrix LSTM (mLSTM) Cell with covariance update
    
    Uses matrix-valued memory for richer state representation
    and better context mixing across time steps.
    """
    
    def __init__(self, input_size, hidden_size):
        super(mLSTMCell, self).__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        
        # Query, Key, Value projections
        self.W_q = nn.Linear(input_size, hidden_size)
        self.W_k = nn.Linear(input_size, hidden_size)
        self.W_v = nn.Linear(input_size, hidden_size)
        
        # Input and forget gates
        self.W_i = nn.Linear(input_size, hidden_size)
        self.W_f = nn.Linear(input_size, hidden_size)
        self.W_o = nn.Linear(input_size, hidden_size)
        
        # Recurrent connections
        self.U_i = nn.Linear(hidden_size, hidden_size, bias=False)
        self.U_f = nn.Linear(hidden_size, hidden_size, bias=False)
        self.U_o = nn.Linear(hidden_size, hidden_size, bias=False)
        
    def forward(self, x, h_prev, C_prev, n_prev):
        """
        Forward pass through mLSTM cell
        
        Args:
            x: Input (batch_size, input_size)
            h_prev: Previous hidden state (batch_size, hidden_size)
            C_prev: Previous memory matrix (batch_size, hidden_size, hidden_size)
            n_prev: Previous normalizer (batch_size, hidden_size)
            
        Returns:
            h: New hidden state
            C: New memory matrix
            n: New normalizer
        """
        batch_size = x.shape[0]
        
        # Compute query, key, value
        q = self.W_q(x)  # (batch_size, hidden_size)
        k = self.W_k(x)  # (batch_size, hidden_size)
        v = self.W_v(x)  # (batch_size, hidden_size)
        
        # Compute gates
        i = torch.exp(self.W_i(x) + self.U_i(h_prev))  # (batch_size, hidden_size)
        f = torch.exp(self.W_f(x) + self.U_f(h_prev))  # (batch_size, hidden_size)
        o = torch.sigmoid(self.W_o(x) + self.U_o(h_prev))
        
        # Update memory matrix (covariance-like update)
        # C_new = f * C_prev + i * (v @ k.T)
        k_expanded = k.unsqueeze(-1)  # (batch_size, hidden_size, 1)
        v_expanded = v.unsqueeze(1)    # (batch_size, 1, hidden_size)
        outer_prod = v_expanded * k_expanded.transpose(1, 2)  # (batch_size, hidden_size, hidden_size)
        
        f_expanded = f.unsqueeze(-1).unsqueeze(-1)  # (batch_size, hidden_size, 1, 1)
        i_expanded = i.unsqueeze(-1)  # (batch_size, hidden_size, 1)
        
        C = f.unsqueeze(-1) * C_prev + i.unsqueeze(-1) * outer_prod
        
        # Update normalizer
        n = f * n_prev + i * k
        
        # Retrieve from memory: h = o * (C @ q) / n
        # C @ q: (batch_size, hidden_size, hidden_size) @ (batch_size, hidden_size)
        memory_retrieval = torch.bmm(C, q.unsqueeze(-1)).squeeze(-1)  # (batch_size, hidden_size)
        h = o * (memory_retrieval / (n + 1e-6))
        
        return h, C, n


class xLSTMBlock(nn.Module):
    """
    xLSTM Block combining sLSTM and mLSTM with residual connections
    """
    
    def __init__(self, input_size, hidden_size, use_mlstm=True):
        super(xLSTMBlock, self).__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.use_mlstm = use_mlstm
        
        # Pre-LayerNorm
        self.ln1 = nn.LayerNorm(input_size)
        
        # Choose cell type
        if use_mlstm:
            self.cell = mLSTMCell(input_size, hidden_size)
        else:
            self.cell = sLSTMCell(input_size, hidden_size)
        
        # Post-projection
        self.proj = nn.Linear(hidden_size, input_size)
        
        # Post-LayerNorm
        self.ln2 = nn.LayerNorm(input_size)
        
    def forward(self, x, state):
        """
        Forward pass through xLSTM block
        
        Args:
            x: Input (batch_size, input_size)
            state: Tuple of (h, c_or_C, n)
            
        Returns:
            output: Block output
            new_state: Updated state
        """
        # Pre-norm
        x_norm = self.ln1(x)
        
        # Apply cell
        h, c_or_C, n = self.cell(x_norm, *state)
        
        # Project back to input dimension
        out = self.proj(h)
        
        # Residual connection
        out = x + out
        
        # Post-norm
        out = self.ln2(out)
        
        return out, (h, c_or_C, n)


class xLSTM(nn.Module):
    """
    Extended LSTM Network for sequence modeling
    
    Stacks multiple xLSTM blocks with alternating sLSTM and mLSTM cells
    for enhanced memory and gradient flow.
    """
    
    def __init__(self, input_size, hidden_size, output_size, 
                 num_layers=2, dropout=0.1, use_mlstm_layers=None):
        super(xLSTM, self).__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        self.num_layers = num_layers
        
        # Determine which layers use mLSTM
        if use_mlstm_layers is None:
            # Alternate: even layers use mLSTM, odd use sLSTM
            use_mlstm_layers = [i % 2 == 0 for i in range(num_layers)]
        
        # Create blocks
        self.blocks = nn.ModuleList()
        for i in range(num_layers):
            self.blocks.append(
                xLSTMBlock(input_size, hidden_size, use_mlstm=use_mlstm_layers[i])
            )
        
        # Dropout
        self.dropout = nn.Dropout(dropout)
        
        # Output layer
        self.output_layer = nn.Linear(input_size, output_size)
        
    def init_states(self, batch_size, device):
        """Initialize hidden states for all blocks"""
        states = []
        for block in self.blocks:
            h = torch.zeros(batch_size, self.hidden_size, device=device)
            n = torch.ones(batch_size, self.hidden_size, device=device)
            
            if block.use_mlstm:
                # Matrix memory
                C = torch.zeros(batch_size, self.hidden_size, self.hidden_size, device=device)
                states.append((h, C, n))
            else:
                # Scalar memory
                c = torch.zeros(batch_size, self.hidden_size, device=device)
                states.append((h, c, n))
        
        return states
    
    def forward(self, x, states=None):
        """
        Forward pass through xLSTM
        
        Args:
            x: Input (batch_size, seq_len, input_size)
            states: Initial states (if None, initialized to zeros)
            
        Returns:
            outputs: Predictions (batch_size, seq_len, output_size)
            final_states: Final hidden states
        """
        batch_size, seq_len, _ = x.shape
        device = x.device
        
        # Initialize states if not provided
        if states is None:
            states = self.init_states(batch_size, device)
        
        outputs = []
        
        # Process sequence
        for t in range(seq_len):
            x_t = x[:, t, :]
            
            # Pass through all blocks
            new_states = []
            for i, block in enumerate(self.blocks):
                x_t, state = block(x_t, states[i])
                new_states.append(state)
                
                # Apply dropout between layers
                if i < len(self.blocks) - 1:
                    x_t = self.dropout(x_t)
            
            states = new_states
            
            # Compute output
            out = self.output_layer(x_t)
            outputs.append(out)
        
        # Stack outputs
        outputs = torch.stack(outputs, dim=1)
        
        return outputs, states


class xLSTMTrajectoryPredictor(nn.Module):
    """
    Trajectory prediction model using xLSTM
    
    Predicts future aircraft positions, altitudes, and speeds
    from historical trajectory data.
    """
    
    def __init__(self, input_size, hidden_size=64, num_layers=2, 
                 predict_steps=10, dropout=0.1):
        super(xLSTMTrajectoryPredictor, self).__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.predict_steps = predict_steps
        
        # xLSTM encoder
        self.xlstm = xLSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            output_size=input_size,
            num_layers=num_layers,
            dropout=dropout
        )
        
        # Prediction head
        self.predictor = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, input_size)
        )
        
    def forward(self, x, predict_future=False):
        """
        Forward pass
        
        Args:
            x: Input sequence (batch_size, seq_len, input_size)
            predict_future: If True, predict next steps autoregressively
            
        Returns:
            predictions: Next-step predictions or future trajectory
        """
        # Encode sequence
        encoded, states = self.xlstm(x)
        
        if not predict_future:
            # Next-step prediction
            predictions = self.predictor(encoded)
            return predictions
        else:
            # Autoregressive future prediction
            batch_size = x.shape[0]
            device = x.device
            
            predictions = []
            last_output = encoded[:, -1, :]  # Start from last encoded state
            
            for _ in range(self.predict_steps):
                # Predict next step
                next_pred = self.predictor(last_output)
                predictions.append(next_pred)
                
                # Use prediction as input for next step
                next_input = next_pred.unsqueeze(1)
                last_output, states = self.xlstm(next_input, states)
                last_output = last_output.squeeze(1)
            
            predictions = torch.stack(predictions, dim=1)
            return predictions


def create_xlstm_model(input_size, model_type='trajectory_predictor', **kwargs):
    """
    Factory function to create xLSTM models
    
    Args:
        input_size: Number of input features
        model_type: Type of model ('trajectory_predictor', 'basic_xlstm')
        **kwargs: Additional model parameters
        
    Returns:
        model: Instantiated xLSTM model
    """
    if model_type == 'trajectory_predictor':
        model = xLSTMTrajectoryPredictor(
            input_size=input_size,
            hidden_size=kwargs.get('hidden_size', 64),
            num_layers=kwargs.get('num_layers', 2),
            predict_steps=kwargs.get('predict_steps', 10),
            dropout=kwargs.get('dropout', 0.1)
        )
    elif model_type == 'basic_xlstm':
        model = xLSTM(
            input_size=input_size,
            hidden_size=kwargs.get('hidden_size', 64),
            output_size=kwargs.get('output_size', input_size),
            num_layers=kwargs.get('num_layers', 2),
            dropout=kwargs.get('dropout', 0.1)
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")
    
    return model


if __name__ == "__main__":
    # Test the xLSTM implementation
    print("Testing xLSTM implementation...")
    
    # Parameters
    batch_size = 4
    seq_len = 20
    input_size = 6
    
    # Create dummy data
    x = torch.randn(batch_size, seq_len, input_size)
    
    # Test basic xLSTM
    print("\n1. Testing basic xLSTM...")
    xlstm = create_xlstm_model(input_size, model_type='basic_xlstm', 
                               hidden_size=32, num_layers=2)
    output, states = xlstm(x)
    print(f"   Input shape: {x.shape}")
    print(f"   Output shape: {output.shape}")
    print(f"   Number of states: {len(states)}")
    
    # Test trajectory predictor
    print("\n2. Testing xLSTM Trajectory Predictor...")
    predictor = create_xlstm_model(input_size, model_type='trajectory_predictor',
                                   hidden_size=32, predict_steps=5)
    
    # Next-step prediction
    next_step = predictor(x, predict_future=False)
    print(f"   Next-step prediction shape: {next_step.shape}")
    
    # Future prediction
    future = predictor(x, predict_future=True)
    print(f"   Future prediction shape: {future.shape}")
    
    print("\n✅ All tests passed!")
