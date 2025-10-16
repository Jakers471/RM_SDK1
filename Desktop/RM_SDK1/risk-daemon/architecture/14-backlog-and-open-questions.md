# Backlog and Open Questions

## Overview

This document captures:
1. **Decisions Made** - Architecture choices locked in by Product Owner
2. **Top Open Questions** - Critical decisions still needed before implementation
3. **First TDD Tickets** - Priority 0 development tasks with test-first approach

---

## Decisions Made (Locked In)

These decisions are **finalized** by the Product Owner and should not be revisited without explicit approval.

### Infrastructure Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Windows Service** | NSSM wrapper for v1 | Simple, reliable, proven. Native pywin32 deferred to v2. |
| **IPC Mechanism** | Local HTTP API on 127.0.0.1 | Simplest cross-platform, token auth, easy testing. Not Named Pipes. |
| **Credential Storage (Dev)** | `.env` file | Quick setup for development. Plain-text acceptable in dev. |
| **Credential Storage (Prod)** | Windows DPAPI-encrypted `secrets.json` | Secure, machine+user bound, no external dependencies. |
| **CLI Framework** | Typer + Rich | Modern, type-safe (Typer), beautiful output (Rich). |
| **Logging Format** | JSON structured logs | Parseable, machine-readable, future-proof. |
| **Money Type** | Python Decimal | No floats. Period. Avoid rounding errors. |
| **Timezone** | America/Chicago (CT) | Futures markets operate on Central Time. DST-safe. |
| **Daily Reset Time** | 17:00 CT (5pm) | Standard futures session boundary. |
| **Event Model** | Single-threaded priority queue | Deterministic, no race conditions, testable. |
| **State Persistence** | JSON files per account | Human-readable, easy debugging, file permissions. |

### Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Repository Layout** | Single repo (daemon + CLIs + docs) | Simplicity for single developer. |
| **Test Location** | Separate `tests/` tree | Clean separation, Test-Orchestrator owns. |
| **Rule Architecture** | Plugin-based (RiskRulePlugin interface) | Extensible, testable in isolation, easy to add rules. |
| **PnL Calculation** | Realized + Unrealized combined | Smart monitoring prevents limit overshoot. |
| **Unrealized Price Source** | Last price (switchable later) | Start simple, refine if needed. |
| **Notification Strategy** | Critical = persisted queue, Info = best-effort | Balance reliability with performance. |
| **Enforcement Latency** | <1 second target | Sub-second response protects account effectively. |
| **Admin CLI Access** | Password-protected | Prevent trader from modifying rules. |
| **Trader CLI Access** | Read-only, no password | Transparency without control. |

---

## Top Open Questions

These questions require Product Owner decisions **before or during implementation**:

### Q1: SDK Unknown - Must Wait for SDK Analyst

**Question**: Which broker SDK capabilities exist vs. must be built?

**Impact**: Affects adapter complexity, performance, gaps to fill.

**Decision Maker**: Product Owner (after reviewing SDK Analyst deliverables)

**Timeline**: After SDK Analyst completes `docs/integration/`

**Blocked Work**:
- Adapter implementation (`src/adapters/sdk_adapter.py`)
- Event normalizer (`src/adapters/event_normalizer.py`)
- Integration tests

---

### Q2: Tick Values Source

**Question**: Where do we get tick values ($ per point per contract)?

**Options**:
1. **Hardcode** in config (simple, must update if values change)
2. **SDK provides** (ideal, if available - SDK Analyst to confirm)
3. **External API** (fetch from public source, adds dependency)

**Impact**: Unrealized PnL calculation accuracy

**Decision Maker**: Product Owner (after SDK Analyst findings)

**Recommendation**: Start with hardcoded config (option 1), move to SDK if available.

**Blocked Work**: PnL calculation implementation

---

### Q3: NoStopLossGrace Implementation

**Question**: How to detect if stop loss is attached to position?

**Options**:
1. **SDK provides SL metadata** with position (ideal - SDK Analyst to confirm)
2. **Query separate order list** (check for stop orders matching position)
3. **Assume no SL** and require trader to place SL within grace period (strictest)

