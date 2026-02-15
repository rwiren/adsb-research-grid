"""
Random Forest and XGBoost Models for ADS-B Spoofing Detection

Traditional tree-based models that provide explainable baseline detection.
These models serve as Tier 1 "sanity check" filters based on physical
feature extraction (RSSI vs Distance consistency, velocity profiles).

Features:
- Fast inference (suitable for Raspberry Pi edge)
- Explainable predictions (feature importances)
- No GPU required
- Treelite compilation for optimized edge deployment

References:
    Breiman (2001). "Random Forests"
    Chen & Guestrin (2016). "XGBoost: A Scalable Tree Boosting System"
"""

import numpy as np
from typing import Dict, Optional, Tuple, List, Any
import warnings

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    warnings.warn("scikit-learn not available. Random Forest will not be functional.")

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    warnings.warn("XGBoost not available. XGBoost model will not be functional.")


class RandomForestDetector:
    """
    Random Forest detector for ADS-B spoofing.
    
    Uses hand-crafted physical features to detect anomalies:
    - RSSI vs Distance consistency (inverse-square law)
    - Velocity profile (acceleration limits)
    - Altitude vs Speed consistency
    - Signal correlation across sensors
    
    Key features:
    - Fast training (< 1 minute on typical dataset)
    - Fast inference (< 1ms per sample)
    - Explainable (feature importances)
    - No GPU required
    
    Attributes:
        model: sklearn RandomForestClassifier
        scaler: StandardScaler for feature normalization
        feature_names: List of feature names for interpretability
        
    Example:
        >>> rf = RandomForestDetector(n_estimators=100)
        >>> rf.fit(X_train, y_train)
        >>> result = rf.predict(X_test)
        >>> print(f"Spoofing probability: {result['probability']}")
    """
    
    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 10,
        min_samples_split: int = 10,
        n_jobs: int = -1,
    ):
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required for RandomForestDetector")
        
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            n_jobs=n_jobs,
            random_state=42,
        )
        
        self.scaler = StandardScaler()
        self.is_fitted = False
        
        # Feature names for interpretability
        self.feature_names = [
            'rssi_distance_ratio',
            'velocity',
            'acceleration',
            'altitude',
            'vertical_rate',
            'heading_change',
            'sensor_correlation',
            'signal_stability',
        ]
    
    def extract_features(self, trajectory: np.ndarray) -> np.ndarray:
        """
        Extract physical features from trajectory data.
        
        Args:
            trajectory: [n_samples, seq_len, raw_features]
                       Raw features: [lat, lon, alt, velocity, heading, rssi, temp, pressure]
            
        Returns:
            Extracted features [n_samples, n_features]
        """
        return _extract_trajectory_features(trajectory)
    
    def fit(self, X: np.ndarray, y: np.ndarray):
        """
        Train the Random Forest detector.
        
        Args:
            X: Training trajectory data [n_samples, seq_len, raw_features]
            y: Labels [n_samples] (0 = normal, 1 = spoofed)
        """
        # Extract features
        X_features = self.extract_features(X)
        
        # Normalize features
        X_scaled = self.scaler.fit_transform(X_features)
        
        # Train model
        self.model.fit(X_scaled, y)
        self.is_fitted = True
        
        return self
    
    def predict(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Predict spoofing probability.
        
        Args:
            X: Trajectory data [n_samples, seq_len, raw_features]
            
        Returns:
            Dictionary with predictions and feature importances
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        
        # Extract and scale features
        X_features = self.extract_features(X)
        X_scaled = self.scaler.transform(X_features)
        
        # Predict
        probabilities = self.model.predict_proba(X_scaled)[:, 1]  # Probability of class 1 (spoofed)
        predictions = (probabilities > 0.5).astype(int)
        
        # Get feature importances
        feature_importance = dict(zip(self.feature_names, self.model.feature_importances_))
        
        return {
            'anomaly_score': probabilities,
            'predictions': predictions,
            'feature_importance': feature_importance,
        }
    
    def __call__(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        """Allow model to be called directly."""
        return self.predict(X)


class XGBoostDetector:
    """
    XGBoost detector for ADS-B spoofing.
    
    High-performance gradient boosting model optimized for edge deployment.
    Can be compiled with Treelite for ultra-fast inference on Raspberry Pi.
    
    Key features:
    - Higher accuracy than Random Forest
    - Treelite compilation for Raspberry Pi
    - Still explainable (SHAP values)
    - Fast inference (< 1ms with Treelite)
    
    Attributes:
        model: XGBoost classifier
        scaler: StandardScaler for feature normalization
        
    Example:
        >>> xgb_model = XGBoostDetector(n_estimators=100)
        >>> xgb_model.fit(X_train, y_train)
        >>> result = xgb_model.predict(X_test)
        >>> print(f"Spoofing probability: {result['probability']}")
    """
    
    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 6,
        learning_rate: float = 0.1,
        subsample: float = 0.8,
    ):
        if not XGBOOST_AVAILABLE:
            raise ImportError("XGBoost is required for XGBoostDetector")
        
        self.model = xgb.XGBClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            subsample=subsample,
            random_state=42,
            eval_metric='logloss',
        )
        
        self.scaler = StandardScaler()
        self.is_fitted = False
        
        # Feature names (same as Random Forest)
        self.feature_names = [
            'rssi_distance_ratio',
            'velocity',
            'acceleration',
            'altitude',
            'vertical_rate',
            'heading_change',
            'sensor_correlation',
            'signal_stability',
        ]
    
    def extract_features(self, trajectory: np.ndarray) -> np.ndarray:
        """
        Extract physical features from trajectory data.
        Uses same feature extraction as Random Forest for consistency.
        """
        return _extract_trajectory_features(trajectory)


