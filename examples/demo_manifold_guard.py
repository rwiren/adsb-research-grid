#!/usr/bin/env python3
"""
Example Usage: ManifoldGuard ADS-B Spoofing Detection

This script demonstrates how to use the ManifoldGuard system for detecting
ADS-B spoofing attacks using the complete 16-Model Zoo architecture.

Usage:
    python examples/demo_manifold_guard.py
"""

import sys
import os

# Add parent directory to path to import models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
from models import ManifoldGuard

# Set random seed for reproducibility
np.random.seed(42)

def generate_normal_trajectory(n_aircraft: int = 10, seq_len: int = 50) -> dict:
    """
    Generate synthetic normal ADS-B trajectory data.
    
    Returns:
        Dictionary with observed, predicted positions and trajectory sequences.
    """
    print("📊 Generating NORMAL trajectory data...")
    
    # Current positions (lat, lon, alt in feet)
    observed = np.array([
        [60.1 + i * 0.01, 24.8 + i * 0.01, 10000 + i * 500]
        for i in range(n_aircraft)
    ])
    
    # Predicted positions (slight physics-based drift)
    # Normal: predictions closely match observations
    noise = np.random.randn(n_aircraft, 3) * 0.001  # Small noise
    predicted = observed + noise
    
    # Historical trajectory sequence
    # Features: [lat, lon, alt, velocity, heading, rssi, temperature, pressure]
    trajectory = np.zeros((n_aircraft, seq_len, 8))
    for i in range(n_aircraft):
        # Smooth trajectory with small variations
        for t in range(seq_len):
            trajectory[i, t, 0] = 60.1 + i * 0.01 + t * 0.0001  # lat
            trajectory[i, t, 1] = 24.8 + i * 0.01 + t * 0.0001  # lon
            trajectory[i, t, 2] = (10000 + i * 500) / 10000.0  # normalized alt
            trajectory[i, t, 3] = 450 + np.random.randn() * 5   # velocity (knots)
            trajectory[i, t, 4] = 90 + np.random.randn() * 2    # heading (degrees)
            trajectory[i, t, 5] = -20 + np.random.randn() * 2   # rssi (dBm)
            trajectory[i, t, 6] = 15 + np.random.randn() * 1    # temperature (C)
            trajectory[i, t, 7] = 1013 + np.random.randn() * 2  # pressure (mbar)
    
    # Time deltas (slightly irregular)
    dt = np.random.uniform(0.8, 1.2, (n_aircraft, seq_len))
    
    return {
        'observed': observed,
        'predicted': predicted,
        'trajectory': trajectory,
        'dt': dt,
    }


def generate_spoofed_trajectory(n_aircraft: int = 10, seq_len: int = 50) -> dict:
    """
    Generate synthetic SPOOFED ADS-B trajectory data.
    
    Spoofing characteristics:
    - Large discrepancy between observed and predicted positions
    - Physically impossible velocity changes
    - Inconsistent trajectory patterns
    
    Returns:
        Dictionary with observed, predicted positions and trajectory sequences.
    """
    print("🚨 Generating SPOOFED trajectory data...")
    
    # Current positions
    observed = np.array([
        [60.1 + i * 0.01, 24.8 + i * 0.01, 10000 + i * 500]
        for i in range(n_aircraft)
    ])
    
    # Predicted positions (large discrepancy - spoofing!)
    # Physics predicts one location, but ADS-B reports another
    predicted = observed + np.random.randn(n_aircraft, 3) * 0.1  # Large error!
    
    # Historical trajectory with anomalies
    trajectory = np.zeros((n_aircraft, seq_len, 8))
    for i in range(n_aircraft):
        for t in range(seq_len):
            # Erratic trajectory with sudden jumps
            jump = np.random.randn() * 0.01 if t % 10 == 0 else 0
            trajectory[i, t, 0] = 60.1 + i * 0.01 + t * 0.0001 + jump
            trajectory[i, t, 1] = 24.8 + i * 0.01 + t * 0.0001 + jump
            trajectory[i, t, 2] = (10000 + i * 500) / 10000.0
            
            # Impossible velocity spikes
            trajectory[i, t, 3] = 450 + np.random.randn() * 50  # Large variance!
            trajectory[i, t, 4] = 90 + np.random.randn() * 20   # Erratic heading
            trajectory[i, t, 5] = -20 + np.random.randn() * 10  # Inconsistent RSSI
            trajectory[i, t, 6] = 15 + np.random.randn() * 5
            trajectory[i, t, 7] = 1013 + np.random.randn() * 10
    
    # Time deltas (highly irregular - sign of spoofing)
    dt = np.random.uniform(0.1, 3.0, (n_aircraft, seq_len))
    
    return {
        'observed': observed,
        'predicted': predicted,
        'trajectory': trajectory,
        'dt': dt,
    }


