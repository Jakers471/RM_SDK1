"""
Unit tests for EventNormalizer edge cases to improve branch coverage.

These tests target missing branches identified in coverage analysis:
- Lines 111, 113-116: Event type extraction with different SDK formats
- Lines 130→132: Symbol extraction edge cases
- Line 169: Quote update without symbol (returns None)
- Line 219: Position closed handler (state update path)
- Lines 244, 280, 285: Connection event data handling (defaults and attributes)
- Lines 447, 470-500: SDK event handler methods
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4
from decimal import Decimal
from datetime import datetime, timezone

from src.adapters.event_normalizer import EventNormalizer
from tests.conftest import Event, FakeStateManager


@pytest.mark.asyncio
@pytest.mark.unit
class TestEventNormalizerEdgeCases:
    """Test edge cases for full branch coverage of EventNormalizer."""

    @pytest.fixture
    def state_manager(self):
        """Create state manager for tests."""
        from tests.conftest import FakeClock
        return FakeStateManager(FakeClock())

    @pytest.fixture
    def instrument_cache(self):
        """Create mock instrument cache."""
        cache = MagicMock()
        cache.get_tick_value = AsyncMock(return_value=Decimal("2.0"))
        return cache

    @pytest.fixture
    def event_bus(self):
        """Create mock event bus."""
        bus = MagicMock()
        bus.emit = AsyncMock()
        return bus

    @pytest.fixture
    def event_normalizer(self, event_bus, state_manager, instrument_cache):
        """Create EventNormalizer instance."""
        return EventNormalizer(event_bus, state_manager, instrument_cache)

    # ===================================================================
    # Event Type Extraction Branch Coverage
    # ===================================================================

    async def test_extract_event_type_with_value_attribute(self, event_normalizer):
        """
        Test line 111: Extract event_type when sdk_event.type has .value attribute.

        This covers enum-style event types used by some SDK versions.
        """
        # Create mock event with nested type.value
        mock_event_type = Mock()
        mock_event_type.value = "ORDER_FILLED"

        mock_sdk_event = Mock()
        mock_sdk_event.type = mock_event_type

        # Execute
        result = event_normalizer._extract_event_type(mock_sdk_event)

        # Assert: Extracted from .value
        assert result == "order_filled"

    async def test_extract_event_type_with_event_type_attribute(self, event_normalizer):
        """
        Test line 114: Extract event_type when sdk_event.event_type exists.

        This covers alternative SDK event structures.
        """
        # Create mock event with .event_type (not .type)
        mock_sdk_event = Mock()
        # Remove .type attribute, add .event_type
        del mock_sdk_event.type
        mock_sdk_event.event_type = "POSITION_UPDATED"

        # Execute
        result = event_normalizer._extract_event_type(mock_sdk_event)

        # Assert: Extracted from .event_type
        assert result == "position_updated"

    async def test_extract_event_type_returns_unknown(self, event_normalizer):
        """
        Test line 116: Returns 'unknown' when no type attribute found.

        This covers malformed or unrecognized SDK events.
        """
        # Create mock event with NO type attributes
        mock_sdk_event = Mock(spec=[])  # Empty spec = no attributes

        # Execute
        result = event_normalizer._extract_event_type(mock_sdk_event)

        # Assert: Returns "unknown"
        assert result == "unknown"

    # ===================================================================
    # Symbol Extraction Branch Coverage
    # ===================================================================

    async def test_extract_symbol_with_invalid_contract_id_returns_full_id(self, event_normalizer):
        """
        Test line 132: Fallback to full contract_id when parsing fails.

        This covers edge case where contract_id doesn't match expected format.
        """
        # Test various invalid formats
        invalid_formats = [
            "INVALID_FORMAT",  # No dots
            "CON.F.US",  # Not enough parts (< 4)
            "CON.F",  # Too short
            "SINGLE"  # Single word
        ]

        for contract_id in invalid_formats:
            result = event_normalizer._extract_symbol(contract_id)
            # Should return full contract_id as fallback
            assert result == contract_id

    async def test_extract_symbol_with_valid_contract_id(self, event_normalizer):
        """
        Test line 131: Extract symbol from valid contract_id (4+ parts).

        This ensures the happy path still works.
        """
        # Valid format: CON.F.US.MNQ.U25
        result = event_normalizer._extract_symbol("CON.F.US.MNQ.U25")
        assert result == "MNQ"

        # Edge case: exactly 4 parts
        result = event_normalizer._extract_symbol("A.B.C.ES")
        assert result == "ES"

        # Edge case: more than 4 parts
        result = event_normalizer._extract_symbol("A.B.C.NQ.E.F.G")
        assert result == "NQ"

    # ===================================================================
    # Quote Update Branch Coverage
    # ===================================================================

    async def test_handle_quote_update_without_symbol_returns_none(self, event_normalizer):
        """
        Test line 186: Quote update without symbol/contractId returns None.

        This covers edge case where quote data is missing symbol identification.
        """
        # Create SDK event with quote data but NO symbol/contractId
        mock_sdk_event = Mock()
        mock_sdk_event.data = {
            "bid": 18000.00,
            "ask": 18002.00,
            # No 'symbol' or 'contractId' field
        }

        # Execute
        result = await event_normalizer._handle_quote_update(mock_sdk_event)

        # Assert: Returns None (can't cache without symbol)
        assert result is None

    async def test_handle_quote_update_with_contract_id(self, event_normalizer):
        """
        Test line 181: Quote update extracts symbol from contractId.

        This covers the contractId branch of symbol extraction.
        """
        # Create SDK event with contractId instead of symbol
        mock_sdk_event = Mock()
        mock_sdk_event.data = {
            "contractId": "CON.F.US.MNQ.U25",
            "bid": 18000.00,
            "ask": 18002.00,
            "timestamp": "2025-10-16T10:00:00Z"
        }

        # Execute
        result = await event_normalizer._handle_quote_update(mock_sdk_event)

        # Assert: Processed successfully, returns None (no event)
        assert result is None

        # Verify price was cached
        cached_price = await event_normalizer.get_cached_price("MNQ")
        assert cached_price == Decimal("18001.00")  # Mid-price

    # ===================================================================
    # Position Closed Handler Branch Coverage
    # ===================================================================

    async def test_handle_position_closed_updates_state(self, event_normalizer, state_manager, account_id):
        """
        Test line 221: Position closed handler calls state_manager.close_position.

        This covers the state update path in position closure.
        """
        # Setup: Add position to state
        from src.state.state_manager import Position
        position_id = uuid4()
        position = Position(
            position_id=position_id,
            account_id=account_id,
            symbol="MNQ",
            side="BUY",
            quantity=1,
            entry_price=Decimal("18000.0"),
            current_price=Decimal("18100.0"),
            unrealized_pnl=Decimal("200.0"),
            opened_at=datetime.now(timezone.utc)
        )
        state_manager.add_position(account_id, position)

        # Create SDK POSITION_CLOSED event
        mock_sdk_event = Mock()
        mock_sdk_event.data = {
            "positionId": str(position_id),
            "accountId": account_id,
            "realizedPnl": 200.00
        }

        # Execute
        result = await event_normalizer._handle_position_closed(mock_sdk_event)

        # Assert: No event returned (state update only)
        assert result is None

        # Verify position was closed in state
        positions = state_manager.get_open_positions(account_id)
        assert len(positions) == 0

        # Verify realized PnL was tracked
        account_state = state_manager.get_account_state(account_id)
        assert account_state.realized_pnl_today == Decimal("200.00")

    # ===================================================================
    # Connection Event Data Handling Branch Coverage
    # ===================================================================

    async def test_normalize_connected_with_missing_data_attribute(self, event_normalizer):
        """
        Test line 236: Connected event handles missing .data attribute.

        This covers SDK events that don't have .data attribute.
        """
        # Create SDK event WITHOUT .data attribute
        mock_sdk_event = Mock(spec=[])  # No attributes

        # Execute
        result = await event_normalizer._normalize_connected(mock_sdk_event)

        # Assert: Uses default account_id = 'system'
        assert result is not None
        assert result["account_id"] == "system"
        assert result["event_type"] == "CONNECTION_CHANGE"
        assert result["data"]["status"] == "connected"

    async def test_normalize_disconnected_with_missing_reason(self, event_normalizer, account_id):
        """
        Test line 276: Disconnected event with missing reason field.

        This covers the .get('reason') fallback when reason is absent.
        """
        # Create SDK event with data but no reason
        mock_sdk_event = Mock()
        mock_sdk_event.data = {
            "accountId": account_id
            # No 'reason' field
        }

        # Execute
        result = await event_normalizer._normalize_disconnected(mock_sdk_event)

        # Assert: reason is None
        assert result["data"]["reason"] is None
        assert result["data"]["status"] == "disconnected"

    async def test_normalize_reconnecting_with_missing_attempt(self, event_normalizer):
        """
        Test line 294: Reconnecting event with missing attempt field.

        This covers default attempt=0 when field is missing.
        """
        # Create SDK event without attempt field
        mock_sdk_event = Mock()
        mock_sdk_event.data = {
            "accountId": "test_account"
            # No 'attempt' field
        }

        # Execute
        result = await event_normalizer._normalize_reconnecting(mock_sdk_event)

        # Assert: Default attempt = 0
        assert result["data"]["attempt"] == 0
        assert result["data"]["status"] == "reconnecting"

    # ===================================================================
    # SDK Event Handler Methods Branch Coverage
    # ===================================================================

    async def test_on_order_filled_emits_event(self, event_normalizer, event_bus, account_id):
        """
        Test line 447: on_order_filled calls normalize and emits to bus.

        This covers the SDK handler wrapper that emits normalized events.
        """
        # Create valid SDK ORDER_FILLED event
        mock_sdk_event = Mock()
        mock_sdk_event.type = "ORDER_FILLED"
        mock_sdk_event.data = {
            "orderId": "order_123",
            "contractId": "CON.F.US.MNQ.U25",
            "side": "buy",
            "quantity": 1,
            "fillPrice": 18000.0,
            "accountId": account_id
        }
        mock_sdk_event.timestamp = datetime.now(timezone.utc)

        # Execute
        await event_normalizer.on_order_filled(mock_sdk_event)

        # Assert: Event bus emit was called
        event_bus.emit.assert_called_once()
        call_args = event_bus.emit.call_args
        assert call_args[0][0] == "FILL"  # event_type

    async def test_on_position_updated_emits_event(self, event_normalizer, event_bus, account_id):
        """
        Test line 458: on_position_updated calls normalize and emits to bus.
        """
        # Create valid SDK POSITION_UPDATED event
        mock_sdk_event = Mock()
        mock_sdk_event.type = "POSITION_UPDATED"
        mock_sdk_event.data = {
            "positionId": str(uuid4()),
            "contractId": "CON.F.US.MNQ.U25",
            "currentPrice": 18100.0,
            "unrealizedPnl": 200.0,
            "accountId": account_id
        }
        mock_sdk_event.timestamp = datetime.now(timezone.utc)

        # Execute
        await event_normalizer.on_position_updated(mock_sdk_event)

        # Assert: Event bus emit was called
        event_bus.emit.assert_called_once()
        call_args = event_bus.emit.call_args
        assert call_args[0][0] == "POSITION_UPDATE"

    async def test_on_connection_lost_emits_event(self, event_normalizer, event_bus, account_id):
        """
        Test line 468: on_connection_lost calls normalize and emits to bus.
        """
        # Create SDK CONNECTION_LOST event (maps to DISCONNECTED)
        mock_sdk_event = Mock()
        mock_sdk_event.type = "DISCONNECTED"
        mock_sdk_event.data = {
            "status": "disconnected",
            "reason": "Network timeout",
            "accountId": account_id
        }

        # Execute
        await event_normalizer.on_connection_lost(mock_sdk_event)

        # Assert: Event bus emit was called
        event_bus.emit.assert_called_once()
        call_args = event_bus.emit.call_args
        assert call_args[0][0] == "CONNECTION_CHANGE"

    async def test_on_quote_update_no_event_emitted(self, event_normalizer, event_bus):
        """
        Test line 479: on_quote_update processes but doesn't emit event.

        Quote updates only cache prices, don't generate internal events.
        """
        # Create SDK QUOTE_UPDATE event
        mock_sdk_event = Mock()
        mock_sdk_event.type = "QUOTE_UPDATE"
        mock_sdk_event.data = {
            "symbol": "MNQ",
            "bid": 18000.0,
            "ask": 18002.0,
            "timestamp": "2025-10-16T10:00:00Z"
        }

        # Execute
        await event_normalizer.on_quote_update(mock_sdk_event)

        # Assert: Event bus NOT called (quote updates are silent)
        event_bus.emit.assert_not_called()

    async def test_on_order_rejected_no_event_emitted(self, event_normalizer, event_bus, account_id):
        """
        Test line 489: on_order_rejected logs but doesn't emit event.

        Order rejections are logged, not propagated as risk events.
        """
        # Create SDK ORDER_REJECTED event
        mock_sdk_event = Mock()
        mock_sdk_event.type = "ORDER_REJECTED"
        mock_sdk_event.data = {
            "orderId": "order_999",
            "reason": "Insufficient margin",
            "contractId": "CON.F.US.MNQ.U25",
            "accountId": account_id
        }

        # Execute with logger mock
        with patch('src.adapters.event_normalizer.logger') as mock_logger:
            await event_normalizer.on_order_rejected(mock_sdk_event)

            # Assert: Logged error
            mock_logger.error.assert_called_once()

        # Assert: Event bus NOT called
        event_bus.emit.assert_not_called()

    async def test_on_order_placed_no_event_emitted(self, event_normalizer, event_bus, account_id):
        """
        Test line 499: on_order_placed tracks but doesn't emit event.

        Order placements are tracked for audit, not risk events.
        """
        # Create SDK ORDER_PLACED event
        mock_sdk_event = Mock()
        mock_sdk_event.type = "ORDER_PLACED"
        mock_sdk_event.data = {
            "orderId": "order_abc",
            "contractId": "CON.F.US.MNQ.U25",
            "accountId": account_id
        }

        # Execute
        await event_normalizer.on_order_placed(mock_sdk_event)

        # Assert: Event bus NOT called (order tracking is silent)
        event_bus.emit.assert_not_called()

    # ===================================================================
    # Additional Edge Cases
    # ===================================================================

    async def test_normalize_with_unknown_event_type_returns_none(self, event_normalizer):
        """
        Test line 87: normalize returns None for unknown event types.

        This ensures unknown SDK events are gracefully ignored.
        """
        # Create SDK event with unknown type
        mock_sdk_event = Mock()
        mock_sdk_event.type = "COMPLETELY_UNKNOWN_EVENT"
        mock_sdk_event.data = {"foo": "bar"}

        # Execute
        result = await event_normalizer.normalize(mock_sdk_event)

        # Assert: Returns None (no crash)
        assert result is None

    async def test_normalize_connected_includes_broker_field(self, event_normalizer, account_id):
        """
        Test line 249: Connected event includes broker='topstepx'.

        Ensures broker field is populated in connection events.
        """
        # Create CONNECTED event
        mock_sdk_event = Mock()
        mock_sdk_event.data = {"accountId": account_id}

        # Execute
        result = await event_normalizer._normalize_connected(mock_sdk_event)

        # Assert: Broker field present
        assert result["data"]["broker"] == "topstepx"
        assert result["data"]["status"] == "connected"

    async def test_normalize_reconnecting_includes_attempt_in_reason(self, event_normalizer, account_id):
        """
        Test line 305: Reconnecting event formats reason with attempt number.

        Ensures reason field includes reconnection attempt count.
        """
        # Create RECONNECTING event with attempt
        mock_sdk_event = Mock()
        mock_sdk_event.data = {
            "accountId": account_id,
            "attempt": 3
        }

        # Execute
        result = await event_normalizer._normalize_reconnecting(mock_sdk_event)

        # Assert: Reason includes attempt
        assert "reconnection_attempt_3" in result["data"]["reason"]
        assert result["data"]["attempt"] == 3
