# ADS-B Data Exploration - February 3, 2026

## Overview

This document describes the comprehensive data exploration performed on the 8-hour ADS-B harvest data from February 3, 2026.

## Quick Access

📊 **View Full Report:** [analysis/feb03_exploration/EXPLORATION_REPORT.html](analysis/feb03_exploration/EXPLORATION_REPORT.html)

📖 **Detailed Documentation:** [analysis/feb03_exploration/README.md](analysis/feb03_exploration/README.md)

📝 **Executive Summary:** [analysis/feb03_exploration/SUMMARY.md](analysis/feb03_exploration/SUMMARY.md)

## What Was Done

A comprehensive exploratory data analysis (EDA) was performed on 8 hours of ADS-B data collected from three distributed sensor nodes:

### Data Analyzed
- **Aircraft tracking data:** ~1.5M observations from north, east, and west sensors
- **Hardware telemetry:** CPU temperature, clock speeds, uptime
- **GNSS positioning data:** Satellite counts, position stability, fix quality
- **Statistical summaries:** Message rates, signal levels, coverage metrics

### Visualizations Generated (20 Total)

#### Temporal Analysis
1. Message rates and aircraft tracking over time
2. Hourly activity patterns

#### Spatial Analysis
3. Aircraft position coverage heatmaps (2D histograms)
4. Altitude distributions
5. Ground speed vs altitude with RSSI overlay

#### Signal Quality
6. RSSI distributions
7. Signal and noise levels over time
8. SNR comparison across sensors

#### Hardware Health
9. CPU temperature monitoring over time
10. Temperature distribution comparison
11. Sample drops (data loss indicators)

#### GNSS Quality
12. Satellite count tracking
13. Position stability (lat/lon variance)
14. Altitude stability

#### Multi-Sensor Comparison
15. Unique aircraft detected per sensor
16. Message rate comparison
17. Geographic coverage comparison

#### Advanced Correlations
18. Distance vs RSSI (signal decay analysis)
19. Aircraft detection overlap
20. Peak signal vs maximum detection distance

## Key Findings

### Performance Metrics
- **Signal-to-Noise Ratio:** 12-26 dB (excellent quality)
- **Detection Range:** Up to 378 km maximum
- **CPU Temperature:** 37-46°C (within safe limits)
- **GNSS Accuracy:** 12+ satellites, sub-meter stability

### Research Implications
- Multi-sensor coverage enables robust cross-validation
- Signal characteristics follow expected physical models
- Hardware stability supports continuous data collection
- GNSS performance suitable for precise multilateration

## How to Run

```bash
# Install dependencies
pip3 install -r requirements.txt

# Run the analysis script
python3 analysis/explore_harvest_feb03.py

# View the HTML report
open analysis/feb03_exploration/EXPLORATION_REPORT.html
```

## Files Structure

```
analysis/
├── explore_harvest_feb03.py              # Main analysis script
└── feb03_exploration/                     # Output directory
    ├── EXPLORATION_REPORT.html            # Interactive HTML report
    ├── README.md                          # Detailed documentation
    ├── SUMMARY.md                         # Executive summary
    ├── 01_temporal_message_rates.png      # Visualization 1
    ├── 02_hourly_activity.png             # Visualization 2
    └── ... (18 more plots)                # Visualizations 3-20
```

## Technical Stack

- **Python 3.12+**
- **pandas 2.3.3** - Data manipulation
- **matplotlib 3.9.4** - Plotting
- **seaborn 0.13.2** - Statistical visualization
- **numpy 2.0.2** - Numerical operations

## Applications

This analysis supports:
1. Understanding normal ADS-B traffic patterns
2. Validating sensor grid performance
3. Establishing baselines for anomaly detection
4. Supporting machine learning model development
5. Identifying data quality issues

## Next Steps

Recommended follow-up analysis:
1. Time-series anomaly detection on aircraft trajectories
2. Multi-sensor cross-validation for specific aircraft
3. Physics-informed validation of flight envelopes
4. Training dataset generation for ML classifiers

---

**Generated:** February 3, 2026  
**Repository:** rwiren/adsb-research-grid  
**License:** MIT
