# Event Mapping: SDK Events → Risk Manager Events

## Overview

This document defines the precise mapping between project-x-py SDK events and Risk Manager Daemon internal events. Each mapping includes:
- SDK event type (EventType enum)
- Our internal event type (from `12-core-interfaces-and-events.md`)
- Data field extraction (SDK event payload → our event.data dict)
- Priority assignment
- Example code for EventNormalizer

---

## Event Type Mappings

### 1. SDK: `EventType.ORDER_FILLED` → Internal: `FILL` (Priority 2)

**When**: Order completely filled (new position opened or added to)

**SDK Event Data**:
```python
{
    'orderId': int,
    'contractId': str,          # "CON.F.US.MNQ.U25"
    'side': int,                # 0=BUY, 1=SELL
    'size': int,                # Contracts filled
    'filledPrice': float,       # Execution price
    'fillTime': str,            # ISO 8601 timestamp
    'accountId': int            # Account ID
}
```

**Internal Event Data** (required fields):
```python
{
    "symbol": str,              # Extracted: "MNQ" from contractId
    "side": str,                # Mapped: "long" (if SDK side=0) or "short" (if SDK side=1)
    "quantity": int,            # Copy: size
    "fill_price": Decimal,      # Convert: Decimal(str(filledPrice))
    "order_id": str,            # Convert: str(orderId)
    "fill_time": datetime       # Parse: ISO string → datetime
}
```

**Extraction Code**:
```python
async def normalize_order_filled(sdk_event: Event) -> Event:
    """Convert SDK ORDER_FILLED to internal FILL event."""
    data = sdk_event.data

    # Extract symbol from contractId (e.g., "CON.F.US.MNQ.U25" → "MNQ")
    contract_id = data['contractId']
    symbol = contract_id.split('.')[3] if '.' in contract_id else contract_id

    # Map side: SDK 0=BUY (long), 1=SELL (short)
    side = "long" if data['side'] == 0 else "short"

    # Parse timestamp
    fill_time = datetime.fromisoformat(data['fillTime'].replace('Z', '+00:00'))

    # Create internal event
    return Event(
        event_id=uuid.uuid4(),
        event_type=EventType.FILL,
        timestamp=fill_time,
        priority=2,
        account_id=str(data['accountId']),
        source="broker",
        data={
            "symbol": symbol,
            "side": side,
            "quantity": data['size'],
            "fill_price": Decimal(str(data['filledPrice'])),
            "order_id": str(data['orderId']),
            "fill_time": fill_time
        },
        correlation_id=None
    )
```

---

### 2. SDK: `EventType.POSITION_UPDATED` → Internal: `POSITION_UPDATE` (Priority 2)

**When**: Open position's price or size changes (market data update or partial close)

**SDK Event Data**:
```python
{
    'positionId': int,
    'contractId': str,
    'size': int,                # Current position size (may have decreased)
    'averagePrice': float,      # Entry price (unchanged unless averaging)
    'updateTimestamp': str      # ISO 8601
}
```

**Internal Event Data**:
```python
{
    "position_id": UUID,            # Convert: UUID from positionId
    "symbol": str,                  # Extract from contractId
    "current_price": Decimal,       # NOTE: SDK doesn't provide! Must get from quote stream
    "unrealized_pnl": Decimal,      # Must calculate: see calculation below
    "quantity": int,                # Copy: size
    "update_time": datetime         # Parse: updateTimestamp
}
```

**Challenge**: SDK POSITION_UPDATED does **NOT** include current market price or unrealized PnL. We must:
1. Cache latest quote price from `QUOTE_UPDATE` events
2. Calculate unrealized PnL ourselves

