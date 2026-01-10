# PROJECT MASTER FILE: ADS-B Spoofing Data Collection
**Version:** 0.4.0
**Date:** 2026-01-09
**Target Node:** `sensor-north`
**OS:** Raspberry Pi OS Lite (64-bit)

## 1. Scientific Objective
To capture raw GNSS and ADS-B signal data. Specifically, we require high-precision Time-of-Arrival (ToA) timestamps. This necessitates running the GPS UART at **230400 baud** to reduce serial transmission latency and jitter.

## 2. Infrastructure Changes (v0.4.0)
* **Architecture:** Migrated from BalenaOS (Container-first) to Raspberry Pi OS Lite (Systemd-first) to gain direct hardware control.
* **GPS Logic:** Implemented a "Two-Stage Handshake" in `gps_hardware_init.sh`:
    1.  Initialize at **38400** (Safe Mode) to flush buffers.
    2.  Escalate to **230400** (Target Mode) for data collection.
* **Boot Logic:** Modified `cmdline.txt` to remove the serial console, preventing OS login prompts from corrupting the NMEA stream.

## 3. Directory Structure
project-root/
├── Makefile                        # Execution wrapper
├── ansible/
│   ├── site.yml                    # Main Playbook
│   ├── inventory/
│   │   └── hosts.ini               # Node IP definitions
│   └── roles/
│       └── sensor_north/
│           ├── tasks/
│           │   ├── main.yml        # Task flow controller
│           │   ├── configure_boot.yml
│           │   └── configure_gps.yml
│           ├── files/
│           │   ├── gps_hardware_init.sh
│           │   └── gps-init.service
│           └── templates/
│               └── gpsd.default.j2
