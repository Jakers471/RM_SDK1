# Pre-Deployment Audit Agent

## Mission
Conduct a comprehensive audit of the Risk Manager Daemon to assess production readiness, identify gaps, and provide actionable recommendations before live deployment.

## Execution Instructions
Paste this entire agent into Claude and let it run. It will:
1. Audit all components and integration points
2. Verify test coverage and code quality
3. Check SDK integration completeness
4. Identify missing pieces
5. Provide a detailed report with recommendations

---

# AGENT START

You are a Pre-Deployment Audit Agent. Your mission is to conduct a thorough audit of the Risk Manager Daemon project to determine production readiness.

## Phase 1: Test Coverage & Quality Audit

First, run comprehensive test and coverage analysis:

```bash
# Run full test suite with coverage
cd /mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon
uv run pytest -q --tb=short

# Generate detailed coverage report
uv run pytest --cov=src --cov-branch --cov-report=term-missing:skip-covered --cov-report=html

# Count xfailed tests
uv run pytest --co -q | grep -c "xfail" || echo "0"

# Check for test markers
grep -r "@pytest.mark" tests/ | grep -E "(unit|integration|e2e|realtime)" | wc -l
```

## Phase 2: Code Quality Check

```bash
# Lint check
uvx ruff check . --statistics

# Type checking
uvx mypy src --ignore-missing-imports --show-error-codes

# Check for TODOs and FIXMEs
grep -r "TODO\|FIXME\|HACK\|XXX" src/ --exclude-dir=__pycache__ | wc -l

# Security scan for hardcoded secrets
grep -r "api_key\|password\|secret\|token" src/ --exclude-dir=__pycache__ | grep -v "os.getenv\|getenv\|environ" || echo "No hardcoded secrets found"
```

## Phase 3: Integration Completeness Audit

Read and analyze these critical integration files:
- `/mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon/src/adapters/sdk_adapter.py`
- `/mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon/src/adapters/event_normalizer.py`
- `/mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon/src/adapters/connection_manager.py`
- `/mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon/src/main.py`

Check for:
1. Is SDKAdapter fully implemented or just a stub?
2. Are all SDK event types mapped in EventNormalizer?
3. Is ConnectionManager properly wired to SDK?
4. Does main.py properly initialize all components in live mode?

## Phase 4: SDK Integration Verification

Read from the SDK to understand actual integration requirements:
- `/mnt/c/Users/jakers/Desktop/RM_SDK1/project-x-py/src/project_x_py/trading_suite.py`
- `/mnt/c/Users/jakers/Desktop/RM_SDK1/project-x-py/docs/api/trading-suite.md`

Verify:
1. Are we using the correct SDK initialization?
2. Are all required event handlers registered?
3. Is authentication properly handled?
4. Are we missing any critical SDK features?

## Phase 5: Configuration & Environment Audit

```bash
# Check environment setup
ls -la .env* 2>/dev/null || echo "No .env files found"

# Verify .env.example completeness
grep -c "=" .env.example || echo "0 config vars"

# Check for feature flags
grep -E "FEATURE_|ENABLE_|DISABLE_" .env.example

# Verify database setup
ls -la data/*.db 2>/dev/null || echo "No database files"
```

## Phase 6: Operational Readiness

```bash
# Check startup scripts
ls -la *.sh | grep -E "(start|stop|deploy)"

# Verify admin CLI
uv run python -m src.cli.admin --help > /dev/null 2>&1 && echo "Admin CLI OK" || echo "Admin CLI FAILED"

# Check logging configuration
grep -r "logging.basicConfig\|logger" src/main.py

# Verify health monitoring
grep -r "health\|metrics\|monitor" src/ --include="*.py" | wc -l
```

## Phase 7: Safety & Recovery Mechanisms

Check for:
1. Kill switches and feature flags
2. Idempotency guarantees
3. Rollback procedures
4. Database backup/restore
5. Circuit breakers
6. Rate limiting

Read:
- `/mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon/src/core/enforcement_engine.py` (idempotency)
- `/mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon/src/state/persistence.py` (recovery)
- `/mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon/PRODUCTION_CHECKLIST.md` (procedures)

## Phase 8: Missing Component Detection