**Extraction Code**:
```python
async def normalize_position_updated(sdk_event: Event, price_cache: dict[str, Decimal]) -> Event:
    """Convert SDK POSITION_UPDATED to internal POSITION_UPDATE event."""
    data = sdk_event.data

    # Extract symbol
    contract_id = data['contractId']
    symbol = contract_id.split('.')[3] if '.' in contract_id else contract_id

    # Get current price from cache (latest quote)
    current_price = price_cache.get(symbol, Decimal('0.0'))

    # Calculate unrealized PnL (need position direction and tick value)
    # This requires querying full Position object to get direction
    # Simplified: assume we have position in state manager
    position = state_manager.get_position(UUID(data['positionId']))
    tick_value = get_tick_value(symbol)  # From instrument metadata

    if position:
        if position.side == "long":
            unrealized_pnl = (current_price - Decimal(str(data['averagePrice']))) * data['size'] * tick_value
        else:
            unrealized_pnl = (Decimal(str(data['averagePrice'])) - current_price) * data['size'] * tick_value
    else:
        unrealized_pnl = Decimal('0.0')

    update_time = datetime.fromisoformat(data['updateTimestamp'].replace('Z', '+00:00'))

    return Event(
        event_id=uuid.uuid4(),
        event_type=EventType.POSITION_UPDATE,
        timestamp=update_time,
        priority=2,
        account_id=position.account_id if position else "unknown",
        source="broker",
        data={
            "position_id": UUID(data['positionId']),
            "symbol": symbol,
            "current_price": current_price,
            "unrealized_pnl": unrealized_pnl.quantize(Decimal('0.01')),
            "quantity": data['size'],
            "update_time": update_time
        }
    )
```

---

### 3. SDK: `EventType.QUOTE_UPDATE` → Internal: Price Cache Update (No Event)

**Purpose**: Maintain current market prices for PnL calculations

**SDK Event Data**:
```python
{
    'contractId': str,
    'bid': float,
    'ask': float,
    'lastPrice': float,
    'timestamp': str
}
```

**Handling**:
```python
async def handle_quote_update(sdk_event: Event, price_cache: dict[str, Decimal]):
    """Update price cache from quote (no internal event emitted)."""
    data = sdk_event.data
    symbol = data['contractId'].split('.')[3]

    # Use mid-price for mark price
    mid_price = Decimal(str((data['bid'] + data['ask']) / 2))
    price_cache[symbol] = mid_price

    # No internal event emitted (price cache is internal state)
```

---

### 4. SDK: `EventType.ORDER_PLACED` → Internal: No Direct Mapping (Track Order)

**Purpose**: Track order placements for idempotency and debugging

**SDK Event Data**:
```python
{
    'orderId': int,
    'contractId': str,
    'side': int,
    'size': int,
    'type': int,  # 1=LIMIT, 2=MARKET, 4=STOP, etc.
    'placementTimestamp': str
}
```

**Handling**:
```python
async def handle_order_placed(sdk_event: Event, order_tracker: OrderTracker):
    """Track order placements (for idempotency and audit)."""
    data = sdk_event.data
    order_tracker.record_placement(
        order_id=data['orderId'],
        contract_id=data['contractId'],
        side=data['side'],
        size=data['size'],
        timestamp=datetime.fromisoformat(data['placementTimestamp'])
    )
    # No internal event needed (tracking only)
```

---

### 5. SDK: `EventType.CONNECTED` → Internal: `CONNECTION_CHANGE` (Priority 1)

**When**: WebSocket connection established

**SDK Event Data**:
```python
{
    'status': 'connected',
    'timestamp': str
}
```

**Internal Event Data**:
```python
{
    "status": str,      # "connected"
    "reason": None,
    "broker": "topstepx"
}
```

**Extraction Code**:
```python
async def normalize_connected(sdk_event: Event) -> Event:
    """Convert SDK CONNECTED to internal CONNECTION_CHANGE."""
    return Event(
        event_id=uuid.uuid4(),
        event_type=EventType.CONNECTION_CHANGE,
        timestamp=datetime.utcnow(),
        priority=1,
        account_id="system",  # System-level event
        source="broker",
        data={
            "status": "connected",
            "reason": None,
            "broker": "topstepx"
        }
    )
```

