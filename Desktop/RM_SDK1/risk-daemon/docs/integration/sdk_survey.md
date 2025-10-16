# SDK Survey: project-x-py v3.5.9

## Overview

**SDK Name**: project-x-py
**Version**: 3.5.9
**Repository**: https://github.com/TexasCoding/project-x-py
**Broker Platform**: TopstepX (ProjectX Gateway API)
**Language**: Python 3.12+
**Architecture**: Async-first (async/await throughout)
**Event Model**: Event-driven with EventBus + WebSocket SignalR hubs

## Executive Summary

The project-x-py SDK is a comprehensive, production-ready async Python library for TopstepX futures trading. It provides:

- **Full async/await support** throughout (no synchronous blocking calls)
- **Event-driven architecture** with centralized EventBus for all components
- **Dual-hub SignalR WebSocket connections** (UserHub + MarketHub) for real-time data
- **Complete order lifecycle management** (market, limit, stop, bracket orders)
- **Real-time position tracking** with WebSocket push updates
- **PnL calculations** available via PositionManager helper methods
- **Authentication** via API key + username (JWT token internally)
- **Auto-reconnection** with exponential backoff and circuit breaker patterns
- **Rate limiting** built-in (configurable, default 60 req/min)
- **High-level TradingSuite** for simplified integration
- **Comprehensive error handling** with typed exceptions

**Key Finding**: The SDK provides **all core capabilities** required by the risk manager daemon, but **does NOT** provide pre-trade order rejection. Enforcement must happen **post-fill** by immediately closing positions.

---

## Architecture Overview

### Core Components

```
TradingSuite (high-level entry point)
    ├── ProjectX (HTTP client)
    │   ├── Authentication (JWT tokens, auto-refresh)
    │   ├── Market Data (REST API: bars, instruments)
    │   └── Trading (REST API: positions, orders, trades)
    ├── ProjectXRealtimeClient (WebSocket client)
    │   ├── UserHub (SignalR: positions, orders, account events)
    │   └── MarketHub (SignalR: quotes, trades, depth)
    ├── OrderManager (order lifecycle management)
    ├── PositionManager (position tracking + analytics)
    ├── RealtimeDataManager (multi-timeframe data + event forwarding)
    ├── EventBus (centralized event routing)
    └── OrderBook (optional: L2 depth analysis)
```

### Communication Patterns

1. **REST API** (synchronous queries)
   - Authentication (`/api/Authentication/signIn`)
   - Position queries (`/api/Position/searchOpen`)
   - Order placement (`/api/Order/placeOrder`)
   - Historical data (`/api/Bar/getBars`)

2. **WebSocket SignalR** (real-time push events)
   - UserHub: `OnPositionUpdate`, `OnOrderUpdate`, `OnTradeUpdate`
   - MarketHub: `OnQuote`, `OnTrade`, `OnDepthUpdate`
   - Auto-reconnect with exponential backoff (built-in)

3. **EventBus** (internal SDK event routing)
   - All components emit events to centralized EventBus
   - EventType enum defines all event types
   - Handlers registered via `await suite.on(EventType.X, handler)`

---

## Authentication and Connection

### Authentication Flow

**Method**: API Key + Username → JWT Token

```python
# Environment variables or config file
PROJECT_X_API_KEY="your_api_key"
PROJECT_X_USERNAME="your_username"

# SDK handles authentication automatically via TradingSuite
suite = await TradingSuite.create("MNQ")
# OR manual via ProjectX client:
async with ProjectX.from_env() as client:
    await client.authenticate()  # JWT token stored internally
    # Token auto-refreshed on expiry
```

**Credentials Required**:
- `api_key` (string): TopstepX API key
- `username` (string): TopstepX account username

**Authentication Endpoint**: `POST /api/Authentication/signIn`
**Response**: JWT token (stored internally, auto-refreshed)

### Connection Management

**WebSocket Hubs**:
1. **UserHub** (`https://rtc.topstepx.com/hubs/user`)
   - Position updates
   - Order updates
   - Trade executions
   - Account events

2. **MarketHub** (`https://rtc.topstepx.com/hubs/market`)
   - Real-time quotes (bid/ask)
   - Trade ticks
   - Market depth (L2 orderbook)

