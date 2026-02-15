#!/usr/bin/env python3
"""
Demo: Complete 16-Model Zoo for ADS-B Spoofing Detection

This script demonstrates all models in the complete ensemble:

Tier 1: Edge Baselines
- Random Forest & XGBoost (tree-based)
- Sinkhorn-Knopp (optimal transport)
- Multi-Agent RL (coordination)

Tier 2: Spatial & Temporal Deep Learning
- Liquid Neural Networks (time-continuous)
- xLSTM (recurrent)
- Mamba (state space models)

Tier 3: Physics & Generative Validation
- PINN (physics-informed)
- KAN (aerodynamic regression)
- DeepSeek MCHC (topology)
- GAN (adversarial detection)

Usage:
    python examples/demo_complete_zoo.py
"""

import sys
import os

# Add parent directory to path to import models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Try to import models
try:
    from models import (
        ManifoldGuard,
        MambaSSM,
        KAN,
        PINN,
        SpoofingGAN,
        MARLCoordination,
        RandomForestDetector,
        XGBoostDetector,
    )
    MODELS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Some models not available: {e}")
    MODELS_AVAILABLE = False

# Set random seed for reproducibility
np.random.seed(42)


def generate_trajectory(n_aircraft: int = 10, seq_len: int = 50, spoofed: bool = False) -> dict:
    """
    Generate synthetic ADS-B trajectory data.
    
    Args:
        n_aircraft: Number of aircraft
        seq_len: Sequence length
        spoofed: If True, generate spoofed patterns
        
    Returns:
        Dictionary with trajectory data
    """
    # Current positions (lat, lon, alt in feet)
    observed = np.array([
        [60.1 + i * 0.01, 24.8 + i * 0.01, 10000 + i * 500]
        for i in range(n_aircraft)
    ])
    
    if spoofed:
        # Large discrepancy for spoofing
        predicted = observed + np.random.randn(n_aircraft, 3) * 0.1
        noise_scale = 0.01
        velocity_scale = 50
        rssi_scale = 10
    else:
        # Small noise for normal
        predicted = observed + np.random.randn(n_aircraft, 3) * 0.001
        noise_scale = 0.0001
        velocity_scale = 5
        rssi_scale = 2
    
    # Historical trajectory sequence
    # Features: [lat, lon, alt, velocity, heading, rssi, temperature, pressure]
    trajectory = np.zeros((n_aircraft, seq_len, 8))
    for i in range(n_aircraft):
        for t in range(seq_len):
            # Position with optional noise
            jump = np.random.randn() * noise_scale if spoofed and t % 10 == 0 else 0
            trajectory[i, t, 0] = 60.1 + i * 0.01 + t * 0.0001 + jump
            trajectory[i, t, 1] = 24.8 + i * 0.01 + t * 0.0001 + jump
            trajectory[i, t, 2] = (10000 + i * 500) / 10000.0  # normalized alt
            
            # Velocity with optional spikes
            trajectory[i, t, 3] = 450 + np.random.randn() * velocity_scale
            trajectory[i, t, 4] = 90 + np.random.randn() * (20 if spoofed else 2)
            trajectory[i, t, 5] = -20 + np.random.randn() * rssi_scale
            trajectory[i, t, 6] = 15 + np.random.randn() * (5 if spoofed else 1)
            trajectory[i, t, 7] = 1013 + np.random.randn() * (10 if spoofed else 2)
    
    # Time deltas
    dt = np.random.uniform(0.8, 1.2, (n_aircraft, seq_len)) if not spoofed else np.random.uniform(0.1, 3.0, (n_aircraft, seq_len))
    
    return {
        'observed': observed,
        'predicted': predicted,
        'trajectory': trajectory,
        'dt': dt,
    }


