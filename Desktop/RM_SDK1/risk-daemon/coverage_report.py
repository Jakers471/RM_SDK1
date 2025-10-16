#!/usr/bin/env python3
# Can also run with: /mnt/c/Users/jakers/AppData/Local/Programs/Python/Python313/python.exe coverage_report.py
"""
Coverage Report Generator - Shows detailed coverage changes and trends
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

def load_coverage_data(filepath: str) -> Dict:
    """Load coverage JSON data."""
    with open(filepath) as f:
        return json.load(f)

def get_coverage_history() -> List[Tuple[str, float]]:
    """Get historical coverage percentages."""
    history_dir = Path("reports/coverage_history")
    if not history_dir.exists():
        return []

    history = []
    for file in sorted(history_dir.glob("coverage_*.json")):
        if "_prev" not in file.name:
            timestamp = file.stem.replace("coverage_", "")
            data = load_coverage_data(file)
            percent = data['totals']['percent_covered']
            history.append((timestamp, percent))

    return history[-10:]  # Last 10 runs

def format_timestamp(timestamp: str) -> str:
    """Format timestamp for display."""
    try:
        dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return timestamp

def main():
    """Generate coverage report with history."""

    # Check if coverage.json exists
    if not Path("reports/coverage.json").exists():
        print("No coverage data found. Run tests with coverage first!")
        return

    current = load_coverage_data("reports/coverage.json")
    curr_total = current['totals']

    print("=" * 60)
    print("COVERAGE REPORT")
    print("=" * 60)
    print(f"\nCurrent Coverage: {curr_total['percent_covered']:.2f}%")
    print(f"Lines Covered: {curr_total['num_statements'] - curr_total['missing_lines']}/{curr_total['num_statements']}")
    print(f"Missing Lines: {curr_total['missing_lines']}")

    # Show history trend
    history = get_coverage_history()
    if history:
        print("\n" + "=" * 60)
        print("COVERAGE TREND (Last {} runs)".format(len(history)))
        print("=" * 60)

        for timestamp, percent in history:
            formatted_time = format_timestamp(timestamp)
            bar_length = int(percent / 2)  # Scale to 50 chars
            bar = "#" * bar_length + "-" * (50 - bar_length)
            print(f"{formatted_time}: {bar} {percent:.1f}%")

        # Show trend
        if len(history) > 1:
            first_percent = history[0][1]
            last_percent = history[-1][1]
            trend = last_percent - first_percent
            if trend > 0:
                print(f"\nTrend: ↑ +{trend:.2f}% improvement over {len(history)} runs")
            elif trend < 0:
                print(f"\nTrend: ↓ {trend:.2f}% decrease over {len(history)} runs")
            else:
                print(f"\nTrend: No change over {len(history)} runs")

    # Show uncovered files
    print("\n" + "=" * 60)
    print("FILES WITH LOWEST COVERAGE")
    print("=" * 60)

    files = [(f.replace('src/', ''), d['summary']['percent_covered'])
             for f, d in current['files'].items()]
    files.sort(key=lambda x: x[1])

    for file, percent in files[:5]:
        if percent < 100:
            print(f"  {percent:5.1f}% - {file}")

    # Show completely uncovered files
    uncovered = [f for f, p in files if p == 0]
    if uncovered:
        print("\n⚠️  Completely Uncovered Files:")
        for file in uncovered:
            print(f"  - {file}")

    print("\n" + "=" * 60)
    print("Run './track_coverage.sh' to update coverage with tracking")
    print("View HTML report: reports/coverage_html/index.html")
    print("=" * 60)

if __name__ == "__main__":
    main()