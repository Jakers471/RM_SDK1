# Risk Engine Architecture

## Overview

The Risk Engine is the brain of the Risk Manager Daemon. It evaluates every trading event against configured risk rules and determines when enforcement actions are required. The engine must be fast, accurate, and modular to support the 12+ risk rules and future extensions.

## Core Responsibilities

1. **Rule Evaluation**: Determine if an event violates any active risk rules
2. **Combined PnL Monitoring**: Continuously track realized + unrealized exposure
3. **Enforcement Decision**: Decide what action to take on rule violation
4. **Rule Prioritization**: Handle scenarios where multiple rules are violated simultaneously
5. **State Coordination**: Work with State Manager to get current account state

## Design Principles

### 1. Plugin-Based Rule Architecture

Each risk rule is a **self-contained module** that implements a standard interface:

```
RiskRule Interface:
    - name: string (e.g., "MaxContracts")
    - enabled: boolean
    - applies_to_event(event_type): boolean
    - evaluate(event, account_state): RuleViolation | None
    - get_enforcement_action(violation): EnforcementAction
```

**Benefits**:
- Easy to add new rules without touching core engine
- Each rule can be tested independently
- Rules can be enabled/disabled per configuration
- Clean separation of concerns

### 2. Stateless Rule Evaluation

Rules themselves are **stateless logic**. They receive:
- **Current event** (fill, position update, etc.)
- **Current account state** (positions, PnL, timers from State Manager)

They return:
- **RuleViolation** if rule breached, with details
- **None** if rule is satisfied

This design keeps rules simple and testable.

### 3. Combined PnL Monitoring (Critical!)

As the user emphasized, the engine must be **smart about PnL tracking**:

```
Total Exposure = Realized PnL (closed positions) + Unrealized PnL (open positions)
```

**Example Scenario**:
- DailyRealizedLoss limit = -$1000
- Currently realized loss = -$800 (from closed trades today)
- Open positions unrealized = -$150
- **Combined exposure = -$950**
- **Remaining buffer = $50 before daily limit hit**

If trader takes another position and it goes -$100 unrealized:
- **New combined = -$800 realized + -$250 unrealized = -$1050**
- **Breaches daily limit → immediate flatten + lockout**

The engine must **continuously monitor** this combined exposure on every position update event.

## Risk Rules Specification

### Rule 1: MaxContracts (Universal Cap)

**Type**: Immediate Adjustment

**Trigger Events**: Fill events

**Logic**:
- Count total open contracts across all instruments for this account
- If count > configured limit, close excess contracts

**Configuration**:
- `max_contracts`: integer (e.g., 4)

**Enforcement**:
- Close excess contracts to bring total to limit
- Close most recently opened positions first (LIFO)

**Example**:
- Limit: 4 contracts
- Current: 2 MNQ long
- New fill: 3 ES long
- Total would be: 5 contracts
- **Action**: Close 1 ES contract → total = 4

---

### Rule 2: MaxContractsPerInstrument

**Type**: Immediate Adjustment

**Trigger Events**: Fill events

**Logic**:
- Count contracts for this specific instrument
- If count > per-instrument limit, close excess

**Configuration**:
- `per_instrument_limits`: dict (e.g., {"MNQ": 2, "ES": 1})

**Enforcement**:
- Close excess contracts for that instrument
- LIFO (most recent first)

**Example**:
- MNQ limit: 2
- Current: 1 MNQ long
- New fill: 2 MNQ long
- Total would be: 3 MNQ
- **Action**: Close 1 MNQ → total = 2

---

### Rule 3: DailyRealizedLoss (Account-Level Lockout)

**Type**: Flatten + Daily Lockout

**Trigger Events**: Position close events, position update events (for combined check)

**Logic**:
- Track total realized loss from all closed positions today (since 5pm CT yesterday)
- **Also check combined**: realized + current unrealized
- If either exceeds limit → flatten all + lockout

**Configuration**:
- `daily_realized_loss_limit`: float (e.g., -1000.00)

**Enforcement**:
- Flatten all open positions immediately
- Set lockout flag until 5pm CT reset
- Block all new orders while locked out

**Example**:
- Limit: -$1000
- Realized so far: -$850
- Open position unrealized: -$200
- **Combined: -$1050 → BREACH**
- **Action**: Flatten all + lockout

---

### Rule 4: DailyRealizedProfit (Account-Level Lockout)

**Type**: Flatten + Daily Lockout

