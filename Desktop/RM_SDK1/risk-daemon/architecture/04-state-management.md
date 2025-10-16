# State Management Architecture

## Overview

The State Manager is the **single source of truth** for all runtime state in the Risk Manager Daemon. It tracks open positions, realized/unrealized PnL, lockout flags, cooldown timers, trade frequency counters, and all other dynamic state needed for risk rule evaluation. This component must be fast, accurate, and persistent to survive daemon restarts.

## Core Responsibilities

1. **Position Tracking**: Maintain current open positions per account
2. **PnL Calculation**: Track realized and unrealized PnL continuously
3. **Lockout Management**: Manage account lockout flags and expiration
4. **Timer Management**: Track cooldown timers, frequency limit windows
5. **Daily Reset Logic**: Reset all daily counters at 5pm Chicago Time
6. **State Persistence**: Save state to disk for crash recovery
7. **State Queries**: Provide fast read access for Risk Engine

## State Data Model

### Account State

Each account has associated state:

```
AccountState:
    account_id: string
    open_positions: List[Position]
    realized_pnl_today: float
    lockout_until: timestamp | null
    cooldown_until: timestamp | null
    trade_frequency_windows: Dict[string, FrequencyWindow]
    last_daily_reset: timestamp
    error_state: boolean
```

### Position Object

```
Position:
    position_id: string (unique identifier)
    account_id: string
    symbol: string (e.g., "MNQ", "ES")
    side: "long" | "short"
    quantity: integer (contracts)
    entry_price: float (average entry)
    current_price: float (last known mark)
    unrealized_pnl: float (calculated)
    opened_at: timestamp
    pending_close: boolean (order sent but not confirmed)
    stop_loss_attached: boolean
    stop_loss_grace_expires: timestamp | null
```

### Frequency Window

For TradeFrequencyLimit tracking:

```
FrequencyWindow:
    rule_id: string (e.g., "trades_per_15min")
    window_start: timestamp
    window_duration: seconds
    trade_count: integer
    resets_at: timestamp
```

## Critical: Combined PnL Calculation

As emphasized, the State Manager must **continuously track combined exposure**:

```
Total Exposure = Realized PnL + Total Unrealized PnL
```

### Realized PnL Tracking

