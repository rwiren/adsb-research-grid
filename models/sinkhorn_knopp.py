"""
Sinkhorn-Knopp Algorithm for Optimal Transport

This module implements the Sinkhorn-Knopp algorithm for projecting cost matrices
onto the Birkhoff Polytope, computing transport costs as anomaly scores for
ADS-B spoofing detection.

References:
    - Cuturi, M. (2013). Sinkhorn Distances: Lightspeed Computation of Optimal Transport.
    - Peyré, G., & Cuturi, M. (2019). Computational Optimal Transport.
"""

import numpy as np
from typing import Tuple, Optional
import warnings


class SinkhornKnoppProjection:
    """
    Sinkhorn-Knopp Algorithm for Optimal Transport on the Birkhoff Polytope.
    
    This class implements the iterative Sinkhorn-Knopp algorithm to compute
    optimal transport plans between observed and predicted aircraft positions.
    The convergence rate and transport cost serve as anomaly indicators.
    
    Attributes:
        epsilon: Regularization parameter (entropy term). Lower = more accurate, slower.
        max_iterations: Maximum number of Sinkhorn iterations.
        convergence_threshold: Stop when row/column marginals converge within this tolerance.
        
    Example:
        >>> # Cost matrix: rows=observed, cols=predicted positions
        >>> cost_matrix = np.random.rand(10, 10)
        >>> sinkhorn = SinkhornKnoppProjection(epsilon=0.1)
        >>> transport_cost, convergence_rate, transport_plan = sinkhorn.project(cost_matrix)
        >>> is_anomaly = transport_cost > threshold
    """
    
    def __init__(
        self,
        epsilon: float = 0.1,
        max_iterations: int = 1000,
        convergence_threshold: float = 1e-6,
    ):
        """
        Initialize the Sinkhorn-Knopp projector.
        
        Args:
            epsilon: Entropy regularization parameter. Smaller values give more 
                     accurate transport but slower convergence. Typical range: [0.01, 1.0]
            max_iterations: Maximum number of iterations before stopping.
            convergence_threshold: Convergence tolerance for marginal constraints.
        """
        self.epsilon = epsilon
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
        
    def project(
        self,
        cost_matrix: np.ndarray,
        source_weights: Optional[np.ndarray] = None,
        target_weights: Optional[np.ndarray] = None,
    ) -> Tuple[float, float, np.ndarray]:
        """
        Project cost matrix onto Birkhoff Polytope using Sinkhorn-Knopp iterations.
        
        Args:
            cost_matrix: (n_observed, n_predicted) cost matrix. Each entry C[i,j] 
                        represents the cost of matching observed position i to 
                        predicted position j (e.g., Euclidean distance).
            source_weights: Optional (n_observed,) distribution over observed positions.
                           Defaults to uniform distribution.
            target_weights: Optional (n_predicted,) distribution over predicted positions.
                           Defaults to uniform distribution.
                           
        Returns:
            transport_cost: Final transport cost (anomaly score). Higher = more anomalous.
            convergence_rate: Rate of convergence (iterations until convergence / max_iterations).
                             Lower = faster convergence, potentially more normal behavior.
            transport_plan: (n_observed, n_predicted) optimal transport plan matrix.
                           Entry [i,j] = probability of matching observed i to predicted j.
                           
        Raises:
            ValueError: If cost_matrix is not 2D or contains invalid values.
        """
        # Input validation
        if cost_matrix.ndim != 2:
            raise ValueError(f"Cost matrix must be 2D, got shape {cost_matrix.shape}")
        
        if np.any(np.isnan(cost_matrix)) or np.any(np.isinf(cost_matrix)):
            raise ValueError("Cost matrix contains NaN or Inf values")
            
        n, m = cost_matrix.shape
        
        # Initialize source and target weights (uniform if not provided)
        if source_weights is None:
            source_weights = np.ones(n) / n
        else:
            source_weights = source_weights / source_weights.sum()
            
        if target_weights is None:
            target_weights = np.ones(m) / m
        else:
            target_weights = target_weights / target_weights.sum()
            
        # Compute the kernel K = exp(-C / epsilon)
        # Use numerically stable computation
        K = np.exp(-cost_matrix / self.epsilon)
        
        # Initialize scaling vectors
        u = np.ones(n)  # Row scaling
        v = np.ones(m)  # Column scaling
        
        # Sinkhorn iterations
        for iteration in range(self.max_iterations):
            u_prev = u.copy()
            
            # Update row scaling: u = source_weights / (K @ v)
            u = source_weights / (K @ v + 1e-10)
            
            # Update column scaling: v = target_weights / (K.T @ u)
            v = target_weights / (K.T @ u + 1e-10)
            
            # Check convergence: has u stabilized?
            if np.max(np.abs(u - u_prev)) < self.convergence_threshold:
                break
                
        else:
            # Max iterations reached without convergence
            warnings.warn(
                f"Sinkhorn algorithm did not converge after {self.max_iterations} iterations",
                RuntimeWarning
            )
        
        # Compute final transport plan: P = diag(u) @ K @ diag(v)
        transport_plan = u[:, np.newaxis] * K * v[np.newaxis, :]
        
        # Compute transport cost: sum of element-wise product C ⊙ P
        transport_cost = np.sum(cost_matrix * transport_plan)
        
        # Convergence rate: normalized iterations (lower = faster/better)
        convergence_rate = (iteration + 1) / self.max_iterations
        
        return transport_cost, convergence_rate, transport_plan
    
    def compute_anomaly_score(
        self,
        cost_matrix: np.ndarray,
        baseline_cost: Optional[float] = None,
    ) -> float:
        """
        Compute a normalized anomaly score from the transport cost.
        
        Args:
            cost_matrix: Cost matrix between observed and predicted positions.
            baseline_cost: Optional baseline cost for normalization. If None,
                          uses the mean of the cost matrix as baseline.
                          
        Returns:
            anomaly_score: Normalized score in [0, 1]. Higher = more anomalous.
                          0.5 = baseline, > 0.7 suggests potential spoofing.
        """
        transport_cost, convergence_rate, _ = self.project(cost_matrix)
        
        if baseline_cost is None:
            baseline_cost = np.mean(cost_matrix)
            
        # Normalize: ratio of actual transport to baseline
        if baseline_cost > 0:
            normalized_cost = transport_cost / (baseline_cost + 1e-10)
        else:
            normalized_cost = 1.0
            
        # Combine transport cost and convergence rate
        # Fast convergence + low cost = normal behavior
        # Slow convergence + high cost = anomalous behavior
        anomaly_score = 0.7 * normalized_cost + 0.3 * convergence_rate
        
        # Clip to [0, 1] for interpretability
        anomaly_score = np.clip(anomaly_score, 0.0, 1.0)
        
        return anomaly_score
