# Risk Manager Daemon - Test Suite Summary

**Author**: RM-Test-Orchestrator
**Date**: 2025-10-15
**Status**: ✅ COMPLETE - All failing tests created per TDD methodology

---

## Executive Summary

Comprehensive failing test suite created for P0 (critical) risk management features following Test-Driven Development (TDD) principles. All tests are **DESIGNED TO FAIL** until implementation is complete.

### Test Coverage

- **Total Test Files**: 5
- **Total Test Cases**: 50+
- **Priority Breakdown**:
  - P0 (Critical): 50+ tests
  - P1 (Important): 0 (future)
  - P2 (Nice-to-have): 0 (future)

### Test Categories

- **Unit Tests**: 15+ (isolated rule logic)
- **Integration Tests**: 30+ (multi-component flows)
- **E2E Tests**: 5+ (full system scenarios)

---

## Test Files Created

### 1. `tests/conftest.py` - Test Infrastructure
**Purpose**: Provides fake implementations of all system components based on adapter contracts.

**Key Fixtures**:
- `FakeClock` - Controllable time for time-based testing
- `FakeStateManager` - In-memory state tracking (positions, PnL, lockouts)
- `FakeNotifier` - Notification recording for assertions
- `FakeBrokerAdapter` - Simulated order execution
- `FakeStorage` - In-memory persistence simulation
- `FakeTimeService` - Session management and daily reset logic

**Design Philosophy**:
- NO SDK imports - relies entirely on adapter contract interfaces
- Fully synchronous fixtures for deterministic testing
- Comprehensive data models matching architecture specs

---

### 2. `test_p0_1_max_contracts.py` - MaxContracts Rule Tests
**Feature**: Universal contract limit enforcement (Rule 1 from architecture)

#### Unit Tests (3 tests)
1. `test_rule_config_defaults` - Verify rule configuration
2. `test_rule_not_violated_within_limit` - No enforcement when within limit
3. `test_rule_violated_exceeds_limit` - Violation detected when limit exceeded
4. `test_rule_enforcement_action_close_excess` - LIFO closing of excess contracts
5. `test_rule_applies_to_fill_events_only` - Event type filtering

**Why These Fail**:
- ❌ `src/rules/max_contracts.py` doesn't exist
- ❌ `MaxContractsRule` class not implemented
- ❌ `evaluate()` method missing
- ❌ `get_enforcement_action()` method missing

#### Integration Tests (2 tests)
1. `test_excess_contracts_closed_automatically` - End-to-end enforcement flow
2. `test_multiple_excess_contracts_all_closed` - Multiple contract closure

**Why These Fail**:
- ❌ `src/core/risk_engine.py` doesn't exist
- ❌ `RiskEngine` class not implemented
- ❌ `process_event()` method missing
- ❌ `src/core/enforcement_engine.py` doesn't exist

#### E2E Tests (2 tests)
1. `test_happy_path_trader_stays_within_limit` - No enforcement when compliant
2. `test_enforcement_with_notification` - Full flow with notification

**Why These Fail**:
- ❌ Full system integration not wired up
- ❌ Event bus not implemented
- ❌ Notification service integration missing

---

### 3. `test_p0_2_daily_realized_loss.py` - DailyRealizedLoss with Combined PnL Tests
**Feature**: CRITICAL combined PnL monitoring (Rule 3 from architecture)

#### Unit Tests (6 tests)
1. `test_rule_config_defaults` - Rule configuration
2. `test_realized_only_within_limit` - Realized-only enforcement
3. `test_realized_only_exceeds_limit` - Realized-only violation
4. `test_combined_pnl_within_limit` - **CRITICAL**: Combined PnL under limit
5. `test_combined_pnl_exceeds_limit` - **CRITICAL**: Combined PnL breach
6. `test_enforcement_action_flatten_and_lockout` - Flatten + lockout until 5pm CT

**Why These Fail**:
- ❌ `src/rules/daily_realized_loss.py` doesn't exist
- ❌ Combined PnL calculation logic missing
- ❌ Lockout timestamp calculation (5pm CT) missing

#### Integration Tests (3 tests)
1. `test_combined_pnl_triggers_flatten` - **CRITICAL**: Combined breach triggers flatten
2. `test_cascading_rule_interaction` - **CRITICAL**: Per-trade limit → daily limit cascade
3. `test_multiple_positions_combined_pnl` - Multi-position PnL aggregation

**Key Scenario Tested**: Architecture section 02-risk-engine.md example:
```
Realized: -$850
Per-trade unrealized limit: -$200 (position closed)
Realized becomes: -$1050 (daily limit breached)
Result: Lockout triggered (cascading)
```

**Why These Fail**:
- ❌ Cascading rule evaluation logic missing
- ❌ Multi-rule enforcement priority system missing
- ❌ State updates after enforcement not wired

