#!/usr/bin/env python3
"""
==============================================================================
TRAINING SCRIPT FOR LIQUID NEURAL NETWORK ANOMALY DETECTOR
==============================================================================
Purpose: Train LNN for detecting anomalies in ADS-B data

Usage:
    python train_lnn_anomaly_detector.py --data_path path/to/data.csv --epochs 50

Author: ADS-B Research Grid Project
License: MIT
==============================================================================
"""

import argparse
import torch
import torch.nn as nn
import torch.optim as optim
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
import json

import sys
sys.path.append(str(Path(__file__).parent.parent))

from models.lnn.liquid_neural_network import create_lnn_model
from models.data_utils import load_adsb_data, AnomalyDataset


def train_epoch(model, train_loader, optimizer, device, criterion_recon, criterion_anomaly):
    """Train for one epoch"""
    model.train()
    total_loss = 0
    total_recon_loss = 0
    total_anomaly_loss = 0
    
    for batch_idx, (x, labels) in enumerate(tqdm(train_loader, desc="Training")):
        x = x.to(device)
        labels = labels.to(device).unsqueeze(-1)  # Add feature dimension
        
        optimizer.zero_grad()
        
        # Forward pass
        reconstruction, anomaly_scores, _ = model(x)
        
        # Compute losses
        recon_loss = criterion_recon(reconstruction, x)
        anomaly_loss = criterion_anomaly(anomaly_scores, labels)
        
        # Combined loss
        loss = recon_loss + 0.5 * anomaly_loss
        
        # Backward pass
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        
        total_loss += loss.item()
        total_recon_loss += recon_loss.item()
        total_anomaly_loss += anomaly_loss.item()
    
    avg_loss = total_loss / len(train_loader)
    avg_recon = total_recon_loss / len(train_loader)
    avg_anomaly = total_anomaly_loss / len(train_loader)
    
    return avg_loss, avg_recon, avg_anomaly


def evaluate(model, test_loader, device, criterion_recon, criterion_anomaly):
    """Evaluate on test set"""
    model.eval()
    total_loss = 0
    total_recon_loss = 0
    total_anomaly_loss = 0
    all_scores = []
    all_labels = []
    
    with torch.no_grad():
        for x, labels in tqdm(test_loader, desc="Evaluating"):
            x = x.to(device)
            labels = labels.to(device).unsqueeze(-1)
            
            reconstruction, anomaly_scores, _ = model(x)
            
            recon_loss = criterion_recon(reconstruction, x)
            anomaly_loss = criterion_anomaly(anomaly_scores, labels)
            loss = recon_loss + 0.5 * anomaly_loss
            
            total_loss += loss.item()
            total_recon_loss += recon_loss.item()
            total_anomaly_loss += anomaly_loss.item()
            
            all_scores.append(anomaly_scores.cpu())
            all_labels.append(labels.cpu())
    
    avg_loss = total_loss / len(test_loader)
    avg_recon = total_recon_loss / len(test_loader)
    avg_anomaly = total_anomaly_loss / len(test_loader)
    
    all_scores = torch.cat(all_scores).numpy()
    all_labels = torch.cat(all_labels).numpy()
    
    return avg_loss, avg_recon, avg_anomaly, all_scores, all_labels


def plot_training_curves(train_losses, test_losses, save_path):
    """Plot training curves"""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    
    # Total loss
    axes[0].plot(train_losses['total'], label='Train')
    axes[0].plot(test_losses['total'], label='Test')
    axes[0].set_xlabel('Epoch')
    axes[0].set_ylabel('Total Loss')
    axes[0].set_title('Total Loss')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    # Reconstruction loss
    axes[1].plot(train_losses['recon'], label='Train')
    axes[1].plot(test_losses['recon'], label='Test')
    axes[1].set_xlabel('Epoch')
    axes[1].set_ylabel('Reconstruction Loss')
    axes[1].set_title('Reconstruction Loss')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    
    # Anomaly loss
    axes[2].plot(train_losses['anomaly'], label='Train')
    axes[2].plot(test_losses['anomaly'], label='Test')
    axes[2].set_xlabel('Epoch')
    axes[2].set_ylabel('Anomaly Loss')
    axes[2].set_title('Anomaly Detection Loss')
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ Training curves saved to {save_path}")