**Impact**: Rule implementation complexity, trader UX

**Decision Maker**: Product Owner (after SDK Analyst findings)

**Recommendation**: If SDK provides SL metadata (option 1), use it. Else option 3.

**Blocked Work**: NoStopLossGrace rule implementation

---

### Q4: Position Close Partial Quantity

**Question**: Can we close partial quantity (e.g., 1 of 3 contracts)?

**Options**:
1. **SDK supports partial close** (query position, close X contracts)
2. **SDK only supports full close** (must close all, re-open remainder)

**Impact**: MaxContracts enforcement (need to close excess only)

**Decision Maker**: SDK Analyst confirms capability

**Recommendation**: If SDK doesn't support partial, close full position and re-open (position - excess). Log this workaround.

**Blocked Work**: MaxContracts enforcement implementation

---

### Q5: Pre-Trade Rejection

**Question**: Can we block orders before they fill?

**Options**:
1. **SDK allows pre-trade validation** (reject before send to exchange)
2. **No pre-trade rejection** (must close immediately after fill)

**Impact**: Enforcement effectiveness (tiny window of exposure if post-fill only)

**Decision Maker**: SDK Analyst confirms capability

**Recommendation**: If no pre-trade (likely), use post-fill immediate close. Accept tiny exposure window (<100ms target).

**Blocked Work**: SymbolBlock, SessionBlockOutside enforcement

---

### Q6: Session Schedule Config Format

**Question**: How do traders configure allowed trading sessions?

**Options**:
1. **Simple**: Days of week + single time range (e.g., Mon-Fri 8:30am-3pm CT)
2. **Complex**: Multiple time ranges per day, per instrument
3. **Preset profiles**: "RTH only", "ETH included", "24/5", etc.

**Impact**: Config complexity, user experience

**Decision Maker**: Product Owner

**Recommendation**: Start simple (option 1), add presets (option 3) in v2.

**Blocked Work**: SessionBlockOutside config schema

---

### Q7: Multiple Account Priority

**Question**: If monitoring multiple accounts, which account's events process first?

**Options**:
1. **Round-robin**: Fair distribution across accounts
2. **Priority by config**: Assign priority levels to accounts
3. **FIFO by event timestamp**: Whichever event arrived first

**Impact**: Fairness if one account has high event volume

**Decision Maker**: Product Owner

**Recommendation**: Option 3 (FIFO by timestamp) for determinism.

**Blocked Work**: Multi-account event routing (can defer to v2)

---

### Q8: Notification Retry Persistence

**Question**: Where to persist critical notifications for retry?

**Options**:
1. **JSON file** (simple, human-readable)
2. **SQLite database** (queryable, transactional)
3. **In-memory queue only** (lost on crash)

**Impact**: Notification delivery guarantee reliability

**Decision Maker**: Product Owner

**Recommendation**: Option 1 (JSON file per notification, delete on success). Simple, meets 24hr TTL requirement.

**Blocked Work**: Notification service persistence

---

## First TDD Tickets (Priority 0)

These are the **first development tasks** to implement using **Test-Driven Development** (TDD). Each ticket includes:
- Unit tests
- Integration tests (where applicable)
- One E2E happy path (P0-1 only)

**Ownership**:
- **Test-Orchestrator** writes tests first (defines behavior)
- **Developer** implements code to pass tests
- Iterative: test → fail → implement → pass → refactor

---

### P0-1: MaxContracts Rule (Unit + Integration + E2E)

**Description**: Implement MaxContracts risk rule with full test coverage.

**Acceptance Criteria**:
- Rule evaluates fill events
- Detects when total contract count exceeds limit
- Returns RuleViolation with details (current count, limit, excess)
- EnforcementAction: close_position for excess contracts (LIFO)

