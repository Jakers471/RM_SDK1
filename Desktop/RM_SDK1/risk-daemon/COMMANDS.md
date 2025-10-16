# 🚀 QUICK COMMAND REFERENCE

## 🎯 THE ONLY COMMAND YOU NEED: `./test`

```bash
./test           # Run all tests with coverage
./test view      # Open HTML report in browser
./test quick     # Run only passing tests (fast)
./test failed    # Run only failing tests
./test p0        # Run priority-0 tests
./test status    # Show coverage summary
./test menu      # Show all options
```

---

## 📊 Using the Makefile (Recommended)

```bash
make test       # Run all tests with coverage
make quick      # Run only passing tests (fast)
make failed     # Run only failing tests
make p0         # Run priority 0 tests
make coverage   # Run with change tracking
make report     # Show coverage summary
make view       # Open HTML report
make ai         # Generate AI analysis
make clean      # Clear cache
make help       # Show all commands
```

---

## 🎮 Using Interactive Menu

```bash
./menu.sh       # Launches interactive menu with all options
```

---

## 🔧 Direct Commands (Manual)

### Basic Testing
```bash
# Run all tests with coverage
./run_tests.sh

# Track coverage changes
./track_coverage.sh

# View coverage summary
./cov

# Open HTML report
./view
```

### Specific Test Suites
```bash
# MaxContracts tests only
./run_tests.sh tests/test_p0_1_max_contracts.py

# DailyLoss tests only
./run_tests.sh tests/test_p0_2_daily_realized_loss.py

# P0 priority tests
./run_tests.sh -m p0
```

### Coverage Analysis
```bash
# Generate AI-readable summary
python ai_coverage_summary.py

# View coverage trends
python coverage_report.py
```

---

## 📁 Important Files

| File | Purpose |
|------|---------|
| `reports/coverage_html/index.html` | Visual coverage report |
| `reports/coverage.json` | Coverage data for AI |
| `reports/junit.xml` | Test results |
| `reports/ai_coverage_summary.json` | AI-friendly summary |

---

## 🏃 Quick Start for New Developers

1. **First time?** Run: `./menu.sh` and press 1
2. **Check coverage:** Run: `make view`
3. **Fix failing tests:** Run: `make failed`
4. **See what changed:** Run: `make coverage`

---

## 💡 Pro Tips

- Use `make` commands - they're shorter!
- The menu (`./menu.sh`) remembers your last choice
- Coverage should stay above 80%
- P0 tests are critical - they must pass!

---

## 🆘 Troubleshooting

**"Command not found"**: Run `chmod +x *.sh` to make scripts executable

**"No such file"**: You might be in wrong directory. Run `cd risk-daemon`

**WSL vs Git Bash issues**: The scripts auto-detect your environment!