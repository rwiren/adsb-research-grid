"""
Multi-Agent Reinforcement Learning (MARL) Coordination Layer

Implements decentralized coordination allowing sensor nodes to cooperatively
optimize grid-wide coverage and detection accuracy.

Each sensor is an agent that:
1. Observes local signals and neighbors' states
2. Takes actions (adjust gain, threshold, detection parameters)
3. Receives rewards based on detection accuracy and coverage
4. Coordinates with other agents to maximize global objective

References:
    Lowe et al. (2017). "Multi-Agent Actor-Critic for Mixed Cooperative-Competitive Environments"
"""

import numpy as np
from typing import Dict, Optional, Tuple, List, Any
import warnings

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    nn = None
    warnings.warn("PyTorch not available. MARL will not be functional.")


class SensorAgent(nn.Module):
    """
    Individual sensor agent for the MARL system.
    
    Each sensor has:
    - Actor network: Chooses actions (sensor parameters)
    - Critic network: Evaluates state-action values
    - Communication module: Shares information with neighbors
    
    Args:
        state_dim: Dimension of agent's observation space
        action_dim: Dimension of agent's action space
        hidden_dim: Hidden layer dimension
        num_neighbors: Maximum number of neighboring agents
    """
    
    def __init__(
        self,
        state_dim: int = 16,
        action_dim: int = 4,
        hidden_dim: int = 128,
        num_neighbors: int = 4,
    ):
        super().__init__()
        
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.num_neighbors = num_neighbors
        
        # Communication encoder (share state with neighbors)
        self.comm_encoder = nn.Sequential(
            nn.Linear(state_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 32),
        )
        
        # Actor network (policy)
        # Input: own state + neighbor communications
        actor_input_dim = state_dim + num_neighbors * 32
        self.actor = nn.Sequential(
            nn.Linear(actor_input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, action_dim),
            nn.Tanh(),  # Actions in [-1, 1]
        )
        
        # Critic network (value function)
        # Input: own state + own action + neighbor states & actions
        critic_input_dim = state_dim + action_dim + num_neighbors * (32 + action_dim)
        self.critic = nn.Sequential(
            nn.Linear(critic_input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )
        
    def encode_communication(self, state: torch.Tensor) -> torch.Tensor:
        """
        Encode state for communication with neighbors.
        
        Args:
            state: Agent's state [batch, state_dim]
            
        Returns:
            Encoded message [batch, 32]
        """
        return self.comm_encoder(state)
    
    def act(
        self,
        state: torch.Tensor,
        neighbor_messages: torch.Tensor,
        deterministic: bool = False,
    ) -> torch.Tensor:
        """
        Choose action based on current state and neighbor communications.
        
        Args:
            state: Agent's state [batch, state_dim]
            neighbor_messages: Messages from neighbors [batch, num_neighbors, 32]
            deterministic: If True, use deterministic policy (no exploration)
            
        Returns:
            Action [batch, action_dim]
        """
        batch_size = state.shape[0]
        
        # Flatten neighbor messages
        neighbor_messages_flat = neighbor_messages.reshape(batch_size, -1)
        
        # Concatenate state and neighbor communications
        actor_input = torch.cat([state, neighbor_messages_flat], dim=-1)
        
        # Get action from policy
        action = self.actor(actor_input)
        
        # Add exploration noise if not deterministic
        if not deterministic:
            noise = torch.randn_like(action) * 0.1
            action = action + noise
            action = torch.clamp(action, -1.0, 1.0)
        
        return action
    
    def evaluate(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
        neighbor_messages: torch.Tensor,
        neighbor_actions: torch.Tensor,
    ) -> torch.Tensor:
        """
        Evaluate state-action value.
        
        Args:
            state: Agent's state [batch, state_dim]
            action: Agent's action [batch, action_dim]
            neighbor_messages: Messages from neighbors [batch, num_neighbors, 32]
            neighbor_actions: Actions from neighbors [batch, num_neighbors, action_dim]
            
        Returns:
            Q-value [batch, 1]
        """
        batch_size = state.shape[0]
        
        # Flatten neighbor information
        neighbor_messages_flat = neighbor_messages.reshape(batch_size, -1)
        neighbor_actions_flat = neighbor_actions.reshape(batch_size, -1)
        
        # Concatenate all information
        critic_input = torch.cat([
            state,
            action,
            neighbor_messages_flat,
            neighbor_actions_flat,
        ], dim=-1)
        
        # Evaluate Q-value
        q_value = self.critic(critic_input)
        
        return q_value


class MARLCoordination(nn.Module):
    """
    Multi-Agent Reinforcement Learning Coordination System.
    
    Manages multiple sensor agents that cooperatively optimize grid-wide
    detection performance. Agents learn to:
    1. Adjust sensor parameters (gain, threshold)
    2. Coordinate coverage patterns
    3. Share detection decisions
    4. Adapt to changing conditions
    
    State space (per agent):
    - Local signal strength (RSSI)
    - Detection confidence
    - Coverage area
    - Neighbor states
    - Recent detection history
    
    Action space (per agent):
    - Gain adjustment [-1, 1]
    - Threshold adjustment [-1, 1]
    - Coverage weight [-1, 1]
    - Detection sensitivity [-1, 1]
    
    Key features:
    - Decentralized execution (each agent acts independently)
    - Centralized training (learns from global reward)
    - Communication between neighboring sensors
    - Adaptive to network changes
    
    Attributes:
        num_agents: Number of sensor agents in grid
        agents: List of SensorAgent instances
        
    Example:
        >>> marl = MARLCoordination(num_agents=4, state_dim=16, action_dim=4)
        >>> states = torch.randn(1, 4, 16)  # [batch, num_agents, state_dim]
        >>> actions, messages = marl.get_actions(states)
        >>> print(f"Agent 0 action: {actions[0, 0]}")
    """
    
    def __init__(
        self,
        num_agents: int = 4,
        state_dim: int = 16,
        action_dim: int = 4,
        hidden_dim: int = 128,
        adjacency_matrix: Optional[torch.Tensor] = None,
    ):
        super().__init__()
        
        self.num_agents = num_agents
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # Create agents
        self.agents = nn.ModuleList([
            SensorAgent(
                state_dim=state_dim,
                action_dim=action_dim,
                hidden_dim=hidden_dim,
                num_neighbors=num_agents - 1,  # Can communicate with all others
            )
            for _ in range(num_agents)
        ])
        
        # Adjacency matrix defines which agents can communicate
        # Default: fully connected
        if adjacency_matrix is None:
            adjacency_matrix = torch.ones(num_agents, num_agents) - torch.eye(num_agents)
        self.register_buffer('adjacency_matrix', adjacency_matrix)
        
    def get_actions(
        self,
        states: torch.Tensor,
        deterministic: bool = False,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Get actions for all agents based on their states.
        
        Args:
            states: States for all agents [batch, num_agents, state_dim]
            deterministic: If True, use deterministic policy
            
        Returns:
            (actions, messages)
            - actions: [batch, num_agents, action_dim]
            - messages: [batch, num_agents, 32] encoded communications
        """
        batch_size = states.shape[0]
        
        # Encode communications from all agents
        messages = torch.stack([
            self.agents[i].encode_communication(states[:, i])
            for i in range(self.num_agents)
        ], dim=1)  # [batch, num_agents, 32]
        
        # Get neighbor messages for each agent based on adjacency
        actions = []
        for i in range(self.num_agents):
            # Get messages from neighbors (based on adjacency matrix)
            neighbor_mask = self.adjacency_matrix[i]  # [num_agents]
            neighbor_messages = messages * neighbor_mask.view(1, -1, 1)
            
            # Get action
            action = self.agents[i].act(
                states[:, i],
                neighbor_messages,
                deterministic=deterministic,
            )
            actions.append(action)
        
        actions = torch.stack(actions, dim=1)  # [batch, num_agents, action_dim]
        
        return actions, messages
    
    def compute_values(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        messages: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute Q-values for all agents.
        
        Args:
            states: States for all agents [batch, num_agents, state_dim]
            actions: Actions for all agents [batch, num_agents, action_dim]
            messages: Messages from all agents [batch, num_agents, 32]
            
        Returns:
            Q-values [batch, num_agents, 1]
        """
        values = []
        for i in range(self.num_agents):
            # Get neighbor information
            neighbor_mask = self.adjacency_matrix[i]
            neighbor_messages = messages * neighbor_mask.view(1, -1, 1)
            neighbor_actions = actions * neighbor_mask.view(1, -1, 1)
            
            # Evaluate
            value = self.agents[i].evaluate(
                states[:, i],
                actions[:, i],
                neighbor_messages,
                neighbor_actions,
            )
            values.append(value)
        
        values = torch.stack(values, dim=1)  # [batch, num_agents, 1]
        
        return values
    
    def forward(
        self,
        states: torch.Tensor,
        deterministic: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass for inference.
        
        Args:
            states: States for all agents [batch, num_agents, state_dim]
            deterministic: If True, use deterministic policy
            
        Returns:
            Dictionary with actions, messages, and coordination score
        """
        actions, messages = self.get_actions(states, deterministic=deterministic)
        
        # Compute coordination score (how well agents coordinate)
        # Measured as variance in detection decisions (lower is better)
        action_variance = actions.var(dim=1).mean(dim=-1)  # [batch]
        coordination_score = 1.0 / (1.0 + action_variance)
        
        return {
            'actions': actions,
            'messages': messages,
            'coordination_score': coordination_score,
            'anomaly_score': coordination_score,  # For ensemble integration
        }


# NumPy fallback
class MARLCoordinationNumPy:
    """
    Simplified NumPy implementation of MARL for CPU-only environments.
    """
    
    def __init__(self, num_agents: int = 4, state_dim: int = 16, action_dim: int = 4):
        self.num_agents = num_agents
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # Simple policy weights
        self.policies = [
            np.random.randn(state_dim, action_dim) * 0.01
            for _ in range(num_agents)
        ]
        
    def __call__(self, states: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Get actions for all agents.
        
        Args:
            states: States for all agents [batch, num_agents, state_dim]
            
        Returns:
            Dictionary with actions and coordination score
        """
        batch_size = states.shape[0]
        
        # Simple feedforward policy
        actions = np.zeros((batch_size, self.num_agents, self.action_dim))
        for i in range(self.num_agents):
            actions[:, i] = np.tanh(np.dot(states[:, i], self.policies[i]))
        
        # Coordination score
        action_variance = actions.var(axis=1).mean(axis=-1)
        coordination_score = 1.0 / (1.0 + action_variance)
        
        return {
            'actions': actions,
            'coordination_score': coordination_score,
            'anomaly_score': coordination_score,
        }