def print_detection_result(result: dict, scenario: str):
    """
    Pretty-print detection results.
    
    Args:
        result: Detection result dictionary from ManifoldGuard.
        scenario: Scenario name (e.g., "NORMAL" or "SPOOFED").
    """
    print(f"\n{'=' * 70}")
    print(f"  Detection Results: {scenario} Traffic")
    print(f"{'=' * 70}")
    
    # Main verdict
    verdict = "🚨 SPOOFING DETECTED" if result['is_spoof'] else "✅ LEGITIMATE"
    print(f"\n  Verdict: {verdict}")
    print(f"  Spoofing Probability: {result['is_spoof_probability']:.2%}")
    print(f"  Confidence: {result['confidence']:.2%}")
    
    # Model scores breakdown
    print(f"\n  {'Model Scores:':<30}")
    print(f"  {'-' * 50}")
    for model, score in result['model_scores'].items():
        model_name = model.upper().ljust(20)
        bar_length = int(score * 30)
        bar = '█' * bar_length + '░' * (30 - bar_length)
        print(f"  {model_name} {bar} {score:.2%}")
    
    # Technical metrics
    print(f"\n  {'Technical Metrics:':<30}")
    print(f"  {'-' * 50}")
    print(f"  Transport Cost (Sinkhorn):    {result['transport_cost']:.4f}")
    print(f"  Convergence Rate:             {result['convergence_rate']:.2%}")
    print(f"  Topology Score (MCHC):        {result['topology_score']:.4f}")
    
    print(f"\n{'=' * 70}\n")


def main():
    """
    Main demonstration function.
    """
    print("\n" + "=" * 70)
    print("  ManifoldGuard ADS-B Spoofing Detection System")
    print("  Tier 1-3 Defense: Sinkhorn-Knopp + LNN + xLSTM + DeepSeek MCHC")
    print("=" * 70 + "\n")
    
    # Initialize ManifoldGuard
    print("🔧 Initializing ManifoldGuard...")
    try:
        guard = ManifoldGuard(
            sinkhorn_epsilon=0.1,
            lnn_hidden_dim=32,
            xlstm_hidden_dim=64,
            mchc_hidden_dim=64,
            device='cpu',  # Use 'cuda' for GPU or 'hailo' for Hailo-8
        )
        print("✅ ManifoldGuard initialized successfully!")
        torch_available = True
    except Exception as e:
        print(f"⚠️  Warning: {e}")
        print("   Running in NumPy-only mode (Sinkhorn-Knopp only)")
        guard = ManifoldGuard()
        torch_available = False
    
    # Scenario 1: Normal Traffic
    print("\n" + "-" * 70)
    print("  Scenario 1: Testing NORMAL traffic patterns")
    print("-" * 70)
    
    normal_data = generate_normal_trajectory(n_aircraft=10, seq_len=50)
    
    if torch_available:
        result_normal = guard.detect_spoofing(
            observed_positions=normal_data['observed'],
            predicted_positions=normal_data['predicted'],
            trajectory_sequence=normal_data['trajectory'],
            dt=normal_data['dt'],
        )
    else:
        # Sinkhorn-only mode
        result_normal = guard.detect_spoofing(
            observed_positions=normal_data['observed'],
            predicted_positions=normal_data['predicted'],
        )
    
    print_detection_result(result_normal, "NORMAL")
    
    # Scenario 2: Spoofed Traffic
    print("\n" + "-" * 70)
    print("  Scenario 2: Testing SPOOFED traffic patterns")
    print("-" * 70)
    
    spoofed_data = generate_spoofed_trajectory(n_aircraft=10, seq_len=50)
    
    if torch_available:
        result_spoofed = guard.detect_spoofing(
            observed_positions=spoofed_data['observed'],
            predicted_positions=spoofed_data['predicted'],
            trajectory_sequence=spoofed_data['trajectory'],
            dt=spoofed_data['dt'],
        )
    else:
        result_spoofed = guard.detect_spoofing(
            observed_positions=spoofed_data['observed'],
            predicted_positions=spoofed_data['predicted'],
        )
    
    print_detection_result(result_spoofed, "SPOOFED")
    
    # Summary
    print("\n" + "=" * 70)
    print("  System Performance Summary")
    print("=" * 70)
    
    normal_correct = not result_normal['is_spoof']
    spoofed_correct = result_spoofed['is_spoof']
    
    print(f"\n  Normal Traffic Detection:   {'✅ PASS' if normal_correct else '❌ FAIL'}")
    print(f"  Spoofed Traffic Detection:  {'✅ PASS' if spoofed_correct else '❌ FAIL'}")
    
    accuracy = (normal_correct + spoofed_correct) / 2.0
    print(f"\n  Overall Accuracy: {accuracy:.0%}")
    
    if torch_available:
        print(f"\n  💡 Tip: Export models for Hailo-8 NPU deployment:")
        print(f"     guard.export_models('./exported_models')")
    
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