**Unit Tests** (Test-Orchestrator writes first):
```python
# tests/unit/test_rules/test_max_contracts.py

def test_max_contracts_not_violated():
    """2 contracts open, limit is 4 → no violation"""
    rule = MaxContractsRule(params={"max_contracts": 4})
    state = mock_account_state(open_positions=[mock_position("MNQ", 2)])
    event = mock_fill_event("ES", 1)  # Total would be 3

    violation = rule.evaluate(event, state)

    assert violation is None


def test_max_contracts_violated():
    """3 contracts open, limit is 4, new fill 2 → violation"""
    rule = MaxContractsRule(params={"max_contracts": 4})
    state = mock_account_state(open_positions=[mock_position("MNQ", 3)])
    event = mock_fill_event("ES", 2)  # Total would be 5

    violation = rule.evaluate(event, state)

    assert violation is not None
    assert violation.current_value == 5
    assert violation.limit_value == 4
    assert violation.exceeded_by == 1


def test_max_contracts_enforcement_action():
    """Violation → close_position action for excess"""
    rule = MaxContractsRule(params={"max_contracts": 4})
    violation = RuleViolation(
        rule_name="MaxContracts",
        current_value=5,
        limit_value=4,
        exceeded_by=1,
        # ... other fields
    )

    action = rule.get_enforcement_action(violation)

    assert action.action_type == "close_position"
    assert action.quantity == 1  # Close 1 excess contract
```

**Integration Test**:
```python
# tests/integration/test_event_flow.py

def test_max_contracts_full_flow():
    """Fill event → State Manager → Risk Engine → Enforcement Engine → Position closed"""
    # Setup
    daemon = setup_test_daemon(config={"max_contracts": 2})
    daemon.state_manager.add_position(mock_position("MNQ", 2))

    # Event: Fill 2 ES (total would be 4, exceeds limit of 2)
    fill_event = create_fill_event("ES", 2)

    # Execute
    daemon.event_bus.publish(fill_event)
    wait_for_processing()

    # Verify
    assert daemon.enforcement_engine.actions_executed == 1
    assert daemon.enforcement_engine.last_action.action_type == "close_position"
    assert daemon.enforcement_engine.last_action.quantity == 2  # Close excess
    assert daemon.state_manager.get_position_count() == 2  # Back to limit
```

**E2E Test** (happy path):
```python
# tests/e2e/test_full_trading_scenario.py

def test_e2e_max_contracts_enforcement():
    """Full scenario: trader opens positions, limit enforced, positions closed"""
    # 1. Daemon starts
    daemon = start_daemon(config_file="tests/fixtures/config.json")

    # 2. Trader opens 2 MNQ (within limit of 4)
    simulate_broker_fill("MNQ", 2)
    assert get_open_positions() == [("MNQ", 2)]

    # 3. Trader opens 3 ES (total 5, exceeds limit 4)
    simulate_broker_fill("ES", 3)

    # 4. Daemon auto-closes 1 ES (excess)
    wait_for_enforcement(timeout=1.0)
    assert get_open_positions() == [("MNQ", 2), ("ES", 2)]

    # 5. Notification sent
    assert notification_received("MaxContracts limit exceeded")

    # 6. Log entry created
    assert log_contains("MaxContracts violated: 5 > 4, closed 1 ES")
```

**Dependencies**: State Manager, Event Bus, Enforcement Engine (can mock initially)

**Estimated Effort**: 4-8 hours (tests + implementation)

---

### P0-2: DailyRealizedLoss with Combined PnL (Unit + Integration)

**Description**: Implement DailyRealizedLoss rule with combined PnL monitoring (realized + unrealized).

**Acceptance Criteria**:
- Rule tracks realized PnL (from closed positions)
- Rule checks combined exposure: `realized + total_unrealized`
- If combined exceeds loss limit → flatten all + lockout
- Lockout persists until 5pm CT daily reset

