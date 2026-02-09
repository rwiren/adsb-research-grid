#!/usr/bin/env python3
"""
==============================================================================
TRAINING SCRIPT FOR xLSTM TRAJECTORY PREDICTOR
==============================================================================
Purpose: Train xLSTM for predicting aircraft trajectories from ADS-B data

Usage:
    python train_xlstm_trajectory.py --data_path path/to/data.csv --epochs 50

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

from models.xlstm.extended_lstm import create_xlstm_model
from models.data_utils import load_adsb_data


def train_epoch(model, train_loader, optimizer, device, criterion):
    """Train for one epoch"""
    model.train()
    total_loss = 0
    
    for batch_idx, (x, y) in enumerate(tqdm(train_loader, desc="Training")):
        x = x.to(device)
        y = y.to(device)
        
        optimizer.zero_grad()
        
        # Forward pass - next step prediction
        predictions = model(x, predict_future=False)
        
        # Compute loss (predict next step)
        # predictions: (batch, seq_len, features)
        # We compare with shifted targets
        loss = criterion(predictions[:, :-1, :], x[:, 1:, :])
        
        # Backward pass
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        
        total_loss += loss.item()
    
    avg_loss = total_loss / len(train_loader)
    return avg_loss


def evaluate(model, test_loader, device, criterion, predict_future=False):
    """Evaluate on test set"""
    model.eval()
    total_loss = 0
    all_predictions = []
    all_targets = []
    
    with torch.no_grad():
        for x, y in tqdm(test_loader, desc="Evaluating"):
            x = x.to(device)
            y = y.to(device)
            
            if predict_future:
                # Future prediction
                predictions = model(x, predict_future=True)
                loss = criterion(predictions, y)
            else:
                # Next-step prediction
                predictions = model(x, predict_future=False)
                loss = criterion(predictions[:, :-1, :], x[:, 1:, :])
            
            total_loss += loss.item()
            
            all_predictions.append(predictions.cpu())
            all_targets.append(y.cpu() if predict_future else x[:, 1:, :].cpu())
    
    avg_loss = total_loss / len(test_loader)
    all_predictions = torch.cat(all_predictions)
    all_targets = torch.cat(all_targets)
    
    # Compute metrics
    mae = torch.mean(torch.abs(all_predictions - all_targets)).item()
    rmse = torch.sqrt(torch.mean((all_predictions - all_targets) ** 2)).item()
    
    return avg_loss, mae, rmse, all_predictions, all_targets


def plot_training_curves(train_losses, test_losses, save_path):
    """Plot training curves"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    epochs = range(1, len(train_losses) + 1)
    ax.plot(epochs, train_losses, label='Train Loss', linewidth=2)
    ax.plot(epochs, test_losses, label='Test Loss', linewidth=2)
    
    ax.set_xlabel('Epoch', fontsize=12)
    ax.set_ylabel('Loss (MSE)', fontsize=12)
    ax.set_title('xLSTM Training Progress', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ Training curves saved to {save_path}")


def plot_predictions(predictions, targets, num_samples=3, save_path=None):
    """Plot sample predictions vs ground truth"""
    fig, axes = plt.subplots(num_samples, 1, figsize=(12, 4 * num_samples))
    
    if num_samples == 1:
        axes = [axes]
    
    for i in range(num_samples):
        if i >= len(predictions):
            break
        
        pred = predictions[i].numpy()
        target = targets[i].numpy()
        
        # Plot first feature (e.g., latitude or altitude)
        time_steps = range(len(pred))
        axes[i].plot(time_steps, target[:, 0], 'b-', label='Ground Truth', linewidth=2)
        axes[i].plot(time_steps, pred[:, 0], 'r--', label='Prediction', linewidth=2)
        
        axes[i].set_xlabel('Time Step', fontsize=11)
        axes[i].set_ylabel('Feature Value', fontsize=11)
        axes[i].set_title(f'Sample {i+1}: Trajectory Prediction', fontsize=12, fontweight='bold')
        axes[i].legend(fontsize=10)
        axes[i].grid(True, alpha=0.3)
    
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"✅ Prediction plots saved to {save_path}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(description='Train xLSTM Trajectory Predictor')
    parser.add_argument('--data_path', type=str, required=True,
                       help='Path to CSV data file')
    parser.add_argument('--output_dir', type=str, default='analysis/models/xlstm/outputs',
                       help='Output directory for models and plots')
    parser.add_argument('--hidden_size', type=int, default=64,
                       help='Hidden size for xLSTM')
    parser.add_argument('--num_layers', type=int, default=2,
                       help='Number of xLSTM layers')
    parser.add_argument('--sequence_length', type=int, default=20,
                       help='Input sequence length')
    parser.add_argument('--prediction_horizon', type=int, default=10,
                       help='Number of steps to predict ahead')
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
    print("xLSTM - TRAJECTORY PREDICTION TRAINING")
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
        prediction_horizon=args.prediction_horizon,
        task='trajectory'
    )
    print(f"   Input size: {input_size}")
    print(f"   Train batches: {len(train_loader)}")
    print(f"   Test batches: {len(test_loader)}")
    
    # Create model
    print("\n🧠 Creating xLSTM model...")
    device = torch.device(args.device)
    model = create_xlstm_model(
        input_size=input_size,
        model_type='trajectory_predictor',
        hidden_size=args.hidden_size,
        num_layers=args.num_layers,
        predict_steps=args.prediction_horizon
    ).to(device)
    
    print(f"   Model parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Optimizer and loss
    optimizer = optim.Adam(model.parameters(), lr=args.lr)
    criterion = nn.MSELoss()
    
    # Training loop
    print("\n🚀 Starting training...")
    train_losses = []
    test_losses = []
    best_test_loss = float('inf')
    
    for epoch in range(args.epochs):
        print(f"\nEpoch {epoch + 1}/{args.epochs}")
        
        # Train
        train_loss = train_epoch(model, train_loader, optimizer, device, criterion)
        
        # Evaluate
        test_loss, mae, rmse, predictions, targets = evaluate(
            model, test_loader, device, criterion, predict_future=False
        )
        
        train_losses.append(train_loss)
        test_losses.append(test_loss)
        
        print(f"  Train Loss: {train_loss:.6f}")
        print(f"  Test Loss:  {test_loss:.6f}")
        print(f"  MAE:        {mae:.6f}")
        print(f"  RMSE:       {rmse:.6f}")
        
        # Save best model
        if test_loss < best_test_loss:
            best_test_loss = test_loss
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'test_loss': test_loss,
                'mae': mae,
                'rmse': rmse,
                'config': vars(args)
            }, output_dir / 'best_xlstm_model.pt')
            print(f"  ✅ Best model saved (test loss: {test_loss:.6f})")
    
    # Plot training curves
    print("\n📊 Generating plots...")
    plot_training_curves(train_losses, test_losses, output_dir / 'xlstm_training_curves.png')
    
    # Plot sample predictions
    plot_predictions(predictions[:3], targets[:3], num_samples=3,
                    save_path=output_dir / 'xlstm_sample_predictions.png')
    
    # Save training history
    history = {
        'train_losses': train_losses,
        'test_losses': test_losses,
        'config': vars(args)
    }
    with open(output_dir / 'xlstm_training_history.json', 'w') as f:
        json.dump(history, f, indent=2)
    
    print("\n" + "=" * 80)
    print("✅ Training complete!")
    print(f"Best test loss: {best_test_loss:.6f}")
    print(f"Model saved to: {output_dir / 'best_xlstm_model.pt'}")
    print("=" * 80)


if __name__ == "__main__":
    main()
