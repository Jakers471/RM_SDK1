
# Claude Collaboration Guide — custom-risk-daemon

## Guardrails
- SDK is **read-only** at `../project-x-py` — never modify it.
- Write scope: `./src/**`, `./tests/**`, `./docs/**`, `./pyproject.toml`, `./pytest.ini`, `.gitignore`, `./scripts/**`.
- Test discovery only in `./tests`.
- Ask before adding dependencies. Work in small steps. Always show unified diffs + exact shell commands.

## AI Workflow Gates (must obey)
- Do **not** proceed past Step 6 in the workflow until I type: “All tests are green — proceed.”
- Do **not** start the next feature until I type: “Merge complete.”

## Test Commands (markers)
- Unit: `uv run pytest -q -m "unit"`
- Integration (opt-in): `ENABLE_INTEGRATION=1 uv run pytest -q -m "integration"`
- E2E (mocked): `uv run pytest -q -m "e2e and not realtime"`
- Realtime (opt-in): `ENABLE_REALTIME=1 uv run pytest -q -m realtime`

## SDK files to READ when needed (no edits)
- src/project_x_py/trading_suite.py
- src/project_x_py/position_manager/core.py
- src/project_x_py/order_manager/core.py
- src/project_x_py/event_bus.py
- docs/api/trading-suite.md, position-manager.md, order-manager.md
- (Optional reference only): src/project_x_py/risk_manager/core.py — we are not using it

---

## Test-Driven Development (TDD) Core Rules — custom-risk-daemon

**CRITICAL:** This project follows strict Test-Driven Development. **Tests define the spec**; code must conform to tests.

### 1) RED–GREEN–REFACTOR (non-negotiable)
1. RED:   Write a failing test that defines expected behavior
2. GREEN: Write the minimum code to pass that test
3. REFACTOR: Improve design while keeping tests green
4. REPEAT
(never write implementation before a failing test exists)

### 2) Test-First Rules
- MANDATORY: tests before implementation; confirm RED first
- FORBIDDEN: “I’ll add tests later” / adding behavior without a test

### 3) Tests = Source of Truth
- Tests describe expected behavior, not current quirks
- If code fails a valid test, fix the code (not the test)

### 4) Test Quality Standards (async-first)
Each test MUST:
- Have a single, clear purpose
- Be isolated
- Use descriptive names about behavior
- Assert outcomes, not private internals
- Use proper async patterns (`@pytest.mark.asyncio`, `await`)

Good name (behavioral):  
    async def test_daily_loss_limit_breach_triggers_flatten_all_positions(): ...

Bad name (implementation-y):  
    async def test_call_enforce_limits_method(): ...

### 5) Async Testing Conventions (this repo)
- All async tests use `@pytest.mark.asyncio` (pytest.ini sets `asyncio_mode=auto`)
- Prefer adapter-level mocking (mock your SdkAdapter) over network
- Use `unittest.mock.AsyncMock` for async functions/callbacks
- If HTTP mocking is needed (SDK uses httpx), use `respx`

### 6) Test Organization & Markers
tests/  
  unit/         # no network; fast  
  integration/  # real SDK connection (opt-in)  
  e2e/          # full flow; mocked by default  
  realtime/     # live websockets/API (opt-in)  

Markers used: unit, integration, e2e, realtime

Run:  
    uv run pytest -q -m "unit"  
    ENABLE_INTEGRATION=1 uv run pytest -q -m "integration"  
    uv run pytest -q -m "e2e and not realtime"  
    ENABLE_REALTIME=1 uv run pytest -q -m "realtime"

### 7) Code Review / Merge Checklist
- Tests exist and were written first (RED seen, then GREEN)
- Refactor kept tests green
- Behavior-focused assertions
- Edge cases covered where relevant
- Entire suite passes locally

### 8) Bug Fix Process
1) write a reproduction test (RED) → 2) fix (GREEN) → 3) refactor (keep green)

### 9) Refactoring Safety
- Start with green suite; keep it green; only change tests if requirements changed

### 10) Critical TDD Violations (never allowed)
- Implementation without tests; changing tests to match bugs; skipping RED; testing internals; bundling features without tests; commenting out failing tests

---

## Feature + Unit-Test Implementation & Post-Green Workflow (AI + Human)

### Before Coding
1) uv sync
2) ./test.sh --version  (or ./scripts/test.sh --version)
3) uv run pytest -q  — all tests must be green

### Feature or Change Implementation
2) Write new failing test first (RED)  
   - create/extend: tests/custom_risk_daemon/unit/test_<feature>.py  
   - define expected behavior + edge cases; run (must fail)  
3) Implement minimal code (GREEN)  
   - only enough logic to pass the new test  
4) Refactor (REFACTOR)  
   - clean structure/naming/perf; keep green  
5) Run quality gates (if installed)  
   - uv run mypy src/  
   - uv run ruff check . --fix  
   - uv run ruff format .  
   - ./test.sh  
6) Verify full suite  
   - uv run pytest -v  (all tests must pass)

### AI/Human Hand-Off Checkpoint
7) Human confirmation (mandatory)  
   - Pause until I type: “All tests are green — proceed.”

### Post-Green Integration Workflow
8) Stabilize branch  
    git status  
    git add .  
    git commit -m "Stable: all tests passing after <feature>"  
9) Push and sync  
    git push -u origin feature/<feature-name>  
10) Optional integration tests  
    uv run pytest -m "integration"  
11) Merge prep  
    git checkout main  
    git pull  
    git merge feature/<feature-name>  
    # resolve if needed  
    ./test.sh  (must still be green)  
12) Tag/version  
    git tag -a vX.Y.Z -m "Stable build after <feature>"  
    git push origin vX.Y.Z  
13) Cleanup (optional)  
    git branch -d feature/<feature-name>  
    git push origin --delete feature/<feature-name>  
14) Documentation update  
    - update CHANGELOG or PLANNING.md (summary, tests, merge timestamp)

### Next Task Transition
15) Start next task only after “merge complete”  
    git pull origin main  
    git checkout -b feature/<next-feature>