def test_individual_models():
    """
    Test individual models independently.
    """
    print("\n" + "=" * 70)
    print("  Testing Individual Models")
    print("=" * 70 + "\n")
    
    # Generate test data
    data = generate_trajectory(n_aircraft=5, seq_len=50, spoofed=False)
    trajectory = data['trajectory']
    
    # Test Tree-based models
    print("1. Random Forest & XGBoost (Tier 1 - Tree-based)")
    print("-" * 50)
    try:
        from models import TreeBasedEnsemble
        tree_model = TreeBasedEnsemble()
        print("   ✅ Tree models initialized")
        # Note: These need to be trained first in production
        # For demo, we just show they can be instantiated
    except Exception as e:
        print(f"   ⚠️  Tree models unavailable: {e}")
    
    # Test PyTorch models
    try:
        import torch
        
        print("\n2. Mamba SSM (Tier 2 - Long-context)")
        print("-" * 50)
        try:
            mamba = MambaSSM(input_dim=8, d_model=32, num_layers=2)
            traj_tensor = torch.from_numpy(trajectory).float()
            output = mamba(traj_tensor)
            print(f"   ✅ Mamba initialized and tested")
            print(f"   Anomaly score: {output['anomaly_score'].mean():.4f}")
        except Exception as e:
            print(f"   ⚠️  Mamba failed: {e}")
        
        print("\n3. KAN (Tier 3 - Aerodynamic Regression)")
        print("-" * 50)
        try:
            kan = KAN(input_dim=8, hidden_dims=[16, 8], output_dim=2)
            traj_tensor = torch.from_numpy(trajectory).float()
            output = kan(traj_tensor)
            print(f"   ✅ KAN initialized and tested")
            print(f"   Lift coeff range: [{output['lift_coeff'].min():.2f}, {output['lift_coeff'].max():.2f}]")
            print(f"   Drag coeff range: [{output['drag_coeff'].min():.2f}, {output['drag_coeff'].max():.2f}]")
        except Exception as e:
            print(f"   ⚠️  KAN failed: {e}")
        
        print("\n4. PINN (Tier 3 - Physics Constraints)")
        print("-" * 50)
        try:
            pinn = PINN(input_dim=8, hidden_dim=32, output_dim=9)
            traj_tensor = torch.from_numpy(trajectory).float()
            dt_tensor = torch.from_numpy(data['dt']).float()
            output = pinn(traj_tensor, dt_tensor)
            print(f"   ✅ PINN initialized and tested")
            print(f"   Physics violation score: {output['anomaly_score'].mean():.4f}")
            losses = output['physics_losses']
            print(f"   Acceleration loss: {losses['accel_loss']:.4f}")
            print(f"   Continuity loss: {losses['continuity_loss']:.4f}")
        except Exception as e:
            print(f"   ⚠️  PINN failed: {e}")
        
        print("\n5. GAN (Tier 3 - Adversarial Detection)")
        print("-" * 50)
        try:
            gan = SpoofingGAN(latent_dim=64, trajectory_dim=8, seq_len=50, hidden_dim=128)
            traj_tensor = torch.from_numpy(trajectory).float()
            output = gan(traj_tensor)
            print(f"   ✅ GAN initialized and tested")
            print(f"   Discriminator score: {output['anomaly_score'].mean():.4f}")
        except Exception as e:
            print(f"   ⚠️  GAN failed: {e}")
        
        print("\n6. MARL (Tier 1 - Multi-Agent Coordination)")
        print("-" * 50)
        try:
            marl = MARLCoordination(num_agents=4, state_dim=16, action_dim=4)
            # Create agent states (simplified)
            agent_states = torch.randn(1, 4, 16)  # [batch, num_agents, state_dim]
            output = marl(agent_states)
            print(f"   ✅ MARL initialized and tested")
            print(f"   Coordination score: {output['coordination_score'].mean():.4f}")
        except Exception as e:
            print(f"   ⚠️  MARL failed: {e}")
        
    except ImportError:
        print("\n   ⚠️  PyTorch not available. Skipping neural network models.")