**Auto-Reconnect**: Yes (built-in)
- Exponential backoff with jitter
- Circuit breaker pattern for fault tolerance
- Events: `EventType.CONNECTED`, `EventType.DISCONNECTED`, `EventType.RECONNECTING`

**Connection Status Detection**:
```python
# Via EventBus
async def on_connection_change(event):
    status = event.data.get('status')  # "connected", "disconnected", "reconnecting"

await suite.on(EventType.CONNECTED, on_connected)
await suite.on(EventType.DISCONNECTED, on_disconnected)
await suite.on(EventType.RECONNECTING, on_reconnecting)
```

**Missed Events After Reconnect**: No automatic replay; must query REST API to reconcile state.

---

## Event Subscriptions (Real-Time Updates)

### Event Model: Push-Based via WebSocket

The SDK provides **push-based** real-time events via SignalR WebSocket hubs. All events flow through the centralized `EventBus`.

### Available EventTypes (SDK-defined)

```python
class EventType(Enum):
    # Market Data Events
    NEW_BAR = "new_bar"
    DATA_UPDATE = "data_update"
    QUOTE_UPDATE = "quote_update"
    TRADE_TICK = "trade_tick"
    ORDERBOOK_UPDATE = "orderbook_update"
    MARKET_DEPTH_UPDATE = "market_depth_update"

    # Order Events
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_PARTIAL_FILL = "order_partial_fill"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    ORDER_EXPIRED = "order_expired"
    ORDER_MODIFIED = "order_modified"

    # Position Events
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_UPDATED = "position_updated"
    POSITION_PNL_UPDATE = "position_pnl_update"

    # Risk Events
    RISK_LIMIT_WARNING = "risk_limit_warning"
    RISK_LIMIT_EXCEEDED = "risk_limit_exceeded"
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    TAKE_PROFIT_TRIGGERED = "take_profit_triggered"

    # System Events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    AUTHENTICATED = "authenticated"
    ERROR = "error"
    WARNING = "warning"
```

### Event Registration

```python
# Register event handler
async def on_position_update(event: Event):
    data = event.data  # dict with event-specific fields
    position_id = data.get('positionId')
    contract_id = data.get('contractId')
    size = data.get('size')
    avg_price = data.get('averagePrice')

await suite.on(EventType.POSITION_UPDATED, on_position_update)
```

### Key Events for Risk Manager

| Event Type | Trigger | Data Fields |
|------------|---------|-------------|
| **ORDER_FILLED** | Order completely filled | `orderId`, `contractId`, `side`, `size`, `filledPrice`, `fillTime` |
| **ORDER_PARTIAL_FILL** | Order partially filled | `orderId`, `fillVolume`, `remaining` |
| **POSITION_UPDATED** | Position size/price changes | `positionId`, `contractId`, `size`, `averagePrice`, `updateTimestamp` |
| **POSITION_CLOSED** | Position size → 0 | `positionId`, `contractId`, `closeTime` |
| **POSITION_OPENED** | New position created | `positionId`, `contractId`, `side`, `size`, `averagePrice` |
| **ORDER_REJECTED** | Order rejected by broker | `orderId`, `errorMessage`, `errorCode` |

---

## Position and Account Queries

### Get Current Positions

**Method**: `client.search_open_positions(account_id=None) → list[Position]`

**Endpoint**: `POST /api/Position/searchOpen`

**Returns**: List of `Position` objects

```python
# Position dataclass fields:
@dataclass
class Position:
    id: int                    # Position ID
    accountId: int             # Account ID
    contractId: str            # Contract (e.g., "CON.F.US.MNQ.U25")
    creationTimestamp: str     # ISO 8601 timestamp
    type: int                  # 1=LONG, 2=SHORT
    size: int                  # Number of contracts (always positive)
    averagePrice: float        # Average entry price

    # Helper properties:
    is_long: bool
    is_short: bool
    direction: str             # "LONG", "SHORT", or "UNDEFINED"
    symbol: str                # Extracted symbol (e.g., "MNQ")
    signed_size: int           # Negative for short positions
```

**Example**:
```python
positions = await client.search_open_positions()
for pos in positions:
    print(f"{pos.symbol}: {pos.direction} {pos.size} @ ${pos.averagePrice:.2f}")
```

### PnL Queries

**SDK Does NOT provide realized/unrealized PnL directly in Position object.**