**Trigger Events**: Position close events, position update events (for combined check)

**Logic**:
- Track total realized profit from closed positions today
- **Also check combined**: realized + current unrealized
- If either exceeds limit → flatten all + lockout (lock in profits)

**Configuration**:
- `daily_realized_profit_limit`: float (e.g., 1500.00)

**Enforcement**:
- Flatten all open positions immediately
- Set lockout flag until 5pm CT reset
- Block all new orders while locked out

**Example**:
- Limit: +$1500
- Realized so far: +$1400
- Open position unrealized: +$150
- **Combined: +$1550 → BREACH**
- **Action**: Flatten all + lockout (lock in the profit)

---

### Rule 5: UnrealizedLoss (Per-Trade)

**Type**: Per-Trade Flatten

**Trigger Events**: Position update events

**Logic**:
- For each open position, calculate unrealized PnL (entry price → current mark)
- If any position's unrealized loss exceeds limit → close that position

**Configuration**:
- `unrealized_loss_limit`: float (e.g., -200.00)

**Enforcement**:
- Close the specific position that violated
- Does NOT lockout trading (can open new position immediately)

**Example**:
- Limit: -$200
- Position: 2 MNQ long, entry 5000, current 4950
- Unrealized: -$100 (OK)
- Price drops to 4900
- Unrealized: -$200 → **BREACH**
- **Action**: Close this MNQ position

**Interaction with Daily Limit**:
- Closing this position converts -$200 unrealized to -$200 realized
- Realized loss now updated, may trigger daily limit if close

---

### Rule 6: UnrealizedProfit (Per-Trade)

**Type**: Per-Trade Flatten

**Trigger Events**: Position update events

**Logic**:
- For each open position, track unrealized profit
- If any position's unrealized profit exceeds limit → close that position (lock in profit)

**Configuration**:
- `unrealized_profit_limit`: float (e.g., 500.00)

**Enforcement**:
- Close the specific position that hit profit target
- Does NOT lockout trading

**Example**:
- Limit: +$500
- Position: 1 ES long, entry 4500, current 4550
- Unrealized: +$500 → **BREACH**
- **Action**: Close this ES position (take profit)

---

### Rule 7: TradeFrequencyLimit

**Type**: Reject + Allow Existing

**Trigger Events**: Fill events

**Logic**:
- Track number of fills within configurable time window
- If new fill would exceed limit → reject/close that fill, keep existing positions

**Configuration**:
- `max_trades`: integer (e.g., 3)
- `time_window`: duration (e.g., "per_day", "per_15min", "per_hour")

**Enforcement**:
- Close the violating fill immediately
- Allow existing positions to remain
- Trader can try again after time window resets

**Example (Daily)**:
- Limit: 3 trades per day
- Fills today: 3
- New fill (4th): **BREACH**
- **Action**: Close this fill, existing 3 positions remain

**Example (Per 15min)**:
- Limit: 1 trade per 15 minutes
- Fill at 10:00am
- Fill at 10:05am: **BREACH**
- **Action**: Close this fill, wait until 10:15am

---

### Rule 8: CooldownAfterLoss

**Type**: Temporary Lockout (Soft Block)

**Trigger Events**: Position close events (when realized loss hits threshold)

**Logic**:
- When a closed position realizes a loss >= threshold → start cooldown timer
- During cooldown: block new orders, block adding to positions
- Allow modifying SL/TP, allow manual closing

**Configuration**:
- `loss_threshold`: float (e.g., -100.00)
- `cooldown_duration`: duration (e.g., 300 seconds = 5 minutes)

**Enforcement**:
- Set cooldown flag with expiration timer
- Block new fills during cooldown
- Allow existing positions to be managed

**Example**:
- Threshold: -$100, Duration: 5 minutes
- Position closed with -$150 loss: **BREACH**
- **Action**: Start 5-minute cooldown, block new orders until 10:05am

---

### Rule 9: NoStopLossGrace

**Type**: Immediate Adjustment

**Trigger Events**: Fill events, order update events

**Logic**:
- When new position opened, start grace period timer
- Check if stop loss order attached within grace period
- If no stop loss after grace expires → close position

**Configuration**:
- `grace_period`: duration (e.g., 5 seconds)

**Enforcement**:
- Close position if no stop loss detected
- Trader can immediately retry with stop loss attached

**Example**:
- Grace: 5 seconds
- Fill at 10:00:00
- No stop loss detected by 10:00:05: **BREACH**
- **Action**: Close position

