#!/bin/bash
# Interactive Test & Coverage Menu - All commands in one place!

# Colors for pretty output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Detect Python path
if [ -d "/mnt/c" ]; then
    PYTHON="/mnt/c/Users/jakers/AppData/Local/Programs/Python/Python313/python.exe"
else
    PYTHON="/c/Users/jakers/AppData/Local/Programs/Python/Python313/python.exe"
fi

clear
echo -e "${CYAN}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║        RISK DAEMON TEST & COVERAGE MENU           ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}MAIN COMMANDS:${NC}"
echo -e "  ${YELLOW}1${NC} → 🚀 Run ALL + Track Changes + Save Reports (BEST!)"
echo -e "  ${YELLOW}2${NC} → View coverage summary (terminal)"
echo -e "  ${YELLOW}3${NC} → Open HTML coverage report (browser)"
echo ""
echo -e "${BLUE}Quick Test Options:${NC}"
echo -e "  ${YELLOW}4${NC} → Run only PASSING tests"
echo -e "  ${YELLOW}5${NC} → Run only FAILING tests"
echo -e "  ${YELLOW}6${NC} → Run P0 (Priority 0) tests only"
echo ""
echo -e "${CYAN}Specific Test Suites:${NC}"
echo -e "  ${YELLOW}7${NC} → MaxContracts tests"
echo -e "  ${YELLOW}8${NC} → DailyLoss tests"
echo -e "  ${YELLOW}9${NC} → Session/Reset tests"
echo ""
echo -e "${RED}Utilities:${NC}"
echo -e "  ${YELLOW}10${NC} → Generate AI analysis summary"
echo -e "  ${YELLOW}11${NC} → Basic run (no tracking)"
echo -e "  ${YELLOW}12${NC} → Run single test (you choose)"
echo -e "  ${YELLOW}13${NC} → Run tests with verbose output"
echo -e "  ${YELLOW}14${NC} → Clear all test cache"
echo ""
echo -e "  ${YELLOW}0${NC} → Exit"
echo ""
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
read -p "Choose option [0-14]: " choice

case $choice in
    1)
        echo -e "${GREEN}🚀 Running ALL tests with tracking + saving all reports...${NC}"
        if [ -f "./track_coverage.sh" ]; then
            ./track_coverage.sh
        else
            # Fallback if track_coverage.sh doesn't exist
            $PYTHON -m pytest --cov=src --cov-report=term-missing --cov-report=html:reports/coverage_html --cov-report=json:reports/coverage.json --cov-report=xml:reports/coverage.xml -v
        fi
        echo ""
        echo -e "${GREEN}✅ Reports saved to:${NC}"
        echo -e "  • HTML: reports/coverage_html/index.html"
        echo -e "  • JSON: reports/coverage.json"
        echo -e "  • History: reports/coverage_history/"
        ;;

    2)
        echo -e "${BLUE}Coverage Summary:${NC}"
        if [ -f "./cov" ]; then
            ./cov
        else
            $PYTHON coverage_report.py
        fi
        ;;

    3)
        echo -e "${BLUE}Opening HTML coverage report...${NC}"
        if [ -f "./view" ]; then
            ./view
        else
            if command -v explorer.exe &> /dev/null; then
                explorer.exe "reports\\coverage_html\\index.html"
            else
                start reports/coverage_html/index.html
            fi
        fi
        ;;

    4)
        echo -e "${GREEN}Running only PASSING tests...${NC}"
        $PYTHON -m pytest -m "not xfail" --lf --ff -v
        ;;

    5)
        echo -e "${RED}Running only FAILING tests...${NC}"
        $PYTHON -m pytest --lf -v
        ;;

    6)
        echo -e "${YELLOW}Running P0 (Priority 0) tests...${NC}"
        $PYTHON -m pytest -m p0 --cov=src --cov-report=term-missing -v
        ;;

    7)
        echo -e "${YELLOW}Running MaxContracts tests...${NC}"
        $PYTHON -m pytest tests/test_p0_1_max_contracts.py -v --cov=src/rules/max_contracts
        ;;

    8)
        echo -e "${YELLOW}Running DailyLoss tests...${NC}"
        $PYTHON -m pytest tests/test_p0_2_daily_realized_loss.py -v --cov=src/rules/daily_realized_loss
        ;;

    9)
        echo -e "${YELLOW}Running Session/Reset tests...${NC}"
        $PYTHON -m pytest tests/test_p0_4_session_and_reset.py -v
        ;;

    10)
        echo -e "${CYAN}Generating AI analysis summary...${NC}"
        $PYTHON ai_coverage_summary.py
        echo ""
        echo -e "${GREEN}Summary saved to: reports/ai_coverage_summary.json${NC}"
        ;;

    11)
        echo -e "${CYAN}Running basic test (no tracking)...${NC}"
        $PYTHON -m pytest --cov=src --cov-report=term-missing -v
        ;;

    12)
        echo "Available test files:"
        ls tests/test_*.py | sed 's/tests\///g'
        echo ""
        read -p "Enter test file name (without tests/): " testfile
        echo -e "${YELLOW}Running tests/$testfile...${NC}"
        $PYTHON -m pytest tests/$testfile -v
        ;;

    13)
        echo -e "${YELLOW}Running ALL tests with verbose output...${NC}"
        $PYTHON -m pytest -vv --tb=long --cov=src --cov-report=term-missing
        ;;

    14)
        echo -e "${RED}Clearing test cache...${NC}"
        rm -rf .pytest_cache __pycache__ tests/__pycache__ src/__pycache__
        echo "Cache cleared!"
        ;;

    0)
        echo -e "${GREEN}Goodbye!${NC}"
        exit 0
        ;;

    *)
        echo -e "${RED}Invalid option!${NC}"
        ;;
esac

echo ""
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${CYAN}Done! Press Enter to return to menu or Ctrl+C to exit${NC}"
read
exec "$0"