def _extract_trajectory_features(trajectory: np.ndarray) -> np.ndarray:
    """
    Shared feature extraction logic for tree-based models.
    
    Args:
        trajectory: [n_samples, seq_len, raw_features]
                   Raw features: [lat, lon, alt, velocity, heading, rssi, temp, pressure]
        
    Returns:
        Extracted features [n_samples, n_features]
    """
    n_samples, seq_len, _ = trajectory.shape
    features = []
    
    for i in range(n_samples):
        traj = trajectory[i]  # [seq_len, raw_features]
        
        # Extract raw features
        lat, lon, alt = traj[:, 0], traj[:, 1], traj[:, 2]
        velocity = traj[:, 3]
        heading = traj[:, 4]
        rssi = traj[:, 5]
        
        # 1. RSSI vs Distance consistency
        # Compute distance traveled
        distances = np.sqrt(
            (lat[1:] - lat[:-1])**2 +
            (lon[1:] - lon[:-1])**2
        )
        distance_total = distances.sum()
        rssi_mean = rssi.mean()
        rssi_distance_ratio = np.abs(rssi_mean) / (distance_total + 1e-6)
        
        # 2. Velocity statistics
        velocity_mean = velocity.mean()
        velocity_std = velocity.std()
        
        # 3. Acceleration (velocity changes)
        velocity_changes = np.abs(velocity[1:] - velocity[:-1])
        acceleration_max = velocity_changes.max()
        
        # 4. Altitude statistics
        altitude_mean = alt.mean()
        altitude_std = alt.std()
        
        # 5. Vertical rate (altitude changes)
        altitude_changes = np.abs(alt[1:] - alt[:-1])
        vertical_rate = altitude_changes.mean()
        
        # 6. Heading changes (turn rate)
        heading_changes = np.abs(heading[1:] - heading[:-1])
        # Handle wraparound (0/360 degrees)
        heading_changes = np.minimum(heading_changes, 360 - heading_changes)
        heading_change_max = heading_changes.max()
        
        # 7. Sensor correlation (RSSI stability)
        rssi_std = rssi.std()
        sensor_correlation = 1.0 / (1.0 + rssi_std)
        
        # 8. Signal stability (overall variance)
        signal_stability = 1.0 / (1.0 + velocity_std + altitude_std)
        
        features.append([
            rssi_distance_ratio,
            velocity_mean,
            acceleration_max,
            altitude_mean,
            vertical_rate,
            heading_change_max,
            sensor_correlation,
            signal_stability,
        ])
    
    return np.array(features)
    
    def fit(self, X: np.ndarray, y: np.ndarray):
        """
        Train the XGBoost detector.
        
        Args:
            X: Training trajectory data [n_samples, seq_len, raw_features]
            y: Labels [n_samples] (0 = normal, 1 = spoofed)
        """
        # Extract features
        X_features = self.extract_features(X)
        
        # Normalize features
        X_scaled = self.scaler.fit_transform(X_features)
        
        # Train model
        self.model.fit(X_scaled, y)
        self.is_fitted = True
        
        return self
    
    def predict(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Predict spoofing probability.
        
        Args:
            X: Trajectory data [n_samples, seq_len, raw_features]
            
        Returns:
            Dictionary with predictions and feature importances
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        
        # Extract and scale features
        X_features = self.extract_features(X)
        X_scaled = self.scaler.transform(X_features)
        
        # Predict
        probabilities = self.model.predict_proba(X_scaled)[:, 1]
        predictions = (probabilities > 0.5).astype(int)
        
        # Get feature importances
        feature_importance = dict(zip(self.feature_names, self.model.feature_importances_))
        
        return {
            'anomaly_score': probabilities,
            'predictions': predictions,
            'feature_importance': feature_importance,
        }
    
    def export_treelite(self, output_path: str):
        """
        Export model to Treelite format for optimized edge deployment.
        
        Args:
            output_path: Path to save Treelite model (.so or .dll)
        """
        try:
            import treelite
            import treelite.sklearn
        except ImportError:
            warnings.warn("Treelite not available. Cannot export model.")
            return
        
        # Convert to Treelite model
        tl_model = treelite.sklearn.import_model(self.model)
        
        # Compile to shared library
        tl_model.export_lib(
            toolchain='gcc',
            libpath=output_path,
            params={'parallel_comp': 4}
        )
        
        print(f"Model exported to {output_path}")
        print("Use treelite_runtime to load and predict with this model on edge devices.")
    
    def __call__(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        """Allow model to be called directly."""
        return self.predict(X)


# Unified interface for both models
class TreeBasedEnsemble:
    """
    Ensemble of Random Forest and XGBoost for robust detection.
    
    Combines predictions from both models using weighted voting.
    
    Example:
        >>> ensemble = TreeBasedEnsemble()
        >>> ensemble.fit(X_train, y_train)
        >>> result = ensemble.predict(X_test)
    """
    
    def __init__(
        self,
        rf_weight: float = 0.4,
        xgb_weight: float = 0.6,
    ):
        self.rf_weight = rf_weight
        self.xgb_weight = xgb_weight
        
        if SKLEARN_AVAILABLE:
            self.rf = RandomForestDetector()
        else:
            self.rf = None
            
        if XGBOOST_AVAILABLE:
            self.xgb = XGBoostDetector()
        else:
            self.xgb = None
        
        if self.rf is None and self.xgb is None:
            raise ImportError("Either scikit-learn or XGBoost must be available")
    
    def fit(self, X: np.ndarray, y: np.ndarray):
        """Train both models."""
        if self.rf is not None:
            self.rf.fit(X, y)
        if self.xgb is not None:
            self.xgb.fit(X, y)
        return self
    
    def predict(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        """Ensemble prediction."""
        scores = []
        
        if self.rf is not None:
            rf_result = self.rf.predict(X)
            scores.append(rf_result['anomaly_score'] * self.rf_weight)
        
        if self.xgb is not None:
            xgb_result = self.xgb.predict(X)
            scores.append(xgb_result['anomaly_score'] * self.xgb_weight)
        
        # Combine scores
        ensemble_score = np.sum(scores, axis=0) / (self.rf_weight + self.xgb_weight)
        
        return {
            'anomaly_score': ensemble_score,
            'predictions': (ensemble_score > 0.5).astype(int),
        }
    
    def __call__(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        return self.predict(X)