**Unit Tests**:
```python
# tests/unit/test_rules/test_daily_realized_loss.py

def test_daily_loss_not_violated():
    """Realized -$500, unrealized -$100, limit -$1000 → OK"""
    rule = DailyRealizedLossRule(params={"limit": Decimal("-1000.00")})
    state = mock_account_state(
        realized_pnl_today=Decimal("-500.00"),
        total_unrealized_pnl=Decimal("-100.00")
    )
    event = mock_position_update_event()

    violation = rule.evaluate(event, state)

    assert violation is None


def test_daily_loss_violated_by_combined():
    """Realized -$900, unrealized -$150, limit -$1000 → VIOLATION"""
    rule = DailyRealizedLossRule(params={"limit": Decimal("-1000.00")})
    state = mock_account_state(
        realized_pnl_today=Decimal("-900.00"),
        total_unrealized_pnl=Decimal("-150.00")  # Combined: -$1050
    )
    event = mock_position_update_event()

    violation = rule.evaluate(event, state)

    assert violation is not None
    assert violation.current_value == Decimal("-1050.00")
    assert violation.limit_value == Decimal("-1000.00")


def test_daily_loss_enforcement_flatten_and_lockout():
    """Violation → flatten_account + set_lockout"""
    rule = DailyRealizedLossRule(params={"limit": Decimal("-1000.00")})
    violation = mock_violation(current_value=Decimal("-1050.00"))

    action = rule.get_enforcement_action(violation)

    assert action.action_type == "flatten_account"
    # Second action for lockout (or combined in one action with lockout_until set)
```

**Integration Test**:
```python
# tests/integration/test_combined_pnl_monitoring.py

def test_combined_pnl_triggers_lockout():
    """Realized loss + unrealized loss → combined exceeds → flatten + lockout"""
    daemon = setup_test_daemon(config={"daily_realized_loss_limit": Decimal("-1000.00")})

    # Setup: Realized loss -$850
    daemon.state_manager.realized_pnl_today = Decimal("-850.00")

    # Open position with -$100 unrealized (combined -$950, still OK)
    daemon.state_manager.add_position(mock_position("MNQ", 2, unrealized=-100))
    assert daemon.state_manager.combined_exposure == Decimal("-950.00")

    # Price moves, unrealized becomes -$200 (combined -$1050, BREACH)
    position_update_event = create_position_update(unrealized=Decimal("-200.00"))
    daemon.event_bus.publish(position_update_event)
    wait_for_processing()

    # Verify: All positions closed, account locked out
    assert daemon.state_manager.get_position_count() == 0
    assert daemon.state_manager.is_locked_out() is True
    assert daemon.state_manager.lockout_until is not None
```

**Dependencies**: State Manager (combined_exposure property), Enforcement Engine

**Estimated Effort**: 6-10 hours

---

### P0-3: EnforcementEngine Idempotency (Integration)

**Description**: Ensure enforcement actions are idempotent (no duplicate closes).

**Acceptance Criteria**:
- Same position close requested multiple times → only executed once
- In-flight actions tracked
- Duplicate actions logged and skipped

**Integration Test**:
```python
# tests/integration/test_enforcement_idempotency.py

def test_idempotency_duplicate_close_position():
    """Two close_position calls for same position → only one executed"""
    enforcement_engine = setup_enforcement_engine()
    mock_sdk = get_mock_sdk_adapter()

    # Call 1: Close position
    enforcement_engine.close_position("ABC123", "pos_001", reason="Test")

    # Call 2: Duplicate close (before Call 1 completes)
    enforcement_engine.close_position("ABC123", "pos_001", reason="Test duplicate")

    # Verify: SDK called only once
    assert mock_sdk.close_position.call_count == 1


def test_idempotency_rapid_fire_events():
    """100 position updates in 1 second → rule triggers once, not 100 times"""
    daemon = setup_test_daemon()
    daemon.state_manager.add_position(mock_position("MNQ", 2, unrealized=Decimal("0")))

    # Rapid-fire position updates (unrealized loss exceeds limit)
    for i in range(100):
        event = create_position_update(unrealized=Decimal("-250.00"))
        daemon.event_bus.publish(event)

    wait_for_processing()

    # Verify: Position closed only once
    assert daemon.enforcement_engine.actions_executed == 1
```

**Dependencies**: Enforcement Engine, Event Bus

**Estimated Effort**: 4-6 hours

---

### P0-4: SessionBlockOutside + 17:00 CT Reset (Integration)

**Description**: Implement session-based trading enforcement and daily reset.

**Acceptance Criteria**:
- SessionBlockOutside rule enforces allowed days/times
- Fills outside session → auto-closed
- Daily reset at 17:00 CT (DST-safe)
- Realized PnL reset to $0, lockouts cleared

