# ✅ IMPLEMENTATION READY - All Approvals Complete

**Status**: 🟢 **APPROVED FOR DEVELOPMENT**
**Product Owner**: Jake
**Approval Date**: 2025-10-15
**Developer**: Ready to start immediately

---

## 📋 Executive Summary

All integration analysis is complete. All Product Owner questions answered and approved. All risks mitigated. All contracts defined. **Zero blockers remain.**

**Integration Timeline**: 4-6 days
**Risk Level**: 🟡 Medium (acceptable with mitigations)
**Recommendation**: ✅ **PROCEED**

---

## ✅ Product Owner Approved Decisions

### Core Policy Decisions

| Decision | Approval | Implementation |
|----------|----------|----------------|
| **Enforcement Latency** | 500ms is fantastic ✅ | Target: <500ms (P95), Max: <1000ms |
| **Loss Limit Buffer** | No buffer ✅ | Use exact configured limits (no adjustment) |
| **Enforcement Failures** | Continue trading + log ✅ | No lockout, alert admin, keep trading |
| **NoStopLossGrace Rule** | Mandatory ✅ | Cannot be disabled, always enforced |
| **Multi-Broker Support** | Future only ✅ | TopstepX now, others later (TBD) |

### Technical Decisions

| Decision | Approval | Implementation |
|----------|----------|----------------|
| **Event Queue Size** | 10,000 events ✅ | `EVENT_QUEUE_MAX_SIZE = 10_000` |
| **State Persistence** | SQLite ✅ | `~/.risk_manager/state.db` (embedded) |
| **Mock SDK** | Yes ✅ | Test-Orchestrator creates `tests/mocks/mock_sdk.py` |
| **Test Environment** | Paper trading account ✅ | Use Jake's practice account |

### Performance Metrics (ALL APPROVED) ✅

**6 Metrics to Track**:

1. **Enforcement Latency** (CRITICAL)
   - Time from FILL → close order
   - Target: <500ms (P95)
   - Alert: If >500ms occurs >5% of time

2. **Event Processing Time** (CRITICAL)
   - Rule evaluation time per event
   - Target: <10ms
   - Alert: If >50ms

3. **Memory Usage** (CRITICAL)
   - RSS over 24 hours
   - Target: <100MB steady state
   - Alert: If >200MB

4. **State Reconciliation Time**
   - Time to reconcile after disconnect
   - Target: <5 seconds
   - Alert: If >10 seconds

5. **Queue Depth**
   - Events pending in queue
   - Target: <100 normally
   - Alert: If >1000 (approaching limit)

6. **Rule Evaluation Time**
   - Per-rule performance
   - Target: <5ms per rule
   - Alert: If any rule >20ms

---

## 🚀 What Developer Must Build

### Phase 1: Core SDK Integration (Day 1-2) - 1.5 days

**Files to Create**:
- `src/adapters/sdk_adapter.py` - SDKAdapter class
- `src/adapters/event_normalizer.py` - EventNormalizer class
- `src/adapters/instrument_cache.py` - InstrumentCache class
- `src/adapters/price_cache.py` - PriceCache class
- `src/adapters/exceptions.py` - Custom exceptions

**Contract**: See [adapter_contracts.md](adapter_contracts.md)

**Key Methods**:
```python
class SDKAdapter:
    async def connect() → None
    async def disconnect() → None
    def is_connected() → bool
    async def get_current_positions(account_id) → List[Position]
    async def close_position(account_id, position_id, quantity) → OrderResult
    async def flatten_account(account_id) → List[OrderResult]
    async def get_instrument_tick_value(symbol) → Decimal
    async def get_current_price(symbol) → Decimal
```

---

### Phase 2: State Persistence (Day 3) - 1 day

**File to Create**: `src/state/sqlite_persistence.py`

**Database**: `~/.risk_manager/state.db` (SQLite)

**Schema**:
```sql
-- Account state
CREATE TABLE account_state (
    account_id TEXT PRIMARY KEY,
    realized_pnl_today REAL NOT NULL,
    unrealized_pnl_total REAL NOT NULL,
    last_daily_reset TIMESTAMP NOT NULL,
    lockout_until TIMESTAMP,
    cooldown_until TIMESTAMP,
    error_state BOOLEAN DEFAULT FALSE,
    error_message TEXT
);

-- Open positions
CREATE TABLE positions (
    position_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,  -- 'long' or 'short'
    quantity INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    current_price REAL,
    unrealized_pnl REAL,
    opened_at TIMESTAMP NOT NULL,
    last_update TIMESTAMP NOT NULL,
    stop_loss_attached BOOLEAN DEFAULT FALSE,
    stop_loss_price REAL,
    FOREIGN KEY (account_id) REFERENCES account_state(account_id)
);

-- Enforcement history (audit trail)
CREATE TABLE enforcement_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL,
    account_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    action_type TEXT NOT NULL,  -- 'close_position', 'flatten_account', 'lockout', etc.
    reason TEXT NOT NULL,
    position_id TEXT,
    order_id TEXT,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    FOREIGN KEY (account_id) REFERENCES account_state(account_id)
);

-- Performance metrics
CREATE TABLE performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    account_id TEXT
);
```

