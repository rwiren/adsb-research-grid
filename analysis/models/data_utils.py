#!/usr/bin/env python3
"""
==============================================================================
DATA UTILITIES FOR LNN AND xLSTM TRAINING
==============================================================================
Purpose: Data loading, preprocessing, and batch creation for ADS-B models

Author: ADS-B Research Grid Project
License: MIT
==============================================================================
"""

import pandas as pd
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from typing import Tuple, Optional, List


class ADSBDataset(Dataset):
    """
    PyTorch Dataset for ADS-B time-series data
    
    Handles sequence creation, normalization, and temporal features
    for aircraft trajectory and signal data.
    """
    
    def __init__(self, data_path, sequence_length=20, prediction_horizon=10,
                 features=None, target_features=None, normalize=True,
                 scaler=None, return_timestamps=False):
        """
        Initialize dataset
        
        Args:
            data_path: Path to CSV file or pandas DataFrame
            sequence_length: Number of time steps in input sequence
            prediction_horizon: Number of steps to predict ahead
            features: List of feature columns to use
            target_features: List of target columns (if None, use features)
            normalize: Whether to normalize features
            scaler: Pre-fitted scaler (if None, fit new one)
            return_timestamps: Whether to return actual timestamps
        """
        self.sequence_length = sequence_length
        self.prediction_horizon = prediction_horizon
        self.normalize = normalize
        self.return_timestamps = return_timestamps
        
        # Load data
        if isinstance(data_path, pd.DataFrame):
            self.df = data_path
        else:
            self.df = pd.read_csv(data_path)
            if 'timestamp' in self.df.columns:
                self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        
        # Select features
        if features is None:
            # Default features for ADS-B data
            features = [
                'lat', 'lon', 'alt_baro', 'gs', 'track', 'baro_rate',
                'rssi', 'distance_km', 'signal_deviation',
                'hour_sin', 'hour_cos', 'track_sin', 'track_cos'
            ]
            # Filter to available columns
            features = [f for f in features if f in self.df.columns]
        
        self.features = features
        self.target_features = target_features if target_features else features
        
        # Handle missing values
        self.df[self.features] = self.df[self.features].fillna(method='ffill').fillna(0)
        
        # Normalization
        if normalize:
            if scaler is None:
                self.scaler = StandardScaler()
                self.df[self.features] = self.scaler.fit_transform(self.df[self.features])
            else:
                self.scaler = scaler
                self.df[self.features] = self.scaler.transform(self.df[self.features])
        else:
            self.scaler = None
        
        # Create sequences grouped by aircraft
        self.sequences = self._create_sequences()
        
    def _create_sequences(self):
        """Create sequences from data, grouped by aircraft"""
        sequences = []
        
        # Group by aircraft (hex)
        if 'hex' in self.df.columns:
            for aircraft_id, group in self.df.groupby('hex'):
                group = group.sort_values('timestamp') if 'timestamp' in group.columns else group
                
                # Create sliding windows
                for i in range(len(group) - self.sequence_length - self.prediction_horizon + 1):
                    seq_data = group.iloc[i:i + self.sequence_length][self.features].values
                    target_data = group.iloc[
                        i + self.sequence_length:i + self.sequence_length + self.prediction_horizon
                    ][self.target_features].values
                    
                    # Get timestamps if needed
                    if self.return_timestamps and 'timestamp' in group.columns:
                        timestamps = group.iloc[i:i + self.sequence_length]['timestamp'].values
                        sequences.append((seq_data, target_data, timestamps))
                    else:
                        sequences.append((seq_data, target_data))
        else:
            # No grouping, just sliding windows
            for i in range(len(self.df) - self.sequence_length - self.prediction_horizon + 1):
                seq_data = self.df.iloc[i:i + self.sequence_length][self.features].values
                target_data = self.df.iloc[
                    i + self.sequence_length:i + self.sequence_length + self.prediction_horizon
                ][self.target_features].values
                
                if self.return_timestamps and 'timestamp' in self.df.columns:
                    timestamps = self.df.iloc[i:i + self.sequence_length]['timestamp'].values
                    sequences.append((seq_data, target_data, timestamps))
                else:
                    sequences.append((seq_data, target_data))
        
        return sequences
    
    def __len__(self):
        return len(self.sequences)
    
    def __getitem__(self, idx):
        if self.return_timestamps:
            seq_data, target_data, timestamps = self.sequences[idx]
            return (torch.FloatTensor(seq_data), 
                   torch.FloatTensor(target_data),
                   timestamps)
        else:
            seq_data, target_data = self.sequences[idx]
            return torch.FloatTensor(seq_data), torch.FloatTensor(target_data)


