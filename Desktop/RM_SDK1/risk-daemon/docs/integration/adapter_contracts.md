# Adapter Contracts: SDK Integration Interfaces

## Overview

This document defines the **exact contracts** for SDK integration adapters. Developers must implement these interfaces **precisely** to integrate project-x-py SDK with the Risk Manager Daemon.

---

## 1. SDKAdapter Class

**Purpose**: Abstraction layer over project-x-py SDK for connection management, queries, and order execution.

**File**: `src/adapters/sdk_adapter.py`

### Class Definition

```python
from decimal import Decimal
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from project_x_py import TradingSuite, ProjectX, EventType as SDKEventType
from src.state.models import Position, Event, EnforcementAction, OrderResult


class SDKAdapter:
    """
    Adapter for project-x-py SDK.

    Provides clean interface for Risk Manager to interact with broker
    without depending on SDK-specific types or methods.
    """

    def __init__(self, api_key: str, username: str, account_id: int):
        """
        Initialize SDK adapter.

        Args:
            api_key: TopstepX API key
            username: TopstepX username
            account_id: Account ID to monitor
        """
        self.api_key = api_key
        self.username = username
        self.account_id = account_id

        self.suite: Optional[TradingSuite] = None
        self.client: Optional[ProjectX] = None
        self._connected = False

    async def connect(self) -> None:
        """
        Establish connection to broker via SDK.

        Creates TradingSuite with WebSocket connections.
        Authenticates and subscribes to position/order events.

        Raises:
            ConnectionError: If authentication or connection fails
        """

    async def disconnect(self) -> None:
        """
        Gracefully disconnect from broker.

        Closes WebSocket connections and HTTP sessions.
        """

    def is_connected(self) -> bool:
        """
        Check if SDK is connected to broker.

        Returns:
            bool: True if WebSocket connected and authenticated
        """

    async def get_current_positions(self, account_id: Optional[str] = None) -> List[Position]:
        """
        Query current open positions for account.

        Args:
            account_id: Account ID (uses self.account_id if None)

        Returns:
            List of Position objects (internal format, not SDK Position)

        Raises:
            QueryError: If position query fails
        """

    async def get_account_pnl(self, account_id: Optional[str] = None) -> dict:
        """
        Get account PnL summary.

        NOTE: SDK does not provide realized/unrealized PnL directly.
        This method queries positions and calculates unrealized PnL.
        Realized PnL must be tracked separately by Risk Manager.

        Args:
            account_id: Account ID (uses self.account_id if None)

        Returns:
            {
                "unrealized": Decimal,  # Total unrealized PnL (calculated)
                "realized": None        # Not provided by SDK (must track separately)
            }

        Raises:
            QueryError: If query fails
        """

    async def close_position(
        self,
        account_id: str,
        position_id: UUID,
        quantity: Optional[int] = None
    ) -> OrderResult:
        """
        Close specific position (full or partial).

        Args:
            account_id: Account ID
            position_id: Position ID to close
            quantity: Number of contracts (None = close all)

        Returns:
            OrderResult with order_id and success status

        Raises:
            OrderError: If order placement fails
        """

    async def flatten_account(self, account_id: str) -> List[OrderResult]:
        """
        Close ALL positions for account.

        NOTE: SDK has no native "flatten all" method.
        Implementation: Loop through positions and close each.

        Args:
            account_id: Account ID

        Returns:
            List of OrderResult (one per position closed)

        Raises:
            OrderError: If any close order fails
        """

    async def get_instrument_tick_value(self, symbol: str) -> Decimal:
        """
        Get tick value (dollars per point) for instrument.

        Args:
            symbol: Instrument symbol (e.g., "MNQ")

        Returns:
            Tick value (e.g., Decimal('2.0') for MNQ)

        Raises:
            InstrumentError: If instrument not found
        """

    async def get_current_price(self, symbol: str) -> Decimal:
        """
        Get current market price for symbol.

        Uses latest quote from WebSocket stream (mid of bid/ask).

        Args:
            symbol: Instrument symbol

        Returns:
            Current mark price (mid of bid/ask)

        Raises:
            PriceError: If no price available
        """
```

### Implementation Notes

**SDK Methods Used**:
- `TradingSuite.create()` → initialize
- `client.search_open_positions()` → get positions
- `suite.orders.close_position(contract_id, method="market")` → close position
- `suite.data.get_current_price()` → get price
- `client.get_instrument(contract_id)` → get tick value

**Error Handling**:
- Wrap all SDK exceptions in custom exceptions (ConnectionError, QueryError, OrderError, etc.)
- Log all errors with full context
- Retry transient errors (network timeouts) with exponential backoff