**PnL Calculation Available Via**:
- `PositionManager.calculate_position_pnl(position, current_price, point_value)`
- `PositionManager.calculate_portfolio_pnl(market_prices)` (aggregates all positions)

**We Must Build**:
- Realized PnL tracking (daily reset at 5pm CT)
- Unrealized PnL calculation using current prices

**Tick Values** (per-instrument constants):
```python
# From Instrument object (queryable via SDK)
instrument = await client.get_instrument("CON.F.US.MNQ.U25")
tick_size = instrument.tickSize    # e.g., 0.25
tick_value = instrument.tickValue  # e.g., 0.50 (dollars per tick)

# Calculate unrealized PnL:
# Long:  (current_price - entry_price) * size * tick_value
# Short: (entry_price - current_price) * size * tick_value
```

---

## Order Execution (Close Positions)

### Close Specific Position

**Method**: `order_manager.close_position(contract_id, method="market")`

**Internally**:
1. Queries current position for `contract_id`
2. Determines opposite side (long → sell, short → buy)
3. Places market order for full position size
4. Returns `OrderPlaceResponse`

**Example**:
```python
response = await suite.orders.close_position("CON.F.US.MNQ.U25", method="market")
if response.success:
    print(f"Close order placed: {response.orderId}")
```

### Flatten Entire Account

**No Native SDK Method** for "flatten all".

**We Must Build**: Loop through all positions and close each individually.

```python
positions = await client.search_open_positions()
for pos in positions:
    await suite.orders.close_position(pos.contractId, method="market")
```

### Order Types Supported

| Order Type | SDK Method | Use Case |
|------------|------------|----------|
| **Market** | `place_market_order(contract_id, side, size)` | Instant execution (enforcement) |
| **Limit** | `place_limit_order(contract_id, side, size, limit_price)` | Price control |
| **Stop** | `place_stop_order(contract_id, side, size, stop_price)` | Stop-loss |
| **Bracket** | `place_bracket_order(contract_id, side, size, entry, stop, target)` | Entry + SL + TP |

### Order Confirmation

**How to Know Order Filled?**

1. **Event-driven** (recommended):
   ```python
   async def on_order_filled(event):
       order_id = event.data['orderId']
       filled_price = event.data['filledPrice']
       print(f"Order {order_id} filled @ ${filled_price}")

   await suite.on(EventType.ORDER_FILLED, on_order_filled)
   ```

2. **Polling** (fallback):
   ```python
   order = await client.get_order(order_id)
   if order.status == OrderStatus.FILLED:
       print(f"Order filled @ ${order.filledPrice}")
   ```

**Latency**: ~50-200ms for market orders (based on network + broker processing)

---

## Stop Loss Detection

### Detecting Attached Stop Loss

**SDK Position Object Does NOT Include Stop Loss Information.**

**Stop Loss Detection Approaches**:

1. **Query Related Orders**:
   ```python
   # Get all open orders for account
   orders = await client.get_open_orders()
   # Filter for stop orders on same contract
   stop_orders = [o for o in orders if o.type == OrderType.STOP and o.contractId == position.contractId]
   ```

2. **Track Bracket Orders**:
   - When `place_bracket_order()` is used, SDK returns `BracketOrderResponse` with `stop_order_id`
   - Store mapping: position → stop_order_id
   - Check if stop order still exists

**Challenge**: If trader places stop loss manually (outside SDK), we cannot detect it without querying all orders.

**Recommendation**: Track orders placed via SDK; for manual stops, poll orders periodically.

---

## Pre-Trade Rejection

### Can We Block Orders Before Execution?

**NO.** The SDK does **not** provide pre-trade validation or order rejection capabilities.

**Why?**
- The SDK is a **client library** communicating with TopstepX broker API
- Order validation happens **broker-side** after submission
- We cannot intercept trader's orders placed via TopstepX web UI or other clients

**Implication for Risk Manager**:
- Enforcement must happen **post-fill**
- When `ORDER_FILLED` event received → evaluate rules → close position if violated
- Latency: ~50-500ms (depends on event propagation + close order execution)

### Fastest Post-Fill Close Path

```python
async def on_order_filled(event):
    # Extract fill details
    contract_id = event.data['contractId']
    size = event.data['size']

    # Evaluate risk rules
    if rule_violated:
        # Immediate market close
        await suite.orders.close_position(contract_id, method="market")
        # Latency: ~50-200ms for market order fill
```

