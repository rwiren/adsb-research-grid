#!/usr/bin/env python3
# ==============================================================================
# 📂 File: scripts/analyze_storage.py
# Version: 0.4.4
# Date: 2026-01-08
# Description: Calculates data growth rates (MB/hr). Handles missing/empty data safely.
# ==============================================================================

import csv
import sys
from datetime import datetime
import os

def safe_int(value):
    """Safely converts a string to int, returning 0 if empty or invalid."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0

def analyze_node(node_name, log_dir):
    history_file = os.path.join(log_dir, "storage_history.csv")
    
    if not os.path.exists(history_file):
        print(f"⚠️  {node_name}: No history file found yet.")
        return

    print(f"\n📊 ANALYSIS: {node_name.upper()}")
    print("-" * 40)

    data = []
    try:
        with open(history_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Filter out rows where timestamp might be empty
                if row.get('timestamp'):
                    data.append(row)
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    if not data:
        print("ℹ️  History file is empty.")
        return

    if len(data) < 2:
        print("ℹ️  Not enough data points yet. Run 'make check' again in 1 hour.")
        # Use safe_int to prevent crashing on empty strings
        last_size_kb = safe_int(data[-1].get('recording_size_kb', 0))
        print(f"   Current Size: {last_size_kb / 1024:.2f} MB")
        return

    # Calculate Growth
    first = data[0]
    last = data[-1]
    
    try:
        t1 = datetime.fromisoformat(first['timestamp'])
        t2 = datetime.fromisoformat(last['timestamp'])
        duration_hours = (t2 - t1).total_seconds() / 3600

        s1 = safe_int(first.get('recording_size_kb', 0))
        s2 = safe_int(last.get('recording_size_kb', 0))
        growth_kb = s2 - s1
        
        rate_mb_hr = 0
        projected_gb_day = 0

        if duration_hours > 0:
            rate_mb_hr = (growth_kb / 1024) / duration_hours
            projected_gb_day = (rate_mb_hr * 24) / 1024

        print(f"📅 Time Window:   {duration_hours:.2f} hours")
        print(f"📈 Data Added:    {growth_kb / 1024:.2f} MB")
        print(f"🚀 Growth Rate:   {rate_mb_hr:.2f} MB/hour")
        print(f"🔮 24h Forecast:  {projected_gb_day:.2f} GB/day")
    
    except Exception as calculation_error:
        print(f"⚠️  Calculation Error: {calculation_error}")
    
    print("-" * 40)

if __name__ == "__main__":
    # Scan the logs directory for all nodes
    # Looks for data in research_data/logs/ (relative to project root)
    base_dir = "research_data/logs"
    today = datetime.now().strftime("%Y-%m-%d")
    
    print(f"🔍 Analyzing fetched data for date: {today}")
    
    if os.path.exists(base_dir):
        # Iterate over every node folder found (north, west, etc.)
        nodes_found = False
        for node in os.listdir(base_dir):
            node_path = os.path.join(base_dir, node, today)
            if os.path.exists(node_path):
                nodes_found = True
                analyze_node(node, node_path)
        
        if not nodes_found:
             print("❌ No logs found for today. Did you run 'make fetch'?")
    else:
        print(f"❌ '{base_dir}' directory not found.")