class AnomalyDataset(Dataset):
    """
    Dataset for anomaly detection tasks
    
    Returns sequences with labels indicating normal vs anomalous behavior
    """
    
    def __init__(self, data_path, sequence_length=20, features=None,
                 anomaly_threshold=None, normalize=True, scaler=None):
        """
        Initialize anomaly detection dataset
        
        Args:
            data_path: Path to CSV or DataFrame
            sequence_length: Length of input sequences
            features: Feature columns to use
            anomaly_threshold: Threshold for anomaly labeling (if available)
            normalize: Whether to normalize
            scaler: Pre-fitted scaler
        """
        self.sequence_length = sequence_length
        self.normalize = normalize
        
        # Load data
        if isinstance(data_path, pd.DataFrame):
            self.df = data_path
        else:
            self.df = pd.read_csv(data_path)
            if 'timestamp' in self.df.columns:
                self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        
        # Select features
        if features is None:
            features = [
                'lat', 'lon', 'alt_baro', 'gs', 'track', 'rssi',
                'distance_km', 'signal_deviation', 'altitude_speed_ratio',
                'hour_sin', 'hour_cos'
            ]
            features = [f for f in features if f in self.df.columns]
        
        self.features = features
        
        # Handle missing values
        self.df[self.features] = self.df[self.features].fillna(method='ffill').fillna(0)
        
        # Determine anomalies (if not already labeled)
        if 'is_anomaly' not in self.df.columns and anomaly_threshold is not None:
            # Use signal_deviation or other metric for anomaly labeling
            if 'signal_deviation' in self.df.columns:
                self.df['is_anomaly'] = (
                    np.abs(self.df['signal_deviation']) > anomaly_threshold
                ).astype(float)
            else:
                self.df['is_anomaly'] = 0.0
        elif 'is_anomaly' not in self.df.columns:
            # Assume all normal if no labels
            self.df['is_anomaly'] = 0.0
        
        # Normalization
        if normalize:
            if scaler is None:
                self.scaler = StandardScaler()
                self.df[self.features] = self.scaler.fit_transform(self.df[self.features])
            else:
                self.scaler = scaler
                self.df[self.features] = self.scaler.transform(self.df[self.features])
        else:
            self.scaler = None
        
        # Create sequences
        self.sequences = self._create_sequences()
    
    def _create_sequences(self):
        """Create sequences with anomaly labels"""
        sequences = []
        
        # Group by aircraft if possible
        if 'hex' in self.df.columns:
            for aircraft_id, group in self.df.groupby('hex'):
                group = group.sort_values('timestamp') if 'timestamp' in group.columns else group
                
                for i in range(len(group) - self.sequence_length + 1):
                    seq_data = group.iloc[i:i + self.sequence_length][self.features].values
                    labels = group.iloc[i:i + self.sequence_length]['is_anomaly'].values
                    sequences.append((seq_data, labels))
        else:
            for i in range(len(self.df) - self.sequence_length + 1):
                seq_data = self.df.iloc[i:i + self.sequence_length][self.features].values
                labels = self.df.iloc[i:i + self.sequence_length]['is_anomaly'].values
                sequences.append((seq_data, labels))
        
        return sequences
    
    def __len__(self):
        return len(self.sequences)
    
    def __getitem__(self, idx):
        seq_data, labels = self.sequences[idx]
        return torch.FloatTensor(seq_data), torch.FloatTensor(labels)


