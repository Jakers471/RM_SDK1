# Capabilities Matrix: Requirements vs SDK

## Overview

This document maps the Risk Manager Daemon's requirements to the project-x-py SDK's capabilities. Each capability is evaluated for:
- **SDK Provides?**: Yes/No/Partial
- **SDK Method/Event**: Exact identifier for implementation
- **Notes**: Implementation details, limitations, considerations
- **We Must Build?**: What custom logic is required

---

## Authentication

| Capability | SDK Provides? | SDK Method/Event | Notes | We Must Build? |
|------------|---------------|------------------|-------|----------------|
| **API key authentication** | ✅ Yes | `ProjectX.from_env()` → `authenticate()` | Reads `PROJECT_X_API_KEY` + `PROJECT_X_USERNAME` from env vars or config file. Returns JWT token stored internally. | ❌ No - SDK handles completely |
| **JWT/OAuth authentication** | ✅ Yes | Automatic (JWT internally) | SDK manages JWT token lifecycle including refresh. Transparent to application. | ❌ No - SDK handles completely |
| **Auto-reconnect on disconnect** | ✅ Yes | Built-in (WebSocket layer) | Exponential backoff with circuit breaker. Events: `EventType.DISCONNECTED`, `EventType.RECONNECTING`, `EventType.CONNECTED` | ❌ No - but must handle reconnect events for state reconciliation |
| **Graceful disconnect** | ✅ Yes | `await suite.disconnect()` | Cleanly closes WebSocket connections and HTTP sessions. | ❌ No - SDK provides method |
| **Multi-account support** | ✅ Yes | `account_id` parameter in queries | Each method accepts optional `account_id`. Can manage multiple accounts with single client. | ❌ No - but must track account mappings in config |

---

## Event Subscriptions

| Capability | SDK Provides? | SDK Method/Event | Notes | We Must Build? |
|------------|---------------|------------------|-------|----------------|
| **Fill events (push)** | ✅ Yes | `EventType.ORDER_FILLED` | Triggered when order fully executed. Data: `{orderId, contractId, side, size, filledPrice, fillTime}` | ❌ No - event provided |
| **Partial fill events** | ✅ Yes | `EventType.ORDER_PARTIAL_FILL` | Triggered on partial fills. Data: `{orderId, fillVolume, remaining}` | ❌ No - event provided |
| **Position update events (push)** | ✅ Yes | `EventType.POSITION_UPDATED` | Triggered on position changes (size, price). Data: `{positionId, contractId, size, averagePrice, updateTimestamp}` | ❌ No - event provided |
| **Position opened events** | ✅ Yes | `EventType.POSITION_OPENED` | Triggered when new position created. Data: `{positionId, contractId, side, size, averagePrice}` | ❌ No - event provided |
| **Position closed events** | ✅ Yes | `EventType.POSITION_CLOSED` | Triggered when position size → 0. Data: `{positionId, contractId, closeTime}` | ❌ No - event provided |
| **Order update events (push)** | ✅ Yes | `EventType.ORDER_PLACED`, `ORDER_MODIFIED`, `ORDER_CANCELLED`, `ORDER_REJECTED` | Full order lifecycle events. Each includes `{orderId, status, updateTimestamp, ...}` | ❌ No - events provided |
| **Connection status events** | ✅ Yes | `EventType.CONNECTED`, `DISCONNECTED`, `RECONNECTING` | WebSocket connection state changes. Data: `{status, reason}` | ❌ No - events provided |
| **Event handler registration** | ✅ Yes | `await suite.on(EventType.X, async_handler)` | Register async callbacks. Handlers receive `Event` object with `.data` dict. | ❌ No - SDK provides EventBus |

---

## Position Queries

