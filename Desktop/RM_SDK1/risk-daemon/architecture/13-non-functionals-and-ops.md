# Non-Functional Requirements and Operations

## Overview

This document specifies the non-functional requirements (NFRs) for the Risk Manager Daemon: performance, reliability, operational characteristics, data handling, and quality attributes. These are the "-ilities" that make the system production-ready.

---

## Performance Requirements

### Latency

**Enforcement Latency**: <1 second from rule violation to position closed

- **Event to Decision**: <100ms (event received → rule evaluated)
- **Decision to Order**: <100ms (violation detected → order sent to broker)
- **Order Execution**: <800ms (broker-dependent, out of our control)
- **Total**: <1000ms (target)

**Measurement**: Log timestamp at each stage:
1. Event received: `t0`
2. Rule violation detected: `t1` (must be `t1 - t0 < 100ms`)
3. Enforcement order sent: `t2` (must be `t2 - t1 < 100ms`)
4. Order confirmed: `t3` (broker-dependent)

**Critical Path Optimization**:
- Event queue: in-memory, non-blocking
- Rule evaluation: O(1) lookup for applicable rules
- State queries: in-memory dict/cache, no disk I/O
- Enforcement orders: async send (don't wait for broker ack before continuing)

### Throughput

**Expected Load** (single trader):
- Fill events: 1-100 per day
- Position updates: ~1 per second per open position (max 4 positions = 4/sec)
- Order updates: Similar to fills
- Timer events: 1 per second (TIME_TICK)

**Target Throughput**: 100 events/second sustained (10x headroom)

**Bottleneck Prevention**:
- Single-threaded event loop (no lock contention)
- Bounded event queue (max 10,000 events)
- If queue 80% full, log warning and alert admin

### Resource Usage

**Memory**:
- Daemon process: <500 MB resident
- Per-account state: <10 MB
- Event queue: <50 MB (10,000 events × 5KB avg)

**CPU**:
- Idle (no trading): <2%
- Active trading: <10%

**Disk I/O**:
- State persistence: Debounced (every 5 seconds max)
- Logging: Async buffered writes (flush every 1 second)

**Monitoring**: Log resource usage in HEARTBEAT event every 30 seconds.

---

## Time and Timezone Handling

### Timezone: America/Chicago (Central Time)

**Why**: TopstepX and futures markets operate on Central Time.

**Daily Reset Time**: 17:00 CT (5:00 PM Central Time)

**DST-Safe**:
- Use `pytz` or `zoneinfo` for timezone-aware datetimes
- Reset time is **17:00 local CT**, not UTC offset
- Example: During CDT (UTC-5), reset at 22:00 UTC; during CST (UTC-6), reset at 23:00 UTC

**Implementation**:
```python
from zoneinfo import ZoneInfo

CHICAGO_TZ = ZoneInfo("America/Chicago")

def get_next_reset_time() -> datetime:
    """Get next 5pm CT reset time."""
    now_ct = datetime.now(CHICAGO_TZ)
    reset_today = now_ct.replace(hour=17, minute=0, second=0, microsecond=0)

    if now_ct >= reset_today:
        # Already past 5pm today, reset is tomorrow at 5pm
        reset_next = reset_today + timedelta(days=1)
    else:
        # Reset is today at 5pm
        reset_next = reset_today

    return reset_next
```

**All Event Timestamps**: UTC (for consistency), convert to CT for display/session checks.

---

## Money and Numeric Handling

### Use Python Decimal (No Floats)

**Why**: Avoid floating-point rounding errors with money.

**All monetary values** (PnL, limits, prices) use `decimal.Decimal`:
```python
from decimal import Decimal, ROUND_HALF_UP

# Correct
realized_pnl = Decimal('150.25')
limit = Decimal('-1000.00')

# WRONG - do not use floats
realized_pnl = 150.25  # NEVER DO THIS
```

### Rounding Rules

**PnL Calculations**: Round to **2 decimal places** (cents)
```python
pnl = (exit_price - entry_price) * quantity * tick_value
pnl = pnl.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
```

**Price Comparisons**: Never use `==` for Decimal, use threshold:
```python
# Correct
if abs(price1 - price2) < Decimal('0.01'):
    # Prices are equal

# Wrong
if price1 == price2:  # Fragile due to rounding
```

### Tick Values

**Tick value** (dollar value per 1-point move per contract) is **instrument-specific**:
- MNQ: $5 per point
- ES: $50 per point
- NQ: $20 per point

**SDK Analyst must provide**: Mapping of symbol → tick_value in `sdk_contract.json`.

**Unrealized PnL Formula**:
```python
# Long position
unrealized = (current_price - entry_price) * quantity * tick_value

# Short position
unrealized = (entry_price - current_price) * quantity * tick_value
```

---

## Persistence and State Recovery

### State Persistence

**What to Persist**:
- All `AccountState` objects (positions, PnL, timers, lockouts)
- Last processed event ID (for de-duplication on restart)

**When to Persist**:
- **Immediately**: Lockout set, daily reset, critical state change
- **Debounced** (every 5 seconds): Position updates, PnL changes
- **On shutdown**: Graceful shutdown saves all state

**Where to Persist**:
- JSON files: `~/.risk_manager/state/{account_id}.json`
- File permissions: 600 (user read/write only)

**Format**:
```json
{
  "account_id": "ABC123",
  "open_positions": [...],
  "realized_pnl_today": "150.25",
  "lockout_until": "2025-10-15T22:00:00Z",
  "last_daily_reset": "2025-10-15T22:00:00Z",
  "saved_at": "2025-10-15T23:45:12Z",
  "version": "1.0"
}
```

### Crash Recovery

**On Restart**:
1. Load persisted state from disk
2. Connect to broker via SDK
3. **Reconcile**: Query current positions from broker
4. **Merge**:
   - If position exists at broker but not in state → add (missed fill during downtime)
   - If position in state but not at broker → remove (missed close during downtime)
5. Log reconciliation actions
6. Resume event processing

**State Reconciliation Example**:
```python
# After restart
persisted_positions = load_state_from_disk()
broker_positions = sdk_adapter.get_current_positions()

for broker_pos in broker_positions:
    if not find_in_persisted(broker_pos):
        logger.warning(f"Reconciliation: Adding missed position {broker_pos}")
        state_manager.add_position(broker_pos)

for persisted_pos in persisted_positions:
    if not find_in_broker(persisted_pos):
        logger.warning(f"Reconciliation: Removing stale position {persisted_pos}")
        state_manager.remove_position(persisted_pos)
```

---

## Idempotency

### Enforcement Action Idempotency

**Problem**: Same event or rule violation might trigger multiple times (e.g., rapid position updates).

**Solution**: Track in-flight enforcement actions to prevent duplicates.

**Implementation**:
```python
class EnforcementEngine:
    def __init__(self):
        self.in_flight_actions = set()  # Set of action keys

    def close_position(self, account_id, position_id, reason):
        action_key = f"{account_id}_{position_id}_close"

        if action_key in self.in_flight_actions:
            logger.debug(f"Action {action_key} already in progress, skipping duplicate")
            return

        self.in_flight_actions.add(action_key)
        try:
            # Send close order to broker
            sdk_adapter.close_position(account_id, position_id)
        finally:
            # Remove from in-flight set after completion (or failure)
            self.in_flight_actions.discard(action_key)
```

**Deduplication Window**: 60 seconds (if same action requested within 60s, it's a duplicate).

### Event Deduplication

**Problem**: Broker SDK might send duplicate events (network retry, etc.).

**Solution**: Track last N event IDs processed (LRU cache, size 1000).

**Implementation**:
```python
from collections import OrderedDict

class EventBus:
    def __init__(self):
        self.processed_events = OrderedDict()  # event_id → timestamp

    def publish(self, event: Event):
        if event.event_id in self.processed_events:
            logger.debug(f"Duplicate event {event.event_id}, skipping")
            return

        # Process event
        self.dispatch(event)

        # Track processed
        self.processed_events[event.event_id] = event.timestamp

        # Maintain LRU cache size
        if len(self.processed_events) > 1000:
            self.processed_events.popitem(last=False)  # Remove oldest
```

---

## Logging and Auditing

### Log Formats

**JSON Structured Logs** (for parsing and analysis):
```json
{
  "timestamp": "2025-10-15T10:23:45.123Z",
  "level": "INFO",
  "category": "enforcement",
  "account_id": "ABC123",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "rule": "UnrealizedLoss",
  "action": "close_position",
  "details": {
    "symbol": "MNQ",
    "quantity": 2,
    "unrealized_pnl": "-210.00",
    "limit": "-200.00"
  },
  "message": "Position closed due to unrealized loss limit exceeded"
}
```

**Human-Readable Logs** (for CLI display):
```
[2025-10-15 10:23:45] INFO | enforcement | ABC123 | UnrealizedLoss
Position closed: MNQ 2 contracts
Unrealized PnL: -$210.00 (limit: -$200.00)
Action: Close position
Result: Success
```

### Log Categories

1. **System Log** (`system.log`): Daemon lifecycle, SDK connection, config
2. **Enforcement Log** (`enforcement.log`): All rule violations and actions
3. **Error Log** (`error.log`): Errors and exceptions
4. **Audit Log** (`audit.log`): Admin actions, config changes

### Log Rotation

- **Max file size**: 50 MB
- **Keep**: Last 10 rotated files
- **Compress**: Old logs (gzip)
- **Retention**: 90 days

### Audit Requirements

**All enforcement actions logged with**:
- Event ID (traceability)
- Rule name and version
- Violation details (current value, limit, exceeded by)
- Action taken (close, flatten, lockout)
- Result (success/failure)
- Timestamp (UTC)

**Immutable**: Audit logs cannot be deleted or modified by daemon (only by admin with OS-level access).

---

## Metrics and Monitoring

### Key Metrics

**System Health**:
- Daemon uptime
- Event queue size (current, max, avg)
- Memory usage (MB)
- CPU usage (%)
- Event processing rate (events/sec)

**Business Metrics**:
- Enforcement actions per day (by rule)
- Lockouts per day
- Average time in lockout
- Notification success rate (by channel)

**Performance Metrics**:
- Event processing latency (p50, p95, p99)
- Enforcement latency (event → order sent)
- State persistence latency

### Metrics Storage

**HEARTBEAT event** (every 30 seconds) logs current metrics.

**Future**: Integrate with Prometheus/Grafana for dashboards.

---

## Notification Guarantees

### Critical Notifications (Must Deliver)

**Events**:
- Account locked out (daily limit hit)
- Account flattened
- Config error (daemon cannot start)
- Enforcement action failed

**Delivery Guarantee**:
- **Persisted queue**: Save notification to disk before considering it "sent"
- **Retry strategy**:
  - 3 quick retries (1s, 2s, 4s)
  - Then exponential backoff (1min, 5min, 15min)
  - Keep retrying until delivered or TTL (24 hours)
- **Fallback**: If all channels fail, log to ERROR log and alert via Windows Event Log

### Informational Notifications (Best Effort)

**Events**:
- Position closed (per-trade limit)
- Cooldown started
- Daily reset

**Delivery Guarantee**:
- 3 quick retries (1s, 2s, 4s)
- If fail, log and drop (don't block daemon)

### Notification Content

**All notifications include**:
- Event ID (for tracing)
- Account ID and name
- Rule name
- Reason (why action taken)
- Action (what was done)
- Timestamp

**Critical notifications** also include:
- Current PnL
- Lockout expiration time (if applicable)

---

## Rate Limiting and Backoff

### API Rate Limits (Broker SDK)

**Assumption**: TopstepX SDK has rate limits (TBD by SDK Analyst).

**Enforcement**:
- Track API calls per time window
- If approaching limit, queue non-urgent requests
- Never rate-limit critical enforcement actions (position close/flatten)

### Notification Rate Limiting

**Prevent spam**:
- Max 10 notifications per channel per minute
- If exceeded, aggregate into summary:
  ```
  "5 enforcement actions in last minute:
  - MNQ closed (unrealized loss)
  - ES closed (unrealized loss)
  - Account flattened (daily loss limit)
  - ..."
  ```

### Retry Backoff

**Exponential backoff** for failed operations:
- Initial: 1 second
- Max: 60 seconds
- Formula: `min(60, 2^attempt)`

**Max retries**:
- Critical operations: Infinite (with exponential backoff up to 15min intervals)
- Non-critical: 3 attempts

---

## Error Handling Philosophy

### Fail-Safe Design

**Principle**: When in doubt, protect the account.

**Examples**:
- If state is ambiguous → assume worst case (close positions)
- If SDK disconnects → alert admin, do NOT auto-flatten (per user preference)
- If rule evaluation fails → log error, skip enforcement (conservative)
- If config invalid → halt daemon startup (don't run with bad config)

### Error Recovery

**Transient Errors** (network timeout, broker API error):
- Retry with backoff
- Log as warning
- Continue operation

**Persistent Errors** (config invalid, state corruption):
- Log as critical
- Alert admin
- Enter safe mode (halt trading, keep monitoring)

**Critical Errors** (cannot enforce):
- Flatten all positions (if possible)
- Alert admin immediately
- Halt daemon

---

## Security and Compliance

### Credential Storage

**Development**:
- `.env` file (not committed to version control)
- Plain-text API keys (acceptable for dev only)

**Production**:
- Windows DPAPI-encrypted `secrets.json`
- Encrypted using machine + user account (daemon service account)
- Only daemon process can decrypt

**Never Log**:
- API keys or secrets
- Passwords (even hashed)
- Full account credentials

### Access Control

**Admin CLI**:
- Password-protected (bcrypt hash)
- Strong password required (8+ chars, mixed case, numbers)
- Failed auth attempts logged

**Trader CLI**:
- No password (read-only access to own account)
- Cannot modify rules or stop daemon

**IPC**:
- Local-only (127.0.0.1)
- Token-based auth for admin commands
- Regular user cannot send admin commands

---

## Operational Characteristics

### Startup Time

**Target**: <30 seconds from service start to ready

**Startup Sequence**:
1. Load config: <5s
2. Load state: <5s
3. Connect to broker: <10s
4. Reconcile state: <5s
5. Start event loop: <1s

If startup exceeds 60 seconds, log warning.

### Shutdown Time

**Graceful Shutdown**: <30 seconds

**Shutdown Sequence**:
1. Stop accepting new events: <1s
2. Process remaining queue: <10s
3. Persist state: <5s
4. Close SDK connection: <5s
5. Exit: <1s

If shutdown exceeds 60 seconds, force kill (logged as error).

### Availability

**Target**: 99.9% uptime during trading hours (market open)

**Downtime Budget**: ~8 hours per year (includes planned restarts for config changes)

**Crash Recovery**: Auto-restart within 10 seconds (via NSSM service manager)

---

## Testing Requirements

### Unit Tests

- **Coverage**: >80% for all rules, enforcement engine, state manager
- **Mocking**: Mock SDK adapter, event bus, notification service

### Integration Tests

- **Event flows**: End-to-end event processing
- **State reconciliation**: Crash and restart scenarios
- **Idempotency**: Duplicate events and actions

### E2E Tests

- **Happy path**: Full trading scenario (fill → position update → close)
- **Enforcement**: Trigger each rule and verify action
- **Daily reset**: Simulate 5pm CT reset

### Performance Tests

- **Load test**: 100 events/second sustained for 1 minute
- **Latency test**: Measure event → enforcement latency (must be <1s)

---

## Summary for Developer and Test-Orchestrator

**Critical NFRs to implement**:

✅ **Latency**: <1s enforcement (measure and log)
✅ **Timezone**: America/Chicago, 17:00 CT daily reset (DST-safe)
✅ **Money**: Decimal everywhere, no floats
✅ **Persistence**: State survives crashes (debounced saves)
✅ **Idempotency**: No duplicate enforcement actions
✅ **Logging**: JSON structured logs + audit trail
✅ **Notifications**: Critical = persisted queue + retries, Info = best effort
✅ **Rate limiting**: 10 notifications/min, exponential backoff on retries
✅ **Fail-safe**: When in doubt, protect the account

**Test coverage must verify**:
- Enforcement latency <1s
- Decimal rounding correctness
- State persistence and recovery
- Idempotency under load
- Daily reset at correct CT time
- Notification delivery guarantees

These NFRs are **non-negotiable** - they ensure the system is production-ready and protects trading accounts reliably.
