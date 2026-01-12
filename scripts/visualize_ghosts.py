import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import IsolationForest
import os

# ==============================================================================
# Script: visualize_ghosts.py (v2.0 - Probabilistic Forensics)
# Purpose: Detects anomalies and assigns a "Ghost Confidence Score".
#          Visualizes severity of physics violations.
# ==============================================================================

# CONFIGURATION
INPUT_FILE = "research_data/ml_ready/training_dataset_v3.csv"
OUTPUT_DIR = "docs/showcase/ghost_hunt"
SENSORS = {
    "sensor-north": {"lat": 60.319555, "lon": 24.830816, "color": "#003f5c", "name": "North"},
    "sensor-east":  {"lat": 60.3621, "lon": 25.3375, "color": "#bc5090", "name": "East"},
    "sensor-west":  {"lat": 60.1478, "lon": 24.5264, "color": "#ffa600", "name": "West"}
}

def load_and_detect_anomalies():
    print(f"👻 Loading dataset: {INPUT_FILE}")
    if not os.path.exists(INPUT_FILE):
        print("❌ Error: Training set not found. Run 'make ml' first.")
        return None

    df = pd.read_csv(INPUT_FILE)
    
    # Select Features
    features = ['lat', 'lon', 'alt', 'ground_speed', 'track', 'rssi']
    X = df[features].fillna(df[features].median())

    print("🤖 Calculating Anomaly Probabilities (Isolation Forest)...")
    # n_jobs=-1 uses all CPU cores
    iso = IsolationForest(n_estimators=100, contamination=0.01, random_state=42, n_jobs=-1)
    
    # 1. Binary Prediction (-1 = Ghost, 1 = Normal)
    df['anomaly'] = iso.fit_predict(X)
    
    # 2. Probability Scoring (Decision Function)
    # The lower the score, the more abnormal.
    # Typical range: -0.5 (Very Anomalous) to 0.5 (Very Normal)
    raw_scores = iso.decision_function(X)
    
    # Normalize negative scores to 0-100% "Ghost Confidence"
    # We only care about anomalies (score < 0)
    # Formula: Map min_score...0 to 100%...0%
    min_score = raw_scores.min()
    df['ghost_score'] = 0.0
    df.loc[raw_scores < 0, 'ghost_score'] = (raw_scores[raw_scores < 0] / min_score) * 100
    
    ghosts = df[df['anomaly'] == -1].copy()
    print(f"🚨 Found {len(ghosts)} Ghosts out of {len(df)} records.")
    
    # Print Top 5 "Most Wanted"
    print("\n👻 TOP 5 HIGHEST CONFIDENCE ANOMALIES:")
    print(ghosts[['hex', 'sensor_id', 'alt', 'ground_speed', 'rssi', 'ghost_score']]
          .sort_values(by='ghost_score', ascending=False).head(5).to_string(index=False))
    print("-" * 60)
    
    return df

def plot_ghost_map(df):
    print("🗺️  Generating 'Probabilistic Ghost Map'...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    plt.figure(figsize=(14, 10))
    
    # 1. Normal Traffic (Background)
    normal = df[df['anomaly'] == 1]
    plt.scatter(normal['lon'], normal['lat'], c='lightgrey', s=1, alpha=0.05, label='Normal Traffic')
    
    # 2. Ghosts (Colored by Severity)
    ghosts = df[df['anomaly'] == -1]
    sc = plt.scatter(ghosts['lon'], ghosts['lat'], 
                     c=ghosts['ghost_score'], cmap='inferno_r', # Darker = Higher Confidence
                     s=30, alpha=0.8, marker='x', label='Anomalies')
    
    # 3. Sensors
    for sid, meta in SENSORS.items():
        plt.scatter(meta['lon'], meta['lat'], c='cyan', marker='^', s=150, edgecolors='black', zorder=10)
        plt.text(meta['lon'], meta['lat'] + 0.02, meta['name'], fontweight='bold', ha='center', fontsize=12)

    plt.colorbar(sc, label='Ghost Confidence Score (%)')
    plt.title(f"Forensic Map: Anomaly Severity Distribution (n={len(ghosts)})", fontsize=16, fontweight='bold')
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.legend(loc='upper right')
    plt.grid(True, alpha=0.3)
    
    plt.savefig(f"{OUTPUT_DIR}/ghost_map_confidence.png", dpi=300)
    plt.close()

def plot_impossible_physics(df):
    print("📉 Generating 'Impossible Physics' Confidence plot...")
    
    ref_lat, ref_lon = 60.3, 24.9
    df['dist_ref'] = np.sqrt((df['lat']-ref_lat)**2 + (df['lon']-ref_lon)**2) * 111
    
    ghosts = df[df['anomaly'] == -1]
    
    fig, ax = plt.subplots(1, 2, figsize=(16, 6))
    
    # Plot 1: Altitude vs Distance (Colored by Confidence)
    sns.scatterplot(data=ghosts, x='dist_ref', y='alt', 
                    hue='ghost_score', palette='inferno_r', size='rssi', sizes=(10, 100),
                    ax=ax[0], alpha=0.7)
    ax[0].set_title("Ghost Altitude vs. Distance (Color=Confidence)")
    ax[0].set_xlabel("Distance from Helsinki (km)")
    ax[0].set_ylabel("Altitude (ft)")
    ax[0].legend(title="Confidence %", loc='upper right')
    
    # Plot 2: Confidence Distribution Histogram
    sns.histplot(ghosts['ghost_score'], kde=True, color='darkred', ax=ax[1])
    ax[1].set_title("Anomaly Confidence Distribution")
    ax[1].set_xlabel("Model Confidence Score (0-100%)")
    ax[1].set_ylabel("Count of Anomalies")
    
    # Stats Annotation
    mean_conf = ghosts['ghost_score'].mean()
    ax[1].axvline(mean_conf, color='black', linestyle='--')
    ax[1].text(mean_conf+2, 50, f"Mean Confidence: {mean_conf:.1f}%", fontsize=12)
    
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/ghost_confidence_stats.png", dpi=300)
    plt.close()

if __name__ == "__main__":
    data = load_and_detect_anomalies()
    if data is not None:
        plot_ghost_map(data)
        plot_impossible_physics(data)
        print(f"✅ Analysis Complete. Check '{OUTPUT_DIR}/' for probabilistic maps.")