| Capability | SDK Provides? | SDK Method/Event | Notes | We Must Build? |
|------------|---------------|------------------|-------|----------------|
| **Get current positions** | ✅ Yes | `client.search_open_positions(account_id=None) → list[Position]` | Returns all open positions for account. Endpoint: `POST /api/Position/searchOpen` | ❌ No - SDK method provided |
| **Position details (symbol, qty, price)** | ✅ Yes | `Position` dataclass fields | Fields: `contractId, type (LONG/SHORT), size, averagePrice, creationTimestamp` | ❌ No - all fields provided |
| **Unrealized PnL (per position)** | ⚠️ Partial | `PositionManager.calculate_position_pnl(position, current_price, point_value)` | SDK helper method for calculation, but NOT in Position object itself. | ✅ Yes - must call calculation method or compute manually |
| **Realized PnL (daily)** | ❌ No | Not provided | SDK does not track realized PnL or provide daily aggregates. Trade history available via `search_trades()` but no daily reset concept. | ✅ Yes - must track realized PnL ourselves with 5pm CT reset |
| **Position side/direction** | ✅ Yes | `Position.type` (1=LONG, 2=SHORT) + helpers (`is_long`, `is_short`, `direction`) | Position direction always provided. | ❌ No - SDK provides |
| **Position entry timestamp** | ✅ Yes | `Position.creationTimestamp` (ISO 8601 string) | Timestamp when position opened. | ❌ No - SDK provides |

---

## Order Execution

| Capability | SDK Provides? | SDK Method/Event | Notes | We Must Build? |
|------------|---------------|------------------|-------|----------------|
| **Close position (market order)** | ✅ Yes | `suite.orders.close_position(contract_id, method="market")` | Closes full position with market order. Internally: queries position → places opposite-side market order. | ❌ No - SDK method provided |
| **Close position (partial qty)** | ✅ Yes | `suite.orders.place_market_order(contract_id, opposite_side, partial_qty)` | Place market order for specific quantity. Must determine opposite side manually. | ⚠️ Partial - must calculate opposite side |
| **Flatten account (all positions)** | ❌ No | Not provided | No single method to close all positions. | ✅ Yes - must loop through positions and call `close_position()` for each |
| **Order confirmation callback** | ✅ Yes | `EventType.ORDER_FILLED` event | Async event when order filled. Includes fill price, quantity, timestamp. | ❌ No - event provided |
| **Order rejection handling** | ✅ Yes | `EventType.ORDER_REJECTED` event | Event includes `{errorMessage, errorCode}`. | ❌ No - event provided |
| **Market order placement** | ✅ Yes | `suite.orders.place_market_order(contract_id, side, size)` | Side: 0=BUY, 1=SELL. Returns `OrderPlaceResponse` with `orderId`. | ❌ No - SDK method provided |
| **Limit order placement** | ✅ Yes | `suite.orders.place_limit_order(contract_id, side, size, limit_price)` | For precise pricing. Returns `OrderPlaceResponse`. | ❌ No - SDK method provided |
| **Stop order placement** | ✅ Yes | `suite.orders.place_stop_order(contract_id, side, size, stop_price)` | For stop-loss. Returns `OrderPlaceResponse`. | ❌ No - SDK method provided |
| **Bracket order (entry+SL+TP)** | ✅ Yes | `suite.orders.place_bracket_order(contract_id, side, size, entry_price, stop_loss_price, take_profit_price)` | Returns `BracketOrderResponse` with IDs for all 3 orders. | ❌ No - SDK method provided |

---

## Stop Loss Detection

| Capability | SDK Provides? | SDK Method/Event | Notes | We Must Build? |
|------------|---------------|------------------|-------|----------------|
| **Detect SL attached to position** | ❌ No | Not provided | `Position` object has no stop loss metadata. | ✅ Yes - must query orders separately via `get_open_orders()` and filter by `type=STOP` and `contractId` |
| **Get SL price** | ⚠️ Partial | Query orders: `order.stopPrice` if `order.type == OrderType.STOP` | Stop price available in Order object, but must query all orders and match to position. | ✅ Yes - must query and match orders to positions |
| **Bracket/OCO order support** | ✅ Yes | `place_bracket_order()` returns `BracketOrderResponse` | SDK supports bracket orders (entry + SL + TP). Returns IDs for tracking. | ⚠️ Partial - SDK places brackets but doesn't link them to positions; must track manually |
| **Detect stop loss trigger** | ✅ Yes | `EventType.STOP_LOSS_TRIGGERED` | Event when stop loss order fills. | ❌ No - event provided |