**Integration Test**:
```python
# tests/integration/test_session_block_outside.py

def test_session_block_outside_allowed_hours():
    """Session: Mon-Fri 8:30am-3pm CT. Fill at 4pm → closed"""
    rule = SessionBlockOutsideRule(params={
        "allowed_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        "allowed_times": [{"start": "08:30", "end": "15:00"}]
    })

    # Mock current time: Friday 4pm CT (outside session)
    with freeze_time("2025-10-17 16:00:00", tz="America/Chicago"):
        event = mock_fill_event("MNQ", 2)
        state = mock_account_state()

        violation = rule.evaluate(event, state)

        assert violation is not None
        assert "outside allowed session" in violation.message


def test_daily_reset_at_5pm_ct():
    """Realized PnL resets at 5pm CT, lockouts cleared"""
    daemon = setup_test_daemon()

    # Setup: Realized loss -$500, locked out
    daemon.state_manager.realized_pnl_today = Decimal("-500.00")
    daemon.state_manager.lockout_until = datetime(2025, 10, 17, 22, 0, 0)  # 5pm CT

    # Simulate time passing to 5pm CT
    with freeze_time("2025-10-17 17:00:00", tz="America/Chicago"):
        daemon.trigger_daily_reset()

    # Verify: PnL reset, lockout cleared
    assert daemon.state_manager.realized_pnl_today == Decimal("0.00")
    assert daemon.state_manager.lockout_until is None
    assert daemon.state_manager.is_locked_out() is False
```

**Dependencies**: State Manager (daily reset logic), SessionBlockOutside rule

**Estimated Effort**: 6-8 hours

---

### P0-5: Notifications (Reason + Action) (Unit)

**Description**: Implement notification service with reason and action in messages.

**Acceptance Criteria**:
- Notifications include: event_id, account, rule, reason, action, timestamp
- Discord webhook integration
- Telegram integration (optional for P0)
- Retry logic (3 quick retries)

**Unit Tests**:
```python
# tests/unit/test_notification_service.py

def test_notification_includes_reason_and_action():
    """Notification message contains reason and action"""
    service = NotificationService(config=mock_discord_config())
    violation = mock_violation(rule="MaxContracts", reason="5 contracts > 4 limit")
    action = mock_enforcement_action(action_type="close_position", quantity=1)

    message = service.format_enforcement_alert(violation, action)

    assert "MaxContracts" in message
    assert "5 contracts > 4 limit" in message
    assert "close_position" in message
    assert "1" in message  # quantity


def test_discord_webhook_called():
    """Discord webhook receives POST request"""
    service = NotificationService(config=mock_discord_config())
    mock_webhook = get_mock_webhook()

    service.send_alert("ABC123", "Test message", severity="warning")

    assert mock_webhook.post.called
    assert "Test message" in mock_webhook.post.call_args[0]
```

**Dependencies**: None (isolated)

**Estimated Effort**: 4-6 hours

---

## Summary: Backlog Priorities

### Immediate (Blocked on SDK Analyst)
- **P0-1** to **P0-5** tickets **cannot fully implement** until SDK Analyst completes integration docs
- Test-Orchestrator can write unit tests (with mocks) immediately
- Developer must wait for adapter contracts before implementing SDK integration

### Post-SDK-Analysis
1. Implement adapters (`src/adapters/`)
2. Implement core components (Event Bus, State Manager, Risk Engine, Enforcement Engine)
3. Implement rules (starting with P0-1 MaxContracts)
4. Implement CLIs (Admin, Trader)
5. Implement daemon service wrapper (NSSM)

### Open Questions Resolution Timeline
- **Q1-Q5**: Resolved by SDK Analyst deliverables
- **Q6-Q8**: Product Owner decisions during sprint planning (can proceed in parallel)

---

## Approval Gate

This backlog is **approved by Product Owner** once:
- ✅ Decisions table reviewed and confirmed
- ✅ Open questions acknowledged (will be resolved during implementation)
- ✅ TDD tickets approved as first development tasks
- ✅ SDK Analyst handoff approved (`99-handoff-to-sdk-analyst.md`)

**Next Step**: Handoff to SDK Analyst for integration analysis.
