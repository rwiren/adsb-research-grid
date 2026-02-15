"""
DeepSeek MCHC (Manifold-Constrained Hyper-Connection)

Graph Neural Network architecture for topology-based anomaly detection in ADS-B data.
Detects violations in aircraft formation topology constrained by manifold logic.

This module requires PyTorch and PyTorch Geometric. It's designed to run on:
- Raspberry Pi 5 CPU (inference)
- Hailo-8 NPU (optimized inference via ONNX export)
- M4 Max MacBook Pro (training)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch import Tensor
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    # Create dummy classes for type hints when torch is not available
    class nn:
        class Module:
            pass
    Tensor = Any


class DeepSeekMCHC(nn.Module if TORCH_AVAILABLE else object):
    """
    DeepSeek MCHC: Manifold-Constrained Hyper-Connection Network.
    
    This Graph Neural Network architecture operates on aircraft trajectories
    modeled as dynamic spatial graphs. Connections are constrained by the
    manifold logic validated through Sinkhorn-Knopp projections.
    
    Key Features:
    - Detects "ghost aircraft" formations (hyper-connection violations)
    - Incorporates geometric constraints from optimal transport
    - Lightweight architecture suitable for edge deployment
    
    Architecture:
    1. Node Embedding Layer: Encodes aircraft state (position, velocity, etc.)
    2. Manifold-Constrained GNN Layers: Message passing with transport-weighted edges
    3. Hyper-Connection Detection: Identifies topologically impossible formations
    4. Output Layer: Binary classification (normal vs. spoofed)
    
    Attributes:
        input_dim: Dimension of input node features (e.g., [lat, lon, alt, velocity, heading]).
        hidden_dim: Dimension of hidden GNN layers.
        output_dim: Output dimension (1 for binary classification).
        num_layers: Number of GNN message-passing layers.
        manifold_weight: Weight for manifold constraint in message passing.
        
    Example:
        >>> model = DeepSeekMCHC(input_dim=8, hidden_dim=64, num_layers=3)
        >>> # Features: [batch_size, num_aircraft, feature_dim]
        >>> node_features = torch.randn(1, 10, 8)
        >>> # Edge index: [2, num_edges] connectivity
        >>> edge_index = torch.tensor([[0,1,2], [1,2,3]])
        >>> # Transport costs from Sinkhorn
        >>> manifold_constraints = torch.randn(1, 10, 10)
        >>> output = model(node_features, edge_index, manifold_constraints)
    """
    
    def __init__(
        self,
        input_dim: int = 8,
        hidden_dim: int = 64,
        output_dim: int = 1,
        num_layers: int = 3,
        manifold_weight: float = 0.5,
        dropout: float = 0.1,
    ):
        """
        Initialize DeepSeek MCHC model.
        
        Args:
            input_dim: Dimension of input features per aircraft node.
            hidden_dim: Hidden dimension for GNN layers.
            output_dim: Output dimension (1 for binary classification).
            num_layers: Number of message-passing layers.
            manifold_weight: Weight [0,1] for manifold constraint in aggregation.
            dropout: Dropout rate for regularization.
        """
        if not TORCH_AVAILABLE:
            raise ImportError(
                "PyTorch is required for DeepSeekMCHC. "
                "Install with: pip install torch torch-geometric"
            )
            
        super(DeepSeekMCHC, self).__init__()
        
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        self.num_layers = num_layers
        self.manifold_weight = manifold_weight
        self.dropout = dropout
        
        # Node embedding layer
        self.embedding = nn.Linear(input_dim, hidden_dim)
        
        # GNN layers (simple message passing without torch_geometric dependency)
        self.gnn_layers = nn.ModuleList([
            nn.Linear(hidden_dim, hidden_dim) for _ in range(num_layers)
        ])
        
        # Manifold constraint layer
        self.manifold_projection = nn.Linear(hidden_dim, hidden_dim)
        
        # Projection layers for integrating LNN and xLSTM hidden states
        # These handle variable input dimensions by projecting concatenated features
        self.lnn_projection = None  # Created dynamically if lnn_hidden provided
        self.xlstm_projection = None  # Created dynamically if xlstm_hidden provided
        
        # Hyper-connection detection layers
        self.hyperconnection_detector = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, hidden_dim // 4),
            nn.ReLU(),
        )
        
        # Output layer for classification
        self.output_layer = nn.Linear(hidden_dim // 4, output_dim)
        
        # Batch normalization layers
        self.batch_norms = nn.ModuleList([
            nn.BatchNorm1d(hidden_dim) for _ in range(num_layers)
        ])
        
    def forward(
        self,
        node_features: Tensor,
        edge_index: Optional[Tensor] = None,
        manifold_constraints: Optional[Tensor] = None,
        lnn_hidden: Optional[Tensor] = None,
        xlstm_hidden: Optional[Tensor] = None,
    ) -> Dict[str, Tensor]:
        """
        Forward pass through the MCHC network.
        
        Args:
            node_features: [batch_size, num_nodes, input_dim] aircraft state features.
            edge_index: [2, num_edges] edge connectivity (optional). If None, fully connected.
            manifold_constraints: [batch_size, num_nodes, num_nodes] transport cost matrix
                                 from Sinkhorn-Knopp (optional).
            lnn_hidden: [batch_size, lnn_hidden_dim] hidden state from LNN (optional).
            xlstm_hidden: [batch_size, xlstm_hidden_dim] hidden state from xLSTM (optional).
            
        Returns:
            Dictionary containing:
                - 'logits': [batch_size, output_dim] classification logits
                - 'probabilities': [batch_size, output_dim] sigmoid probabilities
                - 'node_embeddings': [batch_size, num_nodes, hidden_dim] learned node representations
                - 'topology_score': [batch_size] hyper-connection violation score
        """
        batch_size, num_nodes, _ = node_features.shape
        
        # 1. Node Embedding
        x = self.embedding(node_features)  # [batch_size, num_nodes, hidden_dim]
        x = F.relu(x)
        
        # 2. GNN Message Passing with Manifold Constraints
        for layer_idx, (gnn_layer, bn) in enumerate(zip(self.gnn_layers, self.batch_norms)):
            # Simple aggregation: mean pooling over neighbors
            # For full deployment, use torch_geometric for efficient graph ops
            
            # Create adjacency matrix if edge_index not provided (fully connected)
            if edge_index is None:
                # Fully connected graph
                adjacency = torch.ones(num_nodes, num_nodes, device=x.device)
                adjacency = adjacency - torch.eye(num_nodes, device=x.device)
            else:
                # Build adjacency from edge_index
                adjacency = torch.zeros(num_nodes, num_nodes, device=x.device)
                adjacency[edge_index[0], edge_index[1]] = 1.0
                
            # Apply manifold constraints to edge weights
            if manifold_constraints is not None:
                # Use transport plan to weight edges
                # Lower transport cost = stronger connection
                manifold_weights = torch.exp(-manifold_constraints[0])
                adjacency = (1 - self.manifold_weight) * adjacency + \
                           self.manifold_weight * manifold_weights
            
            # Normalize adjacency
            degree = adjacency.sum(dim=1, keepdim=True) + 1e-10
            adjacency_norm = adjacency / degree
            
            # Message passing: aggregate neighbor features
            x_aggregated = torch.bmm(
                adjacency_norm.unsqueeze(0).expand(batch_size, -1, -1),
                x
            )
            
            # Update node features
            x = gnn_layer(x_aggregated)
            
            # Reshape for batch norm: [batch_size * num_nodes, hidden_dim]
            x_flat = x.reshape(-1, self.hidden_dim)
            x_flat = bn(x_flat)
            x = x_flat.reshape(batch_size, num_nodes, self.hidden_dim)
            
            x = F.relu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)
            
        # 3. Manifold Projection (topology validation)
        x_manifold = self.manifold_projection(x)
        x = x + x_manifold  # Residual connection
        
        # 4. Global Pooling (graph-level representation)
        x_global = torch.mean(x, dim=1)  # [batch_size, hidden_dim]
        
        # 5. Integrate LNN and xLSTM hidden states if provided
        if lnn_hidden is not None:
            # Create projection layer on first use if not already created
            if self.lnn_projection is None:
                combined_dim = self.hidden_dim + lnn_hidden.shape[-1]
                self.lnn_projection = nn.Linear(combined_dim, self.hidden_dim).to(x_global.device)
            x_global = torch.cat([x_global, lnn_hidden], dim=-1)
            x_global = self.lnn_projection(x_global)
            
        if xlstm_hidden is not None:
            # Create projection layer on first use if not already created
            if self.xlstm_projection is None:
                combined_dim = self.hidden_dim + xlstm_hidden.shape[-1]
                self.xlstm_projection = nn.Linear(combined_dim, self.hidden_dim).to(x_global.device)
            x_global = torch.cat([x_global, xlstm_hidden], dim=-1)
            x_global = self.xlstm_projection(x_global)
        
        # 6. Hyper-connection Detection
        topology_features = self.hyperconnection_detector(x_global)
        
        # Compute topology violation score
        topology_score = torch.norm(topology_features, p=2, dim=-1)
        
        # 7. Classification
        logits = self.output_layer(topology_features)
        probabilities = torch.sigmoid(logits)
        
        return {
            'logits': logits,
            'probabilities': probabilities,
            'node_embeddings': x,
            'topology_score': topology_score,
        }
    
    def export_to_onnx(self, output_path: str, batch_size: int = 1, num_nodes: int = 10):
        """
        Export model to ONNX format for Hailo-8 NPU deployment.
        
        Args:
            output_path: Path to save ONNX model.
            batch_size: Batch size for export.
            num_nodes: Number of aircraft nodes in the graph.
        """
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required for ONNX export")
            
        dummy_features = torch.randn(batch_size, num_nodes, self.input_dim)
        dummy_manifold = torch.randn(batch_size, num_nodes, num_nodes)
        
        torch.onnx.export(
            self,
            (dummy_features, None, dummy_manifold, None, None),
            output_path,
            input_names=['node_features', 'manifold_constraints'],
            output_names=['logits', 'probabilities'],
            dynamic_axes={
                'node_features': {0: 'batch_size', 1: 'num_nodes'},
                'manifold_constraints': {0: 'batch_size', 1: 'num_nodes', 2: 'num_nodes'},
            },
            opset_version=11,
        )
        print(f"Model exported to {output_path}")