---

## Price Data

| Capability | SDK Provides? | SDK Method/Event | Notes | We Must Build? |
|------------|---------------|------------------|-------|----------------|
| **Current mark/last price** | ✅ Yes | `suite.data.get_current_price()` or `EventType.QUOTE_UPDATE` | Quote updates via WebSocket include `{bid, ask}`. Mid-price = (bid+ask)/2 for mark price. | ❌ No - SDK provides |
| **Real-time quote stream** | ✅ Yes | `EventType.QUOTE_UPDATE` event | Push-based. Data: `{contractId, bid, ask, lastPrice, volume, timestamp}` | ❌ No - event provided |
| **Tick value per instrument** | ✅ Yes | `instrument = await client.get_instrument(contract_id)` → `instrument.tickValue` | Tick value (dollars per tick) available in Instrument metadata. Example: MNQ tickValue=0.5 | ❌ No - SDK provides |
| **Tick size per instrument** | ✅ Yes | `instrument.tickSize` | Minimum price increment. Example: MNQ tickSize=0.25 | ❌ No - SDK provides |
| **Point value calculation** | ⚠️ Partial | `point_value = tickValue / tickSize` | Must calculate from tick size and value. Example: MNQ → 0.5/0.25 = $2/point | ✅ Yes - must calculate or hardcode common values |
| **Historical price data** | ✅ Yes | `client.get_bars(symbol, days=N)` or `start_time/end_time` | REST API for historical bars. Returns Polars DataFrame with OHLCV data. | ❌ No - SDK provides (but not needed for enforcement) |

---

## Pre-Trade Rejection

| Capability | SDK Provides? | SDK Method/Event | Notes | We Must Build? |
|------------|---------------|------------------|-------|----------------|
| **Block order before execution** | ❌ No | Not possible | SDK is client-side library. Cannot intercept orders placed via other clients (web UI, mobile app). Broker API doesn't support pre-trade hooks. | ✅ Yes - IMPOSSIBLE. Must enforce post-fill by immediately closing positions. |
| **Pre-trade validation hooks** | ❌ No | Not provided | No extension points for order validation before submission. | ✅ Yes - IMPOSSIBLE. Enforcement must be reactive, not proactive. |

---

## Rate Limits

| Capability | SDK Provides? | SDK Method/Event | Notes | We Must Build? |
|------------|---------------|------------------|-------|----------------|
| **API calls per second limit** | ✅ Yes | `ProjectXConfig(requests_per_minute=60, burst_limit=10)` | Default: 60 req/min (1/sec avg), burst of 10. Built-in `RateLimiter` enforces. | ❌ No - SDK enforces automatically |
| **SDK enforces rate limits** | ✅ Yes | Automatic throttling | SDK delays requests if limit approached. No manual handling needed. | ❌ No - SDK handles |
| **Rate limit error handling** | ✅ Yes | Automatic retry with backoff | HTTP 429 responses trigger exponential backoff retry. | ❌ No - SDK handles |
| **Circuit breaker for failures** | ✅ Yes | Built-in for WebSocket connections | Prevents excessive reconnect attempts. Configurable thresholds. | ❌ No - SDK provides |

---

## Time and Session Management

