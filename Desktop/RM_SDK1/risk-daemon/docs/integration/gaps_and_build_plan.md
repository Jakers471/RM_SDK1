# Gaps and Build Plan

## Overview

This document identifies capabilities **NOT** provided by project-x-py SDK and defines the build plan for implementing them.

---

## Gap 1: Pre-Trade Order Rejection

**What's Missing**: No way to block orders before they reach the broker.

**Impact**: CRITICAL
**Priority**: P0 (Core design implication)

**Why SDK Can't Provide**:
- SDK is client-side library
- Cannot intercept orders placed via other clients (web UI, mobile app)
- Broker API has no pre-trade validation hooks

**Build Plan**:
❌ **CANNOT BUILD** - Architectural limitation

**Mitigation Strategy**:
1. **Enforce Post-Fill**:
   - Listen for `ORDER_FILLED` events
   - Evaluate rules immediately upon fill
   - Close position via market order if rule violated

2. **Minimize Latency**:
   - Single-threaded event loop (no async overhead)
   - Pre-calculate rule thresholds
   - Use market orders for instant execution

3. **Expected Performance**:
   - Event propagation: 50-100ms
   - Rule evaluation: <10ms
   - Close order placement: 20-50ms
   - Order fill confirmation: 50-200ms
   - **Total latency**: 120-360ms from fill to close

**Acceptance Criteria**:
✅ 95% of enforcement actions execute within 500ms
✅ No rule violation goes unenforced for >1 second
✅ All enforcement actions logged with timestamps

**Testing**:
- Simulate fills with varying network latency
- Measure end-to-end enforcement time
- Stress test with rapid fills

---

## Gap 2: Flatten All Positions

**What's Missing**: No single SDK method to close all positions at once.

**Impact**: LOW
**Priority**: P2 (Nice to have)

**Build Plan**:

**Implementation**:
```python
async def flatten_account(self, account_id: str) -> List[OrderResult]:
    """Close all positions for account."""
    # 1. Query current positions
    positions = await self.client.search_open_positions(account_id)

    # 2. Close each position
    results = []
    for position in positions:
        try:
            result = await self.suite.orders.close_position(
                position.contractId,
                method="market"
            )
            results.append(OrderResult(
                success=True,
                order_id=str(result.orderId),
                contract_id=position.contractId,
                quantity=position.size
            ))
        except Exception as e:
            results.append(OrderResult(
                success=False,
                error_message=str(e),
                contract_id=position.contractId,
                quantity=position.size
            ))

    return results
```

**Edge Cases**:
1. **Race Condition**: New position opened during flatten
   - **Mitigation**: Query positions again after flatten, close any new positions
2. **Partial Failures**: Some positions close, others fail
   - **Mitigation**: Return list of OrderResult, log all failures

**Acceptance Criteria**:
✅ All positions closed within 2 seconds (for up to 10 positions)
✅ Failed closes logged with error details
✅ Idempotent (safe to call twice)

**Estimated Effort**: 2 hours (including tests)

---

## Gap 3: Realized PnL Tracking

**What's Missing**: SDK doesn't track realized PnL or provide daily aggregates.

**Impact**: HIGH
**Priority**: P0 (Core feature)

**Build Plan**:

**Data Structure** (add to `AccountState`):
```python
@dataclass
class AccountState:
    # ... existing fields ...

    realized_pnl_today: Decimal = Decimal('0.00')  # Closes since last reset
    last_daily_reset: datetime                      # When last reset occurred
```

**Implementation**:

1. **Track Realized PnL**:
   ```python
   async def on_position_closed(event: Event):
       """Update realized PnL when position closes."""
       # Query trades for closed position
       trades = await client.search_trades(
           contract_id=event.data['contractId'],
           start_date=last_daily_reset
       )

       # Sum PnL from closing trades
       realized_pnl = sum(
           trade.profitAndLoss or 0
           for trade in trades
           if trade.profitAndLoss is not None
       )

       # Update state
       state.realized_pnl_today += Decimal(str(realized_pnl))
   ```