**When Updated**:
- Position close event (add closed position's PnL to realized total)
- Daily reset at 5pm CT (reset to 0)

**Calculation**:
```
realized_pnl_today = sum(all closed positions' PnL since last 5pm CT)
```

### Unrealized PnL Tracking

**When Updated**:
- Position update event (price movement)
- New fill (new position opened)
- Position close (remove from total)

**Calculation per Position**:
```
For long position:
    unrealized_pnl = (current_price - entry_price) * quantity * multiplier

For short position:
    unrealized_pnl = (entry_price - current_price) * quantity * multiplier
```

**Total Unrealized**:
```
total_unrealized_pnl = sum(unrealized_pnl for all open positions)
```

**Note**: Implementation agent must determine `multiplier` from SDK (point value per contract per instrument).

### Combined Exposure

```
def get_combined_exposure(account_id):
    account = get_account_state(account_id)
    realized = account.realized_pnl_today
    unrealized = sum(p.unrealized_pnl for p in account.open_positions)
    return realized + unrealized
```

This method is called **on every position update event** to check against daily limits.

## Position Management

### Adding Position (Fill Event)

```
def add_position(account_id, fill_data):
    position = Position(
        position_id=generate_id(),
        account_id=account_id,
        symbol=fill_data.symbol,
        side=fill_data.side,
        quantity=fill_data.quantity,
        entry_price=fill_data.fill_price,
        current_price=fill_data.fill_price,
        unrealized_pnl=0.0,
        opened_at=now(),
        pending_close=False,
        stop_loss_attached=False,
        stop_loss_grace_expires=now() + grace_period  # if NoStopLossGrace enabled
    )

    account_state = get_account_state(account_id)
    account_state.open_positions.append(position)

    # Trigger state persistence
    persist_state()
```

### Updating Position (Position Update Event)

```
def update_position(account_id, position_update):
    position = find_position(account_id, position_update.symbol, position_update.side)

    if position:
        position.current_price = position_update.mark_price
        position.unrealized_pnl = calculate_unrealized(position)

        # Trigger state persistence (debounced for performance)
        persist_state_debounced()
```

### Closing Position (Position Close Event)

```
def close_position(account_id, position_id, closed_pnl):
    account_state = get_account_state(account_id)
    position = find_position_by_id(account_id, position_id)

    if position:
        # Update realized PnL
        account_state.realized_pnl_today += closed_pnl

        # Remove from open positions
        account_state.open_positions.remove(position)

        # Trigger state persistence
        persist_state()
```

### Marking Position as Pending Close

When enforcement order sent but not yet confirmed:

```
def mark_pending_close(account_id, position_id):
    position = find_position_by_id(account_id, position_id)
    if position:
        position.pending_close = True
```

Risk Engine checks `pending_close` flag to avoid duplicate enforcement.

## Lockout Management

### Setting Lockout

```
def set_lockout(account_id, until_timestamp, reason):
    account_state = get_account_state(account_id)
    account_state.lockout_until = until_timestamp

    logger.log(f"Account {account_id} locked out until {until_timestamp}: {reason}")
    persist_state()
```

### Checking Lockout

```
def is_locked_out(account_id):
    account_state = get_account_state(account_id)

    if account_state.lockout_until:
        if now() < account_state.lockout_until:
            return True
        else:
            # Lockout expired, clear flag
            account_state.lockout_until = None
            persist_state()
            return False

    return False
```

### Daily Lockout Reset

At 5pm CT daily reset, lockout flags are cleared (unless still within lockout period).

## Cooldown Timer Management

### Starting Cooldown

```
def start_cooldown(account_id, duration_seconds, reason):
    account_state = get_account_state(account_id)
    account_state.cooldown_until = now() + timedelta(seconds=duration_seconds)

    logger.log(f"Account {account_id} cooldown started for {duration_seconds}s: {reason}")
    persist_state()
```

### Checking Cooldown

```
def is_in_cooldown(account_id):
    account_state = get_account_state(account_id)

    if account_state.cooldown_until:
        if now() < account_state.cooldown_until:
            return True
        else:
            # Cooldown expired
            account_state.cooldown_until = None
            persist_state()
            return False

    return False
```

Cooldowns are **temporary** and auto-expire (unlike lockouts which last until 5pm CT).

## Trade Frequency Tracking

### Recording Trade

For TradeFrequencyLimit rules:

```
def record_trade(account_id, rule_id, window_config):
    account_state = get_account_state(account_id)

    if rule_id not in account_state.trade_frequency_windows:
        # Initialize new window
        account_state.trade_frequency_windows[rule_id] = FrequencyWindow(
            rule_id=rule_id,
            window_start=now(),
            window_duration=window_config.duration,
            trade_count=0,
            resets_at=now() + window_config.duration
        )

    window = account_state.trade_frequency_windows[rule_id]

    # Check if window expired
    if now() >= window.resets_at:
        # Reset window
        window.window_start = now()
        window.trade_count = 0
        window.resets_at = now() + window.window_duration

    # Increment count
    window.trade_count += 1
    persist_state()
```

### Checking Frequency Limit

```
def check_frequency_limit(account_id, rule_id, max_trades):
    account_state = get_account_state(account_id)

    if rule_id not in account_state.trade_frequency_windows:
        return False  # No trades yet, not violated

    window = account_state.trade_frequency_windows[rule_id]

    # Check if window expired
    if now() >= window.resets_at:
        return False  # Window reset, fresh start

    return window.trade_count >= max_trades
```

## Daily Reset Logic

### Reset Schedule

All daily counters reset at **5pm Chicago Time**:
- Realized PnL → 0
- Trade frequency (daily windows) → reset
- Lockout flags → cleared (if daily lockout)

### Implementation

**Option 1: Scheduled Task**
- Background thread/task runs every minute
- Checks if current time passed 5pm CT and last reset was before 5pm CT
- If yes, execute reset

**Option 2: Event-Driven Reset**
- On first event after 5pm CT, check if reset needed
- Execute reset before processing event

**Recommended: Option 1** (scheduled task) - ensures reset happens even if no trading activity.

```
def check_and_reset_daily():
    chicago_tz = timezone("America/Chicago")
    now_ct = datetime.now(chicago_tz)
    reset_time_today = now_ct.replace(hour=17, minute=0, second=0)

    for account_id, account_state in all_accounts():
        last_reset = account_state.last_daily_reset

        if last_reset < reset_time_today <= now_ct:
            # Time to reset
            account_state.realized_pnl_today = 0.0
            account_state.lockout_until = None  # Clear daily lockouts

            # Reset daily frequency windows
            for rule_id, window in account_state.trade_frequency_windows.items():
                if window.window_duration >= 86400:  # Daily window
                    window.trade_count = 0
                    window.window_start = now_ct
                    window.resets_at = reset_time_today + timedelta(days=1)

            account_state.last_daily_reset = now_ct
            logger.log(f"Daily reset executed for account {account_id}")
            persist_state()
```

Run this check every minute via background task.

## State Persistence

### Why Persistence?

If daemon crashes or is restarted:
- **Must not lose current state** (positions, PnL, timers)
- **Must resume enforcement** exactly where left off
- **Cannot rely solely on broker state** (may have pending enforcement actions)

### Persistence Strategy

**Save to Disk**:
- JSON file per account (human-readable for debugging)
- Location: configurable (e.g., `~/.risk_manager/state/`)

**When to Save**:
- After every state change (debounced for performance)
- On graceful shutdown
- Periodically (every 30 seconds as backup)

**What to Save**:
- All AccountState objects
- Timestamp of save (for validation on load)

### State File Format (Conceptual)

```json
{
  "account_id": "ABC123",
  "open_positions": [
    {
      "position_id": "pos_001",
      "symbol": "MNQ",
      "side": "long",
      "quantity": 2,
      "entry_price": 5000.50,
      "current_price": 5010.00,
      "unrealized_pnl": 190.00,
      "opened_at": "2025-10-15T10:23:45Z",
      "pending_close": false,
      "stop_loss_attached": true
    }
  ],
  "realized_pnl_today": -150.50,
  "lockout_until": null,
  "cooldown_until": null,
  "trade_frequency_windows": {
    "daily_limit": {
      "rule_id": "daily_limit",
      "window_start": "2025-10-15T17:00:00-05:00",
      "window_duration": 86400,
      "trade_count": 2,
      "resets_at": "2025-10-16T17:00:00-05:00"
    }
  },
  "last_daily_reset": "2025-10-15T17:00:00-05:00",
  "error_state": false,
  "saved_at": "2025-10-15T10:45:30Z"
}
```

### Loading State on Startup

```
def load_persisted_state():
    for account_config in config.accounts:
        state_file = f"state/{account_config.account_id}.json"

        if file_exists(state_file):
            account_state = load_json(state_file)
            validate_state(account_state)
            accounts[account_config.account_id] = account_state
        else:
            # No saved state, initialize fresh
            accounts[account_config.account_id] = AccountState(
                account_id=account_config.account_id,
                open_positions=[],
                realized_pnl_today=0.0,
                lockout_until=None,
                cooldown_until=None,
                trade_frequency_windows={},
                last_daily_reset=now(),
                error_state=False
            )
```

### State Reconciliation

After loading persisted state, **reconcile with broker** to catch any missed events during downtime:

```
def reconcile_state_with_broker(account_id):
    # Query current positions from broker via SDK
    broker_positions = sdk_adapter.get_current_positions(account_id)

    # Compare with loaded state
    state_positions = get_account_state(account_id).open_positions

    for broker_pos in broker_positions:
        if not find_matching_position(state_positions, broker_pos):
            # Position exists at broker but not in state (missed fill event)
            logger.log(f"Reconciliation: Adding missed position {broker_pos}")
            add_position(account_id, broker_pos)

    for state_pos in state_positions:
        if not find_matching_position(broker_positions, state_pos):
            # Position in state but not at broker (missed close event)
            logger.log(f"Reconciliation: Removing stale position {state_pos}")
            close_position(account_id, state_pos.position_id, 0.0)  # Unknown PnL
```

This ensures state is accurate even if daemon was down during trading.

## State Query Interface

Risk Engine and other components query state via clean interface:

```
StateManager:
    get_account_state(account_id) -> AccountState
    get_open_positions(account_id) -> List[Position]
    get_realized_pnl(account_id) -> float
    get_total_unrealized_pnl(account_id) -> float
    get_combined_exposure(account_id) -> float
    is_locked_out(account_id) -> boolean
    is_in_cooldown(account_id) -> boolean
    check_frequency_limit(account_id, rule_id, max_trades) -> boolean
    get_position_count(account_id) -> integer
    get_position_count_by_symbol(account_id, symbol) -> integer
```

All queries are **fast reads** from in-memory state (no disk I/O on query).

## Concurrency and Thread Safety

### Single-Threaded Access (Recommended)

If daemon uses single-threaded event loop:
- No locking needed
- All state updates happen sequentially in event handlers
- Simpler, safer

### Multi-Threaded Access (If Needed)

If daemon is multi-threaded:
- Use **read-write locks** for account state
- Multiple readers allowed (queries)
- Single writer (state updates)
- Or use **actor model** (one thread per account)

## Performance Optimization

### In-Memory State

All state kept in memory for fast access:
- Position lookups: O(1) with dict indexing
- PnL calculations: Incremental (not recalculated from scratch)

### Debounced Persistence

Don't write to disk on every tiny update:
- Batch state saves (e.g., every 5 seconds)
- Immediate save on critical events (lockout, flatten)

### Lazy Cleanup

Expired timers (cooldowns, frequency windows):
- Don't actively scan for expiration
- Check on access (lazy expiration)
- Reduces background processing

## Testing Strategy

### Unit Tests

Test state operations independently:

```
Test: add_position updates open positions
Given: Empty account state
When: add_position called with fill data
Then: open_positions contains 1 position
And: position fields match fill data
```

### Integration Tests

Test state persistence and loading:

```
Test: State survives restart
Given: Account with open positions and realized PnL
When: State saved and reloaded
Then: All positions and PnL match original
```

### Reconciliation Tests

Test state sync with broker:

```
Test: Reconcile missed fill
Given: Broker has position not in state
When: reconcile_state_with_broker called
Then: Position added to state
And: Logged as reconciliation
```

## Edge Cases

### 1. Rapid Position Updates

**Scenario**: Price changes rapidly, many position update events

**Handling**:
- Update unrealized PnL on each event
- Debounce persistence to avoid disk thrashing
- Risk Engine evaluates on every update (no throttling, might trigger enforcement)

### 2. Clock Skew (5pm Reset)

**Scenario**: System clock drifts, 5pm reset happens at wrong time

**Handling**:
- Use Chicago timezone explicitly
- Log all reset times for audit
- Admin can manually trigger reset if needed

### 3. State Corruption

**Scenario**: Saved state file corrupted or invalid

**Handling**:
- Validate on load (check required fields, data types)
- If validation fails, alert admin and initialize fresh state
- Keep backup of last known good state

## Summary for Implementation Agent

**To implement State Manager, you need to:**

1. **Define AccountState and Position data models**
2. **Implement position tracking** (add, update, close)
3. **Implement PnL calculation logic** (realized, unrealized, combined)
4. **Build lockout and cooldown management**
5. **Implement trade frequency tracking**
6. **Create daily reset logic** (5pm CT scheduler)
7. **Build state persistence** (save/load from JSON)
8. **Implement state reconciliation** with broker on startup
9. **Create query interface** for Risk Engine
10. **Determine PnL calculation specifics** from SDK (multipliers, point values)

State Manager is the **memory** of the system. It must be **accurate** (correct PnL), **fast** (sub-millisecond queries), and **durable** (survive crashes). Every other component depends on it.