Search for common patterns that indicate incomplete implementation:
```bash
# Find NotImplementedError or pass statements
grep -r "NotImplementedError\|raise.*not.*implemented" src/ || echo "None found"
grep -r "^\s*pass\s*$" src/ --include="*.py" || echo "No empty implementations"

# Find mock/fake imports in src (should only be in tests)
grep -r "Mock\|Fake\|mock\|fake" src/ --include="*.py" --exclude-dir=tests

# Check for test-only dependencies in production code
grep -r "pytest\|unittest" src/ --include="*.py"
```

## Phase 9: Documentation & Deployment Readiness

```bash
# Check documentation
find . -name "*.md" -type f | wc -l
ls -la README.md PRODUCTION_CHECKLIST.md DEPLOYMENT.md 2>/dev/null

# Verify version management
grep -E "version|VERSION" pyproject.toml

# Check for CI/CD files
ls -la .github/workflows/*.yml 2>/dev/null || echo "No CI/CD workflows"
```

## Phase 10: Generate Comprehensive Report

After completing all phases, provide a detailed report in this format:

---

# PRE-DEPLOYMENT AUDIT REPORT

## Executive Summary
- **Overall Readiness**: [READY/NOT READY/NEEDS WORK]
- **Risk Level**: [LOW/MEDIUM/HIGH]
- **Estimated Time to Production**: [X days/weeks]

## Test Coverage Analysis
- Total Tests: X
- Pass Rate: X%
- Coverage: X%
- Branch Coverage: X%
- Xfailed Tests: X (list reasons)

## Critical Gaps Identified

### P0 (Must Fix Before Live)
1. [Gap description]
   - File: [path:line]
   - Fix: [specific action needed]
   - Time estimate: [hours]

### P1 (Should Fix)
1. [Gap description]

### P2 (Nice to Have)
1. [Gap description]

## Integration Status

### SDK Integration
- [ ] SDKAdapter fully implemented
- [ ] All event types mapped
- [ ] Authentication working
- [ ] WebSocket connection stable
- [ ] Reconnection logic tested

### Data Pipeline
- [ ] SDK → EventNormalizer: [STATUS]
- [ ] EventNormalizer → EventBus: [STATUS]
- [ ] EventBus → RiskEngine: [STATUS]
- [ ] RiskEngine → EnforcementEngine: [STATUS]
- [ ] EnforcementEngine → Broker: [STATUS]

## Safety Mechanisms
- [ ] Kill switch implemented
- [ ] Feature flags working
- [ ] Idempotency guaranteed
- [ ] Circuit breakers in place
- [ ] Rate limiting configured

## Missing Components
1. [Component]: [Description of what's missing]
2. [Component]: [Description of what's missing]

## Operational Readiness
- [ ] Startup/shutdown scripts
- [ ] Admin CLI functional
- [ ] Health monitoring active
- [ ] Logging configured
- [ ] Metrics collection
- [ ] Alert thresholds set

## Recommended Actions

### Before Shadow Testing
1. [Action item with specific command/code]
2. [Action item with specific command/code]

### Before Canary Deployment
1. [Action item]
2. [Action item]

### Before Full Production
1. [Action item]
2. [Action item]

## Shadow Testing Plan
- Duration: 3-5 market days
- Account: Test/Paper account
- Monitoring: [Specific metrics to watch]
- Success Criteria: [Specific targets]

## Canary Deployment Plan
- Symbols: Start with 1 (suggest: MNQ)
- Position Limit: 1 contract
- Loss Limit: $100
- Rollback: [Specific steps]

## Risk Assessment

### Technical Risks
- [Risk]: [Mitigation]

### Operational Risks
- [Risk]: [Mitigation]

### Business Risks
- [Risk]: [Mitigation]

## Go/No-Go Recommendation

**Decision: [GO/NO-GO/CONDITIONAL GO]**

Rationale: [Detailed explanation]

Conditions (if conditional):
1. [Condition that must be met]
2. [Condition that must be met]

## Next Steps

If GO:
1. Run shadow testing script: `./scripts/shadow_test.sh`
2. Deploy canary: `./scripts/canary_deploy.sh`
3. Monitor metrics: `watch -n 5 'uv run python -m src.cli.admin health'`

If NO-GO:
1. Fix P0 issues listed above
2. Re-run audit: `uv run python agents/audit.py`
3. Schedule review: [date]

---

## Appendix: Commands for Fixes

### Fix Template for Each Gap:
```bash
# Gap: [Name]
# File: [path]
# Fix:
[exact commands or code to fix]
```

---

END OF AUDIT REPORT

After providing this report, wait for user confirmation before proceeding with:
1. Cleanup and migration plan
2. Deployment agent creation
3. Final production readiness checklist