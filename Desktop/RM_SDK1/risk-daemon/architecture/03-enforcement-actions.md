# Enforcement Actions Architecture

## Overview

The Enforcement Engine is the **executor** of risk management. When the Risk Engine detects a rule violation, the Enforcement Engine takes concrete action: closing positions, flattening accounts, setting lockouts, or sending alerts. This module must be reliable, fast, and handle errors gracefully since it's the last line of defense against account blow-ups.

## Core Responsibilities

1. **Execute Actions**: Close specific positions, flatten entire accounts, set lockouts
2. **Order Management**: Send close/flatten orders to broker via SDK Adapter
3. **Retry Logic**: Handle failed orders with intelligent retry
4. **Idempotency**: Ensure repeated action requests don't cause issues
5. **Error Handling**: Gracefully handle broker rejections, network errors
6. **Logging**: Record all actions with full context for audit trail

## Enforcement Action Types

Based on our risk rule analysis, we have **5 distinct action types**:

### 1. Close Specific Position

**Description**: Close a specific position (partial or full)

**Used By**:
- UnrealizedLoss (per-trade)
- UnrealizedProfit (per-trade)
- MaxContracts (close excess)
- MaxContractsPerInstrument (close excess)
- NoStopLossGrace
- SymbolBlock

**Parameters**:
- `account_id`: string
- `position_id`: string (or instrument + side)
- `quantity`: integer (how many contracts to close)
- `reason`: string (why this action taken, for logging)

**Execution**:
- Send market order to close specified quantity
- If partial close, verify correct quantity closed
- Update State Manager on confirmation

**Example**:
```
close_position(
    account_id="ABC123",
    position_id="MNQ_LONG",
    quantity=1,
    reason="MaxContractsPerInstrument limit exceeded"
)
```

---

### 2. Flatten Account (All Positions)

**Description**: Close ALL open positions for an account immediately

**Used By**:
- DailyRealizedLoss (with lockout)
- DailyRealizedProfit (with lockout)
- SessionBlockOutside (at session end)

**Parameters**:
- `account_id`: string
- `reason`: string

**Execution**:
- Query all open positions for account
- Send market orders to close each position
- Wait for all confirmations (or timeout)
- Update State Manager when complete

**Example**:
```
flatten_account(
    account_id="ABC123",
    reason="Daily realized loss limit exceeded (-$1050 / -$1000)"
)
```

---

### 3. Set Account Lockout

**Description**: Block all new trading until specified time

**Used By**:
- DailyRealizedLoss (until 5pm CT)
- DailyRealizedProfit (until 5pm CT)

**Parameters**:
- `account_id`: string
- `until`: timestamp (when lockout expires)
- `reason`: string

**Execution**:
- Set lockout flag in State Manager
- All subsequent fill events rejected while locked out
- Lockout auto-expires at specified time

**Example**:
```
set_lockout(
    account_id="ABC123",
    until="2025-10-15T17:00:00-05:00",  # 5pm CT
    reason="Daily realized loss limit exceeded"
)
```

---

### 4. Start Cooldown Timer

**Description**: Temporarily block new orders, allow existing position management

**Used By**:
- CooldownAfterLoss
- TradeFrequencyLimit (per-minute/hour variants)

**Parameters**:
- `account_id`: string
- `duration`: seconds
- `reason`: string

**Execution**:
- Set cooldown timer in State Manager
- Block new fills during cooldown
- Allow SL/TP modifications and manual closes
- Timer auto-expires after duration

**Example**:
```
start_cooldown(
    account_id="ABC123",
    duration=300,  # 5 minutes
    reason="Loss of -$150 triggered cooldown threshold"
)
```

---

### 5. Send Alert (No Position Action)

**Description**: Notify trader without taking position action

**Used By**:
- AuthLossGuard (connection loss)

**Parameters**:
- `account_id`: string
- `message`: string
- `severity`: enum (info, warning, critical)

**Execution**:
- Send notification via Discord/Telegram
- Log alert
- No position changes

**Example**:
```
send_alert(
    account_id="ABC123",
    message="SDK connection to TopstepX lost",
    severity="critical"
)
```

---

## Enforcement Engine Design

### Core Interface

The Enforcement Engine exposes these methods:

```
EnforcementEngine:
    close_position(account_id, position_id, quantity, reason)
    flatten_account(account_id, reason)
    set_lockout(account_id, until, reason)
    start_cooldown(account_id, duration, reason)
    send_alert(account_id, message, severity)
```

### Execution Flow