| Capability | SDK Provides? | SDK Method/Event | Notes | We Must Build? |
|------------|---------------|------------------|-------|----------------|
| **Trading session detection** | ⚠️ Partial | `SessionConfig(session_type=SessionType.RTH/ETH)` (experimental) | SDK v3.4.0+ has session filtering but marked experimental. RTH = 9:30am-4pm ET, ETH = 24hr. | ✅ Yes - must implement reliable 5pm CT daily reset logic ourselves |
| **5pm CT daily reset** | ❌ No | Not provided | No built-in concept of trading day reset. | ✅ Yes - must implement timer to reset realized PnL at 5pm CT |
| **Timezone handling** | ✅ Yes | `ProjectXConfig(timezone="America/Chicago")` | SDK uses pytz for timezone conversions. All timestamps in UTC, can convert to CT. | ⚠️ Partial - SDK has timezone support but must implement reset logic |
| **System time/clock** | ✅ Yes | `datetime.now(pytz.UTC)` (Python stdlib) | Standard Python datetime. | ✅ Yes - must implement TIME_TICK (1-second interval) ourselves |

---

## Error Handling and Reliability

| Capability | SDK Provides? | SDK Method/Event | Notes | We Must Build? |
|------------|---------------|------------------|-------|----------------|
| **Typed exceptions** | ✅ Yes | `ProjectXAuthenticationError`, `ProjectXOrderError`, `ProjectXConnectionError`, `ProjectXRateLimitError`, etc. | Comprehensive exception hierarchy for different error types. | ❌ No - SDK provides |
| **Automatic retry on network errors** | ✅ Yes | Configured via `ProjectXConfig(retry_attempts=3, retry_delay_seconds=2.0)` | Built-in retry logic with exponential backoff. | ❌ No - SDK handles |
| **Error event emission** | ✅ Yes | `EventType.ERROR`, `EventType.WARNING` | Errors emitted as events. Data: `{original_event, handler, error}` | ❌ No - SDK provides |
| **State reconciliation after reconnect** | ❌ No | Not provided | SDK reconnects WebSocket but doesn't replay missed events. | ✅ Yes - must query REST API (positions, orders) after reconnect to reconcile state |

---

## Notifications

| Capability | SDK Provides? | SDK Method/Event | Notes | We Must Build? |
|------------|---------------|------------------|-------|----------------|
| **Discord webhook integration** | ❌ No | Not provided | SDK is trading-focused, no notification integrations. | ✅ Yes - must implement webhook POST requests ourselves |
| **Telegram bot integration** | ❌ No | Not provided | Not part of SDK scope. | ✅ Yes - must implement Telegram API integration ourselves |
| **Email notifications** | ❌ No | Not provided | Not part of SDK scope. | ✅ Yes - must implement SMTP or email service integration |
| **Custom alert system** | ❌ No | Not provided | Can listen to SDK events and trigger custom alerts. | ✅ Yes - must build notification service that listens to risk events |

---

## Logging and Monitoring

| Capability | SDK Provides? | SDK Method/Event | Notes | We Must Build? |
|------------|---------------|------------------|-------|----------------|
| **Structured logging** | ✅ Yes | `setup_logging(level, format_json=True)` | SDK provides logging utilities. Can output JSON for production. | ❌ No - SDK provides |
| **Event history** | ⚠️ Partial | `EventBus.enable_history(max_size=1000)` | Can enable event history for debugging. Limited to N recent events. | ✅ Yes - must implement persistent audit trail for enforcement actions |
| **Performance metrics** | ⚠️ Partial | `suite.get_stats()` (v3.3.0+) | SDK provides health score, API call stats, memory usage. | ⚠️ Partial - SDK has basic stats, but must track custom metrics (enforcement latency, rule violations) |
| **Health monitoring** | ✅ Yes | `suite.get_health_score() → 0-100` | Async health scoring with component-specific metrics. | ❌ No - SDK provides |

---

## Summary Matrix

### ✅ Fully Provided by SDK (43 capabilities)
- Authentication (API key, JWT, auto-reconnect)
- Event subscriptions (fills, positions, orders, connection events)
- Position queries (current positions with full details)
- Order execution (market, limit, stop, bracket orders)
- Price data (real-time quotes, tick values)
- Rate limiting and automatic retry
- Error handling with typed exceptions
- Logging and basic monitoring

