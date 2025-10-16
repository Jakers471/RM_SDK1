# Risk Daemon Makefile - Simple commands for everything
# Usage: make test, make coverage, make help, etc.

# Detect Python path
ifeq ($(wildcard /mnt/c/.*),)
    PYTHON := /c/Users/jakers/AppData/Local/Programs/Python/Python313/python.exe
else
    PYTHON := /mnt/c/Users/jakers/AppData/Local/Programs/Python/Python313/python.exe
endif

.PHONY: help test coverage quick p0 report view clean menu

# Default target - show help
help:
	@echo "╔════════════════════════════════════════════════════╗"
	@echo "║          RISK DAEMON - QUICK COMMANDS              ║"
	@echo "╚════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Common Commands:"
	@echo "  make test      → Run all tests with coverage"
	@echo "  make quick     → Run only passing tests"
	@echo "  make failed    → Run only failing tests"
	@echo "  make p0        → Run priority 0 tests"
	@echo ""
	@echo "Coverage Commands:"
	@echo "  make coverage  → Generate coverage with tracking"
	@echo "  make report    → Show coverage summary"
	@echo "  make view      → Open HTML report in browser"
	@echo "  make ai        → Generate AI analysis"
	@echo ""
	@echo "Utility Commands:"
	@echo "  make clean     → Clear all cache files"
	@echo "  make menu      → Interactive menu"
	@echo "  make help      → Show this help"
	@echo ""

# Main test command - runs everything
test:
	@echo "Running all tests with coverage..."
	@$(PYTHON) -m pytest --cov=src --cov-report=term-missing --cov-report=html:reports/coverage_html -v

# Quick test - only passing
quick:
	@echo "Running quick tests (likely to pass)..."
	@$(PYTHON) -m pytest -x --lf --ff -v

# Run only failing tests
failed:
	@echo "Running failing tests..."
	@$(PYTHON) -m pytest --lf -v

# Priority 0 tests
p0:
	@echo "Running P0 priority tests..."
	@$(PYTHON) -m pytest -m p0 --cov=src --cov-report=term-missing -v

# Coverage with tracking
coverage:
	@echo "Running tests with coverage tracking..."
	@./track_coverage.sh

# Show coverage report
report:
	@echo "Coverage Report:"
	@$(PYTHON) coverage_report.py

# Open HTML coverage
view:
	@echo "Opening coverage report..."
	@./view

# Generate AI summary
ai:
	@echo "Generating AI coverage summary..."
	@$(PYTHON) ai_coverage_summary.py
	@echo "Summary saved to: reports/ai_coverage_summary.json"

# Clean cache files
clean:
	@echo "Cleaning cache files..."
	@rm -rf .pytest_cache __pycache__ tests/__pycache__ src/__pycache__ reports/coverage_html/.gitignore
	@echo "Cache cleared!"

# Launch interactive menu
menu:
	@./menu.sh

# Specific test suites
max-contracts:
	@echo "Testing MaxContracts rule..."
	@$(PYTHON) -m pytest tests/test_p0_1_max_contracts.py -v

daily-loss:
	@echo "Testing DailyLoss rule..."
	@$(PYTHON) -m pytest tests/test_p0_2_daily_realized_loss.py -v

session:
	@echo "Testing Session rules..."
	@$(PYTHON) -m pytest tests/test_p0_4_session_and_reset.py -v

# Watch mode - re-run on file changes (requires entr)
watch:
	@echo "Watching for changes..."
	@find src tests -name "*.py" | entr -c make quick