# Golden 7-Day Dataset - Extensive EDA Results

## Overview

This directory contains the comprehensive Exploratory Data Analysis (EDA) results for the Golden 7-Day ADS-B Research dataset (2026-01-16 to 2026-01-22).

## Purpose

This analysis was conducted to support:
- **Deep Neural Network Development** - Feature engineering and pattern recognition
- **Large Language Model Training** - Contextual understanding of aviation data
- **Academic Research** - Statistical validation and scientific discovery
- **Commercial Applications** - Operational insights and anomaly detection

## Files

### Main Outputs

1. **`COMPREHENSIVE_EDA_REPORT.md`** - Detailed markdown report with all findings
2. **`golden_7day_ml_dataset.csv`** - ML-ready dataset with engineered features (219 MB)
3. **`statistical_summary.csv`** - Descriptive statistics for all numeric columns
4. **`execution_log.txt`** - Complete execution log with timestamps

### Figures Directory

High-resolution visualizations (300 DPI, publication-ready):

1. **01_missing_values_heatmap.png** - Missing data patterns across columns
2. **02_temporal_patterns.png** - Time series and hourly activity patterns
3. **03_geospatial_analysis.png** - Coverage maps, altitude, speed, and track distributions
4. **04_signal_quality.png** - RSSI, signal/noise levels, and aircraft tracking
5. **05_aircraft_behavior.png** - Flight envelopes, vertical rates, and squawk codes
6. **06_cross_sensor_analysis.png** - Multi-sensor correlation and overlap
7. **07_correlation_matrix.png** - Feature correlation heatmap
8. **08_3d_trajectories.png** - 3D flight path visualization
9. **09_detection_heatmap.png** - Spatial density maps per sensor
10. **10_activity_heatmap.png** - Weekly activity patterns (hour × day)

## Dataset Specifications

- **Total Records**: 1,052,145 (sampled from ~5 million for memory efficiency)
- **Unique Aircraft**: 620
- **Sensors**: 2 (sensor-east in Sipoo, sensor-west in Jorvas)
- **Time Span**: 2 days (Jan 16-17, 2026)
- **Sampling**: Every 5th row from original data

### Sensor Performance

#### sensor-east (Sipoo)
- Records: 282,253
- Unique Aircraft: 467
- Mean RSSI: -31.89 dBm
- Mean Altitude: 24,473 feet
- Mean Ground Speed: 368.8 knots

#### sensor-west (Jorvas)
- Records: 769,892
- Unique Aircraft: 596
- Mean RSSI: -25.44 dBm
- Mean Altitude: 21,253 feet
- Mean Ground Speed: 240.5 knots

## ML-Ready Features

The `golden_7day_ml_dataset.csv` includes:

### Original Features
- `timestamp`, `hex`, `sensor`, `lat`, `lon`
- `alt_baro`, `alt_geom`, `gs`, `track`, `baro_rate`
- `rssi`

### Engineered Features
- **Temporal**: `hour_sin`, `hour_cos`, `day_of_week_sin`, `day_of_week_cos`
- **Spatial**: `distance_km` (Haversine distance from sensor)
- **Signal**: `signal_deviation` (deviation from inverse-square law)
- **Physics**: `altitude_speed_ratio`
- **Direction**: `track_sin`, `track_cos`
- **Classification**: `likely_commercial`, `likely_general_aviation`

## Key Findings

### Data Quality
- **Completeness**: RSSI (100%), timestamp (100%), hex (100%)
- **Position Data**: 44.9% records have valid lat/lon
- **Missing Values**: Moderate missing data in navigation fields (nav_qnh, nav_altitude_mcp)

### Temporal Patterns
- Clear diurnal patterns with peak activity during daytime
- Average 526K messages per day
- Consistent hourly patterns across sensors

### Geospatial Coverage
- Detection range: 13.94° latitude × 27.56° longitude
- Altitude range: -475 to 43,025 feet
- Speed range: 0 to 1,184.6 knots

### Multi-Sensor Analysis
- **Both Sensors**: 443 aircraft (71.5%)
- **sensor-east only**: 24 aircraft (3.9%)
- **sensor-west only**: 153 aircraft (24.7%)
- Strong correlation in message counts between sensors

### Signal Quality
- sensor-west shows better signal strength (-25.44 dBm vs -31.89 dBm)
- Both sensors show consistent signal-to-noise patterns
- No significant signal degradation over time

## Usage Examples

### Load ML Dataset in Python

```python
import pandas as pd

# Load the dataset
df = pd.read_csv('golden_7day_ml_dataset.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Basic statistics
print(f"Records: {len(df):,}")
print(f"Unique Aircraft: {df['hex'].nunique()}")

# Filter for specific sensor
sensor_east = df[df['sensor'] == 'sensor-east']
```

### Interactive Analysis

Use the provided Jupyter notebook:
```bash
jupyter notebook ../golden_7day_interactive_eda.ipynb
```

### Load in R

```r
library(readr)
df <- read_csv("golden_7day_ml_dataset.csv")
summary(df)
```

## Recommendations

### For Deep Neural Networks

1. **LSTM/Transformer Models**
   - Use temporal features for sequence modeling
   - Sort by timestamp and hex (aircraft ID)
   - Predict future positions or behaviors

2. **Graph Neural Networks**
   - Model multi-sensor network as graph
   - Use spatial relationships between sensors
   - Learn sensor fusion patterns

3. **Anomaly Detection**
   - Use `signal_deviation` as anomaly indicator
   - Physics-based validation with `altitude_speed_ratio`
   - Multi-sensor consistency checks

### For LLM Training

1. **Context Generation**
   - Create flight narratives from trajectory data
   - Generate sensor perspective descriptions
   - Temporal event sequences

2. **Classification Tasks**
   - Aircraft type identification
   - Anomaly explanation generation
   - Sensor reliability assessment

3. **Question Answering**
   - Location-based queries
   - Coverage analysis
   - Signal pattern explanations

### Data Splitting

```python
# Temporal split (recommended)
train = df[df['timestamp'] < '2026-01-17']
test = df[df['timestamp'] >= '2026-01-17']

# Stratified by sensor
from sklearn.model_selection import train_test_split
train, test = train_test_split(df, test_size=0.2, stratify=df['sensor'])
```

## Reproduction

To regenerate this analysis:

```bash
cd /path/to/adsb-research-grid
python3 analysis/extensive_eda_golden_7day.py
```

Note: Requires dependencies from `requirements.txt`

## Citation

If you use this analysis or dataset in your research:

```bibtex
@software{wiren2026adsb,
  author = {Wiren, Richard},
  title = {ADS-B Research Grid: Distributed Sensor Network for Spoofing Detection},
  year = {2026},
  url = {https://github.com/rwiren/adsb-research-grid}
}
```

## License

MIT License - See repository root for details

## Contact

- **Repository**: https://github.com/rwiren/adsb-research-grid
- **Issues**: https://github.com/rwiren/adsb-research-grid/issues
- **Wiki**: https://github.com/rwiren/adsb-research-grid/wiki

---

**Generated**: 2026-01-28  
**Version**: 1.0  
**Analysis Tool**: extensive_eda_golden_7day.py