---

## Price Data and Tick Values

### Current Price Sources

**Real-Time Price** (via WebSocket):
```python
# Subscribe to quote updates
async def on_quote(event):
    bid = event.data['bid']
    ask = event.data['ask']
    mid_price = (bid + ask) / 2

await suite.on(EventType.QUOTE_UPDATE, on_quote)
```

**Last Price** (via RealtimeDataManager):
```python
current_price = await suite.data.get_current_price()
```

**Which Price for Unrealized PnL?**
- **Mark Price** (mid of bid/ask) recommended for most accurate PnL
- **Last Price** acceptable but may lag in low-volume periods
- SDK provides both via WebSocket events

### Tick Values Per Instrument

**Query Instrument Metadata**:
```python
instrument = await client.get_instrument("CON.F.US.MNQ.U25")
tick_size = instrument.tickSize    # Minimum price increment (e.g., 0.25)
tick_value = instrument.tickValue  # Dollar value per tick (e.g., 0.50)

# Calculate point value:
point_value = tick_value / tick_size
# Example: MNQ → 0.50 / 0.25 = $2 per point
```

**Common Futures Tick Values** (reference):
```python
TICK_VALUES = {
    "MNQ": 0.5,   # $0.50 per tick (0.25 tick size) → $2 per point
    "NQ": 5.0,    # $5.00 per tick (0.25 tick size) → $20 per point
    "MES": 1.25,  # $1.25 per tick (0.25 tick size) → $5 per point
    "ES": 12.5,   # $12.50 per tick (0.25 tick size) → $50 per point
}
```

### Unrealized PnL Calculation

**SDK Does NOT Auto-Calculate Unrealized PnL.**

**We Must Compute**:
```python
def calculate_unrealized_pnl(position: Position, current_price: float, tick_value: float) -> float:
    if position.is_long:
        pnl = (current_price - position.averagePrice) * position.size * tick_value
    elif position.is_short:
        pnl = (position.averagePrice - current_price) * position.size * tick_value
    else:
        pnl = 0.0
    return round(pnl, 2)
```

**Alternatively**, use SDK helper:
```python
pnl_result = await suite.positions.calculate_position_pnl(
    position=pos,
    current_price=current_price,
    point_value=tick_value
)
unrealized_pnl = pnl_result['unrealized_pnl']
```

---

## Rate Limits and Backoff

### API Rate Limits

**Default Configuration**:
```python
ProjectXConfig(
    requests_per_minute=60,  # 60 requests per minute (1 req/sec average)
    burst_limit=10           # Allow burst of 10 requests
)
```

**SDK Enforcement**: Built-in `RateLimiter` class automatically throttles requests.

**Behavior**:
- If limit exceeded → SDK waits/delays request automatically
- No manual backoff needed in application code
- Circuit breaker pattern prevents cascading failures

### Retry Strategy

**Built-in Retry Logic**:
```python
ProjectXConfig(
    retry_attempts=3,           # Retry failed requests up to 3 times
    retry_delay_seconds=2.0     # Wait 2 seconds between retries
)
```

**Retry Triggers**:
- Network errors (timeout, connection reset)
- HTTP 5xx errors (server errors)
- Rate limit errors (HTTP 429)

**Exponential Backoff**: Yes (for WebSocket reconnections)

**Circuit Breaker**: Built-in for WebSocket connections (prevents excessive reconnect attempts)

---

## SDK Limitations and Quirks

### Known Limitations

1. **No Pre-Trade Rejection**
   - Cannot block orders before they reach broker
   - Must enforce rules post-fill

2. **No Native "Flatten All" Method**
   - Must loop through positions and close individually
   - Race condition risk if new positions opened during flatten

3. **No Realized PnL in Position Object**
   - Must track realized PnL separately
   - SDK only provides position entry price and current size

4. **No Stop Loss Metadata in Position**
   - Must query orders separately to detect attached stops
   - Cannot easily detect manually-placed stops

5. **No Daily Reset Logic**
   - SDK has no concept of "trading day reset" (5pm CT)
   - Must implement custom timer/session logic

6. **Event Replay After Reconnect**
   - Missed events during disconnect are NOT replayed
   - Must query REST API to reconcile state after reconnect

### SDK Quirks