```
Risk Engine detects violation
    ↓
Calls EnforcementEngine.close_position()
    ↓
EnforcementEngine validates request (idempotency check)
    ↓
Sends order via SDK Adapter
    ↓
Waits for confirmation (with timeout)
    ↓
On success: Update State Manager, log action, send notification
    ↓
On failure: Retry with backoff, alert admin if exhausted
```

## Idempotency and Safety

### Idempotency Requirements

**Problem**: Risk Engine might call same action multiple times (e.g., multiple events trigger same rule)

**Solution**: Track in-flight enforcement actions

```
EnforcementEngine.close_position():
    action_key = f"{account_id}_{position_id}_close"

    if action_key in in_flight_actions:
        logger.log("Action already in progress, skipping duplicate")
        return

    in_flight_actions.add(action_key)
    try:
        execute_close_order()
    finally:
        in_flight_actions.remove(action_key)
```

### Preventing Over-Enforcement

**Scenario**: Rule triggers, position close order sent, but before confirmation another event triggers same rule

**Protection**:
- Mark position as "pending close" immediately when order sent
- Risk Engine checks pending status before evaluating rules
- Don't send second close order for same position

## Order Execution Details

### Market Orders for Speed

All enforcement orders should be **market orders** for immediate execution:
- **Why**: Need instant enforcement, can't wait for limit order fills
- **Trade-off**: May get slight slippage, but protection is more important

### Partial vs Full Position Closes

Some rules close partial positions (e.g., MaxContracts might close 1 of 3 contracts):
- Specify exact quantity in close order
- Verify correct quantity filled (check confirmation)
- If wrong quantity, log error and alert admin

### Flatten Account Implementation

To flatten account:
1. Query current open positions via SDK Adapter
2. For each position, send market order to close full quantity
3. Track all orders sent
4. Wait for all confirmations (parallel execution)
5. If any fail, retry those specific closes

**Timeout**: If confirmation not received within X seconds (e.g., 10s), log error and alert admin

## Retry Logic and Error Handling

### When Orders Fail