### ⚠️ Partially Provided (9 capabilities)
- Unrealized PnL (helper method exists but must call explicitly)
- Stop loss detection (must query orders separately)
- Partial position close (must calculate opposite side)
- Point value (must calculate from tick size/value)
- Session management (experimental SDK feature)
- State reconciliation (SDK reconnects but no event replay)
- Performance metrics (basic stats provided, custom metrics needed)

### ❌ Not Provided - Must Build (15 capabilities)
- **Pre-trade rejection** (impossible - client-side limitation)
- **Flatten all positions** (must loop through positions)
- **Realized PnL tracking** (daily reset at 5pm CT)
- **5pm CT daily reset logic**
- **TIME_TICK and SESSION_TICK events** (must generate internally)
- **Stop loss detection** (must query and match orders)
- **Bracket order tracking** (must link to positions manually)
- **State reconciliation logic** (must query REST API after reconnect)
- **Discord/Telegram notifications** (must implement webhooks)
- **Custom alert system** (must build on top of SDK events)
- **Persistent audit trail** (must log enforcement actions to database)
- **Custom enforcement metrics** (latency tracking, violation counts)

---

## Critical Findings

### 1. Pre-Trade Rejection: IMPOSSIBLE
- **Impact**: HIGH
- **Mitigation**: Enforce post-fill by immediately closing violating positions
- **Expected Latency**: ~50-500ms (event propagation + market order execution)

### 2. Realized PnL: Must Track Separately
- **Impact**: MEDIUM
- **Mitigation**: Build state manager to track realized PnL per account, reset daily at 5pm CT
- **SDK Dependency**: Query trades via `search_trades()` for reconciliation

### 3. No Native "Flatten All"
- **Impact**: LOW
- **Mitigation**: Simple loop: `for pos in positions: close_position(pos.contractId)`
- **Race Condition Risk**: New positions might open during flatten; must handle

### 4. Stop Loss Detection: Non-Trivial
- **Impact**: MEDIUM
- **Mitigation**: Query all orders, filter by `type=STOP`, match `contractId` to positions
- **Limitation**: Cannot detect manually-placed stops (outside SDK); periodic polling needed

### 5. State Reconciliation After Disconnect
- **Impact**: MEDIUM
- **Mitigation**: On `RECONNECTING` event → query REST API for current positions, orders, compare with cached state
- **SDK Gap**: No automatic event replay

---

## Integration Complexity Assessment

**Overall**: 🟡 Medium Complexity

**Reasons**:
- ✅ SDK provides ~75% of required capabilities out-of-box
- ✅ Event-driven architecture aligns perfectly with our design
- ⚠️ Must build custom logic for PnL tracking, daily resets, and reconciliation
- ⚠️ Post-fill enforcement adds latency (acceptable for use case)
- ❌ No pre-trade rejection (architectural limitation, not SDK flaw)

**Developer Effort Estimate**: 2-3 weeks for full integration (adapters + state management + tests)

---

## Next Steps

1. **Design SDK Adapter Contracts** ([adapter_contracts.md](adapter_contracts.md))
   - Define `SDKAdapter` class with methods mapping to SDK calls
   - Define `EventNormalizer` class for SDK events → internal events

2. **Map Event Types** ([event_mapping.md](event_mapping.md))
   - SDK EventType → Risk Manager EventType
   - Data field mapping for each event

3. **Create Integration Flows** ([integration_flows.md](integration_flows.md))
   - Sequence diagrams for key scenarios
   - Error handling and reconnection flows

4. **Document Build Plan** ([gaps_and_build_plan.md](gaps_and_build_plan.md))
   - Implementation approach for custom components
   - Testing strategy for adapters

---

**Document Status**: ✅ Complete
**Last Updated**: 2025-10-15
**Author**: RM-SDK-Analyst
**Approved By**: [Pending Product Owner Review]
