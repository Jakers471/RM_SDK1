#!/bin/bash
# Convenience script to run pytest with coverage

# Detect if we're in WSL or Git Bash
if [ -d "/mnt/c" ]; then
    # WSL path
    PYTHON="/mnt/c/Users/jakers/AppData/Local/Programs/Python/Python313/python.exe"
else
    # Git Bash path
    PYTHON="/c/Users/jakers/AppData/Local/Programs/Python/Python313/python.exe"
fi

# Run pytest with coverage via python -m pytest
$PYTHON -m pytest --cov=src --cov-report=term-missing --cov-report=html:reports/coverage_html "$@"