Possible failure scenarios:
- Network error (can't reach broker)
- Broker rejection (invalid symbol, market closed, etc.)
- SDK error (bug, unexpected response)

### Retry Strategy

```
Max retries: 3
Backoff: Exponential (1s, 2s, 4s)

on_order_failure(error):
    if retries < max_retries:
        wait(backoff_time)
        retry_order()
    else:
        alert_admin("Enforcement order failed after retries")
        log_critical_error(error)
```

### Critical Errors

If enforcement action fails completely (all retries exhausted):
- **Log as critical error**
- **Alert admin immediately** (Discord/Telegram + system alert)
- **Continue daemon operation** (don't crash, protect other accounts)
- **Mark account as "error state"** to prevent further trading until admin intervenes

## State Coordination

### State Updates Post-Enforcement

After successful enforcement:

```
on_close_position_confirmed(position_id):
    state_manager.remove_position(account_id, position_id)
    state_manager.update_realized_pnl(account_id, closed_pnl)
    logger.log_enforcement("Position closed", reason, details)
    notification_service.alert(account_id, "Position closed: {reason}")
```

### State Updates for Lockouts

```
on_set_lockout(account_id, until):
    state_manager.set_lockout_flag(account_id, True, until)
    logger.log_enforcement("Account locked out", reason, until)
    notification_service.alert(account_id, "Trading locked until {until}")
```

## Logging Requirements

Every enforcement action must be logged with:

1. **Timestamp**: When action executed
2. **Account ID**: Which account
3. **Rule Name**: Which rule triggered enforcement
4. **Reason**: Why rule was violated (details)
5. **Action Taken**: What was done (close position, flatten, lockout)
6. **Position Details**: Symbol, quantity, price if applicable
7. **Result**: Success or failure
8. **Order ID**: Broker order ID for reference

### Log Format Example

```
[2025-10-15 10:23:45] ENFORCEMENT
Account: ABC123
Rule: UnrealizedLoss
Reason: Position MNQ 2 contracts unrealized loss -$210 exceeds limit -$200
Action: Close position MNQ_LONG quantity 2
Order ID: 1234567890
Result: Success (filled @ 5042.50)
Realized PnL from close: -$210
```

This log is displayed in **red text** in Trader CLI and stored for audit.

## Notification Integration

After enforcement action:

```
notification_service.send(
    account_id=account_id,
    title="Risk Enforcement",
    message=f"Closed {position} - {reason}",
    severity="warning"
)
```

Trader receives real-time alert via configured channel (Discord/Telegram).

## SDK Adapter Integration

Enforcement Engine relies on SDK Adapter for order execution:

### Required SDK Adapter Methods

```
SDKAdapter:
    close_position(account_id, position_id, quantity) -> OrderResult
    flatten_account(account_id) -> List[OrderResult]
    get_open_positions(account_id) -> List[Position]
```

Implementation agent will map these to actual project-x-py SDK methods.

### Order Confirmation

SDK Adapter should return:
- **Success**: Order ID, fill price, filled quantity
- **Failure**: Error message, error code

Enforcement Engine waits for this response before updating state.

## Concurrency Considerations

### Parallel Enforcement

Multiple rules might trigger simultaneously (e.g., daily limit AND per-trade limit):
- Enforcement Engine should handle **queued actions** sequentially
- Use action queue to prevent race conditions
- Process one action at a time per account

### Across Multiple Accounts

If monitoring multiple accounts:
- Enforcement actions for **different accounts** can execute in parallel
- Enforcement actions for **same account** must be serialized

## Testing Strategy

### Unit Tests

Test each action type independently:

```
Test: close_position
Given: Mock SDK Adapter
When: close_position called
Then: Correct SDK method called with correct parameters
And: State Manager updated on confirmation
And: Log entry created
```

### Integration Tests

Test full enforcement flow:

```
Test: Unrealized loss enforcement
Given: Real State Manager and mock SDK
When: Position update shows -$210 loss (limit -$200)
Then: Risk Engine triggers enforcement
And: close_position called
And: SDK order sent
And: State updated with realized loss
And: Notification sent
```

### Failure Tests

Test retry logic and error handling:

```
Test: Order fails then succeeds on retry
Given: SDK fails first call, succeeds second
When: close_position called
Then: First attempt fails
And: Retry after backoff
And: Second attempt succeeds
And: State updated correctly
```

## Performance Requirements

### Latency

- **Order submission**: <100ms from enforcement decision to order sent
- **Total enforcement time**: <1 second from rule violation to position closed (broker-dependent)

### Reliability

- **99.9% success rate** on enforcement orders (under normal conditions)
- **Zero missed enforcements** (all violations must result in action)

## Edge Cases and Scenarios

### 1. Position Already Closed

**Scenario**: Trader manually closes position just as enforcement triggers

**Handling**:
- SDK returns error "position not found"
- Log as "no action needed, position already closed"
- Update State Manager to remove position
- No alert needed (trader already closed it)

### 2. Insufficient Liquidity

**Scenario**: Market order to close position can't be filled (illiquid market)

**Handling**:
- SDK order may partially fill
- Alert admin immediately (critical)
- Mark account as error state
- Attempt to close remaining quantity with limit order at worse price

### 3. Market Closed

**Scenario**: Enforcement triggered outside market hours

**Handling**:
- SDK likely rejects order
- Log error
- **Set flag to flatten at market open** (pending enforcement)
- Alert admin
- Lockout account until manual intervention

### 4. Multiple Rules Violated Simultaneously

**Scenario**: Daily limit AND per-trade limit both breached

**Handling**:
- Risk Engine prioritizes daily limit (flatten all)
- Execute flatten account (also closes the per-trade violating position)
- Log both violations
- Single enforcement action serves both rules

## Graceful Degradation

If Enforcement Engine is unable to execute actions:
- **Daemon does NOT crash**
- **Account marked as error state** (no further trading allowed)
- **Admin alerted immediately**
- **All events logged for manual review**
- **Trader notified via CLI** that enforcement is in error state

The system **fails safe**: if can't enforce, block all trading.

## Summary for Implementation Agent

**To implement the Enforcement Engine, you need to:**

1. **Create EnforcementEngine class** with 5 core methods
2. **Integrate with SDK Adapter** for order execution
3. **Implement idempotency tracking** to prevent duplicate actions
4. **Build retry logic** with exponential backoff
5. **Coordinate with State Manager** for state updates post-enforcement
6. **Integrate with Notification Service** for alerts
7. **Create comprehensive logging** for all actions
8. **Handle all error scenarios** gracefully (position not found, market closed, etc.)
9. **Implement action queue** for serialization per account
10. **Map enforcement actions to SDK methods** (close position, flatten account)

The Enforcement Engine is the **final safety net**. It must be bulletproof, because if it fails, the account is at risk. Every design decision prioritizes **reliability and fail-safe behavior** over performance or complexity.
