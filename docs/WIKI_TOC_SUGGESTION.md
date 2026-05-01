# Table of Contents Suggestion for Science Run Wiki Page

## Overview
This document contains the suggested Table of Contents (TOC) for the Science Run (Raw I/Q Data Capture) wiki page.

**Wiki Page URL:** https://github.com/rwiren/adsb-research-grid/wiki/Science-Run-(Raw-I-Q-Data-Capture)

## Suggested TOC

The following Table of Contents should be added right after the main title and before Section 1:

```markdown
## 📋 Table of Contents
1. [Objective: TDOA Localization](#1-objective-tdoa-localization)
2. [The Problem: Decoded vs. Raw Data](#2-the-problem-decoded-vs-raw-data)
3. [The Solution: Raw I/Q Recording](#3-the-solution-raw-iq-recording)
   - [Methodology: Cross-Correlation](#methodology-cross-correlation)
4. [Technical Constraints: The "Data Tsunami"](#4-technical-constraints-the-data-tsunami)
   - [The Math](#the-math)
   - [Data Comparison](#data-comparison)
5. [Operational Strategy: "Store-and-Forward"](#5-operational-strategy-store-and-forward)
6. [Network Performance Benchmark (2026-02-01)](#6-network-performance-benchmark-2026-02-01)
7. [TDOA Synchronization Results (2026-02-01)](#7-tdoa-synchronization-results-2026-02-01)
8. [Visual Verification (Signal Alignment)](#8-visual-verification-signal-alignment)
9. [Hyperbolic Localization Proof (The Map)](#9-hyperbolic-localization-proof-the-map)
10. [Calibration Constants (Derived 2026-02-01)](#10-calibration-constants-derived-2026-02-01)
11. [Inverse Multilateration (Reverse Engineering Experiment)](#11-inverse-multilateration-reverse-engineering-experiment)
12. [The "Drift" Discovery (System Heartbeat)](#12-the-drift-discovery-system-heartbeat)
13. [Final Validation: Triangulation Geometry](#13-final-validation-triangulation-geometry)
14. [Live Network Topology](#14-live-network-topology)
15. [Hardware Considerations: RTC vs. GNSS](#15-hardware-considerations-rtc-vs-gnss)
    - [15.1 The Role of DS3231 (TCXO RTC)](#151-the-role-of-ds3231-tcxo-rtc)
    - [15.2 The Role of GNSS PPS (The Anchor)](#152-the-role-of-gnss-pps-the-anchor)
16. [Final Conclusion](#16-final-conclusion)
17. [Acknowledgements](#17-acknowledgements)

---
```

## How to Apply

Since GitHub Wiki pages are managed through a separate git repository, the TOC should be added manually by:

1. Navigating to the wiki repository: `https://github.com/rwiren/adsb-research-grid.wiki.git`
2. Cloning the wiki repo: `git clone https://github.com/rwiren/adsb-research-grid.wiki.git`
3. Opening the file `Science-Run-(Raw-I-Q-Data-Capture).md`
4. Adding the TOC section right after the title (line 2) and before Section 1
5. Committing and pushing the changes

Alternatively, you can edit the page directly through the GitHub web interface:
1. Go to https://github.com/rwiren/adsb-research-grid/wiki/Science-Run-(Raw-I-Q-Data-Capture)
2. Click "Edit" button
3. Add the TOC at the beginning
4. Save changes

## Benefits of Adding TOC

1. **Better Navigation**: Users can quickly jump to specific sections
2. **Overview**: Provides a clear structure of the document at a glance
3. **Professional Appearance**: Makes the wiki page look more organized and polished
4. **Improved Usability**: Especially helpful for long technical documents like this one (17 sections)

## Structure Details

The TOC includes:
- **17 main sections** covering the entire Science Run documentation
- **Subsections** for detailed topics (Cross-Correlation, hardware comparisons, etc.)
- **GitHub anchor links** that match the exact section headings
- **Emoji icon** (📋) for visual appeal and consistency with main README
- **Hierarchical organization** with proper indentation for subsections