2. **Daily Reset (5pm CT)**:
   ```python
   async def on_session_tick(event: Event):
       """Reset realized PnL at 5pm CT daily."""
       if event.data['tick_type'] == 'daily_reset':
           for account_id, state in accounts.items():
               state.realized_pnl_today = Decimal('0.00')
               state.last_daily_reset = datetime.utcnow()
               logger.info(f"Daily reset for account {account_id}")
   ```

**Acceptance Criteria**:
✅ Realized PnL accurately reflects closed positions
✅ Daily reset occurs exactly at 5pm CT (±5 seconds)
✅ PnL persists across daemon restarts (until reset)
✅ Combined exposure (realized + unrealized) calculated correctly

**Estimated Effort**: 1 day (including timer logic and persistence)

---

## Gap 4: Unrealized PnL Calculation

**What's Missing**: SDK Position object doesn't include unrealized PnL.

**Impact**: HIGH
**Priority**: P0 (Core feature)

**Build Plan**:

**Implementation** (in `EventNormalizer` or `StateManager`):
```python
def calculate_unrealized_pnl(
    position: Position,
    current_price: Decimal,
    tick_value: Decimal
) -> Decimal:
    """
    Calculate unrealized PnL for position.

    Args:
        position: Position object with entry price and size
        current_price: Current market price (from quote cache)
        tick_value: Dollars per point (from instrument cache)

    Returns:
        Unrealized PnL in dollars (rounded to cents)
    """
    if position.side == "long":
        pnl = (current_price - position.entry_price) * position.quantity * tick_value
    else:  # short
        pnl = (position.entry_price - current_price) * position.quantity * tick_value

    return pnl.quantize(Decimal('0.01'))
```

**Data Requirements**:
1. **Current Price**: From `QUOTE_UPDATE` events → price cache
2. **Tick Value**: From instrument metadata → instrument cache

**Price Cache**:
```python
class PriceCache:
    """Cache latest quotes for PnL calculation."""

    def __init__(self):
        self._prices: Dict[str, Decimal] = {}

    async def update_from_quote(self, event: Event):
        """Update cache from QUOTE_UPDATE event."""
        symbol = extract_symbol(event.data['contractId'])
        bid = Decimal(str(event.data['bid']))
        ask = Decimal(str(event.data['ask']))
        mid_price = (bid + ask) / 2
        self._prices[symbol] = mid_price

    def get_price(self, symbol: str) -> Optional[Decimal]:
        """Get cached price for symbol."""
        return self._prices.get(symbol)
```

**Acceptance Criteria**:
✅ Unrealized PnL calculated within 100ms of quote update
✅ PnL accuracy ±$0.01 (due to rounding)
✅ Handles missing prices gracefully (returns 0.0 and logs warning)

**Estimated Effort**: 4 hours (including price cache)

---

## Gap 5: Daily Reset Logic (5pm CT)

**What's Missing**: No built-in concept of trading day reset.

**Impact**: HIGH
**Priority**: P0 (Core feature)

**Build Plan**:

**Timer Implementation**:
```python
import pytz
import asyncio
from datetime import datetime, time

async def session_timer(event_bus: EventBus):
    """
    Generate SESSION_TICK events at 5pm CT daily.

    Runs continuously, checking time every second.
    Emits 'daily_reset' event exactly once per day at 5pm.
    """
    ct_tz = pytz.timezone("America/Chicago")
    reset_time = time(hour=17, minute=0, second=0)  # 5pm CT

    last_reset_date = None

    while True:
        now_ct = datetime.now(ct_tz)
        current_date = now_ct.date()
        current_time = now_ct.time()

        # Check if 5pm CT and haven't reset today yet
        if (
            current_time.hour == 17
            and current_time.minute == 0
            and last_reset_date != current_date
        ):
            # Emit daily reset event
            event = Event(
                event_id=uuid4(),
                event_type=EventType.SESSION_TICK,
                timestamp=datetime.utcnow(),
                priority=5,
                account_id="system",
                source="session_timer",
                data={
                    "tick_type": "daily_reset",
                    "tick_time": datetime.utcnow(),
                    "timezone": "America/Chicago"
                }
            )
            await event_bus.publish(event)

            last_reset_date = current_date
            logger.info(f"Daily reset triggered at {now_ct}")

            # Wait 60 seconds to avoid duplicate resets
            await asyncio.sleep(60)

        await asyncio.sleep(1)  # Check every second
```