**Key Operations**:
```python
async def save_account_state(account_id: str, state: AccountState) → None
async def load_account_state(account_id: str) → Optional[AccountState]
async def record_enforcement(action: EnforcementAction, result: OrderResult) → None
async def record_metric(name: str, value: float, account_id: Optional[str]) → None
```

---

### Phase 3: Custom Components (Day 3-4) - 1.5 days

**3.1 Realized PnL Tracker** (`src/state/pnl_tracker.py`)
```python
class PnLTracker:
    async def update_realized_pnl(account_id: str, trade_pnl: Decimal) → None
    async def reset_daily_pnl(account_id: str) → None
    async def get_combined_exposure(account_id: str) → Decimal
```

**3.2 Session Timer** (`src/timers/session_timer.py`)
```python
async def session_timer(event_bus: EventBus):
    """Generate SESSION_TICK at 5pm CT daily."""
    ct_tz = pytz.timezone("America/Chicago")
    while True:
        now_ct = datetime.now(ct_tz)
        if now_ct.hour == 17 and now_ct.minute == 0:
            # Emit SESSION_TICK (daily_reset)
            await event_bus.publish(create_session_tick_event())
            await asyncio.sleep(60)  # Prevent duplicate
        await asyncio.sleep(1)
```

**3.3 Time Tick Generator** (`src/timers/time_tick.py`)
```python
async def time_tick_generator(event_bus: EventBus):
    """Generate TIME_TICK every 1 second."""
    while True:
        await event_bus.publish(create_time_tick_event())
        await asyncio.sleep(1.0)
```

---

### Phase 4: Reliability (Day 5) - 1 day

**4.1 State Reconciler** (`src/adapters/state_reconciler.py`)
```python
async def reconcile_state_after_reconnect(account_id: str):
    """Query REST API and reconcile cached state."""
    # 1. Query current positions from SDK
    # 2. Compare with cached state
    # 3. Log discrepancies
    # 4. Update state
    # 5. Re-evaluate all rules
```

**4.2 Stop Loss Detector** (`src/adapters/stop_loss_detector.py`)
```python
class StopLossDetector:
    async def detect_stop_loss(position: Position) → bool
    async def poll_for_manual_stops() → None  # Every 30s
    def track_bracket_order(position_id: UUID, stop_order_id: str) → None
```

---

### Phase 5: Optional Features (Day 6) - 0.5 days

**5.1 Notification Service** (`src/notifications/discord.py`, `telegram.py`)
```python
async def send_discord_alert(webhook_url: str, message: str, severity: str)
async def send_telegram_alert(bot_token: str, chat_id: str, message: str)
```

---

## 📊 Performance Tracking Implementation

**File**: `src/monitoring/performance_tracker.py`

```python
class PerformanceTracker:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.enforcement_latencies = []
        self.event_processing_times = []

    async def record_enforcement_latency(self, latency_ms: float):
        """Track enforcement latency (FILL → close order)."""
        self.enforcement_latencies.append(latency_ms)

        # Save to DB
        await self.db.record_metric("enforcement_latency_ms", latency_ms)

        # Check P95
        if len(self.enforcement_latencies) >= 100:
            p95 = np.percentile(self.enforcement_latencies, 95)
            if p95 > 500:
                logger.warning(f"⚠️ Enforcement latency P95: {p95:.1f}ms (target: <500ms)")
                await notification_service.alert_warning(
                    f"Enforcement latency degraded: {p95:.1f}ms"
                )

    async def record_event_processing_time(self, event_type: str, processing_ms: float):
        """Track event processing time."""
        self.event_processing_times.append(processing_ms)
        await self.db.record_metric(f"event_processing_{event_type}_ms", processing_ms)

        if processing_ms > 50:
            logger.warning(f"⚠️ Slow event processing: {event_type} took {processing_ms:.1f}ms")

    async def record_memory_usage(self):
        """Track memory usage (run every 60s)."""
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024

        await self.db.record_metric("memory_usage_mb", memory_mb)

        if memory_mb > 200:
            logger.error(f"🔴 High memory usage: {memory_mb:.1f}MB (target: <100MB)")
            await notification_service.alert_critical(
                f"Memory usage high: {memory_mb:.1f}MB"
            )

    async def record_queue_depth(self, depth: int):
        """Track event queue depth."""
        await self.db.record_metric("queue_depth", depth)

        if depth > 1000:
            logger.warning(f"⚠️ High queue depth: {depth} events (limit: 10000)")

    async def record_reconciliation_time(self, time_sec: float):
        """Track state reconciliation time."""
        await self.db.record_metric("reconciliation_time_sec", time_sec)

        if time_sec > 10:
            logger.warning(f"⚠️ Slow reconciliation: {time_sec:.1f}s (target: <5s)")

    async def record_rule_evaluation_time(self, rule_name: str, time_ms: float):
        """Track per-rule evaluation time."""
        await self.db.record_metric(f"rule_eval_{rule_name}_ms", time_ms)

        if time_ms > 20:
            logger.warning(f"⚠️ Slow rule: {rule_name} took {time_ms:.1f}ms (target: <5ms)")
```

