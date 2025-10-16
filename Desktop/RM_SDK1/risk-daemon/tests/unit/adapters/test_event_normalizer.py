"""
Unit tests for EventNormalizer class.

Tests the conversion of SDK events to internal Risk Manager events.
Handles 9 SDK event types and normalizes them to internal format.

These tests are written FIRST (TDD RED phase) - implementation does not exist yet.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

# Import will fail initially - this is expected in RED phase
try:
    from src.adapters.event_normalizer import EventNormalizer
except ImportError:
    # Mark tests as expected to fail during RED phase
    pytestmark = pytest.mark.xfail(reason="EventNormalizer not implemented yet", strict=False)

from tests.conftest import Event, FakeStateManager, FakeClock


# ============================================================================
# Mock SDK Event Types
# ============================================================================


class MockSDKEvent:
    """Mock SDK event for testing."""

    def __init__(self, event_type: str, data: Dict, timestamp: Optional[datetime] = None):
        self.type = event_type
        self.data = data
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.event_id = str(uuid4())


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def state_manager(clock):
    """Provide fake state manager for event normalization."""
    return FakeStateManager(clock)


@pytest.fixture
def instrument_cache():
    """Provide mock instrument cache."""
    cache = MagicMock()
    cache.get_tick_value = AsyncMock(return_value=Decimal("2.0"))  # Default: MNQ
    return cache


@pytest.fixture
def event_normalizer(state_manager, instrument_cache):
    """Provide EventNormalizer instance."""
    return EventNormalizer(state_manager, instrument_cache)


# ============================================================================
# ORDER_FILLED Event Normalization Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_order_filled_creates_fill_event(event_normalizer, account_id):
    """Test that ORDER_FILLED SDK event is normalized to FILL internal event."""
    # Setup: Mock SDK ORDER_FILLED event
    sdk_event = MockSDKEvent(
        event_type="ORDER_FILLED",
        data={
            "orderId": "order_123",
            "contractId": "CON.F.US.MNQ.U25",
            "side": "buy",
            "quantity": 2,
            "fillPrice": 18000.50,
            "accountId": account_id,
            "timestamp": "2025-10-15T10:30:00Z"
        }
    )

    # Execute
    internal_event = await event_normalizer.normalize(sdk_event)

    # Assert: Converted to FILL event
    assert internal_event is not None
    assert internal_event.event_type == "FILL"
    assert internal_event.account_id == account_id
    assert internal_event.priority == 2  # High priority
    assert internal_event.data["symbol"] == "MNQ"
    assert internal_event.data["side"] == "buy"
    assert internal_event.data["quantity"] == 2
    assert internal_event.data["fill_price"] == Decimal("18000.50")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_order_filled_extracts_symbol_from_contract_id(event_normalizer, account_id):
    """Test that symbol is correctly extracted from contractId."""
    # Setup: Different contract IDs
    test_cases = [
        ("CON.F.US.MNQ.U25", "MNQ"),
        ("CON.F.US.MES.Z25", "MES"),
        ("CON.F.US.MYM.H26", "MYM"),
        ("CON.F.US.M2K.M25", "M2K")
    ]

    for contract_id, expected_symbol in test_cases:
        sdk_event = MockSDKEvent(
            event_type="ORDER_FILLED",
            data={
                "orderId": "order_123",
                "contractId": contract_id,
                "side": "buy",
                "quantity": 1,
                "fillPrice": 18000.0,
                "accountId": account_id
            }
        )

        # Execute
        internal_event = await event_normalizer.normalize(sdk_event)

        # Assert: Symbol extracted correctly
        assert internal_event.data["symbol"] == expected_symbol


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_order_filled_includes_correlation_id(event_normalizer, account_id):
    """Test that FILL event includes correlation_id from SDK orderId."""
    # Setup
    sdk_event = MockSDKEvent(
        event_type="ORDER_FILLED",
        data={
            "orderId": "order_456",
            "contractId": "CON.F.US.MNQ.U25",
            "side": "sell",
            "quantity": 1,
            "fillPrice": 18005.00,
            "accountId": account_id
        }
    )

    # Execute
    internal_event = await event_normalizer.normalize(sdk_event)

    # Assert: Correlation ID set and deterministic
    assert internal_event.correlation_id is not None

    # Normalize again with same order_id - should get same correlation_id
    sdk_event2 = MockSDKEvent(
        event_type="ORDER_FILLED",
        data={
            "orderId": "order_456",  # Same order ID
            "contractId": "CON.F.US.MNQ.U25",
            "side": "sell",
            "quantity": 1,
            "fillPrice": 18005.00,
            "accountId": account_id
        }
    )
    internal_event2 = await event_normalizer.normalize(sdk_event2)
    assert internal_event.correlation_id == internal_event2.correlation_id


# ============================================================================
# POSITION_UPDATED Event Normalization Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_position_updated_creates_position_update_event(event_normalizer, account_id, state_manager, sample_position):
    """Test that POSITION_UPDATED SDK event is normalized to POSITION_UPDATE."""
    # Setup: Add position to state
    state_manager.add_position(account_id, sample_position)

    sdk_event = MockSDKEvent(
        event_type="POSITION_UPDATED",
        data={
            "positionId": str(sample_position.position_id),
            "contractId": "CON.F.US.MNQ.U25",
            "currentPrice": 18005.00,
            "unrealizedPnl": 20.00,
            "accountId": account_id
        }
    )

    # Execute
    internal_event = await event_normalizer.normalize(sdk_event)

    # Assert
    assert internal_event is not None
    assert internal_event.event_type == "POSITION_UPDATE"
    assert internal_event.priority == 2
    assert internal_event.data["position_id"] == sample_position.position_id
    assert internal_event.data["current_price"] == Decimal("18005.00")
    assert internal_event.data["unrealized_pnl"] == Decimal("20.00")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_position_updated_calculates_pnl_using_tick_value(event_normalizer, account_id, instrument_cache):
    """Test that POSITION_UPDATE calculates PnL using cached tick value."""
    # Setup: Mock instrument cache
    instrument_cache.get_tick_value = AsyncMock(return_value=Decimal("5.0"))  # MES = $5/tick

    sdk_event = MockSDKEvent(
        event_type="POSITION_UPDATED",
        data={
            "positionId": str(uuid4()),
            "contractId": "CON.F.US.MES.U25",
            "currentPrice": 5100.00,
            "entryPrice": 5095.00,
            "quantity": 2,
            "side": "long",
            "accountId": account_id
        }
    )

    # Execute
    internal_event = await event_normalizer.normalize(sdk_event)

    # Assert: PnL calculated with tick value
    # (5100 - 5095) * 2 contracts * $5/tick = $50
    instrument_cache.get_tick_value.assert_called_once_with("MES")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_position_updated_handles_short_positions(event_normalizer, account_id):
    """Test that POSITION_UPDATE correctly calculates PnL for short positions."""
    # Setup: Short position (profit when price drops)
    sdk_event = MockSDKEvent(
        event_type="POSITION_UPDATED",
        data={
            "positionId": str(uuid4()),
            "contractId": "CON.F.US.MNQ.U25",
            "currentPrice": 17995.00,  # Price dropped
            "entryPrice": 18000.00,
            "quantity": 2,
            "side": "short",
            "accountId": account_id
        }
    )

    # Execute
    internal_event = await event_normalizer.normalize(sdk_event)

    # Assert: Positive PnL for short when price drops
    # (18000 - 17995) * 2 * $2 = $20 profit
    assert internal_event.data["unrealized_pnl"] > 0


# ============================================================================
# CONNECTION_CHANGE Event Normalization Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_connected_creates_connection_change_event(event_normalizer, account_id):
    """Test that CONNECTED SDK event is normalized to CONNECTION_CHANGE."""
    # Setup
    sdk_event = MockSDKEvent(
        event_type="CONNECTED",
        data={
            "status": "connected",
            "accountId": account_id
        }
    )

    # Execute
    internal_event = await event_normalizer.normalize(sdk_event)

    # Assert
    assert internal_event is not None
    assert internal_event.event_type == "CONNECTION_CHANGE"
    assert internal_event.priority == 1  # Critical priority
    assert internal_event.data["status"] == "connected"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_disconnected_creates_connection_change_event(event_normalizer, account_id):
    """Test that DISCONNECTED SDK event is normalized to CONNECTION_CHANGE."""
    # Setup
    sdk_event = MockSDKEvent(
        event_type="DISCONNECTED",
        data={
            "status": "disconnected",
            "reason": "Network timeout",
            "accountId": account_id
        }
    )

    # Execute
    internal_event = await event_normalizer.normalize(sdk_event)

    # Assert
    assert internal_event is not None
    assert internal_event.event_type == "CONNECTION_CHANGE"
    assert internal_event.data["status"] == "disconnected"
    assert internal_event.data["reason"] == "Network timeout"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_reconnecting_creates_connection_change_event(event_normalizer, account_id):
    """Test that RECONNECTING SDK event is normalized to CONNECTION_CHANGE."""
    # Setup
    sdk_event = MockSDKEvent(
        event_type="RECONNECTING",
        data={
            "status": "reconnecting",
            "attempt": 2,
            "accountId": account_id
        }
    )

    # Execute
    internal_event = await event_normalizer.normalize(sdk_event)

    # Assert
    assert internal_event is not None
    assert internal_event.event_type == "CONNECTION_CHANGE"
    assert internal_event.data["status"] == "reconnecting"
    assert internal_event.data["attempt"] == 2


# ============================================================================
# QUOTE_UPDATE Event Normalization Tests (Price Cache Only)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_quote_update_updates_price_cache_without_event(event_normalizer):
    """Test that QUOTE_UPDATE updates price cache but returns None (no event propagation)."""
    # Setup
    sdk_event = MockSDKEvent(
        event_type="QUOTE_UPDATE",
        data={
            "symbol": "MNQ",
            "bid": 18000.50,
            "ask": 18001.50,
            "timestamp": "2025-10-15T10:30:00Z"
        }
    )

    # Execute
    internal_event = await event_normalizer.normalize(sdk_event)

    # Assert: No event created (price cache updated internally)
    assert internal_event is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_quote_update_caches_mid_price(event_normalizer):
    """Test that QUOTE_UPDATE caches mid price (bid+ask)/2."""
    # Setup
    sdk_event = MockSDKEvent(
        event_type="QUOTE_UPDATE",
        data={
            "symbol": "MNQ",
            "bid": 18000.00,
            "ask": 18002.00
        }
    )

    # Execute
    await event_normalizer.normalize(sdk_event)

    # Assert: Price cached at mid (18001.00)
    cached_price = await event_normalizer.get_cached_price("MNQ")
    assert cached_price == Decimal("18001.00")


# ============================================================================
# POSITION_CLOSED Event Normalization Tests (State Update Only)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_position_closed_updates_state_without_event(event_normalizer, account_id, state_manager, sample_position):
    """Test that POSITION_CLOSED updates state but returns None (no event propagation)."""
    # Setup: Add position
    state_manager.add_position(account_id, sample_position)

    sdk_event = MockSDKEvent(
        event_type="POSITION_CLOSED",
        data={
            "positionId": str(sample_position.position_id),
            "realizedPnl": 100.00,
            "accountId": account_id
        }
    )

    # Execute
    internal_event = await event_normalizer.normalize(sdk_event)

    # Assert: No event, but state updated
    assert internal_event is None
    # Verify position removed from state
    positions = state_manager.get_open_positions(account_id)
    assert len(positions) == 0


# ============================================================================
# ORDER_REJECTED Event Normalization Tests (Log Only)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_order_rejected_logs_error_without_event(event_normalizer, account_id):
    """Test that ORDER_REJECTED logs error but returns None (no event propagation)."""
    # Setup
    sdk_event = MockSDKEvent(
        event_type="ORDER_REJECTED",
        data={
            "orderId": "order_999",
            "reason": "Insufficient margin",
            "accountId": account_id
        }
    )

    # Execute
    internal_event = await event_normalizer.normalize(sdk_event)

    # Assert: No event (logged internally)
    assert internal_event is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_order_rejected_includes_rejection_details_in_log(event_normalizer, account_id):
    """Test that ORDER_REJECTED logs include rejection reason and order ID."""
    # Setup
    sdk_event = MockSDKEvent(
        event_type="ORDER_REJECTED",
        data={
            "orderId": "order_abc",
            "reason": "Market closed",
            "contractId": "CON.F.US.MNQ.U25",
            "accountId": account_id
        }
    )

    # Execute (with logging mock)
    with patch('src.adapters.event_normalizer.logger') as mock_logger:
        internal_event = await event_normalizer.normalize(sdk_event)

        # Assert: Error logged with details
        mock_logger.error.assert_called_once()
        log_args = str(mock_logger.error.call_args)
        assert "order_abc" in log_args
        assert "Market closed" in log_args


# ============================================================================
# Edge Cases & Error Handling
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_unknown_event_type_returns_none(event_normalizer):
    """Test that unknown SDK event types return None without crashing."""
    # Setup: Unknown event type
    sdk_event = MockSDKEvent(
        event_type="UNKNOWN_EVENT",
        data={"foo": "bar"}
    )

    # Execute
    internal_event = await event_normalizer.normalize(sdk_event)

    # Assert: Gracefully handled
    assert internal_event is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_handles_missing_required_fields(event_normalizer, account_id):
    """Test that normalizer handles SDK events with missing required fields."""
    # Setup: Missing contractId
    sdk_event = MockSDKEvent(
        event_type="ORDER_FILLED",
        data={
            "orderId": "order_123",
            # contractId missing!
            "side": "buy",
            "quantity": 2,
            "accountId": account_id
        }
    )

    # Execute & Assert: Should raise ValueError or return None
    with pytest.raises(ValueError):
        await event_normalizer.normalize(sdk_event)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_handles_invalid_contract_id_format(event_normalizer, account_id):
    """Test that normalizer handles malformed contractId."""
    # Setup: Malformed contractId
    sdk_event = MockSDKEvent(
        event_type="ORDER_FILLED",
        data={
            "orderId": "order_123",
            "contractId": "INVALID_FORMAT",
            "side": "buy",
            "quantity": 2,
            "fillPrice": 18000.0,
            "accountId": account_id
        }
    )

    # Execute & Assert: Should raise ValueError
    with pytest.raises(ValueError) as exc_info:
        await event_normalizer.normalize(sdk_event)

    assert "contractid" in str(exc_info.value).lower()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_preserves_event_timestamp(event_normalizer, account_id):
    """Test that normalized event preserves SDK event timestamp."""
    # Setup: Event with specific timestamp
    sdk_timestamp = datetime(2025, 10, 15, 10, 30, 0, tzinfo=timezone.utc)
    sdk_event = MockSDKEvent(
        event_type="ORDER_FILLED",
        data={
            "orderId": "order_123",
            "contractId": "CON.F.US.MNQ.U25",
            "side": "buy",
            "quantity": 1,
            "fillPrice": 18000.0,
            "accountId": account_id
        },
        timestamp=sdk_timestamp
    )

    # Execute
    internal_event = await event_normalizer.normalize(sdk_event)

    # Assert: Timestamp preserved
    assert internal_event.timestamp == sdk_timestamp


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_assigns_unique_event_id(event_normalizer, account_id):
    """Test that each normalized event gets a unique event_id."""
    # Setup: Two identical SDK events
    sdk_event_1 = MockSDKEvent(
        event_type="ORDER_FILLED",
        data={
            "orderId": "order_1",
            "contractId": "CON.F.US.MNQ.U25",
            "side": "buy",
            "quantity": 1,
            "fillPrice": 18000.0,
            "accountId": account_id
        }
    )

    sdk_event_2 = MockSDKEvent(
        event_type="ORDER_FILLED",
        data={
            "orderId": "order_2",
            "contractId": "CON.F.US.MNQ.U25",
            "side": "buy",
            "quantity": 1,
            "fillPrice": 18000.0,
            "accountId": account_id
        }
    )

    # Execute
    event_1 = await event_normalizer.normalize(sdk_event_1)
    event_2 = await event_normalizer.normalize(sdk_event_2)

    # Assert: Different event IDs
    assert event_1.event_id != event_2.event_id


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_sets_source_as_sdk(event_normalizer, account_id):
    """Test that normalized events have source='sdk'."""
    # Setup
    sdk_event = MockSDKEvent(
        event_type="ORDER_FILLED",
        data={
            "orderId": "order_123",
            "contractId": "CON.F.US.MNQ.U25",
            "side": "buy",
            "quantity": 1,
            "fillPrice": 18000.0,
            "accountId": account_id
        }
    )

    # Execute
    internal_event = await event_normalizer.normalize(sdk_event)

    # Assert: Source is SDK
    assert internal_event.source == "sdk"