def load_adsb_data(data_path, test_size=0.2, sequence_length=20, 
                   prediction_horizon=10, features=None, task='trajectory'):
    """
    Load and split ADS-B data for training
    
    Args:
        data_path: Path to CSV file
        test_size: Fraction of data for testing
        sequence_length: Length of input sequences
        prediction_horizon: Steps to predict ahead
        features: Feature columns to use
        task: 'trajectory' or 'anomaly'
        
    Returns:
        train_loader: Training data loader
        test_loader: Test data loader
        scaler: Fitted scaler
        input_size: Number of input features
    """
    # Load full dataset to fit scaler
    df = pd.read_csv(data_path)
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
    
    # Split by time
    split_idx = int(len(df) * (1 - test_size))
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    
    # Create datasets
    if task == 'trajectory':
        train_dataset = ADSBDataset(
            train_df, sequence_length=sequence_length,
            prediction_horizon=prediction_horizon, features=features,
            normalize=True, scaler=None
        )
        test_dataset = ADSBDataset(
            test_df, sequence_length=sequence_length,
            prediction_horizon=prediction_horizon, features=features,
            normalize=True, scaler=train_dataset.scaler
        )
    elif task == 'anomaly':
        train_dataset = AnomalyDataset(
            train_df, sequence_length=sequence_length,
            features=features, normalize=True, scaler=None
        )
        test_dataset = AnomalyDataset(
            test_df, sequence_length=sequence_length,
            features=features, normalize=True, scaler=train_dataset.scaler
        )
    else:
        raise ValueError(f"Unknown task: {task}")
    
    # Create data loaders
    train_loader = DataLoader(
        train_dataset, batch_size=32, shuffle=True, num_workers=0
    )
    test_loader = DataLoader(
        test_dataset, batch_size=32, shuffle=False, num_workers=0
    )
    
    input_size = len(train_dataset.features)
    
    return train_loader, test_loader, train_dataset.scaler, input_size


if __name__ == "__main__":
    # Test data utilities
    print("Testing ADS-B data utilities...")
    
    # Create dummy data
    n_samples = 1000
    dummy_data = pd.DataFrame({
        'timestamp': pd.date_range('2026-01-16', periods=n_samples, freq='1s'),
        'hex': ['ABC123'] * (n_samples // 2) + ['DEF456'] * (n_samples // 2),
        'lat': np.random.randn(n_samples) * 0.1 + 60.0,
        'lon': np.random.randn(n_samples) * 0.1 + 25.0,
        'alt_baro': np.random.randn(n_samples) * 1000 + 30000,
        'gs': np.random.randn(n_samples) * 50 + 450,
        'track': np.random.rand(n_samples) * 360,
        'rssi': np.random.randn(n_samples) * 5 - 30,
        'distance_km': np.random.rand(n_samples) * 100,
        'signal_deviation': np.random.randn(n_samples) * 2,
        'hour_sin': np.sin(2 * np.pi * np.arange(n_samples) / 24),
        'hour_cos': np.cos(2 * np.pi * np.arange(n_samples) / 24),
    })
    
    print("\n1. Testing trajectory dataset...")
    traj_dataset = ADSBDataset(dummy_data, sequence_length=10, prediction_horizon=5)
    print(f"   Number of sequences: {len(traj_dataset)}")
    x, y = traj_dataset[0]
    print(f"   Input shape: {x.shape}")
    print(f"   Target shape: {y.shape}")
    
    print("\n2. Testing anomaly dataset...")
    anom_dataset = AnomalyDataset(dummy_data, sequence_length=10)
    print(f"   Number of sequences: {len(anom_dataset)}")
    x, labels = anom_dataset[0]
    print(f"   Input shape: {x.shape}")
    print(f"   Labels shape: {labels.shape}")
    
    print("\n✅ All tests passed!")