**Edge Cases**:
1. **Daylight Saving Time**: pytz handles DST automatically
2. **Daemon Restart**: Check if reset already occurred today (persist last_reset_date)
3. **Missed Reset**: If daemon down during 5pm, trigger reset on startup if past 5pm

**Acceptance Criteria**:
✅ Reset occurs exactly at 5pm CT (±5 seconds)
✅ Reset occurs exactly once per day (no duplicates)
✅ DST transitions handled correctly
✅ Missed resets triggered on startup

**Estimated Effort**: 6 hours (including DST handling and persistence)

---

## Gap 6: TIME_TICK Events (1-second interval)

**What's Missing**: No built-in timer events for rule evaluation.

**Impact**: MEDIUM
**Priority**: P1 (For timer-based rules)

**Build Plan**:

**Implementation**:
```python
async def time_tick_generator(event_bus: EventBus):
    """
    Generate TIME_TICK events every 1 second.

    Used for timer-based rule evaluation (grace periods, cooldowns).
    """
    while True:
        event = Event(
            event_id=uuid4(),
            event_type=EventType.TIME_TICK,
            timestamp=datetime.utcnow(),
            priority=4,
            account_id="system",
            source="timer",
            data={"tick_time": datetime.utcnow()}
        )
        await event_bus.publish(event)
        await asyncio.sleep(1.0)
```

**Usage in Rules**:
```python
class NoStopLossGrace(RiskRulePlugin):
    """Check if stop loss grace period expired."""

    def applies_to_event(self, event_type: EventType) -> bool:
        return event_type == EventType.TIME_TICK

    def evaluate(self, event: Event, state: AccountState) -> Optional[RuleViolation]:
        now = event.data['tick_time']

        for position in state.open_positions:
            if position.stop_loss_grace_expires and now >= position.stop_loss_grace_expires:
                if not position.stop_loss_attached:
                    return RuleViolation(
                        rule_name="NoStopLossGrace",
                        message=f"Grace period expired without stop loss",
                        position_id=position.position_id
                    )
        return None
```

**Acceptance Criteria**:
✅ Tick generated every 1 second (±50ms)
✅ Low CPU overhead (<1% with 12 rules)
✅ Graceful shutdown (stop ticking)

**Estimated Effort**: 2 hours

---

## Gap 7: Stop Loss Detection

**What's Missing**: Position object doesn't indicate if stop loss attached.

**Impact**: MEDIUM
**Priority**: P1 (For NoStopLossGrace rule)

**Build Plan**:

**Approach 1: Query Orders Periodically**
```python
async def detect_stop_loss(position: Position) -> bool:
    """Check if position has stop loss attached."""
    # Get all open orders
    orders = await client.get_open_orders()

    # Filter for stop orders on same contract
    stop_orders = [
        o for o in orders
        if o.type == OrderType.STOP
        and o.contractId == position.contractId
        and not o.is_terminal
    ]

    return len(stop_orders) > 0
```

**Approach 2: Track Bracket Orders**
```python
# When bracket order placed:
bracket = await suite.orders.place_bracket_order(...)
position_stop_map[position_id] = {
    'stop_order_id': bracket.stop_order_id,
    'target_order_id': bracket.target_order_id
}

# Check if stop still exists:
async def has_stop_loss(position_id: UUID) -> bool:
    if position_id not in position_stop_map:
        return False

    stop_order_id = position_stop_map[position_id]['stop_order_id']
    order = await client.get_order(stop_order_id)
    return order.is_working  # True if not filled/cancelled
```

**Recommendation**: Use **Approach 2** (track internally) for SDK-placed orders, fallback to **Approach 1** (periodic query) for manually-placed stops.

**Acceptance Criteria**:
✅ Detect SDK-placed stops with 100% accuracy
✅ Detect manually-placed stops within 30 seconds (polling interval)
✅ Handle stop cancellation/modification

**Estimated Effort**: 1 day (both approaches)

---

## Gap 8: State Reconciliation After Reconnect

**What's Missing**: SDK reconnects WebSocket but doesn't replay missed events.

**Impact**: MEDIUM
**Priority**: P1 (Reliability)

