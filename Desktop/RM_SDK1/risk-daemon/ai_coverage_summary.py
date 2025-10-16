#!/usr/bin/env python3
"""
AI Coverage Summary - Extracts key coverage info for AI/debugger analysis
Point your AI debugger to: reports/coverage.json
"""
import json
from pathlib import Path

def get_coverage_summary():
    """Extract key metrics for AI analysis."""

    coverage_file = Path("reports/coverage.json")
    if not coverage_file.exists():
        return {"error": "No coverage data. Run ./track_coverage.sh first"}

    with open(coverage_file) as f:
        data = json.load(f)

    totals = data['totals']
    files = data['files']

    # Find problem areas
    low_coverage = []
    uncovered = []

    for filepath, filedata in files.items():
        percent = filedata['summary']['percent_covered']
        missing = filedata['summary']['missing_lines']

        if percent == 0 and missing > 0:
            uncovered.append({
                "file": filepath,
                "missing_lines": missing
            })
        elif percent < 80:
            low_coverage.append({
                "file": filepath,
                "coverage": percent,
                "missing_lines": missing,
                "missing_line_numbers": filedata.get('missing_lines', [])
            })

    # Sort by coverage (lowest first)
    low_coverage.sort(key=lambda x: x['coverage'])

    summary = {
        "overall_coverage": totals['percent_covered'],
        "total_lines": totals['num_statements'],
        "covered_lines": totals['num_statements'] - totals['missing_lines'],
        "missing_lines": totals['missing_lines'],
        "files_below_80_percent": low_coverage,
        "completely_uncovered_files": uncovered,
        "recommendation": get_recommendation(totals['percent_covered'], low_coverage)
    }

    return summary

def get_recommendation(coverage, low_files):
    """Get AI-friendly recommendations."""
    if coverage >= 90:
        return "Excellent coverage. Focus on edge cases."
    elif coverage >= 80:
        return f"Good coverage. Improve {len(low_files)} files below 80%."
    elif coverage >= 70:
        return f"Moderate coverage. Priority: {low_files[0]['file'] if low_files else 'N/A'}"
    else:
        return "Low coverage. Significant testing needed."

def main():
    """Generate AI-readable summary."""
    summary = get_coverage_summary()

    # Output as JSON for easy parsing
    print(json.dumps(summary, indent=2))

    # Also save to file for AI access
    with open("reports/ai_coverage_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("\nSummary saved to: reports/ai_coverage_summary.json")

if __name__ == "__main__":
    main()