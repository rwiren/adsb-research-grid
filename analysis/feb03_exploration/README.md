# ADS-B Data Exploration - February 3, 2026 (8-Hour Harvest)

## Overview
This directory contains a comprehensive exploratory data analysis (EDA) of the 8-hour ADS-B data harvest collected on February 3, 2026, from the distributed sensor grid.

**Dataset:** `ADSB_Harvest_8h_Feb03.zip`

## Data Sources
The analysis includes data from three sensor nodes:
- **NORTH:** Primary reference node with Stratum-1 timing
- **EAST:** Remote node in Sibbo
- **WEST:** Remote node in Jorvas

Each sensor provided:
- Aircraft tracking data (positions, speeds, altitudes, RSSI)
- Hardware telemetry (CPU temperature, clock speed, throttling status)
- GNSS positioning data (location, satellite count, fix quality)
- Statistical summaries (message rates, signal levels, coverage)

## Key Findings

### Multi-Sensor Performance
- **Total Unique Aircraft Detected:** 
  - North: 148 aircraft
  - East: 176 aircraft  
  - West: 162 aircraft
- **Data Collection Duration:**
  - North: ~4 hours
  - East: ~8.7 hours
  - West: ~12.7 hours

### Signal Quality
- **Average Signal-to-Noise Ratios (SNR):**
  - North: ~26 dB (best performance)
  - East: ~19 dB
  - West: ~12 dB
- Signal quality follows expected inverse-square law decay with distance
- Strong correlation between RSSI and distance from sensor

### Hardware Stability
- **CPU Temperatures:**
  - East: 37.4°C - 45.7°C (avg: 41.3°C)
  - North & West: Temperature data not available in this dataset
- No throttling events observed
- Consistent message processing rates maintained

### GNSS Performance
- **Average Satellite Count:** 12 satellites across all sensors
- **Position Stability:** Very low standard deviation in lat/lon
- **Fix Types:** Primarily high-quality 3D fixes (Type 4)
- Excellent positioning accuracy for multilateration algorithms

## Generated Visualizations

### Temporal Analysis (Plots 1-2)
1. **Message Rates Over Time:** Shows message ingestion rates and number of aircraft tracked over the 8-hour period
2. **Hourly Activity:** Aircraft detection patterns by hour of day

### Spatial Analysis (Plots 3-5)
3. **Coverage Heatmaps:** 2D histograms showing aircraft position density
4. **Altitude Distribution:** Flight level distributions for each sensor
5. **Speed vs Altitude:** Correlation between ground speed and altitude with RSSI overlay

### Signal Quality (Plots 6-8)
6. **RSSI Distribution:** Received signal strength histograms
7. **Signal/Noise Temporal:** Signal and noise levels tracked over time
8. **SNR Comparison:** Box plots comparing signal-to-noise ratios across sensors

### Hardware Health (Plots 9-11)
9. **CPU Temperature:** Temperature trends over collection period
10. **Temperature Distribution:** Comparative temperature histograms
11. **Sample Drops:** Data loss indicators over time

### GNSS Quality (Plots 12-14)
12. **Satellite Count:** Number of tracked satellites over time
13. **Position Stability:** Latitude and longitude variance analysis
14. **Altitude Stability:** GNSS height measurements over time

### Multi-Sensor Comparison (Plots 15-17)
15. **Unique Aircraft:** Bar chart comparing aircraft detection counts
16. **Message Rates:** Average message processing rates comparison
17. **Coverage Area:** Geographic coverage range comparison

### Advanced Correlations (Plots 18-20)
18. **Distance vs RSSI:** Signal decay analysis with trend lines
19. **Aircraft Overlap:** Detection overlap between sensors
20. **Peak Signal vs Distance:** Maximum detection range analysis

## Files in This Directory
- `EXPLORATION_REPORT.html` - Comprehensive HTML report with all findings
- `01_temporal_message_rates.png` through `20_peak_signal_vs_distance.png` - Individual plot files
- `README.md` - This file

## How to View
Open `EXPLORATION_REPORT.html` in any web browser to view the complete interactive report with all visualizations and statistics.

## Analysis Script
Generated using: `/home/runner/work/adsb-research-grid/adsb-research-grid/analysis/explore_harvest_feb03.py`

## Technical Details
- **Analysis Date:** February 3, 2026
- **Total Records Processed:** ~1.5 million aircraft observations
- **Processing Time:** ~3 minutes
- **Dependencies:** pandas, matplotlib, seaborn, numpy

## Observations for Future Research

### Spoofing Detection Implications
1. **Multi-Sensor Validation:** The significant overlap in detected aircraft across sensors enables cross-validation for spoofing detection
2. **Signal Consistency:** Strong RSSI-distance correlation can help identify anomalous signals
3. **GNSS Stability:** Low position variance confirms sensor positioning accuracy for TDOA/MLAT algorithms

### Recommended Follow-Up Analysis
1. Investigate the maximum distance values (>300,000 km) which appear to be data anomalies
2. Analyze aircraft that were detected by all three sensors for trajectory validation
3. Perform time-series analysis on aircraft that exhibited unusual RSSI patterns
4. Cross-reference with known flight schedules to identify any anomalous aircraft IDs

---
**Report Generated:** February 3, 2026  
**Repository:** rwiren/adsb-research-grid  
**License:** MIT