**Technical Note**: Implementation agent must determine how to detect stop loss from SDK (order update events showing attached stop, or position query).

---

### Rule 10: SessionBlockOutside

**Type**: Session-Based Flatten

**Trigger Events**: Fill events, periodic time checks

**Logic**:
- Define allowed trading sessions (days of week + time ranges)
- If fill occurs outside session → close immediately
- Periodically check if still in session (flatten at session end if positions remain)

**Configuration**:
- `allowed_days`: list (e.g., ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
- `allowed_times`: list of time ranges (e.g., [{"start": "08:00", "end": "15:00"}])
- `timezone`: string (e.g., "America/Chicago")

**Enforcement**:
- Close any fills outside session immediately
- At session end (e.g., 3:00pm), flatten all remaining positions

**Example**:
- Session: Mon-Fri, 8am-3pm CT
- Fill at 4:30pm: **BREACH**
- **Action**: Close immediately
- At 3:00pm with open positions: **Action**: Flatten all

---

### Rule 11: SymbolBlock

**Type**: Immediate Adjustment

**Trigger Events**: Fill events

**Logic**:
- Maintain list of blocked symbols
- If fill on blocked symbol → close immediately

**Configuration**:
- `blocked_symbols`: list (e.g., ["GC", "CL"])

**Enforcement**:
- Close position on blocked instrument immediately
- Trader can retry on allowed instruments

**Example**:
- Blocked: ["GC"]
- Fill: 1 GC long: **BREACH**
- **Action**: Close GC position

---

### Rule 12: AuthLossGuard

**Type**: Alert Only

**Trigger Events**: Connection status events (disconnect)

**Logic**:
- Detect SDK connection loss to broker
- Send alert to trader via notifications
- Do NOT take enforcement action (per user preference)

**Configuration**:
- `alert_on_disconnect`: boolean (true)

**Enforcement**:
- Send Discord/Telegram alert
- Log event
- Continue monitoring (attempt reconnect per SDK adapter)

---

## Rule Evaluation Priority

When multiple rules are violated simultaneously, **enforcement actions are prioritized**:

1. **Session/Symbol blocks** (immediate rejection, no point evaluating others)
2. **Daily lockout rules** (flatten all, highest priority)
3. **Per-trade limits** (close specific positions)
4. **Contract limits** (reduce to allowed size)
5. **Frequency/cooldown** (reject new, allow existing)

**Rationale**: More severe actions (lockout, flatten all) take precedence over minor adjustments.

## Combined PnL Monitoring Logic

This is critical to the engine's design:

### Continuous Monitoring

On **every position update event**:

```
realized_pnl = state_manager.get_realized_pnl(account_id)
unrealized_pnl = state_manager.get_total_unrealized_pnl(account_id)
combined_pnl = realized_pnl + unrealized_pnl

if combined_pnl <= daily_realized_loss_limit:
    # Flatten all + lockout

if combined_pnl >= daily_realized_profit_limit:
    # Flatten all + lockout
```

### Per-Trade Unrealized Monitoring

Also on position update events, **for each open position**:

```
for position in open_positions:
    unrealized = position.calculate_unrealized_pnl()

    if unrealized <= unrealized_loss_limit:
        # Close this position

    if unrealized >= unrealized_profit_limit:
        # Close this position
```

### Interaction Between Rules

When per-trade unrealized limit closes a position:
1. Position closed → unrealized becomes realized
2. Realized PnL updated
3. **Re-evaluate combined PnL** against daily limits
4. May trigger daily lockout as secondary effect

**Example**:
- Daily loss limit: -$1000
- Realized: -$850
- Position A unrealized: -$200 (hits per-trade limit of -$200)
- **Action 1**: Close Position A (per-trade rule)
- **Result**: Realized now -$1050
- **Action 2**: Lockout triggered (daily rule)

This cascading logic must be handled by the engine.

## State Coordination

The Risk Engine does **not maintain state itself**. It coordinates with the State Manager:

### Required State Queries

```
state_manager.get_account_state(account_id):
    - open_positions: list of Position objects
    - realized_pnl_today: float
    - total_unrealized_pnl: float
    - lockout_status: boolean
    - cooldown_timers: dict of active cooldowns
    - trade_count_windows: dict of frequency limit tracking
```

### State Updates

After enforcement actions, the engine notifies State Manager:

```
state_manager.set_lockout(account_id, until_timestamp)
state_manager.start_cooldown(account_id, duration)
state_manager.close_position(account_id, position_id)
```

## Rule Configuration Management

Each rule can be:
- **Enabled/Disabled** per account
- **Configured with parameters** (limits, thresholds, durations)
- **Applied universally** across all accounts or per-account

### Configuration Structure (Conceptual)

```
account_config:
    account_id: "ABC123"
    rules:
        - rule: "MaxContracts"
          enabled: true
          params:
              max_contracts: 4

        - rule: "DailyRealizedLoss"
          enabled: true
          params:
              daily_realized_loss_limit: -1000.00

        - rule: "UnrealizedLoss"
          enabled: true
          params:
              unrealized_loss_limit: -200.00
```

Implementation agent will design exact config schema (see 05-configuration-system.md).

## Engine Execution Flow

### On Event Received

```
1. Retrieve account_state from State Manager
2. Check if account locked out → if yes, reject any new fills immediately
3. Get all enabled rules for this account
4. Filter rules that apply to this event type
5. Evaluate each rule:
    a. Call rule.evaluate(event, account_state)
    b. If violation returned, prioritize by severity
6. Execute highest priority enforcement action
7. If action taken, update state and log
8. Continue to next rule if applicable
```

### Pseudo-Code

```python
def on_event(event):
    account_state = state_manager.get_account_state(event.account_id)

    # Check lockout status first
    if account_state.is_locked_out():
        if event.type == "fill":
            enforcement_engine.close_position(event.data.position)
            logger.log("Account locked out, rejecting fill")
        return

    # Get applicable rules
    active_rules = config.get_enabled_rules(event.account_id)
    applicable_rules = [r for r in active_rules if r.applies_to_event(event.type)]

    violations = []
    for rule in applicable_rules:
        violation = rule.evaluate(event, account_state)
        if violation:
            violations.append(violation)

    # Prioritize and enforce
    if violations:
        violations.sort(key=lambda v: v.severity, reverse=True)
        highest_priority = violations[0]

        enforcement_action = highest_priority.rule.get_enforcement_action(highest_priority)
        enforcement_engine.execute(enforcement_action)

        notification_service.alert(highest_priority)
        logger.log_enforcement(highest_priority, enforcement_action)
```

## Testing Strategy

### Unit Testing Rules

Each rule tested independently with mock events and state:

```
Test: MaxContracts rule
Given: account_state with 3 open contracts, limit is 4
When: fill event adds 2 contracts
Then: rule.evaluate returns violation with "close 1 contract"
```

### Integration Testing

Full rule evaluation with real state manager:

```
Test: Combined PnL monitoring
Given: realized -$900, unrealized -$50, daily limit -$1000
When: position update shows unrealized now -$150
Then: combined = -$1050 → daily lockout triggered
```

### Cascading Rule Testing

Test rules that interact:

```
Test: Per-trade limit triggers daily limit
Given: realized -$850, unrealized loss limit -$200, daily limit -$1000
When: position hits -$200 unrealized
Then: position closed, realized becomes -$1050, daily lockout triggered
```

## Performance Considerations

### Fast Rule Evaluation

- **Lazy loading**: Only load rules that apply to event type
- **Early exit**: If high-priority violation found, skip lower-priority rules
- **Cached config**: Don't re-parse config on every event

### Memory Efficiency

- Rules are stateless (no per-rule state storage)
- State Manager handles all state (single source)

## Extensibility

### Adding New Rules

To add a new risk rule (e.g., "AutoBreakeven"):

1. Create new rule module implementing RiskRule interface
2. Define rule logic in `evaluate()` method
3. Define enforcement action in `get_enforcement_action()`
4. Add rule to configuration schema
5. Register rule with Risk Engine

**No changes to core engine needed!**

## Summary for Implementation Agent

**To implement the Risk Engine, you need to:**

1. **Create RiskRule interface/base class**
2. **Implement each of the 12 rules** as separate modules
3. **Build rule evaluation orchestrator** (the main engine loop)
4. **Integrate with State Manager** for state queries
5. **Integrate with Enforcement Engine** for action execution
6. **Implement combined PnL monitoring** logic (critical!)
7. **Handle rule prioritization** and cascading effects
8. **Create rule configuration loading** mechanism

The Risk Engine is the core logic that makes this system work. All design decisions here flow from the requirement to **prevent account blow-ups** through **instant, accurate, automated enforcement**.