**State Management**:
- Price cache (symbol → Decimal) for PnL calculations
- Instrument cache (symbol → tick_value) to avoid repeated queries
- Connection state tracking

---

## 2. EventNormalizer Class

**Purpose**: Convert SDK events to internal Risk Manager events.

**File**: `src/adapters/event_normalizer.py`

### Class Definition

```python
from typing import Optional, Dict
from decimal import Decimal
from uuid import UUID

from project_x_py.event_bus import Event as SDKEvent, EventType as SDKEventType
from src.state.models import Event, EventType
from src.state.state_manager import StateManager


class EventNormalizer:
    """
    Normalizes SDK events to internal Risk Manager events.

    Responsibilities:
    - Extract data from SDK event payloads
    - Map SDK event types to internal EventType enum
    - Populate internal event.data dict with normalized fields
    - Maintain price cache for PnL calculations
    """

    def __init__(
        self,
        state_manager: StateManager,
        instrument_cache: InstrumentCache
    ):
        """
        Initialize event normalizer.

        Args:
            state_manager: State manager for position lookups
            instrument_cache: Cache for tick values
        """

    async def normalize(self, sdk_event: SDKEvent) -> Optional[Event]:
        """
        Normalize SDK event to internal event.

        Args:
            sdk_event: Event from project-x-py SDK

        Returns:
            Internal Event object, or None if event doesn't require propagation

        Example:
            sdk_event = SDKEvent(type=SDKEventType.ORDER_FILLED, data={...})
            internal_event = await normalizer.normalize(sdk_event)
            # internal_event.event_type == EventType.FILL
        """

    def _extract_symbol(self, contract_id: str) -> str:
        """
        Extract symbol from contractId.

        Args:
            contract_id: SDK contract ID (e.g., "CON.F.US.MNQ.U25")

        Returns:
            Symbol (e.g., "MNQ")
        """

    async def _calculate_unrealized_pnl(
        self,
        position_id: UUID,
        current_price: Decimal,
        entry_price: Decimal,
        quantity: int,
        symbol: str
    ) -> Decimal:
        """
        Calculate unrealized PnL for position.

        Args:
            position_id: Position ID
            current_price: Current market price
            entry_price: Entry price
            quantity: Position size
            symbol: Instrument symbol

        Returns:
            Unrealized PnL in dollars (rounded to cents)
        """
```

### Event Mapping Table

| SDK Event | Internal Event | Priority | Notes |
|-----------|---------------|----------|-------|
| `ORDER_FILLED` | `FILL` | 2 | New position fill |
| `POSITION_UPDATED` | `POSITION_UPDATE` | 2 | Price/size change |
| `CONNECTED` | `CONNECTION_CHANGE` | 1 | WebSocket connected |
| `DISCONNECTED` | `CONNECTION_CHANGE` | 1 | WebSocket disconnected |
| `RECONNECTING` | `CONNECTION_CHANGE` | 1 | Reconnection attempt |
| `QUOTE_UPDATE` | *(no event)* | - | Update price cache only |
| `POSITION_CLOSED` | *(no event)* | - | Update state only |
| `ORDER_REJECTED` | *(no event)* | - | Log error only |

**See [event_mapping.md](event_mapping.md) for detailed field mappings.**

---

## 3. InstrumentCache Class

**Purpose**: Cache instrument metadata (tick values) to avoid repeated SDK queries.

**File**: `src/adapters/instrument_cache.py`

```python
from decimal import Decimal
from typing import Dict

from project_x_py import ProjectX


class InstrumentCache:
    """
    Cache for instrument metadata (tick values, contract IDs).

    Reduces API calls by storing instrument data after first query.
    """

    def __init__(self, client: ProjectX):
        self.client = client
        self._cache: Dict[str, InstrumentMetadata] = {}

    async def get_tick_value(self, symbol: str) -> Decimal:
        """
        Get tick value for symbol (cached).

        Args:
            symbol: Instrument symbol (e.g., "MNQ")

        Returns:
            Tick value in dollars per tick (e.g., Decimal('0.5'))
        """

    async def get_contract_id(self, symbol: str) -> str:
        """
        Get current contract ID for symbol.

        Args:
            symbol: Root symbol (e.g., "MNQ")

        Returns:
            Full contract ID (e.g., "CON.F.US.MNQ.U25")
        """

    async def _fetch_instrument(self, symbol: str) -> InstrumentMetadata:
        """Fetch instrument metadata from SDK (uncached)."""
```

---

## 4. OrderResult Dataclass

