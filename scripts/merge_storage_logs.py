#!/usr/bin/env python3
import glob
import os

# Configuration
OUTPUT_FILE = "storage_history.csv"
SEARCH_PATTERN = "research_data/**/storage_history.csv"

def main():
    print(f"🔍 Searching for log files in: {SEARCH_PATTERN}")
    files = glob.glob(SEARCH_PATTERN, recursive=True)
    print(f"📂 Found {len(files)} files to merge.")

    # Sort files to keep data chronological (optional but nice)
    files.sort()

    count_new_format = 0
    count_total_lines = 0

    with open(OUTPUT_FILE, "w") as out:
        # 1. Write the correct header for the plotting script
        out.write("timestamp,node_name,disk_used_kb,recording_size_kb\n")
        
        # 2. Loop through every downloaded log file
        for f in files:
            try:
                with open(f, "r") as infile:
                    for line in infile:
                        # Only grab data lines (starting with the year 20..)
                        if line.strip().startswith("20"):
                            out.write(line)
                            count_total_lines += 1
                            if "sensor-" in line:
                                count_new_format += 1
            except Exception as e:
                print(f"❌ Error reading {f}: {e}")

    print("-" * 40)
    print(f"✅ Merge Complete.")
    print(f"📊 Total Data Points: {count_total_lines}")
    print(f"✨ New Format Points: {count_new_format} (These have 'sensor-name')")
    
    if count_new_format == 0:
        print("⚠️ WARNING: No data with 'sensor-name' found. Check 'make fetch' results.")
    else:
        print("🚀 Ready to plot!")

if __name__ == "__main__":
    main()