def test_full_ensemble():
    """
    Test the complete ensemble system.
    """
    print("\n" + "=" * 70)
    print("  Testing Complete 16-Model Ensemble")
    print("=" * 70 + "\n")
    
    # Initialize ManifoldGuard with all models enabled
    print("Initializing ManifoldGuard with full model zoo...")
    try:
        guard = ManifoldGuard(
            enable_all_models=True,
            device='cpu',
        )
        print("✅ ManifoldGuard initialized with all models!\n")
    except Exception as e:
        print(f"⚠️  Some models unavailable: {e}")
        print("   Initializing with core models only...\n")
        guard = ManifoldGuard(
            enable_all_models=False,
            device='cpu',
        )
    
    # Test on normal traffic
    print("-" * 70)
    print("  Scenario 1: Normal Traffic")
    print("-" * 70)
    
    normal_data = generate_trajectory(n_aircraft=10, seq_len=50, spoofed=False)
    
    try:
        result_normal = guard.detect_spoofing(
            observed_positions=normal_data['observed'],
            predicted_positions=normal_data['predicted'],
            trajectory_sequence=normal_data['trajectory'],
            dt=normal_data['dt'],
        )
        
        print(f"\n  Verdict: {'🚨 SPOOFING' if result_normal['is_spoof'] else '✅ LEGITIMATE'}")
        print(f"  Probability: {result_normal['is_spoof_probability']:.2%}")
        print(f"  Confidence: {result_normal['confidence']:.2%}")
        
        print(f"\n  Model Breakdown:")
        for model, score in result_normal['model_scores'].items():
            if score > 0:
                print(f"    {model.upper():<12} {'█' * int(score * 30):<30} {score:.2%}")
    
    except Exception as e:
        print(f"  ❌ Detection failed: {e}")
    
    # Test on spoofed traffic
    print("\n" + "-" * 70)
    print("  Scenario 2: Spoofed Traffic")
    print("-" * 70)
    
    spoofed_data = generate_trajectory(n_aircraft=10, seq_len=50, spoofed=True)
    
    try:
        result_spoofed = guard.detect_spoofing(
            observed_positions=spoofed_data['observed'],
            predicted_positions=spoofed_data['predicted'],
            trajectory_sequence=spoofed_data['trajectory'],
            dt=spoofed_data['dt'],
        )
        
        print(f"\n  Verdict: {'🚨 SPOOFING' if result_spoofed['is_spoof'] else '✅ LEGITIMATE'}")
        print(f"  Probability: {result_spoofed['is_spoof_probability']:.2%}")
        print(f"  Confidence: {result_spoofed['confidence']:.2%}")
        
        print(f"\n  Model Breakdown:")
        for model, score in result_spoofed['model_scores'].items():
            if score > 0:
                print(f"    {model.upper():<12} {'█' * int(score * 30):<30} {score:.2%}")
    
    except Exception as e:
        print(f"  ❌ Detection failed: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("  Performance Summary")
    print("=" * 70)
    
    try:
        normal_correct = not result_normal['is_spoof']
        spoofed_correct = result_spoofed['is_spoof']
        
        print(f"\n  Normal Traffic:   {'✅ PASS' if normal_correct else '❌ FAIL'}")
        print(f"  Spoofed Traffic:  {'✅ PASS' if spoofed_correct else '❌ FAIL'}")
        
        accuracy = (normal_correct + spoofed_correct) / 2.0
        print(f"\n  Overall Accuracy: {accuracy:.0%}")
    except:
        print("\n  Unable to compute summary (some tests failed)")


def main():
    """
    Main demonstration function.
    """
    print("\n" + "=" * 70)
    print("  ADS-B Research Grid: Complete 16-Model Zoo Demo")
    print("=" * 70)
    print("\n  This demo showcases all models in the detection ensemble:")
    print("  - Tier 1: RF, XGBoost, Sinkhorn-Knopp, MARL")
    print("  - Tier 2: LNN, xLSTM, Mamba")
    print("  - Tier 3: PINN, KAN, DeepSeek MCHC, GAN")
    print("\n" + "=" * 70)
    
    if not MODELS_AVAILABLE:
        print("\n  ⚠️  Warning: Not all models are available.")
        print("     Please install required dependencies:")
        print("     pip install -r requirements.txt\n")
    
    # Test individual models
    test_individual_models()
    
    # Test full ensemble
    test_full_ensemble()
    
    print("\n" + "=" * 70)
    print("  Demo Complete!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
