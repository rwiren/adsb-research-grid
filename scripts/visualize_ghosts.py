#!/usr/bin/env python3
# ------------------------------------------------------------------
# [FILE] scripts/visualize_ghosts.py
# [VERSION] 3.0.0 (Renumbered D7-D10)
# ------------------------------------------------------------------

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime
from sklearn.ensemble import IsolationForest

DATA_PATH = Path("research_data/ml_ready/training_dataset_v3.csv")
OUT_DIR = Path("docs/showcase/ghost_hunt")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def visualize():
    if not DATA_PATH.exists(): return
    print(f"👻 Loading dataset: {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    
    # Re-run lightweight ML
    features = ['lat', 'lon', 'alt', 'ground_speed', 'track', 'rssi']
    X = df[features].fillna(df[features].median())
    iso = IsolationForest(n_estimators=100, contamination=0.01, random_state=42)
    df['score'] = iso.fit_predict(X)
    df['confidence'] = iso.decision_function(X)
    ghosts = df[df['score'] == -1]
    
    t_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    plt.style.use('seaborn-v0_8-paper')

    # --- D7: Confidence Stats ---
    print("   🎨 Generating D7 (Confidence Dist)...")
    plt.figure(figsize=(10,6))
    sns.histplot(df['confidence'], bins=50, kde=True, color="green", label="Normal")
    sns.histplot(ghosts['confidence'], bins=50, kde=True, color="red", label="Anomaly")
    plt.title(f"D7: Anomaly Confidence Distribution | Gen: {t_str}")
    plt.legend()
    plt.savefig(OUT_DIR / "D7_Ghost_Confidence.png")
    plt.close()

    # --- D8: Confidence Map ---
    print("   🎨 Generating D8 (Conf Map)...")
    plt.figure(figsize=(10,8))
    plt.scatter(df['lon'], df['lat'], c='lightgray', s=1, alpha=0.1)
    sc = plt.scatter(ghosts['lon'], ghosts['lat'], c=ghosts['confidence'], cmap='inferno', s=5)
    plt.colorbar(sc, label="Anomaly Score")
    plt.title(f"D8: Spatial Confidence Map | Gen: {t_str}")
    plt.savefig(OUT_DIR / "D8_Ghost_Map_Confidence.png")
    plt.close()
    
    # --- D9: Spatial Clusters ---
    print("   🎨 Generating D9 (Spatial Clusters)...")
    plt.figure(figsize=(10,8))
    sns.scatterplot(data=ghosts, x='lon', y='lat', hue='sensor_id', s=10)
    plt.title(f"D9: Ghost Clusters by Sensor | Gen: {t_str}")
    plt.savefig(OUT_DIR / "D9_Ghost_Map_Spatial.png")
    plt.close()

    # --- D10: Physics ---
    print("   🎨 Generating D10 (Physics)...")
    plt.figure(figsize=(10,6))
    sns.scatterplot(data=ghosts, x='ground_speed', y='alt', hue='confidence', palette='viridis', s=10)
    plt.title(f"D10: Impossible Physics | Gen: {t_str}")
    plt.savefig(OUT_DIR / "D10_Ghost_Physics.png")
    plt.close()

    print(f"✅ Analysis Complete. Check '{OUT_DIR}'.")

if __name__ == "__main__":
    visualize()