def main():
    parser = argparse.ArgumentParser(description='Train LNN Anomaly Detector')
    parser.add_argument('--data_path', type=str, required=True,
                       help='Path to CSV data file')
    parser.add_argument('--output_dir', type=str, default='analysis/models/lnn/outputs',
                       help='Output directory for models and plots')
    parser.add_argument('--hidden_size', type=int, default=64,
                       help='Hidden size for LNN')
    parser.add_argument('--latent_size', type=int, default=32,
                       help='Latent dimension')
    parser.add_argument('--num_layers', type=int, default=2,
                       help='Number of LNN layers')
    parser.add_argument('--sequence_length', type=int, default=20,
                       help='Sequence length')
    parser.add_argument('--epochs', type=int, default=50,
                       help='Number of training epochs')
    parser.add_argument('--lr', type=float, default=0.001,
                       help='Learning rate')
    parser.add_argument('--device', type=str, default='cuda' if torch.cuda.is_available() else 'cpu',
                       help='Device to use for training')
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("LIQUID NEURAL NETWORK - ANOMALY DETECTION TRAINING")
    print("=" * 80)
    print(f"Device: {args.device}")
    print(f"Data path: {args.data_path}")
    print(f"Output directory: {output_dir}")
    
    # Load data
    print("\n📥 Loading data...")
    train_loader, test_loader, scaler, input_size = load_adsb_data(
        args.data_path,
        test_size=0.2,
        sequence_length=args.sequence_length,
        task='anomaly'
    )
    print(f"   Input size: {input_size}")
    print(f"   Train batches: {len(train_loader)}")
    print(f"   Test batches: {len(test_loader)}")
    
    # Create model
    print("\n🧠 Creating LNN model...")
    device = torch.device(args.device)
    model = create_lnn_model(
        input_size=input_size,
        model_type='anomaly_detector',
        hidden_size=args.hidden_size,
        latent_size=args.latent_size,
        num_layers=args.num_layers
    ).to(device)
    
    print(f"   Model parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Optimizer and loss functions
    optimizer = optim.Adam(model.parameters(), lr=args.lr)
    criterion_recon = nn.MSELoss()
    criterion_anomaly = nn.BCELoss()
    
    # Training loop
    print("\n🚀 Starting training...")
    train_losses = {'total': [], 'recon': [], 'anomaly': []}
    test_losses = {'total': [], 'recon': [], 'anomaly': []}
    best_test_loss = float('inf')
    
    for epoch in range(args.epochs):
        print(f"\nEpoch {epoch + 1}/{args.epochs}")
        
        # Train
        train_loss, train_recon, train_anomaly = train_epoch(
            model, train_loader, optimizer, device,
            criterion_recon, criterion_anomaly
        )
        
        # Evaluate
        test_loss, test_recon, test_anomaly, scores, labels = evaluate(
            model, test_loader, device,
            criterion_recon, criterion_anomaly
        )
        
        # Store losses
        train_losses['total'].append(train_loss)
        train_losses['recon'].append(train_recon)
        train_losses['anomaly'].append(train_anomaly)
        test_losses['total'].append(test_loss)
        test_losses['recon'].append(test_recon)
        test_losses['anomaly'].append(test_anomaly)
        
        print(f"  Train Loss: {train_loss:.4f} (Recon: {train_recon:.4f}, Anomaly: {train_anomaly:.4f})")
        print(f"  Test Loss:  {test_loss:.4f} (Recon: {test_recon:.4f}, Anomaly: {test_anomaly:.4f})")
        
        # Save best model
        if test_loss < best_test_loss:
            best_test_loss = test_loss
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'test_loss': test_loss,
                'config': vars(args)
            }, output_dir / 'best_lnn_model.pt')
            print(f"  ✅ Best model saved (test loss: {test_loss:.4f})")
    
    # Plot training curves
    print("\n📊 Generating plots...")
    plot_training_curves(train_losses, test_losses, output_dir / 'lnn_training_curves.png')
    
    # Save training history
    history = {
        'train_losses': train_losses,
        'test_losses': test_losses,
        'config': vars(args)
    }
    with open(output_dir / 'lnn_training_history.json', 'w') as f:
        json.dump(history, f, indent=2)
    
    print("\n" + "=" * 80)
    print("✅ Training complete!")
    print(f"Best test loss: {best_test_loss:.4f}")
    print(f"Model saved to: {output_dir / 'best_lnn_model.pt'}")
    print("=" * 80)


if __name__ == "__main__":
    main()