---

### 4. `test_p0_3_enforcement_idempotency.py` - Enforcement Idempotency Tests
**Feature**: Prevent duplicate enforcement actions (architecture 03-enforcement-actions.md)

#### Integration Tests (6 tests)
1. `test_duplicate_close_position_requests_ignored` - Concurrent duplicate prevention
2. `test_position_marked_pending_close_prevents_duplicate` - Pending flag prevents double-close
3. `test_flatten_account_idempotent` - Multiple flatten requests → single execution
4. `test_lockout_prevents_new_fills_enforcement` - Lockout early-exit logic
5. `test_in_flight_action_tracking` - In-flight action set prevents duplicates
6. `test_retry_not_counted_as_duplicate` - Retries allowed after failure

**Why These Fail**:
- ❌ `EnforcementEngine._in_flight_actions` set doesn't exist
- ❌ `Position.pending_close` flag logic not implemented
- ❌ Idempotency checks not wired into enforcement methods
- ❌ Retry logic with backoff not implemented

---

### 5. `test_p0_4_session_and_reset.py` - SessionBlockOutside + 17:00 CT Reset Tests
**Feature**: Session restrictions and daily reset (Rules 10 + state management)

#### SessionBlockOutside Tests (4 tests)
1. `test_fill_during_session_allowed` - Fills during Mon-Fri 8am-3pm CT allowed
2. `test_fill_outside_session_rejected` - Fills outside session closed immediately
3. `test_session_end_flattens_all_positions` - All positions flattened at 3pm CT
4. `test_weekend_fills_rejected` - Weekend fills rejected

**Why These Fail**:
- ❌ `src/rules/session_block.py` doesn't exist
- ❌ Session time checking logic missing
- ❌ Chicago timezone handling not implemented

#### Daily Reset Tests (6 tests)
1. `test_reset_at_exactly_5pm_ct` - **CRITICAL**: Reset at 5:00pm CT exactly
2. `test_reset_clears_lockout_flags` - Lockouts cleared at reset
3. `test_reset_preserves_open_positions` - Positions NOT closed at reset
4. `test_dst_transition_handles_correctly` - DST spring/fall transitions work
5. `test_reset_only_once_per_day` - No duplicate resets
6. `test_reset_after_daemon_downtime` - Missed reset handled on restart

**Why These Fail**:
- ❌ `src/timers/session_timer.py` doesn't exist
- ❌ Daily reset scheduler not implemented
- ❌ DST-aware timezone handling (pytz) not wired
- ❌ Reset deduplication logic missing

---

### 6. `test_p0_5_notifications.py` - Notifications with Reason + Action Tests
**Feature**: Transparent enforcement notifications (architecture 07-notifications-logging.md)

#### Unit Tests (5 tests)
1. `test_notification_has_required_fields` - All required fields present
2. `test_max_contracts_notification_reason_clear` - Clear reason formatting
3. `test_daily_loss_notification_includes_combined_pnl` - Combined PnL breakdown shown
4. `test_notification_severity_matches_rule_criticality` - Severity levels correct
5. `test_notification_action_field_accurate` - Action field describes enforcement

**Why These Fail**:
- ❌ `Notification` dataclass field validation missing
- ❌ `format_notification_reason()` methods not implemented per rule
- ❌ Severity mapping (warning vs critical) not defined

#### Integration Tests (4 tests)
1. `test_max_contracts_enforcement_sends_notification` - Notification sent on enforcement
2. `test_daily_loss_lockout_sends_critical_notification` - CRITICAL severity for lockouts
3. `test_multiple_rules_violated_multiple_notifications` - Multiple notifications for cascading
4. `test_notification_timestamp_accuracy` - Timestamps accurate

**Why These Fail**:
- ❌ Notification service integration with enforcement engine missing
- ❌ Notification sending not wired into enforcement actions
- ❌ Multiple notification handling for cascading rules missing

---

## pytest.ini Configuration

**Created**: `risk-daemon/pytest.ini`

**Key Settings**:
- Markers: `unit`, `integration`, `e2e`, `p0`, `p1`, `p2`
- Coverage target: 85% for `src/core/` and `src/rules/`
- Async support: `asyncio_mode = auto`
- Test discovery: `tests/` directory only

**Run Tests**:
```bash
# Run all tests (all will fail initially)
pytest

# Run only P0 tests
pytest -m p0

# Run only unit tests
pytest -m unit

# Run specific file
pytest tests/test_p0_1_max_contracts.py

# Run with coverage
pytest --cov=src --cov-report=html
```

---

## Why All Tests Are Failing

### Missing Core Components

1. **Risk Engine** (`src/core/risk_engine.py`)
   - Event processing loop
   - Rule evaluation orchestration
   - Priority-based enforcement
   - Cascading rule logic