---

## 🧪 Testing Requirements

### Async Testing (MANDATORY)

**ALL tests MUST follow async patterns** per `project-x-py/.cursor/rules/async_testing.md`:

```python
import pytest
from unittest.mock import AsyncMock
from aioresponses import aioresponses

@pytest.mark.asyncio
async def test_sdk_adapter_connect():
    """Test SDK connection with async patterns."""
    adapter = SDKAdapter(api_key="test", username="test", account_id=123)

    # Mock SDK
    with aioresponses() as m:
        m.post("https://api.topstepx.com/api/Authentication/signIn", payload={"token": "test_jwt"})

        await adapter.connect()
        assert adapter.is_connected() is True

    await adapter.disconnect()

@pytest.mark.asyncio
async def test_enforcement_latency():
    """Test enforcement latency meets target."""
    import time

    # Simulate FILL event
    start = time.time()

    event = create_fill_event(symbol="MNQ", quantity=1, price=18000.0)
    await risk_handler.handle_event(event)

    latency_ms = (time.time() - start) * 1000

    # Assert within target
    assert latency_ms < 500, f"Enforcement took {latency_ms:.1f}ms (target: <500ms)"
```

---

## 📁 File Structure (What to Create)

```
risk-daemon/
├── src/
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── sdk_adapter.py           # ← CREATE (Day 1)
│   │   ├── event_normalizer.py      # ← CREATE (Day 1)
│   │   ├── instrument_cache.py      # ← CREATE (Day 2)
│   │   ├── price_cache.py           # ← CREATE (Day 2)
│   │   ├── state_reconciler.py      # ← CREATE (Day 5)
│   │   ├── stop_loss_detector.py    # ← CREATE (Day 5)
│   │   └── exceptions.py            # ← CREATE (Day 1)
│   ├── state/
│   │   ├── sqlite_persistence.py    # ← CREATE (Day 3)
│   │   ├── pnl_tracker.py           # ← CREATE (Day 3)
│   │   └── models.py                # Already exists (add OrderResult)
│   ├── timers/
│   │   ├── __init__.py
│   │   ├── session_timer.py         # ← CREATE (Day 4)
│   │   └── time_tick.py             # ← CREATE (Day 4)
│   ├── monitoring/
│   │   ├── __init__.py
│   │   └── performance_tracker.py   # ← CREATE (Day 3-4)
│   └── notifications/               # ← CREATE (Day 6, optional)
│       ├── __init__.py
│       ├── discord.py
│       └── telegram.py
├── tests/
│   ├── mocks/
│   │   └── mock_sdk.py              # ← CREATE (Test-Orchestrator Day 1)
│   ├── unit/
│   │   ├── test_sdk_adapter.py      # ← CREATE (Test-Orchestrator Day 1-2)
│   │   ├── test_event_normalizer.py
│   │   ├── test_pnl_tracker.py
│   │   └── test_performance_tracker.py
│   └── integration/
│       ├── test_enforcement_flow.py # ← CREATE (Test-Orchestrator Day 3)
│       └── test_state_reconciliation.py
└── .risk_manager/                   # Runtime directory
    └── state.db                     # SQLite database (auto-created)
```

---

## ✅ Success Criteria

**Before marking implementation complete**:

- [ ] All 10 adapter methods implemented and tested
- [ ] EventNormalizer handles all 9 SDK event types
- [ ] SQLite database schema created with 4 tables
- [ ] PnL tracking with 5pm CT reset working
- [ ] Session timer generates daily reset events
- [ ] State reconciliation after disconnect tested
- [ ] Stop loss detection (SDK + manual) working
- [ ] All 6 performance metrics tracked and logged
- [ ] Unit test coverage >80%
- [ ] Integration tests pass with paper account
- [ ] Enforcement latency <500ms (P95) verified
- [ ] No memory leaks over 24-hour run
- [ ] All async tests use `@pytest.mark.asyncio`
- [ ] Code reviewed and approved

---

## 🚦 Go/No-Go Checklist

**Before starting development**:

- [x] Product Owner approved all decisions
- [x] All integration docs read and understood
- [x] SDK installed (`uv add project-x-py`)
- [x] Paper trading account credentials available
- [x] Test environment confirmed working
- [x] Git repository and branches set up
- [x] Developer understands async testing requirements
- [x] Test-Orchestrator ready to create mock SDK

**Status**: 🟢 **ALL GREEN - START DEVELOPMENT**

---

## 📞 Support

**For questions during implementation**:
1. Check integration docs first
2. Review SDK examples: `../project-x-py/examples/`
3. Check async testing rules: `../project-x-py/.cursor/rules/async_testing.md`
4. Escalate blockers to Product Owner (Jake)

---

**🚀 READY TO BUILD - START WITH [handoff_to_dev_and_test.md](handoff_to_dev_and_test.md)**

**Good luck, Developer! All the planning is done. Time to code.** 💪
