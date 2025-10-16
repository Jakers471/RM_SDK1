# Event-Driven Core Architecture

## Overview

The Risk Manager Daemon operates on an **event-driven architecture** rather than polling. This design ensures low-latency enforcement, efficient resource usage, and immediate reaction to trading activity. Events from the broker (via the project-x-py SDK) flow through an event bus to handlers that evaluate risk rules and trigger enforcement actions.

## Why Event-Driven?

### Advantages Over Polling

1. **Instant Response**: React immediately when fills or position updates occur (sub-second enforcement)
2. **Resource Efficiency**: No unnecessary CPU cycles checking state repeatedly
3. **Scalability**: Handle multiple accounts and high-frequency events without overhead
4. **Accuracy**: No risk of missing events between poll intervals
5. **Natural Fit**: Broker SDKs typically expose event-based APIs

### When Polling Is Still Needed

While the core is event-driven, some scenarios may require periodic checks:
- **Timer-based rules**: Cooldown expiration, frequency limit resets
- **Session enforcement**: Check if current time is outside allowed trading hours
- **Heartbeat/watchdog**: Ensure daemon is alive and SDK connection is healthy

These are supplementary to the event-driven core, not the primary mechanism.

## Event Sources

Events originate from the broker via the project-x-py SDK. The implementation agent will identify specific event types, but conceptually we expect:

### 1. Fill Events
**Trigger**: New position opened or added to existing position

**Information Expected**:
- Account ID
- Instrument symbol
- Side (long/short)
- Quantity (contracts filled)
- Fill price
- Timestamp
- Order ID

**Risk Rules Triggered**:
- MaxContracts
- MaxContractsPerInstrument
- TradeFrequencyLimit
- SymbolBlock
- SessionBlockOutside
- NoStopLossGrace (start timer)

### 2. Position Update Events
**Trigger**: Existing position's unrealized PnL changes (price movement)

**Information Expected**:
- Account ID
- Instrument symbol
- Current quantity
- Average entry price
- Current mark price
- Unrealized PnL (current)
- Side (long/short)

**Risk Rules Triggered**:
- UnrealizedLoss (per-trade)
- UnrealizedProfit (per-trade)
- DailyRealizedLoss (combined realized + unrealized check)
- DailyRealizedProfit (combined realized + unrealized check)

### 3. Order Update Events
**Trigger**: Order status changes (placed, filled, cancelled, modified)

**Information Expected**:
- Account ID
- Order ID
- Instrument symbol
- Order type (market, limit, stop)
- Attached stop loss / take profit details
- Order status (working, filled, cancelled)

**Risk Rules Triggered**:
- NoStopLossGrace (verify stop loss attached)
- DuplicateOrderStorm (track order placement rate) - *Note: This was merged with TradeFrequencyLimit, may not be separate*

### 4. Position Close Events
**Trigger**: Position fully closed (manually or via stop/target)

**Information Expected**:
- Account ID
- Instrument symbol
- Realized PnL from this close
- Timestamp

**State Updates**:
- Update realized PnL for the day
- Remove position from open positions
- Re-evaluate combined exposure

### 5. Connection Status Events
**Trigger**: SDK connection established, lost, or reconnected

**Information Expected**:
- Connection status (connected, disconnected)
- Timestamp
- Reason (if disconnect)

**Risk Rules Triggered**:
- AuthLossGuard (alert only, no flatten per user preference)

## Event Bus Architecture

### Conceptual Design

The event bus is the central nervous system of the daemon. It receives raw events from the SDK adapter and routes them to appropriate handlers.

```
SDK Adapter
    ↓ (raw SDK events)
Event Normalizer (convert to internal format)
    ↓ (normalized events)
Event Bus
    ↓ ↓ ↓ (dispatch to multiple handlers)
    ↓ ↓ ↓
Risk    State    Logging
Handler Manager  Handler
```

### Event Flow

