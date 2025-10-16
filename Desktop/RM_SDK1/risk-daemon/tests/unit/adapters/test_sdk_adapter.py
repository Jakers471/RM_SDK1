"""
Unit tests for SDKAdapter class.

Tests the 10 core adapter methods that provide the interface between
the Risk Manager Daemon and the project-x-py SDK.

These tests are written FIRST (TDD RED phase) - implementation does not exist yet.
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

# Import will fail initially - this is expected in RED phase
try:
    from src.adapters.sdk_adapter import SDKAdapter
    from src.adapters.exceptions import (
        ConnectionError,
        OrderError,
        PriceError,
        QueryError,
        InstrumentError,
    )
except ImportError:
    # Mark tests as expected to fail during RED phase
    pytestmark = pytest.mark.xfail(reason="SDKAdapter not implemented yet", strict=False)

from tests.conftest import Position, OrderResult


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def api_credentials():
    """Provide test API credentials."""
    return {
        "api_key": "test_api_key_12345",
        "username": "test_user",
        "account_id": 123456
    }


@pytest.fixture
def mock_trading_suite():
    """Provide mock TradingSuite instance."""
    mock_suite = MagicMock()
    mock_suite.orders = MagicMock()
    mock_suite.data = MagicMock()
    mock_suite.client = MagicMock()
    return mock_suite


@pytest.fixture
def sdk_adapter(api_credentials):
    """Provide SDKAdapter instance with test credentials."""
    return SDKAdapter(
        api_key=api_credentials["api_key"],
        username=api_credentials["username"],
        account_id=api_credentials["account_id"]
    )


# ============================================================================
# Connection Management Tests (Methods 1-3)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_connect_establishes_connection_successfully(sdk_adapter, mock_trading_suite):
    """Test that connect() establishes broker connection via SDK."""
    # Setup: Mock TradingSuite.create() to return mock suite
    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)

        # Execute
        await sdk_adapter.connect()

        # Assert: Connection established
        assert sdk_adapter.is_connected() is True
        assert sdk_adapter.suite is not None
        mock_ts_class.create.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_connect_raises_connection_error_on_authentication_failure(sdk_adapter):
    """Test that connect() raises ConnectionError when authentication fails."""
    # Setup: Mock TradingSuite.create() to raise exception
    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(side_effect=Exception("Invalid API key"))

        # Execute & Assert
        with pytest.raises(ConnectionError) as exc_info:
            await sdk_adapter.connect()

        assert "Invalid API key" in str(exc_info.value)
        assert sdk_adapter.is_connected() is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_disconnect_closes_connection_gracefully(sdk_adapter, mock_trading_suite):
    """Test that disconnect() gracefully closes WebSocket and HTTP sessions."""
    # Setup: Connect first
    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        await sdk_adapter.connect()

        mock_trading_suite.close = AsyncMock()

        # Execute
        await sdk_adapter.disconnect()

        # Assert: Connection closed
        assert sdk_adapter.is_connected() is False
        mock_trading_suite.close.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_is_connected_returns_false_when_not_connected(sdk_adapter):
    """Test that is_connected() returns False before connection established."""
    # Assert: No connection yet
    assert sdk_adapter.is_connected() is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_is_connected_returns_true_after_successful_connection(sdk_adapter, mock_trading_suite):
    """Test that is_connected() returns True after successful connection."""
    # Setup: Connect
    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        await sdk_adapter.connect()

        # Assert
        assert sdk_adapter.is_connected() is True


# ============================================================================
# Position Query Tests (Method 4)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_current_positions_returns_normalized_positions(sdk_adapter, mock_trading_suite, account_id):
    """Test that get_current_positions() queries and normalizes SDK positions."""
    # Setup: Mock SDK position data
    mock_sdk_positions = [
        MagicMock(
            id="pos_123",
            contractId="CON.F.US.MNQ.U25",
            side="long",
            quantity=2,
            avgEntryPrice=18000.50,
            currentPrice=18005.00,
            unrealizedPnl=9.00
        ),
        MagicMock(
            id="pos_456",
            contractId="CON.F.US.MES.U25",
            side="short",
            quantity=1,
            avgEntryPrice=5100.00,
            currentPrice=5095.00,
            unrealizedPnl=25.00
        )
    ]

    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.client.search_open_positions = AsyncMock(
            return_value=mock_sdk_positions
        )

        await sdk_adapter.connect()

        # Execute
        positions = await sdk_adapter.get_current_positions(account_id)

        # Assert: Returns internal Position objects
        assert len(positions) == 2
        assert isinstance(positions[0], Position)
        assert positions[0].symbol == "MNQ"
        assert positions[0].side == "long"
        assert positions[0].quantity == 2
        assert positions[1].symbol == "MES"
        assert positions[1].side == "short"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_current_positions_returns_empty_list_when_no_positions(sdk_adapter, mock_trading_suite, account_id):
    """Test that get_current_positions() returns empty list when no open positions."""
    # Setup: Mock SDK returns empty list
    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.client.search_open_positions = AsyncMock(return_value=[])

        await sdk_adapter.connect()

        # Execute
        positions = await sdk_adapter.get_current_positions(account_id)

        # Assert
        assert positions == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_current_positions_raises_query_error_on_sdk_failure(sdk_adapter, mock_trading_suite, account_id):
    """Test that get_current_positions() raises QueryError when SDK query fails."""
    # Setup: Mock SDK raises exception
    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.client.search_open_positions = AsyncMock(
            side_effect=Exception("API timeout")
        )

        await sdk_adapter.connect()

        # Execute & Assert
        with pytest.raises(QueryError) as exc_info:
            await sdk_adapter.get_current_positions(account_id)

        assert "API timeout" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_current_positions_uses_default_account_id_when_not_provided(sdk_adapter, mock_trading_suite):
    """Test that get_current_positions() uses self.account_id when account_id param is None."""
    # Setup
    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.client.search_open_positions = AsyncMock(return_value=[])

        await sdk_adapter.connect()

        # Execute: Don't pass account_id
        await sdk_adapter.get_current_positions()

        # Assert: Uses self.account_id
        mock_trading_suite.client.search_open_positions.assert_called_once_with(
            account_id=sdk_adapter.account_id
        )


# ============================================================================
# PnL Query Tests (Method 5)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_account_pnl_calculates_unrealized_pnl_from_positions(sdk_adapter, mock_trading_suite, account_id):
    """Test that get_account_pnl() calculates unrealized PnL from open positions."""
    # Setup: Mock positions with unrealized PnL
    mock_sdk_positions = [
        MagicMock(unrealizedPnl=100.50),
        MagicMock(unrealizedPnl=-50.25),
        MagicMock(unrealizedPnl=25.00)
    ]

    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.client.search_open_positions = AsyncMock(
            return_value=mock_sdk_positions
        )

        await sdk_adapter.connect()

        # Execute
        pnl = await sdk_adapter.get_account_pnl(account_id)

        # Assert: Calculates total unrealized PnL
        assert pnl["unrealized"] == Decimal("75.25")
        assert pnl["realized"] is None  # SDK doesn't provide this


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_account_pnl_returns_zero_when_no_positions(sdk_adapter, mock_trading_suite, account_id):
    """Test that get_account_pnl() returns zero unrealized PnL when no positions."""
    # Setup: No positions
    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.client.search_open_positions = AsyncMock(return_value=[])

        await sdk_adapter.connect()

        # Execute
        pnl = await sdk_adapter.get_account_pnl(account_id)

        # Assert
        assert pnl["unrealized"] == Decimal("0.00")
        assert pnl["realized"] is None


# ============================================================================
# Order Execution Tests (Methods 6-7)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_close_position_places_market_order_to_close(sdk_adapter, mock_trading_suite, account_id):
    """Test that close_position() places market order to close specific position."""
    # Setup
    position_id = uuid4()
    mock_order_result = MagicMock(
        orderId="order_789",
        success=True,
        contractId="CON.F.US.MNQ.U25",
        side="sell",
        quantity=2
    )

    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.orders.close_position = AsyncMock(return_value=mock_order_result)

        await sdk_adapter.connect()

        # Execute
        result = await sdk_adapter.close_position(account_id, position_id, quantity=2)

        # Assert: OrderResult returned
        assert isinstance(result, OrderResult)
        assert result.success is True
        assert result.order_id == "order_789"
        assert result.contract_id == "CON.F.US.MNQ.U25"
        assert result.quantity == 2

        mock_trading_suite.orders.close_position.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_close_position_closes_full_position_when_quantity_is_none(sdk_adapter, mock_trading_suite, account_id):
    """Test that close_position() closes entire position when quantity=None."""
    # Setup
    position_id = uuid4()
    mock_order_result = MagicMock(
        orderId="order_999",
        success=True,
        contractId="CON.F.US.MNQ.U25",
        side="sell",
        quantity=5  # Full position size
    )

    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.orders.close_position = AsyncMock(return_value=mock_order_result)

        await sdk_adapter.connect()

        # Execute: quantity=None means close all
        result = await sdk_adapter.close_position(account_id, position_id, quantity=None)

        # Assert: Full position closed
        assert result.success is True
        assert result.quantity == 5


@pytest.mark.asyncio
@pytest.mark.unit
async def test_close_position_raises_order_error_on_failure(sdk_adapter, mock_trading_suite, account_id):
    """Test that close_position() raises OrderError when order placement fails."""
    # Setup: Mock order failure
    position_id = uuid4()

    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.orders.close_position = AsyncMock(
            side_effect=Exception("Order rejected: insufficient margin")
        )

        await sdk_adapter.connect()

        # Execute & Assert
        with pytest.raises(OrderError) as exc_info:
            await sdk_adapter.close_position(account_id, position_id, quantity=2)

        assert "insufficient margin" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_flatten_account_closes_all_positions(sdk_adapter, mock_trading_suite, account_id):
    """Test that flatten_account() closes all open positions for account."""
    # Setup: Mock 3 open positions
    mock_positions = [
        MagicMock(id=uuid4(), contractId="CON.F.US.MNQ.U25", quantity=2),
        MagicMock(id=uuid4(), contractId="CON.F.US.MES.U25", quantity=1),
        MagicMock(id=uuid4(), contractId="CON.F.US.MYM.U25", quantity=3)
    ]

    mock_order_results = [
        MagicMock(orderId=f"order_{i}", success=True, quantity=pos.quantity)
        for i, pos in enumerate(mock_positions)
    ]

    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.client.search_open_positions = AsyncMock(
            return_value=mock_positions
        )
        mock_trading_suite.orders.close_position = AsyncMock(
            side_effect=mock_order_results
        )

        await sdk_adapter.connect()

        # Execute
        results = await sdk_adapter.flatten_account(account_id)

        # Assert: All positions closed
        assert len(results) == 3
        assert all(r.success for r in results)
        assert mock_trading_suite.orders.close_position.call_count == 3


@pytest.mark.asyncio
@pytest.mark.unit
async def test_flatten_account_returns_empty_list_when_no_positions(sdk_adapter, mock_trading_suite, account_id):
    """Test that flatten_account() returns empty list when no open positions."""
    # Setup: No positions
    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.client.search_open_positions = AsyncMock(return_value=[])

        await sdk_adapter.connect()

        # Execute
        results = await sdk_adapter.flatten_account(account_id)

        # Assert
        assert results == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_flatten_account_continues_on_partial_failure(sdk_adapter, mock_trading_suite, account_id):
    """Test that flatten_account() attempts to close all positions even if some fail."""
    # Setup: 3 positions, 2nd one fails
    mock_positions = [
        MagicMock(id=uuid4(), contractId="CON.F.US.MNQ.U25", quantity=2),
        MagicMock(id=uuid4(), contractId="CON.F.US.MES.U25", quantity=1),
        MagicMock(id=uuid4(), contractId="CON.F.US.MYM.U25", quantity=3)
    ]

    async def mock_close_position(*args, **kwargs):
        # Fail on 2nd call
        if mock_trading_suite.orders.close_position.call_count == 2:
            raise Exception("Order rejected")
        return MagicMock(orderId="order_ok", success=True)

    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.client.search_open_positions = AsyncMock(
            return_value=mock_positions
        )
        mock_trading_suite.orders.close_position = AsyncMock(
            side_effect=mock_close_position
        )

        await sdk_adapter.connect()

        # Execute & Assert: Should not raise, but collect errors
        results = await sdk_adapter.flatten_account(account_id)

        # Should have 3 results (2 success, 1 failure)
        assert len(results) == 3
        assert sum(1 for r in results if r.success) == 2
        assert sum(1 for r in results if not r.success) == 1


# ============================================================================
# Instrument Metadata Tests (Method 8)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_instrument_tick_value_returns_cached_value(sdk_adapter, mock_trading_suite):
    """Test that get_instrument_tick_value() returns tick value for symbol."""
    # Setup: Mock instrument query
    mock_instrument = MagicMock(
        tickValue=Decimal("2.0"),  # MNQ = $2 per tick
        symbol="MNQ"
    )

    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.client.get_instrument = AsyncMock(
            return_value=mock_instrument
        )

        await sdk_adapter.connect()

        # Execute
        tick_value = await sdk_adapter.get_instrument_tick_value("MNQ")

        # Assert
        assert tick_value == Decimal("2.0")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_instrument_tick_value_caches_result(sdk_adapter, mock_trading_suite):
    """Test that get_instrument_tick_value() caches results to avoid repeated queries."""
    # Setup
    mock_instrument = MagicMock(tickValue=Decimal("2.0"), symbol="MNQ")

    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.client.get_instrument = AsyncMock(
            return_value=mock_instrument
        )

        await sdk_adapter.connect()

        # Execute: Call twice
        tick_value_1 = await sdk_adapter.get_instrument_tick_value("MNQ")
        tick_value_2 = await sdk_adapter.get_instrument_tick_value("MNQ")

        # Assert: Only queried once (cached)
        assert tick_value_1 == tick_value_2
        assert mock_trading_suite.client.get_instrument.call_count == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_instrument_tick_value_raises_instrument_error_on_not_found(sdk_adapter, mock_trading_suite):
    """Test that get_instrument_tick_value() raises InstrumentError when symbol not found."""
    # Setup: Mock instrument not found
    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.client.get_instrument = AsyncMock(
            side_effect=Exception("Instrument INVALID not found")
        )

        await sdk_adapter.connect()

        # Execute & Assert
        with pytest.raises(InstrumentError) as exc_info:
            await sdk_adapter.get_instrument_tick_value("INVALID")

        assert "not found" in str(exc_info.value)


# ============================================================================
# Price Query Tests (Method 9)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_current_price_returns_mid_price_from_quote(sdk_adapter, mock_trading_suite):
    """Test that get_current_price() returns mid price (bid+ask)/2 from latest quote."""
    # Setup: Mock quote data
    mock_quote = MagicMock(
        bid=Decimal("18000.50"),
        ask=Decimal("18001.50")
    )

    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.data.get_current_price = AsyncMock(
            return_value=mock_quote
        )

        await sdk_adapter.connect()

        # Execute
        price = await sdk_adapter.get_current_price("MNQ")

        # Assert: Returns mid price
        assert price == Decimal("18001.00")  # (18000.50 + 18001.50) / 2


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_current_price_raises_price_error_when_no_quote_available(sdk_adapter, mock_trading_suite):
    """Test that get_current_price() raises PriceError when no quote available."""
    # Setup: No quote data
    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.data.get_current_price = AsyncMock(
            side_effect=Exception("No quote available")
        )

        await sdk_adapter.connect()

        # Execute & Assert
        with pytest.raises(PriceError) as exc_info:
            await sdk_adapter.get_current_price("MNQ")

        assert "No quote available" in str(exc_info.value)


# ============================================================================
# Event Handler Registration Tests (Method 10)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_register_event_handler_subscribes_to_sdk_events(sdk_adapter, mock_trading_suite):
    """Test that register_event_handler() registers handler for SDK event type."""
    # Setup
    handler = AsyncMock()

    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.on = MagicMock()

        await sdk_adapter.connect()

        # Execute
        sdk_adapter.register_event_handler("ORDER_FILLED", handler)

        # Assert: Handler registered with SDK
        mock_trading_suite.on.assert_called_once_with("ORDER_FILLED", handler)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_register_event_handler_supports_multiple_handlers(sdk_adapter, mock_trading_suite):
    """Test that register_event_handler() supports registering multiple handlers."""
    # Setup
    handler_1 = AsyncMock()
    handler_2 = AsyncMock()

    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.on = MagicMock()

        await sdk_adapter.connect()

        # Execute: Register multiple handlers
        sdk_adapter.register_event_handler("ORDER_FILLED", handler_1)
        sdk_adapter.register_event_handler("POSITION_UPDATED", handler_2)

        # Assert: Both registered
        assert mock_trading_suite.on.call_count == 2


# ============================================================================
# Error Handling & Edge Cases
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_operations_raise_error_when_not_connected(sdk_adapter, account_id):
    """Test that operations raise appropriate errors when adapter is not connected."""
    # Assert: Not connected yet
    assert not sdk_adapter.is_connected()

    # All operations should fail with ConnectionError
    with pytest.raises(ConnectionError):
        await sdk_adapter.get_current_positions(account_id)

    with pytest.raises(ConnectionError):
        await sdk_adapter.get_account_pnl(account_id)

    with pytest.raises(ConnectionError):
        await sdk_adapter.close_position(account_id, uuid4(), 1)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_adapter_handles_connection_loss_during_operation(sdk_adapter, mock_trading_suite, account_id):
    """Test that adapter detects and reports connection loss during operations."""
    # Setup: Connected, then lose connection
    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        await sdk_adapter.connect()

        # Simulate connection loss
        mock_trading_suite.client.search_open_positions = AsyncMock(
            side_effect=Exception("WebSocket disconnected")
        )

        # Execute & Assert: Should detect connection loss
        with pytest.raises(QueryError) as exc_info:
            await sdk_adapter.get_current_positions(account_id)

        assert "disconnected" in str(exc_info.value).lower()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_adapter_retries_transient_errors_with_exponential_backoff(sdk_adapter, mock_trading_suite, account_id):
    """Test that adapter retries transient errors (network timeouts) with exponential backoff."""
    # Setup: Fail twice, succeed on 3rd attempt
    attempt_count = 0

    async def mock_query(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise Exception("Network timeout")
        return []  # Success on 3rd try

    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.client.search_open_positions = AsyncMock(
            side_effect=mock_query
        )

        await sdk_adapter.connect()

        # Execute: Should retry and eventually succeed
        positions = await sdk_adapter.get_current_positions(account_id)

        # Assert: Retried 3 times total
        assert attempt_count == 3
        assert positions == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_adapter_does_not_retry_non_transient_errors(sdk_adapter, mock_trading_suite, account_id):
    """Test that adapter does NOT retry non-transient errors (auth failure, invalid order)."""
    # Setup: Non-retryable error
    with patch('src.adapters.sdk_adapter.TradingSuite') as mock_ts_class:
        mock_ts_class.create = AsyncMock(return_value=mock_trading_suite)
        mock_trading_suite.orders.close_position = AsyncMock(
            side_effect=Exception("Invalid position ID")
        )

        await sdk_adapter.connect()

        # Execute & Assert: Should fail immediately, no retries
        with pytest.raises(OrderError) as exc_info:
            await sdk_adapter.close_position(account_id, uuid4(), 1)

        assert "Invalid position ID" in str(exc_info.value)
        # Should be called only once (no retries)
        assert mock_trading_suite.orders.close_position.call_count == 1
