# SDK Adapter Layer

This directory contains the adapter layer that connects the Risk Manager Daemon to the project-x-py SDK.

## Overview

The adapter layer provides a clean abstraction over the project-x-py SDK, allowing the Risk Manager to interact with the broker without depending on SDK-specific types or methods.

## Components

### 1. SDKAdapter (`sdk_adapter.py`)

Main adapter class for broker integration.

**Key Methods:**
- `connect()` - Establish connection to broker
- `disconnect()` - Gracefully disconnect
- `get_current_positions()` - Query open positions
- `close_position()` - Close specific position
- `flatten_account()` - Close all positions
- `get_instrument_tick_value()` - Get tick value for instrument
- `get_current_price()` - Get current market price

**Features:**
- Automatic retry with exponential backoff
- Connection state management
- Error handling with custom exceptions

### 2. EventNormalizer (`event_normalizer.py`)

Converts SDK events to internal Risk Manager event format.

**Supported SDK Events:**
- `ORDER_FILLED` → `FILL`
- `POSITION_UPDATED` → `POSITION_UPDATE`
- `CONNECTED` → `CONNECTION_CHANGE`
- `DISCONNECTED` → `CONNECTION_CHANGE`
- `RECONNECTING` → `CONNECTION_CHANGE`
- `QUOTE_UPDATE` → (updates price cache, no event)
- `POSITION_CLOSED` → (updates state, no event)
- `ORDER_REJECTED` → (logs error, no event)

**Key Method:**
- `normalize(sdk_event)` - Convert SDK event to internal event

### 3. InstrumentCache (`instrument_cache.py`)

Caches instrument metadata to reduce API calls.

**Cached Data:**
- Tick values (dollars per tick)
- Contract IDs
- Tick sizes

**Key Methods:**
- `get_tick_value(symbol)` - Get tick value (cached)
- `get_contract_id(symbol)` - Get contract ID (cached)
- `clear_cache()` - Clear cache (for daily reset)

### 4. PriceCache (`price_cache.py`)

Maintains current market prices for PnL calculations.

**Features:**
- Updates from QUOTE_UPDATE events
- Stale price detection (>60s old)
- Bid/ask spread tracking

**Key Methods:**
- `update_from_quote(symbol, bid, ask)` - Update price
- `get_price(symbol)` - Get current price
- `is_price_fresh(symbol)` - Check if price is fresh

### 5. Custom Exceptions (`exceptions.py`)

Adapter-specific exceptions for error handling.

**Exception Hierarchy:**
```
SDKAdapterError (base)
├── ConnectionError - Connection/authentication failures
├── QueryError - Position/account query failures
├── OrderError - Order placement failures
├── PriceError - Price query failures
└── InstrumentError - Instrument not found/invalid
```

## Usage Example

```python
from src.adapters import SDKAdapter, EventNormalizer, InstrumentCache, PriceCache

# Initialize adapter
adapter = SDKAdapter(
    api_key="your_api_key",
    username="your_username",
    account_id=123456
)

# Connect to broker
await adapter.connect()

# Query positions
positions = await adapter.get_current_positions()

# Close a position
result = await adapter.close_position(
    account_id="123456",
    position_id=position.position_id,
    quantity=None  # Close all
)

# Disconnect
await adapter.disconnect()
```

## Implementation Status

**Current Status:** ✅ **Structure Complete**

The adapter layer structure has been implemented with all required classes and methods. Each component includes:
- Full method signatures per adapter_contracts.md
- Docstrings with parameter and return types
- Error handling with custom exceptions
- Basic implementation structure

**Next Steps:**

1. **Test-Driven Development** (per CLAUDE.md TDD rules):
   - Test-Orchestrator will write comprehensive unit tests
   - Developer will implement methods to make tests pass (GREEN phase)
   - Refactor for cleanliness while keeping tests green

2. **SDK Integration**:
   - Import actual project-x-py SDK classes
   - Implement TradingSuite connection logic
   - Subscribe to WebSocket events
   - Convert SDK types to internal types

3. **Testing**:
   - Unit tests with mock SDK
   - Integration tests with real SDK
   - Performance tests (enforcement latency <500ms)

## Architecture Decisions

### Why Adapter Pattern?

The adapter pattern isolates the Risk Manager from SDK-specific details:
- **Testability**: Easy to mock for unit tests
- **Maintainability**: SDK changes only affect adapter layer
- **Flexibility**: Can support multiple brokers in future

### Error Handling Strategy

All SDK exceptions are wrapped in custom exceptions:
- **Retryable errors** (network timeouts): Auto-retry with exponential backoff (3 attempts)
- **Non-retryable errors** (auth failures): Raise immediately
- **Logging**: All errors logged with full context

### Caching Strategy

Two caches minimize API calls:
- **InstrumentCache**: Instrument metadata (rarely changes)
- **PriceCache**: Current prices (updates from WebSocket)

## Testing

Run adapter structure tests:
```bash
uv run pytest tests/unit/adapters/ -v
```

## Documentation References

- [adapter_contracts.md](../../docs/integration/adapter_contracts.md) - Full interface specifications
- [event_mapping.md](../../docs/integration/event_mapping.md) - SDK to internal event mappings
- [gaps_and_build_plan.md](../../docs/integration/gaps_and_build_plan.md) - Implementation guide
- [CLAUDE.md](../../CLAUDE.md) - TDD rules and workflow

## Notes

- All adapter methods use `async/await` patterns
- All money values use `Decimal` type (no floats!)
- All timestamps use `datetime` with UTC timezone
- Connection retry: 3 attempts with exponential backoff (1s, 2s, 4s)
- Price cache stale threshold: 60 seconds

---

**Status**: Structure complete, awaiting TDD implementation
**Last Updated**: 2025-10-16
**Developer**: RM-SDK-Developer
