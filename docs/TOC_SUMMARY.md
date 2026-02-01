# Summary: Table of Contents for Science Run Wiki Page

## What Was Requested
The user requested a Table of Contents (TOC) suggestion for the Science Run wiki page at:
https://github.com/rwiren/adsb-research-grid/wiki/Science-Run-(Raw-I-Q-Data-Capture)

## What Was Delivered

### 1. Comprehensive TOC Structure
A professionally formatted Table of Contents has been created with:
- **17 main sections** covering all content in the wiki page
- **6 subsections** for detailed topics
- **Hierarchical organization** with proper indentation
- **GitHub anchor links** for easy navigation
- **Emoji icon** (📋) for visual consistency with the main README

### 2. Files Created

#### `docs/WIKI_TOC_SUGGESTION.md`
- Complete documentation of the suggested TOC
- Instructions on how to apply it to the wiki
- Benefits and rationale for the structure
- Can be directly referenced when updating the wiki

#### `docs/Science-Run-(Raw-I-Q-Data-Capture)-WITH-TOC.md`
- Full copy of the wiki page with the TOC already integrated
- Shows the exact placement and formatting
- Can be used as a reference or directly copied to the wiki

## TOC Structure Overview

```
📋 Table of Contents
├── 1. Objective: TDOA Localization
├── 2. The Problem: Decoded vs. Raw Data
├── 3. The Solution: Raw I/Q Recording
│   └── Methodology: Cross-Correlation
├── 4. Technical Constraints: The "Data Tsunami"
│   ├── The Math
│   └── Data Comparison
├── 5. Operational Strategy: "Store-and-Forward"
├── 6. Network Performance Benchmark (2026-02-01)
├── 7. TDOA Synchronization Results (2026-02-01)
├── 8. Visual Verification (Signal Alignment)
├── 9. Hyperbolic Localization Proof (The Map)
├── 10. Calibration Constants (Derived 2026-02-01)
├── 11. Inverse Multilateration (Reverse Engineering Experiment)
├── 12. The "Drift" Discovery (System Heartbeat)
├── 13. Final Validation: Triangulation Geometry
├── 14. Live Network Topology
├── 15. Hardware Considerations: RTC vs. GNSS
│   ├── 15.1 The Role of DS3231 (TCXO RTC)
│   └── 15.2 The Role of GNSS PPS (The Anchor)
├── 16. Final Conclusion
└── 17. Acknowledgements
```

## How to Apply to Wiki

### Option 1: Direct Web Edit
1. Go to https://github.com/rwiren/adsb-research-grid/wiki/Science-Run-(Raw-I-Q-Data-Capture)
2. Click the "Edit" button
3. Copy the TOC from `docs/WIKI_TOC_SUGGESTION.md`
4. Paste it right after the title (line 2) and before "## 1. Objective: TDOA Localization"
5. Save the page

### Option 2: Git Clone Method
1. Clone the wiki: `git clone https://github.com/rwiren/adsb-research-grid.wiki.git`
2. Open `Science-Run-(Raw-I-Q-Data-Capture).md`
3. Copy the content from `docs/Science-Run-(Raw-I-Q-Data-Capture)-WITH-TOC.md`
4. Commit and push: `git commit -am "docs: Add Table of Contents" && git push`

## Benefits

1. **Improved Navigation**: Jump directly to any section with a single click
2. **Better Overview**: See the full document structure at a glance
3. **Professional Appearance**: Matches best practices for technical documentation
4. **Enhanced Usability**: Critical for a 224-line document with complex topics
5. **Consistency**: Uses the same 📋 emoji as the main README.md TOC

## Technical Details

- All anchor links follow GitHub's automatic header ID generation
- Subsections use proper indentation (3 spaces for nested items)
- Links are lowercase with hyphens replacing spaces
- Special characters in headers are handled correctly (parentheses, colons)
- Horizontal rule (`---`) separates TOC from content for visual clarity