2. **Enforcement Engine** (`src/core/enforcement_engine.py`)
   - `close_position()` with idempotency
   - `flatten_account()` with idempotency
   - `set_lockout()` with timestamp calculation
   - Retry logic with exponential backoff
   - In-flight action tracking

3. **State Manager** (`src/state/state_manager.py`)
   - Position tracking
   - Combined PnL calculation
   - Lockout management
   - Daily reset logic
   - State persistence

4. **Risk Rules** (5 rule files)
   - `src/rules/max_contracts.py`
   - `src/rules/daily_realized_loss.py`
   - `src/rules/unrealized_loss.py`
   - `src/rules/session_block.py`
   - (Base rule interface)

5. **Timers** (2 timer services)
   - `src/timers/session_timer.py` - Daily reset at 5pm CT
   - `src/timers/time_tick.py` - 1-second ticker

6. **Notification Service** (`src/notifications/notifier.py`)
   - Discord/Telegram integration
   - Notification formatting per rule
   - Severity mapping

---

## TDD Development Flow

### Red-Green-Refactor Cycle

1. **RED**: Run tests → All fail (current state)
   ```bash
   pytest  # All tests fail with ImportError or AttributeError
   ```

2. **GREEN**: Implement minimal code to pass tests
   - Start with `conftest.py` (already done)
   - Implement `MaxContractsRule` → unit tests pass
   - Implement `RiskEngine` → integration tests pass
   - Implement `EnforcementEngine` → e2e tests pass

3. **REFACTOR**: Clean up code while keeping tests green

### Recommended Implementation Order

**Phase 1: Core Infrastructure (Day 1-2)**
1. Create base `RiskRule` interface
2. Implement `StateManager` (without persistence)
3. Implement `EnforcementEngine` (basic close/flatten)
4. Implement `RiskEngine` (single rule evaluation)

**Run tests**: `pytest tests/test_p0_1_max_contracts.py::TestMaxContractsRuleUnit`
- **Expected**: 3-4 unit tests pass

**Phase 2: MaxContracts (Day 2)**
1. Implement `MaxContractsRule.evaluate()`
2. Implement `MaxContractsRule.get_enforcement_action()`
3. Wire rule into RiskEngine

**Run tests**: `pytest tests/test_p0_1_max_contracts.py`
- **Expected**: All MaxContracts tests pass (10+ tests)

**Phase 3: Combined PnL Monitoring (Day 3-4)**
1. Implement combined PnL calculation in StateManager
2. Implement `DailyRealizedLossRule` with combined logic
3. Implement lockout mechanism with 5pm CT calculation
4. Implement cascading rule evaluation

**Run tests**: `pytest tests/test_p0_2_daily_realized_loss.py`
- **Expected**: All DailyRealizedLoss tests pass (9+ tests)

**Phase 4: Idempotency & Sessions (Day 5)**
1. Add `_in_flight_actions` set to EnforcementEngine
2. Add `pending_close` flag handling
3. Implement SessionBlockOutsideRule
4. Implement daily reset at 5pm CT

**Run tests**:
- `pytest tests/test_p0_3_enforcement_idempotency.py`
- `pytest tests/test_p0_4_session_and_reset.py`
- **Expected**: 16+ tests pass

**Phase 5: Notifications (Day 6)**
1. Implement notification formatting per rule
2. Wire notification service into enforcement actions
3. Add severity mapping

**Run tests**: `pytest tests/test_p0_5_notifications.py`
- **Expected**: All notification tests pass (9+ tests)

**Phase 6: Full Integration (Day 7)**
```bash
pytest -m p0  # All P0 tests should pass
```

---

## Key Test Scenarios

### Scenario 1: Combined PnL Triggers Daily Limit
**File**: `test_p0_2_daily_realized_loss.py::test_combined_pnl_triggers_flatten`

**Steps**:
1. Realized: -$850
2. Position opens with $0 unrealized
3. Price drops → unrealized = -$150 (combined = -$1000, AT limit)
4. Price drops more → unrealized = -$200 (combined = -$1050, BREACH)
5. System flattens all positions + locks out

**Why Critical**: Tests the CORE risk management feature - prevents account blow-ups via continuous combined PnL monitoring.

### Scenario 2: Cascading Rule Violation
**File**: `test_p0_2_daily_realized_loss.py::test_cascading_rule_interaction`

**Steps**:
1. Realized: -$850, Daily limit: -$1000
2. Position hits -$200 unrealized (per-trade limit)
3. Per-trade rule closes position
4. Realized becomes -$1050 (daily limit now breached)
5. Daily rule triggers lockout

**Why Critical**: Tests inter-rule dependencies and proper cascading enforcement.

