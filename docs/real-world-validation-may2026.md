# Real-World ADS-B Spoofing Detection — May 15, 2026

## Summary

On May 15, 2026, our distributed ADS-B sensor grid in the Helsinki FIR detected a confirmed spoofing event: four fabricated aircraft tracks injected into 1090 MHz in the eastern Gulf of Finland. A GRU autoencoder trained exclusively on normal traffic detected the primary spoofed track at 4,462× above the anomaly threshold.

To our knowledge, this represents the first reported detection of a confirmed real-world ADS-B spoofing event by an academic sensor network.

## The Event

- **Time**: 05:42–06:18 UTC, May 15, 2026
- **Location**: Eastern Gulf of Finland (~59.65°N, 29.35°E)
- **Spoofed tracks**: 4 fabricated aircraft with Russian ICAO addresses (15xxxx block)
- **Characteristics**: Physically impossible kinematics (500→52 kt instantaneous deceleration), heading snap to ~157°, sequential squawk codes (6624/6625/6626)
- **Confirmation**: 3 of 4 tracks invisible to all other ADS-B receivers globally (OpenSky Network cross-validation)

## Detection Methodology

### Training
- **Data**: Mon–Thu May 11–14, 2026 (4 days of normal traffic)
- **Sequences**: 879,765 (624 aircraft, 3 sensors)
- **Model**: GRU autoencoder with information bottleneck (latent_size=4)
- **Features**: 11 physics-informed engineered features (velocity, displacement, RSSI, distance)
- **Training**: Unsupervised — model learns to reconstruct normal flight patterns only

### Inference
- **Test data**: All 310 aircraft observed on Friday May 15
- **Detection**: Sequences with reconstruction error > threshold τ flagged as anomalous
- **No labeled attack data used** — pure unsupervised anomaly detection

## Results

### Model Comparison

| Configuration | Params | Threshold τ | FP Rate | 151fb6 Detection | Tracks Detected |
|--------------|--------|-------------|---------|-----------------|-----------------|
| h128/l8/3L (research) | 508K | 0.021 | 0.45% | 656× | 2/4 (mean) |
| h128/l4/2L (deployed) | 309K | 0.004 | 0.57% | 4,462× | 2/4 (mean) |
| h256/l4/2L (production) | 1.2M | 0.136 | 0.12% | 51.7× | 1/4 (mean) |

With persistence filtering (k≥3 consecutive above-threshold sequences): **4/4 detected** across all configurations.

### Feature Attribution

97.5% of the detection signal comes from three velocity-based features:
- `velocity_drift_weighted`: 33.5%
- `velocity_error`: 32.2%
- `velocity_calculated`: 31.8%

RSSI and distance features contributed <1% — consistent with the attack mechanism (ADS-B message injection does not alter signal propagation).

### Temporal Pattern

Peak reconstruction error (2,360) occurred at **06:11 UTC** — within the confirmed spoofing window (05:42–06:18 UTC).

## Hardware

| Component | Details | Cost |
|-----------|---------|------|
| Sensor North | Raspberry Pi 4 + FlightAware Blue SDR + u-blox F9P | ~$150 |
| Sensor East | Raspberry Pi 4 + FlightAware Blue SDR | ~$120 |
| Sensor West | Raspberry Pi 4 + FlightAware Blue SDR (antenna broken) | ~$120 |
| Server | VPS (securingskies.eu) | ~$15/mo |
| **Total** | | **<$500** |

## Relationship to Helsinki Airport Closure

On the same morning (01:00–04:00 UTC), Helsinki-Vantaa Airport was closed for a suspected drone threat. These are **operationally distinct events**:

1. **Drone alert**: Low altitude (hundreds of meters), military radar/intelligence, 01:00–04:00 UTC
2. **ADS-B spoofing**: High altitude (FL340–370, 10–11 km), our civilian sensors, 05:42–06:18 UTC

The airport closure served as the contextual trigger that prompted investigation of our sensor logs. The Defence Forces did not respond to our detected spoofing — it occurred 90 minutes after the airport reopened, at a completely different altitude.

## Reproducibility

```bash
# Train model on Mon-Thu
python -m src.pipeline.run_pipeline \
    --config pipeline_config_week2.yaml \
    --feature-set engineered --arch gru \
    --train-slice "2026-05-11:2026-05-14" \
    --test-slice "2026-05-15" \
    --stride 3 --n-trials 50

# Run spoofing detection check (see notebooks/colab_pipeline_v7.ipynb, Cell 8)
```

## References

- Reuters (2026): "Helsinki airport closed after drone threat"
- Politico (2026): "Finland confirms no drones found"
- OpenSky Network: Global ADS-B receiver database (cross-validation source)
- Aireon (2025): Space-based ADS-B surveillance
- ION GNSS+ (2024): Baltic GNSS interference studies