**Build Plan**:

**Implementation**:
```python
async def on_reconnected(event: Event):
    """Reconcile state after WebSocket reconnection."""
    logger.warning("Reconnected to broker, reconciling state...")

    for account_id in monitored_accounts:
        # 1. Query current positions from REST API
        sdk_positions = await client.search_open_positions(account_id)

        # 2. Compare with cached state
        cached_positions = state_manager.get_account_state(account_id).open_positions

        # 3. Detect discrepancies
        missing_in_cache = [p for p in sdk_positions if p.id not in [cp.position_id for cp in cached_positions]]
        extra_in_cache = [cp for cp in cached_positions if cp.position_id not in [p.id for p in sdk_positions]]

        # 4. Update state
        for position in missing_in_cache:
            logger.warning(f"Position {position.id} opened during disconnect, adding to state")
            state_manager.add_position_from_sdk(position)

        for position in extra_in_cache:
            logger.warning(f"Position {position.position_id} closed during disconnect, removing from state")
            state_manager.remove_position(position.position_id)

        # 5. Re-evaluate rules with reconciled state
        await risk_engine.re_evaluate_all_rules(account_id)

    logger.info("State reconciliation complete")
```

**Acceptance Criteria**:
✅ Reconciliation completes within 5 seconds of reconnect
✅ All state discrepancies detected and logged
✅ Rules re-evaluated after reconciliation

**Estimated Effort**: 6 hours (including testing)

---

## Gap 9: Discord/Telegram Notifications

**What's Missing**: SDK has no notification integrations.

**Impact**: LOW
**Priority**: P2 (User convenience)

**Build Plan**:

**Discord Webhook**:
```python
import aiohttp

async def send_discord_alert(webhook_url: str, message: str, severity: str):
    """Send alert to Discord via webhook."""
    color = {
        "info": 0x3498db,      # Blue
        "warning": 0xf39c12,   # Orange
        "critical": 0xe74c3c   # Red
    }[severity]

    payload = {
        "embeds": [{
            "title": f"Risk Manager Alert ({severity.upper()})",
            "description": message,
            "color": color,
            "timestamp": datetime.utcnow().isoformat()
        }]
    }

    async with aiohttp.ClientSession() as session:
        await session.post(webhook_url, json=payload)
```

**Telegram Bot**:
```python
async def send_telegram_alert(bot_token: str, chat_id: str, message: str):
    """Send alert via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    async with aiohttp.ClientSession() as session:
        await session.post(url, json=payload)
```

**Acceptance Criteria**:
✅ Alerts delivered within 2 seconds
✅ Rate limiting (max 1 alert per minute per channel)
✅ Retry on network errors

**Estimated Effort**: 4 hours (both platforms)

---

## Summary: Build Effort Estimate

| Gap | Priority | Effort | Complexity |
|-----|----------|--------|------------|
| Pre-Trade Rejection | P0 | **N/A (impossible)** | N/A |
| Flatten All | P2 | 2 hours | Low |
| Realized PnL Tracking | P0 | 1 day | Medium |
| Unrealized PnL Calc | P0 | 4 hours | Low |
| Daily Reset Logic | P0 | 6 hours | Medium |
| TIME_TICK Events | P1 | 2 hours | Low |
| Stop Loss Detection | P1 | 1 day | Medium |
| State Reconciliation | P1 | 6 hours | Medium |
| Notifications | P2 | 4 hours | Low |

**Total Effort (P0 + P1)**: ~4-5 days
**Total Effort (All)**: ~5-6 days

---

## Build Order (Recommended)

1. **Day 1**: SDK Adapter + Event Normalizer (P0)
2. **Day 2**: Unrealized PnL + Price Cache (P0)
3. **Day 3**: Realized PnL Tracking + Daily Reset (P0)
4. **Day 4**: TIME_TICK + Stop Loss Detection (P1)
5. **Day 5**: State Reconciliation + Flatten All (P1-P2)
6. **Day 6**: Notifications + Testing (P2)

---

**Document Status**: ✅ Complete
**Last Updated**: 2025-10-15
**Author**: RM-SDK-Analyst
**Approved By**: [Pending Product Owner Review]