**Purpose**: Standard return type for order execution methods.

**File**: `src/state/models.py` (add to existing models)

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class OrderResult:
    """
    Result of order execution attempt.

    Returned by SDKAdapter.close_position() and flatten_account().
    """

    success: bool                      # True if order placed successfully
    order_id: Optional[str]            # Broker order ID (if success=True)
    error_message: Optional[str]       # Error details (if success=False)
    contract_id: str                   # Contract that was traded
    side: str                          # "buy" or "sell"
    quantity: int                      # Contracts ordered
    price: Optional[Decimal]           # Limit price (None for market orders)
```

---

## 5. Error Handling

### Custom Exceptions

**File**: `src/adapters/exceptions.py`

```python
class SDKAdapterError(Exception):
    """Base exception for SDK adapter errors."""


class ConnectionError(SDKAdapterError):
    """Failed to connect or authenticate with broker."""


class QueryError(SDKAdapterError):
    """Failed to query positions, orders, or account data."""


class OrderError(SDKAdapterError):
    """Failed to place, modify, or cancel order."""


class PriceError(SDKAdapterError):
    """Failed to get current market price."""


class InstrumentError(SDKAdapterError):
    """Instrument not found or invalid."""
```

### Retry Logic

**Transient Errors** (network timeouts, HTTP 500):
- Retry up to 3 times with exponential backoff (1s, 2s, 4s)
- If all retries fail → raise exception

**Non-Retryable Errors** (authentication failure, invalid order):
- Raise exception immediately

---

## Integration Flow

```
Risk Manager Daemon
    ↓
SDKAdapter.get_current_positions()
    ↓
project-x-py: client.search_open_positions()
    ↓
SDK returns List[SDK Position]
    ↓
SDKAdapter converts → List[Internal Position]
    ↓
Return to Risk Manager
```

**Event Flow**:
```
Broker (TopstepX)
    ↓ WebSocket
project-x-py SDK EventBus
    ↓ SDK Event (ORDER_FILLED)
Event Handler (registered via suite.on(...))
    ↓
EventNormalizer.normalize(sdk_event)
    ↓ Internal Event (FILL)
Risk Manager EventBus.publish(event)
    ↓
Risk Handler, State Manager, etc.
```

---

## Testing Contracts

### Mock SDK for Testing

**File**: `tests/mocks/mock_sdk.py`

```python
class MockTradingSuite:
    """Mock TradingSuite for testing without broker connection."""

    def __init__(self):
        self.positions = []
        self.orders = []
        self.events = []

    async def on(self, event_type, handler):
        """Register event handler."""
        self.events.append((event_type, handler))

    # ... (implement minimal SDK interface for testing)
```

### Test Cases

**Test 1**: Position Query
```python
async def test_get_current_positions():
    adapter = SDKAdapter(api_key="test", username="test", account_id=123)
    # Mock SDK returns 2 positions
    positions = await adapter.get_current_positions()
    assert len(positions) == 2
    assert positions[0].symbol == "MNQ"
```

**Test 2**: Event Normalization
```python
async def test_normalize_order_filled():
    normalizer = EventNormalizer(state_manager, instrument_cache)
    sdk_event = SDKEvent(
        type=SDKEventType.ORDER_FILLED,
        data={'orderId': 123, 'contractId': 'CON.F.US.MNQ.U25', ...}
    )
    internal_event = await normalizer.normalize(sdk_event)
    assert internal_event.event_type == EventType.FILL
    assert internal_event.data['symbol'] == "MNQ"
```

**Test 3**: Close Position
```python
async def test_close_position():
    adapter = SDKAdapter(...)
    result = await adapter.close_position(
        account_id="123",
        position_id=UUID("..."),
        quantity=None  # Close all
    )
    assert result.success is True
    assert result.order_id is not None
```

---

## Summary: Developer Checklist

**To implement SDK integration, Developer must**:

✅ Implement `SDKAdapter` class with all 10 methods
✅ Implement `EventNormalizer` class with normalize() method
✅ Implement `InstrumentCache` for tick value caching
✅ Create custom exceptions (ConnectionError, QueryError, etc.)
✅ Add `OrderResult` dataclass to `src/state/models.py`
✅ Write unit tests for each adapter method
✅ Write integration tests with mock SDK
✅ Handle all error cases with proper logging
✅ Document any SDK quirks or limitations encountered

**Estimated Effort**: 3-5 days (including tests)

---

**Document Status**: ✅ Complete
**Last Updated**: 2025-10-15
**Author**: RM-SDK-Analyst
**Approved By**: [Pending Product Owner Review]
