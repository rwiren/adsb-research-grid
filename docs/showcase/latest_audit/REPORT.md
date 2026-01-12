# 📡 ADS-B Grid Audit: 2026-01-12_1056

**Metadata:** `Git-SHA: e387742 | Date: 2026-01-12`

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
Definition of collected data fields across the ADS-B Research Grid.

### 5.1 Aircraft Intercepts (`*_aircraft_log.csv`)
| Field | Type | Unit | Description |
| :--- | :--- | :--- | :--- |
| `timestamp` | ISO 8601 | UTC | Precise packet arrival time. |
| `hex` | String | Hex | ICAO 24-bit unique airframe address. |
| `lat`/`lon` | Float | Deg | WGS84 Position (Null if Mode-S only). |
| `alt` | Int | Feet | Barometric Altitude. |
| `rssi` | Float | dBFS | Signal Strength (0 to -49.5). |
| `category` | String | Enum | Emitter Category. |

### 5.2 Receiver Performance (`*_stats_log.csv`)
| Field | Type | Description |
| :--- | :--- | :--- |
| `messages` | Int | Total Mode-S messages decoded. |
| `msg_rate` | Float | Messages per second (Hz). |
| `gain_db` | Float | Current Tuner Gain setting. |

### 5.3 Hardware Forensics (`hardware_health.csv`)
| Field | Type | Unit | Description |
| :--- | :--- | :--- | :--- |
| `Temp_C` | Float | C | CPU SoC Temperature. |
| `Throttled_Hex` | Hex | Bitmask | 0x50000 = Under-voltage. |
