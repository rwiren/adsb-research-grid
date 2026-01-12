# 📡 ADS-B Grid Audit: 2026-01-12_1106

**Metadata:** `Git-SHA: 56fe654 | Date: 2026-01-12`

## 1. 📋 Executive Summary
| Metric | Value |
|---|---|
| **Data Start** | `2026-01-11 21:30:45 UTC` |
| **Data End** | `2026-01-12 08:15:26 UTC` |
| **Total Messages** | 708,579 |
| **Unique Aircraft** | 194 |
| **Active Sensors** | 2 |

## 2. 🏥 Data Health Check
|      |   Missing Rows |   Missing % |
|:-----|---------------:|------------:|
| lat  |         443388 |       62.57 |
| lon  |         443388 |       62.57 |
| alt  |         224462 |       31.68 |
| rssi |              0 |        0    |

## 3. 📊 Fleet Performance Matrix
### 3.1 Packet Volume
| sensor_id   |   Packets |   Share % |
|:------------|----------:|----------:|
| sensor-east |    303907 |      42.9 |
| sensor-west |    404672 |      57.1 |

### 3.2 Signal Forensics (RSSI)
| sensor_id   |   Avg RSSI |   Peak Signal |   Noise Floor |   Std Dev |
|:------------|-----------:|--------------:|--------------:|----------:|
| sensor-east |     -32.27 |          -1.8 |         -49.5 |      5.49 |
| sensor-west |     -32.13 |          -2.7 |         -49.5 |      5.31 |

### 3.3 Spatial Coverage
| sensor_id   |   Max Range (km) |   Avg Alt (ft) |   Unique Aircraft |
|:------------|-----------------:|---------------:|------------------:|
| sensor-east |            836   |        24405.2 |               170 |
| sensor-west |            831.8 |        18032.8 |               174 |

## 4. 🖼️ Visual Evidence
![D1](figures/D1_Operational.png)
![D2](figures/D2_Physics.png)
![D3](figures/D3_Spatial.png)
![D4](figures/D4_Forensics.png)

## 5. 📚 Research Data Schema
Comprehensive definition of all collected data fields.

### 5.1 Aircraft Telemetry (`aircraft.json`)
| Field | Unit | Description | Relevance |
| :--- | :--- | :--- | :--- |
| `hex` | 24-bit | Unique ICAO Address | Target ID |
| `flight` | String | Call Sign | Identification |
| `squawk` | Octal | Transponder Code | ATC Assignment |
| `lat`/`lon` | Deg | WGS84 Position | Geolocation |
| `alt_baro` | Feet | Barometric Altitude | Vertical Profile |
| `alt_geom` | Feet | GNSS Altitude | Anti-Spoofing (Check vs Baro) |
| `gs` | Knots | Ground Speed | Kinematics |
| `track` | Deg | True Track | Heading Analysis |
| `baro_rate` | ft/min | Climb/Sink Rate | Vertical Dynamics |
| `nic` | 0-11 | Nav Integrity Category | **Spoofing Indicator (Trust)** |
| `sil` | 0-3 | Source Integrity Level | **Spoofing Indicator (Probability)** |
| `nac_p` | 0-11 | Nav Accuracy Category | **Spoofing Indicator (Precision)** |
| `rc` | Meters | Radius of Containment | Safety Bubble |
| `version` | Int | DO-260 Standard | 0=Old, 2=DO-260B |
| `rssi` | dBFS | Signal Strength | Receiver Proximity |

### 5.2 Hardware Stress (`stats.json`)
| Field | Unit | Description | Criticality |
| :--- | :--- | :--- | :--- |
| `samples_processed` | Raw | Total RF Samples | Throughput |
| `samples_dropped` | Raw | **Buffer Overflows** | **CPU/USB Saturation Warning** |
| `strong_signals` | Count | Signals > -3dBFS | **LNA Overload Warning** |
| `cpu.demod` | ms | CPU time demodulating | Processing Load |
| `cpu.background` | ms | CPU time idle/bg | Overhead |