---

### 6. SDK: `EventType.DISCONNECTED` → Internal: `CONNECTION_CHANGE` (Priority 1)

**When**: WebSocket connection lost

**SDK Event Data**:
```python
{
    'status': 'disconnected',
    'reason': Optional[str],  # "network_error", "timeout", etc.
    'timestamp': str
}
```

**Internal Event Data**:
```python
{
    "status": str,              # "disconnected"
    "reason": Optional[str],    # Copy from SDK
    "broker": "topstepx"
}
```

**Extraction Code**:
```python
async def normalize_disconnected(sdk_event: Event) -> Event:
    """Convert SDK DISCONNECTED to internal CONNECTION_CHANGE."""
    data = sdk_event.data
    return Event(
        event_id=uuid.uuid4(),
        event_type=EventType.CONNECTION_CHANGE,
        timestamp=datetime.utcnow(),
        priority=1,
        account_id="system",
        source="broker",
        data={
            "status": "disconnected",
            "reason": data.get('reason'),
            "broker": "topstepx"
        }
    )
```

---

### 7. SDK: `EventType.RECONNECTING` → Internal: `CONNECTION_CHANGE` (Priority 1)

**When**: WebSocket attempting reconnection

**SDK Event Data**:
```python
{
    'status': 'reconnecting',
    'attempt': int,  # Reconnection attempt number
    'timestamp': str
}
```

**Internal Event Data**:
```python
{
    "status": str,      # "reconnecting"
    "reason": str,      # "reconnection_attempt_{N}"
    "broker": "topstepx"
}
```

---

### 8. SDK: `EventType.ORDER_REJECTED` → Internal: No Direct Mapping (Log Error)

**When**: Order rejected by broker (insufficient margin, invalid price, etc.)

**SDK Event Data**:
```python
{
    'orderId': int,
    'errorMessage': str,
    'errorCode': int,
    'timestamp': str
}
```

**Handling**:
```python
async def handle_order_rejected(sdk_event: Event, logger: Logger):
    """Log order rejection (not a risk event unless unexpected)."""
    data = sdk_event.data
    logger.error(
        f"Order {data['orderId']} rejected: {data['errorMessage']} (code: {data['errorCode']})"
    )
    # If this was an enforcement action, alert admin (critical failure)
    if enforcement_tracker.is_enforcement_order(data['orderId']):
        notification_service.alert_critical(
            f"ENFORCEMENT FAILED: Order {data['orderId']} rejected"
        )
```

---

### 9. SDK: `EventType.POSITION_CLOSED` → Internal: Update State (No Event to Risk Engine)

**When**: Position fully closed (size → 0)

**SDK Event Data**:
```python
{
    'positionId': int,
    'contractId': str,
    'closeTime': str
}
```

**Handling**:
```python
async def handle_position_closed(sdk_event: Event, state_manager: StateManager):
    """Update state when position closed (via fill or manual close)."""
    data = sdk_event.data
    position_id = UUID(data['positionId'])

    # Remove from open positions
    state_manager.remove_position(position_id)

    # No internal event needed (state update only)
    # Realized PnL updated via FILL events when closing order fills
```

---

## Internal-Only Events (Not from SDK)

These events are **generated internally** by the Risk Manager Daemon, not from SDK:

### 10. Internal: `TIME_TICK` (Priority 4)

**Generated By**: Internal timer (asyncio.sleep loop)

**Purpose**: Check timer-based rules (cooldowns, grace periods)

**Data**:
```python
{
    "tick_time": datetime  # Current time (UTC)
}
```