1. **SDK emits event** (e.g., onFill callback)
2. **SDK Adapter receives raw event** and extracts data
3. **Event Normalizer** converts to internal standard format
4. **Event Bus dispatches** to all registered handlers
5. **Handlers process in parallel** (risk evaluation, state update, logging)
6. **Risk Handler** determines if enforcement needed
7. **Enforcement Engine** executes action if violation detected

### Event Handler Types

**Risk Handler**
- Evaluates event against all active risk rules
- Determines if enforcement action required
- Sends enforcement command to Enforcement Engine

**State Manager Handler**
- Updates internal state (positions, PnL, timers)
- Maintains single source of truth for account state

**Logging Handler**
- Records all events for audit trail
- Pushes enforcement logs to Trader CLI

**Notification Handler**
- Sends alerts to Discord/Telegram on violations

## SDK Adapter Layer

The SDK Adapter abstracts the project-x-py SDK and provides a clean interface to the rest of the system. This layer is crucial for:

1. **Decoupling**: Core logic doesn't depend on SDK-specific details
2. **Testability**: Can mock SDK for testing without broker connection
3. **Maintainability**: SDK updates only affect adapter, not entire system
4. **Normalization**: Convert SDK's data formats to our internal standard

### Adapter Responsibilities

**Inbound (Events from SDK)**
- Register callbacks/listeners for SDK events
- Normalize event data to internal format
- Emit normalized events to Event Bus
- Handle SDK-specific quirks or edge cases

**Outbound (Commands to SDK)**
- Execute close position orders
- Execute flatten account orders
- Query current positions/PnL if needed
- Manage authentication and connection lifecycle

**Connection Management**
- Handle SDK initialization
- Maintain connection health
- Reconnect on disconnect
- Emit connection status events

### Normalized Event Format (Conceptual)

All events entering the Event Bus should follow a consistent structure:

```
Event {
    event_type: "fill" | "position_update" | "order_update" | "position_close" | "connection_status"
    timestamp: ISO 8601 timestamp
    account_id: string
    data: {
        // Event-specific fields
        // Standardized regardless of SDK format
    }
}
```

Implementation agent will define exact schema based on SDK capabilities.

## Event Handler Design

### Risk Handler (Primary Focus)

The Risk Handler is where risk rules are evaluated. On each event:

1. **Retrieve current state** from State Manager
2. **Evaluate all active rules** for this account
3. **Determine violations** based on event + state
4. **Prioritize enforcement** if multiple rules violated
5. **Send enforcement command** to Enforcement Engine

**Pseudo-logic**:
```
on_event(event):
    account_state = state_manager.get_account_state(event.account_id)

    for rule in active_rules(event.account_id):
        if rule.applies_to_event(event):
            violation = rule.evaluate(event, account_state)

            if violation:
                enforcement_action = rule.get_enforcement_action(violation)
                enforcement_engine.execute(enforcement_action)
                notification_service.alert(violation)
                logger.log_enforcement(violation, enforcement_action)
```

### State Manager Handler

Updates state on every event to maintain accurate real-time view:

```
on_event(event):
    if event.type == "fill":
        state_manager.add_position(event.account_id, event.data)
        state_manager.check_daily_reset()

    elif event.type == "position_update":
        state_manager.update_unrealized_pnl(event.account_id, event.data)

    elif event.type == "position_close":
        state_manager.update_realized_pnl(event.account_id, event.data)
        state_manager.remove_position(event.account_id, event.data)
```

## Event Processing Guarantees

### Key Requirements