1. **Contract ID Format**: `"CON.F.US.{SYMBOL}.{MONTH}{YEAR}"`
   - Example: `"CON.F.US.MNQ.U25"` (MNQ September 2025)
   - Must parse to extract symbol

2. **Position Type Enum**: `1=LONG`, `2=SHORT`, `0=UNDEFINED`
   - Not standard enum values

3. **Order Side Enum**: `0=BUY`, `1=SELL`
   - Counter-intuitive (0 typically means unknown)

4. **Async-Only**: No synchronous methods
   - All calls require `await`
   - Must run in async event loop

5. **EventBus Naming**: EventType enum uses snake_case strings
   - `"order_filled"` not `"ORDER_FILLED"`

---

## Dependencies and Installation

### Installation

```bash
# Via uv (recommended)
uv add project-x-py

# Via pip
pip install project-x-py
```

**Python Version**: 3.12+ required

### Key Dependencies

- `aiohttp` (async HTTP client)
- `signalrcore` (SignalR WebSocket client)
- `polars` (high-performance dataframes for indicators)
- `pytz` (timezone handling)
- `pydantic` (data validation)

### Configuration

**Environment Variables**:
```bash
export PROJECT_X_API_KEY="your_api_key"
export PROJECT_X_USERNAME="your_username"
```

**Config File** (`~/.config/projectx/config.json`):
```json
{
    "api_key": "your_api_key",
    "username": "your_username",
    "api_url": "https://api.topstepx.com/api",
    "timezone": "America/Chicago"
}
```

---

## Summary: SDK Fit for Risk Manager

### Capabilities Provided by SDK

✅ **Authentication**: API key + username → JWT tokens
✅ **Connection Management**: Auto-reconnect with circuit breaker
✅ **Real-Time Events**: Push-based via WebSocket (positions, orders, prices)
✅ **Position Queries**: `search_open_positions()` returns all open positions
✅ **Order Execution**: Market orders for closing positions
✅ **Event-Driven Architecture**: Centralized EventBus with async handlers
✅ **Rate Limiting**: Built-in throttling and retry logic
✅ **Error Handling**: Typed exceptions with comprehensive error messages

### Capabilities We Must Build

❌ **Pre-Trade Rejection**: No way to block orders before execution
❌ **Flatten All**: Must loop through positions manually
❌ **Realized PnL Tracking**: Must track separately (daily reset at 5pm CT)
❌ **Unrealized PnL Calculation**: Must compute from current price + tick value
❌ **Daily Reset Logic**: Must implement custom 5pm CT timer
❌ **Stop Loss Detection**: Must query orders separately
❌ **Timer Events**: Must generate TIME_TICK and SESSION_TICK internally
❌ **Idempotency**: Must track enforcement actions to prevent duplicates
❌ **Notification Service**: Must integrate Discord/Telegram webhooks separately

### Overall Assessment

**SDK Readiness**: ⭐⭐⭐⭐⭐ (Excellent)

The project-x-py SDK provides **all essential capabilities** for building the risk manager daemon:
- Robust async architecture
- Real-time event push (no polling needed)
- Comprehensive order and position management
- Production-ready error handling and reconnection logic

**Key Gap**: Lack of pre-trade rejection means enforcement must be **reactive** (post-fill), not **proactive** (pre-trade). This is acceptable given broker architecture constraints.

**Integration Complexity**: **Low to Medium**
- High-level `TradingSuite` simplifies setup
- Event-driven model aligns with our architecture
- Must build custom logic for PnL tracking and daily resets

**Recommendation**: Proceed with integration. SDK is mature, well-documented, and actively maintained.

---

## Next Steps for Integration

1. **Map SDK Events → Risk Manager Events** (see [event_mapping.md](event_mapping.md))
2. **Design SDK Adapter Contracts** (see [adapter_contracts.md](adapter_contracts.md))
3. **Define Integration Flows** (see [integration_flows.md](integration_flows.md))
4. **Identify Build Plan for Gaps** (see [gaps_and_build_plan.md](gaps_and_build_plan.md))
5. **Document Risks and Open Questions** (see [risks_open_questions.md](risks_open_questions.md))

---

**Document Status**: ✅ Complete
**Last Updated**: 2025-10-15
**Author**: RM-SDK-Analyst
**Approved By**: [Pending Product Owner Review]