**Generation Code**:
```python
async def time_tick_generator(event_bus: EventBus):
    """Generate TIME_TICK events every 1 second."""
    while True:
        await asyncio.sleep(1.0)
        event = Event(
            event_id=uuid.uuid4(),
            event_type=EventType.TIME_TICK,
            timestamp=datetime.utcnow(),
            priority=4,
            account_id="system",
            source="timer",
            data={"tick_time": datetime.utcnow()}
        )
        await event_bus.publish(event)
```

---

### 11. Internal: `SESSION_TICK` (Priority 5)

**Generated By**: Internal session manager

**Purpose**: Daily reset (5pm CT), session boundaries

**Data**:
```python
{
    "tick_type": str,       # "session_open", "session_close", "daily_reset"
    "tick_time": datetime,
    "timezone": str         # "America/Chicago"
}
```

**Generation Code**:
```python
async def session_tick_generator(event_bus: EventBus, timezone_str: str = "America/Chicago"):
    """Generate SESSION_TICK events at session boundaries."""
    tz = pytz.timezone(timezone_str)

    while True:
        now_ct = datetime.now(tz)

        # Check if 5pm CT (daily reset)
        if now_ct.hour == 17 and now_ct.minute == 0 and now_ct.second == 0:
            event = Event(
                event_id=uuid.uuid4(),
                event_type=EventType.SESSION_TICK,
                timestamp=datetime.utcnow(),
                priority=5,
                account_id="system",
                source="session_manager",
                data={
                    "tick_type": "daily_reset",
                    "tick_time": datetime.utcnow(),
                    "timezone": timezone_str
                }
            )
            await event_bus.publish(event)
            await asyncio.sleep(60)  # Wait 1 minute to avoid duplicate

        await asyncio.sleep(1)  # Check every second
```

---

## Event Normalizer Implementation

### Complete EventNormalizer Class

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional
from uuid import UUID, uuid4
import pytz

