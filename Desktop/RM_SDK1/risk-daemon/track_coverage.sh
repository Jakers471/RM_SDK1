#!/bin/bash
# Coverage tracking script - saves history and shows changes

# Detect environment
if [ -d "/mnt/c" ]; then
    PYTHON="/mnt/c/Users/jakers/AppData/Local/Programs/Python/Python313/python.exe"
else
    PYTHON="/c/Users/jakers/AppData/Local/Programs/Python/Python313/python.exe"
fi

# Create history directory if it doesn't exist
mkdir -p reports/coverage_history

# Get current timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Save current coverage if it exists
if [ -f "reports/coverage.json" ]; then
    cp reports/coverage.json "reports/coverage_history/coverage_${TIMESTAMP}_prev.json"
fi

# Run tests with JSON output for comparison
echo "Running tests with coverage tracking..."
$PYTHON -m pytest --cov=src \
    --cov-report=term-missing \
    --cov-report=html:reports/coverage_html \
    --cov-report=json:reports/coverage.json \
    "$@"

# Save test exit code
TEST_EXIT_CODE=$?

# If we have both current and previous coverage, show diff
if [ -f "reports/coverage.json" ] && [ -f "reports/coverage_history/coverage_${TIMESTAMP}_prev.json" ]; then
    echo ""
    echo "=== Coverage Changes ==="
    $PYTHON -c "
import json
import sys

# Load current and previous coverage
with open('reports/coverage.json') as f:
    current = json.load(f)
with open('reports/coverage_history/coverage_${TIMESTAMP}_prev.json') as f:
    previous = json.load(f)

# Get totals
curr_total = current['totals']
prev_total = previous['totals']

# Calculate changes
curr_percent = curr_total['percent_covered']
prev_percent = prev_total['percent_covered']
change = curr_percent - prev_percent

# Show summary
print(f'Previous Coverage: {prev_percent:.2f}%')
print(f'Current Coverage:  {curr_percent:.2f}%')
if change > 0:
    print(f'Change: UP +{change:.2f}% [IMPROVED]')
elif change < 0:
    print(f'Change: DOWN {change:.2f}% [WARNING]')
else:
    print(f'Change: No change')

print(f'')
print(f'Lines: {curr_total[\"num_statements\"]} total, {curr_total[\"missing_lines\"]} missing')
print(f'Previously: {prev_total[\"num_statements\"]} total, {prev_total[\"missing_lines\"]} missing')

# Show file-level changes
curr_files = current['files']
prev_files = previous['files']

changes = []
for file, data in curr_files.items():
    if file in prev_files:
        curr_pct = data['summary']['percent_covered']
        prev_pct = prev_files[file]['summary']['percent_covered']
        if curr_pct != prev_pct:
            changes.append((file.replace('src/', ''), prev_pct, curr_pct))

# New files
for file in curr_files:
    if file not in prev_files:
        changes.append((file.replace('src/', ''), 0, curr_files[file]['summary']['percent_covered']))

if changes:
    print(f'\\nFile Changes:')
    for file, prev, curr in sorted(changes, key=lambda x: x[2] - x[1], reverse=True):
        diff = curr - prev
        symbol = '+' if diff > 0 else '-'
        print(f'  {symbol} {file}: {prev:.1f}% -> {curr:.1f}% ({diff:+.1f}%)')
"
fi

# Save current as timestamped backup
if [ -f "reports/coverage.json" ]; then
    cp reports/coverage.json "reports/coverage_history/coverage_${TIMESTAMP}.json"

    # Keep only last 10 coverage reports
    cd reports/coverage_history
    ls -t coverage_*.json | tail -n +21 | xargs -r rm
    cd ../..
fi

# Save a summary log
echo "${TIMESTAMP}: Coverage run completed" >> reports/coverage_history/history.log

exit $TEST_EXIT_CODE