1. **Order Preservation**: Events for the same account processed in order received
2. **No Lost Events**: All events from SDK must be captured and processed
3. **Idempotency**: Re-processing same event doesn't cause incorrect state
4. **Atomicity**: State updates and enforcement actions are atomic (don't leave inconsistent state)

### Error Handling

**If Event Processing Fails**:
- Log error with full event details
- Alert admin via notification service
- Continue processing other events (don't crash daemon)
- For critical errors (state corruption): enter safe mode (halt trading, alert admin)

**If Enforcement Action Fails**:
- Retry with exponential backoff
- Alert admin if retries exhausted
- Log failure for audit

## Concurrency Considerations

### Single-Threaded vs Multi-Threaded

**Recommendation: Single-threaded event loop** (like asyncio in Python)

**Rationale**:
- Simpler to reason about state consistency
- No race conditions on shared state
- Easier debugging and testing
- Python's GIL makes true parallelism difficult anyway

**If Multi-Threaded** (future optimization):
- Event Bus dispatches to thread pool
- State Manager uses locks for thread safety
- Careful ordering guarantees needed

### Async I/O

Use asynchronous I/O for:
- SDK event handling (non-blocking callbacks)
- Notification webhooks (Discord/Telegram)
- Logging to files/databases

Avoid blocking the event loop with synchronous I/O.

## Initialization and Shutdown

### Daemon Startup Sequence

1. **Load configuration** from files
2. **Initialize State Manager** (load persisted state if exists)
3. **Initialize SDK Adapter** (connect to broker)
4. **Register event handlers** with Event Bus
5. **Start SDK event listeners**
6. **Enter event processing loop**
7. **Signal ready** (daemon is live)

### Graceful Shutdown

1. **Receive shutdown signal** (admin CLI or service stop)
2. **Stop accepting new events** from SDK
3. **Finish processing queued events**
4. **Persist current state** to disk
5. **Close SDK connection**
6. **Exit**

### Crash Recovery

If daemon crashes unexpectedly:
- **On restart**: Load persisted state from disk
- **Reconcile with broker**: Query current positions via SDK
- **Log discrepancies** if state diverged during downtime
- **Resume normal operation**

## Performance Considerations

### Expected Event Volume

For a single trader:
- **Fill events**: 1-100 per day (low volume)
- **Position updates**: ~1 per second per open position (moderate)
- **Order updates**: Similar to fills

**Estimated throughput needed**: <100 events/second comfortably

### Latency Requirements

- **Event to enforcement**: <1 second (ideally <100ms)
- **Critical for per-trade limits**: Must close position before loss deepens

### Optimization Strategies

- **Lazy rule evaluation**: Only evaluate rules that apply to specific event type
- **Caching**: Cache frequently accessed state (current PnL, position count)
- **Batch notifications**: Aggregate multiple violations into single alert if rapid-fire

## Testing Strategy

### Event Simulation

Create mock event generators to test without live broker:
- Simulate fill sequences
- Simulate price movements (unrealized PnL changes)
- Simulate connection loss/recovery

### Handler Testing

Test each handler independently:
- Risk Handler: Verify rule evaluations with known events
- State Manager: Verify state updates are correct
- Notification Handler: Verify alerts sent properly

### Integration Testing

Full event flow testing:
- Send event through SDK Adapter → Event Bus → All Handlers
- Verify end-to-end behavior (enforcement action executed, state updated, logs created)

## Summary for Implementation Agent

**To implement the event-driven core, you need to:**

1. **Identify SDK event types** in project-x-py:
   - What callbacks/listeners are available?
   - What data is provided in each event?
   - How to register handlers?

2. **Design SDK Adapter**:
   - How to wrap SDK event callbacks?
   - How to normalize SDK data formats?
   - How to execute orders (close position, flatten)?

3. **Build Event Bus**:
   - Simple pub/sub pattern or use existing library?
   - Handler registration mechanism
   - Event dispatch logic

4. **Create normalized event schemas**:
   - Define internal event format
   - Mapping from SDK events to normalized format

5. **Implement core handlers**:
   - Risk Handler (rule evaluation)
   - State Manager Handler (state updates)
   - Logging and notification handlers

This event-driven core is the foundation. All other components (risk rules, enforcement, state management) plug into this architecture.
