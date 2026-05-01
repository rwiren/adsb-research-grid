# ADS-B Research Grid - Analysis Directory

## Overview

This directory contains analysis tools and results for the ADS-B Research Grid project.

## Golden 7-Day Dataset - Extensive EDA ⭐

### 🎯 Quick Start

The **Golden 7-Day Dataset** has been comprehensively analyzed for ML/LLM development:

```bash
# Run the automated EDA pipeline
python3 analysis/extensive_eda_golden_7day.py

# Or explore interactively
jupyter notebook analysis/golden_7day_interactive_eda.ipynb
```

### 📂 EDA Results Location

All results are in: **`analysis/golden_7day_eda_results/`**

#### Key Files:
- **`COMPREHENSIVE_EDA_REPORT.md`** - Full analysis report
- **`README.md`** - Detailed usage guide
- **`golden_7day_ml_dataset.csv`** - ML-ready dataset (219MB, gitignored)
- **`statistical_summary.csv`** - Descriptive statistics
- **`figures/`** - 10 publication-ready visualizations

### 🚀 What's Included

#### 1. Automated Analysis Script
`extensive_eda_golden_7day.py` - Complete EDA pipeline:
- Data extraction and cleaning
- 10 analysis stages
- Feature engineering
- Visualization generation
- Report creation

#### 2. Interactive Notebook
`golden_7day_interactive_eda.ipynb` - Jupyter notebook with:
- Step-by-step analysis
- Custom query examples
- Visualization embedding
- ML recommendations

#### 3. Comprehensive Results
`golden_7day_eda_results/` - Analysis outputs:
- ✅ 1,052,145 records analyzed
- ✅ 620 unique aircraft
- ✅ 22 engineered features
- ✅ 10 high-resolution figures
- ✅ Statistical validation

### 📊 Dataset Highlights

| Metric | Value |
|--------|-------|
| **Total Records** | 1,052,145 |
| **Unique Aircraft** | 620 |
| **Sensors** | 2 (east, west) |
| **Time Span** | 2 days |
| **Both Sensors** | 443 aircraft (71.5%) |
| **Geographic Range** | 13.94° × 27.56° |
| **Altitude Range** | -475 to 43,025 ft |
| **Speed Range** | 0 to 1,184.6 knots |

### 🧠 ML/LLM Features

The ML-ready dataset includes:

**Temporal Features:**
- `hour_sin`, `hour_cos` - Cyclic time encoding
- `day_of_week_sin`, `day_of_week_cos` - Day encoding

**Spatial Features:**
- `distance_km` - Haversine distance from sensor
- `lat`, `lon`, `alt_baro` - Position data

**Signal Features:**
- `rssi` - Received signal strength
- `signal_deviation` - Deviation from inverse-square law

**Physics Features:**
- `altitude_speed_ratio` - Flight envelope validation
- `track_sin`, `track_cos` - Direction encoding

**Classification Features:**
- `likely_commercial` - High altitude + speed indicator
- `likely_general_aviation` - Low altitude + speed indicator

### 📈 Visualizations

10 publication-ready figures (300 DPI):

1. **Missing Values Heatmap** - Data completeness
2. **Temporal Patterns** - Time series and hourly activity
3. **Geospatial Analysis** - Coverage, altitude, speed
4. **Signal Quality** - RSSI, SNR, tracking
5. **Aircraft Behavior** - Flight envelopes, rates
6. **Cross-Sensor Analysis** - Multi-sensor correlation
7. **Correlation Matrix** - Feature relationships
8. **3D Trajectories** - Flight path visualization
9. **Detection Heatmap** - Spatial density
10. **Activity Heatmap** - Weekly patterns

### 🎓 Recommendations

#### For Deep Neural Networks:
- **LSTM/Transformers**: Time series forecasting
- **Graph Neural Networks**: Multi-sensor fusion
- **Anomaly Detection**: Signal deviation analysis

#### For LLMs:
- **Context Generation**: Flight narratives
- **Classification**: Aircraft type identification
- **Q&A**: Location and coverage queries

#### For Academic Research:
- **Statistical Validation**: 1M+ records
- **Multi-sensor Studies**: Cross-validation
- **Physics Validation**: Signal propagation

### 📝 Citation

```bibtex
@software{wiren2026adsb,
  author = {Wiren, Richard},
  title = {ADS-B Research Grid: Distributed Sensor Network for Spoofing Detection},
  year = {2026},
  url = {https://github.com/rwiren/adsb-research-grid}
}
```

### 🔗 Links

- **Repository**: https://github.com/rwiren/adsb-research-grid
- **Wiki**: https://github.com/rwiren/adsb-research-grid/wiki
- **Issues**: https://github.com/rwiren/adsb-research-grid/issues

---

## Other Analysis Tools

### Daily Reports
Location: `analysis/daily_reports/`  
Purpose: Automated daily forensic reports

### Archive
Location: `analysis/archive/`  
Purpose: Historical analysis scripts and legacy tools

### Scripts
Various Python analysis scripts for:
- `academic_eda.py` - General forensic reporting
- `ds_pipeline_master.py` - ML pipeline
- `visualize_ghosts.py` - Anomaly visualization
- More in root `scripts/` directory

---

**Last Updated**: 2026-01-28  
**Version**: 1.0  
**License**: MIT