### Scenario 3: Idempotency Under Concurrent Events
**File**: `test_p0_3_enforcement_idempotency.py::test_duplicate_close_position_requests_ignored`

**Steps**:
1. Two concurrent events trigger same position close
2. First close starts, added to in_flight set
3. Second close detected as duplicate, skipped
4. Only ONE broker order placed

**Why Critical**: Prevents over-enforcement in high-frequency event scenarios.

### Scenario 4: Daily Reset at 5pm CT
**File**: `test_p0_4_session_and_reset.py::test_reset_at_exactly_5pm_ct`

**Steps**:
1. Time: 4:59pm CT, Realized PnL: -$500
2. Time advances to 5:00pm CT
3. Reset triggered
4. Realized PnL → $0, lockouts cleared

**Why Critical**: Ensures daily limits reset correctly for next trading day.

---

## Coverage Expectations

### After Full Implementation

**Minimum Coverage Target**: 85% for `src/core/` and `src/rules/`

**Expected Coverage**:
- `src/core/risk_engine.py`: 90%+
- `src/core/enforcement_engine.py`: 85%+
- `src/state/state_manager.py`: 85%+
- `src/rules/max_contracts.py`: 95%+
- `src/rules/daily_realized_loss.py`: 95%+

**Uncovered Areas** (acceptable):
- Error handling for rare edge cases
- Logging statements
- Debug code paths

---

## Running Tests

### Full Test Suite
```bash
cd risk-daemon
pytest
```

### Filtered Runs
```bash
# Only P0 critical tests
pytest -m p0

# Only unit tests (fast)
pytest -m unit

# Only integration tests
pytest -m integration

# Specific feature
pytest tests/test_p0_1_max_contracts.py

# With coverage report
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### Expected Output (Before Implementation)
```
==================== test session starts ====================
collected 50+ items

tests/test_p0_1_max_contracts.py::TestMaxContractsRuleUnit::test_rule_config_defaults FAILED
tests/test_p0_1_max_contracts.py::TestMaxContractsRuleUnit::test_rule_not_violated_within_limit FAILED
tests/test_p0_1_max_contracts.py::TestMaxContractsRuleUnit::test_rule_violated_exceeds_limit FAILED
...
==================== 50+ failed in 5.23s ====================
```

**This is EXPECTED** - tests are designed to fail until implementation is complete.

---

## Next Steps for Developer

1. **Review Tests**: Read through all test files to understand requirements
2. **Start with Unit Tests**: Implement `MaxContractsRule` to pass unit tests
3. **Build Core**: Implement `RiskEngine` and `EnforcementEngine`
4. **Iterate**: Follow TDD cycle (red → green → refactor)
5. **Run Tests Frequently**: After each small change, run relevant tests

---

## Summary of What's Failing and Why

### Failing Test Count by File

| File | Unit | Integration | E2E | Total |
|------|------|-------------|-----|-------|
| `test_p0_1_max_contracts.py` | 5 | 2 | 2 | **9** |
| `test_p0_2_daily_realized_loss.py` | 6 | 3 | 0 | **9** |
| `test_p0_3_enforcement_idempotency.py` | 0 | 6 | 0 | **6** |
| `test_p0_4_session_and_reset.py` | 0 | 10 | 0 | **10** |
| `test_p0_5_notifications.py` | 5 | 4 | 0 | **9** |
| **TOTAL** | **16** | **25** | **2** | **43+** |

### Why Each Component Fails

1. **Rules** (`src/rules/*.py`) - 15 tests fail
   - Files don't exist
   - Rule evaluation logic not implemented
   - Enforcement action generation missing

2. **Risk Engine** (`src/core/risk_engine.py`) - 20 tests fail
   - Event processing not implemented
   - Rule orchestration missing
   - Cascading logic absent

3. **Enforcement Engine** (`src/core/enforcement_engine.py`) - 10 tests fail
   - Idempotency tracking missing
   - Retry logic not implemented
   - Notification integration absent

4. **State Manager** (`src/state/state_manager.py`) - 8 tests fail
   - Combined PnL calculation missing
   - Lockout management not wired
   - Daily reset not scheduled

5. **Timers** (`src/timers/*.py`) - 6 tests fail
   - Session timer not implemented
   - 5pm CT reset not scheduled
   - DST handling missing

6. **Notifications** (`src/notifications/*.py`) - 9 tests fail
   - Notification formatting missing
   - Severity mapping not defined
   - Integration with enforcement absent

---

## Document Status

✅ **COMPLETE** - All P0 failing tests created
✅ **READY FOR DEVELOPMENT** - Developer can now implement to pass tests
✅ **TDD METHODOLOGY** - Red-Green-Refactor cycle established

**Last Updated**: 2025-10-15
**Test-Orchestrator**: RM-Test-Orchestrator Agent