class EventNormalizer:
    """
    Converts SDK events to internal Risk Manager events.

    Responsibilities:
    - Extract data from SDK event payloads
    - Map SDK event types to internal EventType enum
    - Populate internal event.data dict with normalized fields
    - Maintain price cache for PnL calculations
    - Handle symbol extraction from contractId
    """

    def __init__(self, state_manager: StateManager, instrument_cache: InstrumentCache):
        self.state_manager = state_manager
        self.instrument_cache = instrument_cache

        # Price cache: symbol → latest mark price
        self.price_cache: Dict[str, Decimal] = {}

        # Mapping: SDK EventType → normalization method
        self.normalizers = {
            "order_filled": self._normalize_order_filled,
            "position_updated": self._normalize_position_updated,
            "position_closed": self._handle_position_closed,
            "quote_update": self._handle_quote_update,
            "connected": self._normalize_connected,
            "disconnected": self._normalize_disconnected,
            "reconnecting": self._normalize_reconnecting,
            "order_rejected": self._handle_order_rejected,
        }

    async def normalize(self, sdk_event: Event) -> Optional[Event]:
        """
        Normalize SDK event to internal event.
        Returns None if event doesn't require internal propagation.
        """
        # Get event type string (SDK uses snake_case strings)
        event_type_str = sdk_event.type.value if hasattr(sdk_event.type, 'value') else str(sdk_event.type)

        # Find normalizer
        normalizer = self.normalizers.get(event_type_str)
        if not normalizer:
            # Unknown event type, log warning
            logger.warning(f"No normalizer for SDK event type: {event_type_str}")
            return None

        # Normalize
        return await normalizer(sdk_event)

    def _extract_symbol(self, contract_id: str) -> str:
        """Extract symbol from contractId (e.g., 'CON.F.US.MNQ.U25' → 'MNQ')."""
        if '.' in contract_id:
            parts = contract_id.split('.')
            if len(parts) >= 4:
                return parts[3]
        return contract_id  # Fallback to full contract ID

    async def _normalize_order_filled(self, sdk_event: Event) -> Event:
        """Convert SDK ORDER_FILLED to internal FILL event."""
        data = sdk_event.data
        symbol = self._extract_symbol(data['contractId'])
        side = "long" if data['side'] == 0 else "short"
        fill_time = datetime.fromisoformat(data['fillTime'].replace('Z', '+00:00'))

        return Event(
            event_id=uuid4(),
            event_type=EventType.FILL,
            timestamp=fill_time,
            priority=2,
            account_id=str(data['accountId']),
            source="broker",
            data={
                "symbol": symbol,
                "side": side,
                "quantity": data['size'],
                "fill_price": Decimal(str(data['filledPrice'])),
                "order_id": str(data['orderId']),
                "fill_time": fill_time
            }
        )

    async def _normalize_position_updated(self, sdk_event: Event) -> Event:
        """Convert SDK POSITION_UPDATED to internal POSITION_UPDATE event."""
        data = sdk_event.data
        symbol = self._extract_symbol(data['contractId'])

        # Get current price from cache
        current_price = self.price_cache.get(symbol, Decimal('0.0'))

        # Calculate unrealized PnL
        position = self.state_manager.get_position_by_id(UUID(data['positionId']))
        tick_value = await self.instrument_cache.get_tick_value(symbol)

        if position and tick_value:
            if position.side == "long":
                unrealized_pnl = (current_price - Decimal(str(data['averagePrice']))) * data['size'] * tick_value
            else:
                unrealized_pnl = (Decimal(str(data['averagePrice'])) - current_price) * data['size'] * tick_value
        else:
            unrealized_pnl = Decimal('0.0')

        update_time = datetime.fromisoformat(data['updateTimestamp'].replace('Z', '+00:00'))

        return Event(
            event_id=uuid4(),
            event_type=EventType.POSITION_UPDATE,
            timestamp=update_time,
            priority=2,
            account_id=str(data.get('accountId', position.account_id if position else 'unknown')),
            source="broker",
            data={
                "position_id": UUID(data['positionId']),
                "symbol": symbol,
                "current_price": current_price,
                "unrealized_pnl": unrealized_pnl.quantize(Decimal('0.01')),
                "quantity": data['size'],
                "update_time": update_time
            }
        )

    async def _handle_quote_update(self, sdk_event: Event) -> None:
        """Update price cache from quote (no internal event emitted)."""
        data = sdk_event.data
        symbol = self._extract_symbol(data['contractId'])

        # Use mid-price for mark price
        if data['bid'] and data['ask']:
            mid_price = Decimal(str((data['bid'] + data['ask']) / 2))
            self.price_cache[symbol] = mid_price

        return None  # No internal event

    async def _handle_position_closed(self, sdk_event: Event) -> None:
        """Handle position closure (state update, no event)."""
        data = sdk_event.data
        position_id = UUID(data['positionId'])
        self.state_manager.remove_position(position_id)
        return None

    async def _normalize_connected(self, sdk_event: Event) -> Event:
        """Convert SDK CONNECTED to internal CONNECTION_CHANGE."""
        return Event(
            event_id=uuid4(),
            event_type=EventType.CONNECTION_CHANGE,
            timestamp=datetime.utcnow(),
            priority=1,
            account_id="system",
            source="broker",
            data={
                "status": "connected",
                "reason": None,
                "broker": "topstepx"
            }
        )

    # ... (similar methods for disconnected, reconnecting, etc.)
```

---

## Summary: Event Flow

```
SDK WebSocket Events
    ↓
SDK EventBus (project-x-py internal)
    ↓
Our Event Handler (registered via suite.on(...))
    ↓
EventNormalizer.normalize(sdk_event)
    ↓
Internal Event (Risk Manager format)
    ↓
Risk Manager Event Bus
    ↓
Risk Handler, State Manager, etc.
```

---

**Document Status**: ✅ Complete
**Last Updated**: 2025-10-15
**Author**: RM-SDK-Analyst
**Approved By**: [Pending Product Owner Review]
