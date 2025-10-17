"""
Unit tests for StateManager edge cases to improve coverage from 60% to 80%+.

Target missing lines from coverage report:
- Lines 101-110: update_position_price with position not found
- Lines 126-131: close_position
- Line 139: get_realized_pnl
- Lines 143-144: get_total_unrealized_pnl with empty positions
- Lines 158-160: get_combined_exposure
- Lines 193-196: start_cooldown
- Lines 200-204: is_in_cooldown edge cases
- Lines 208-209: get_position_count
- Lines 213-214: get_position_count_by_symbol
- Lines 227-232: daily_reset
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import Mock

from src.state.state_manager import StateManager, Position, AccountState


@pytest.mark.unit
class TestStateManagerEdgeCases:
    """Edge case tests to achieve 80%+ coverage of StateManager."""

    @pytest.fixture
    def state_manager(self):
        """Create state manager with mock clock."""
        mock_clock = Mock()
        mock_clock.now = Mock(return_value=datetime(2025, 10, 16, 12, 0, 0))
        return StateManager(clock=mock_clock)

    @pytest.fixture
    def account_id(self):
        """Standard test account ID."""
        return "test_account"

    def test_update_position_price_position_not_found(self, state_manager, account_id):
        """
        Test line 103 branch: update_position_price when position_id doesn't exist.

        Should complete without error (no position to update).
        """
        state_manager.get_account_state(account_id)
        non_existent_position_id = uuid4()

        # Should not raise exception
        state_manager.update_position_price(
            account_id=account_id,
            position_id=non_existent_position_id,
            current_price=Decimal("5000.0")
        )

        # No positions should exist
        positions = state_manager.get_open_positions(account_id)
        assert len(positions) == 0

    def test_update_position_price_long_position(self, state_manager, account_id):
        """
        Test lines 106-107: PnL calculation for long position.

        Long profit = (current_price - entry_price) * quantity * tick_value
        """
        position_id = uuid4()
        position = Position(
            position_id=position_id,
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500.0"),
            current_price=Decimal("4500.0"),
            unrealized_pnl=Decimal("0.0"),
            opened_at=datetime.utcnow()
        )
        state_manager.add_position(account_id, position)

        # Update price to +10 points
        state_manager.update_position_price(
            account_id=account_id,
            position_id=position_id,
            current_price=Decimal("4510.0")
        )

        # Check PnL calculation: (4510 - 4500) * 1 * 2.0 = 20.0
        positions = state_manager.get_open_positions(account_id)
        assert positions[0].unrealized_pnl == Decimal("20.0")

    def test_update_position_price_short_position(self, state_manager, account_id):
        """
        Test lines 108-109: PnL calculation for short position.

        Short profit = (entry_price - current_price) * quantity * tick_value
        """
        position_id = uuid4()
        position = Position(
            position_id=position_id,
            account_id=account_id,
            symbol="ES",
            side="short",
            quantity=1,
            entry_price=Decimal("4500.0"),
            current_price=Decimal("4500.0"),
            unrealized_pnl=Decimal("0.0"),
            opened_at=datetime.utcnow()
        )
        state_manager.add_position(account_id, position)

        # Update price to -10 points (profit for short)
        state_manager.update_position_price(
            account_id=account_id,
            position_id=position_id,
            current_price=Decimal("4490.0")
        )

        # Check PnL calculation: (4500 - 4490) * 1 * 2.0 = 20.0
        positions = state_manager.get_open_positions(account_id)
        assert positions[0].unrealized_pnl == Decimal("20.0")

    def test_close_position_removes_from_open_positions(self, state_manager, account_id):
        """
        Test lines 126-131: close_position removes position and updates realized PnL.
        """
        position_id = uuid4()
        position = Position(
            position_id=position_id,
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500.0"),
            current_price=Decimal("4510.0"),
            unrealized_pnl=Decimal("20.0"),
            opened_at=datetime.utcnow()
        )
        state_manager.add_position(account_id, position)

        # Close with realized PnL
        state_manager.close_position(
            account_id=account_id,
            position_id=position_id,
            realized_pnl=Decimal("20.0")
        )

        # Position should be removed
        positions = state_manager.get_open_positions(account_id)
        assert len(positions) == 0

        # Realized PnL should be updated
        realized = state_manager.get_realized_pnl(account_id)
        assert realized == Decimal("20.0")

    def test_get_realized_pnl_for_new_account(self, state_manager):
        """
        Test line 139: get_realized_pnl for account with no realized PnL.
        """
        account_id = "new_account"
        realized = state_manager.get_realized_pnl(account_id)
        assert realized == Decimal("0.0")

    def test_get_total_unrealized_pnl_with_empty_positions(self, state_manager, account_id):
        """
        Test lines 143-144: get_total_unrealized_pnl with no positions.

        Should return Decimal("0.0") not raise exception.
        """
        state_manager.get_account_state(account_id)
        unrealized = state_manager.get_total_unrealized_pnl(account_id)
        assert unrealized == Decimal("0.0")

    def test_get_total_unrealized_pnl_with_multiple_positions(self, state_manager, account_id):
        """
        Test lines 143-144: Sum unrealized PnL across multiple positions.
        """
        # Add two positions with different PnL
        pos1 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500.0"),
            current_price=Decimal("4510.0"),
            unrealized_pnl=Decimal("20.0"),
            opened_at=datetime.utcnow()
        )
        pos2 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="NQ",
            side="long",
            quantity=2,
            entry_price=Decimal("15000.0"),
            current_price=Decimal("15005.0"),
            unrealized_pnl=Decimal("20.0"),
            opened_at=datetime.utcnow()
        )
        state_manager.add_position(account_id, pos1)
        state_manager.add_position(account_id, pos2)

        # Total should be sum
        unrealized = state_manager.get_total_unrealized_pnl(account_id)
        assert unrealized == Decimal("40.0")

    def test_get_combined_exposure(self, state_manager, account_id):
        """
        Test lines 158-160: get_combined_exposure = realized + unrealized.
        """
        # Add position with unrealized PnL
        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500.0"),
            current_price=Decimal("4510.0"),
            unrealized_pnl=Decimal("20.0"),
            opened_at=datetime.utcnow()
        )
        state_manager.add_position(account_id, position)

        # Close another position to add realized PnL
        closed_pos_id = uuid4()
        closed_pos = Position(
            position_id=closed_pos_id,
            account_id=account_id,
            symbol="NQ",
            side="long",
            quantity=1,
            entry_price=Decimal("15000.0"),
            current_price=Decimal("15010.0"),
            unrealized_pnl=Decimal("0.0"),
            opened_at=datetime.utcnow()
        )
        state_manager.add_position(account_id, closed_pos)
        state_manager.close_position(account_id, closed_pos_id, Decimal("30.0"))

        # Combined should be 20 (unrealized) + 30 (realized) = 50
        combined = state_manager.get_combined_exposure(account_id)
        assert combined == Decimal("50.0")

    def test_is_locked_out_when_lockout_is_none(self, state_manager, account_id):
        """
        Test line 186: is_locked_out returns False when lockout_until is None.
        """
        state_manager.get_account_state(account_id)
        assert not state_manager.is_locked_out(account_id)

    def test_is_locked_out_when_lockout_expired(self, state_manager, account_id):
        """
        Test line 188: is_locked_out returns False when lockout_until is in past.
        """
        # Set lockout to 1 hour ago
        past_time = state_manager.clock.now() - timedelta(hours=1)
        state_manager.set_lockout(account_id, past_time, "Test lockout")

        assert not state_manager.is_locked_out(account_id)

    def test_is_locked_out_when_lockout_active(self, state_manager, account_id):
        """
        Test line 188: is_locked_out returns True when lockout_until is in future.
        """
        # Set lockout to 1 hour from now
        future_time = state_manager.clock.now() + timedelta(hours=1)
        state_manager.set_lockout(account_id, future_time, "Test lockout")

        assert state_manager.is_locked_out(account_id)

    def test_start_cooldown(self, state_manager, account_id):
        """
        Test lines 193-196: start_cooldown sets cooldown_until correctly.
        """
        state_manager.start_cooldown(account_id, 300, "Test cooldown")

        state = state_manager.get_account_state(account_id)
        expected_time = state_manager.clock.now() + timedelta(seconds=300)
        assert state.cooldown_until == expected_time

    def test_is_in_cooldown_when_cooldown_is_none(self, state_manager, account_id):
        """
        Test line 201: is_in_cooldown returns False when cooldown_until is None.
        """
        state_manager.get_account_state(account_id)
        assert not state_manager.is_in_cooldown(account_id)

    def test_is_in_cooldown_when_cooldown_expired(self, state_manager, account_id):
        """
        Test line 203: is_in_cooldown returns False when cooldown_until is in past.
        """
        # Manually set expired cooldown
        state = state_manager.get_account_state(account_id)
        state.cooldown_until = state_manager.clock.now() - timedelta(seconds=1)

        assert not state_manager.is_in_cooldown(account_id)

    def test_is_in_cooldown_when_cooldown_active(self, state_manager, account_id):
        """
        Test line 203: is_in_cooldown returns True when cooldown_until is in future.
        """
        state_manager.start_cooldown(account_id, 300, "Test")
        assert state_manager.is_in_cooldown(account_id)

    def test_get_position_count_with_empty_positions(self, state_manager, account_id):
        """
        Test lines 208-209: get_position_count returns 0 for empty positions.
        """
        state_manager.get_account_state(account_id)
        count = state_manager.get_position_count(account_id)
        assert count == 0

    def test_get_position_count_with_multiple_positions(self, state_manager, account_id):
        """
        Test lines 208-209: get_position_count sums quantities across positions.
        """
        pos1 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=2,
            entry_price=Decimal("4500.0"),
            current_price=Decimal("4500.0"),
            unrealized_pnl=Decimal("0.0"),
            opened_at=datetime.utcnow()
        )
        pos2 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="NQ",
            side="long",
            quantity=3,
            entry_price=Decimal("15000.0"),
            current_price=Decimal("15000.0"),
            unrealized_pnl=Decimal("0.0"),
            opened_at=datetime.utcnow()
        )
        state_manager.add_position(account_id, pos1)
        state_manager.add_position(account_id, pos2)

        count = state_manager.get_position_count(account_id)
        assert count == 5  # 2 + 3

    def test_get_position_count_by_symbol_with_no_matching_positions(self, state_manager, account_id):
        """
        Test lines 213-214: get_position_count_by_symbol returns 0 for unknown symbol.
        """
        pos = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=2,
            entry_price=Decimal("4500.0"),
            current_price=Decimal("4500.0"),
            unrealized_pnl=Decimal("0.0"),
            opened_at=datetime.utcnow()
        )
        state_manager.add_position(account_id, pos)

        count = state_manager.get_position_count_by_symbol(account_id, "NQ")
        assert count == 0

    def test_get_position_count_by_symbol_with_matching_positions(self, state_manager, account_id):
        """
        Test lines 213-214: get_position_count_by_symbol sums for specific symbol.
        """
        pos1 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=2,
            entry_price=Decimal("4500.0"),
            current_price=Decimal("4500.0"),
            unrealized_pnl=Decimal("0.0"),
            opened_at=datetime.utcnow()
        )
        pos2 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=3,
            entry_price=Decimal("4510.0"),
            current_price=Decimal("4510.0"),
            unrealized_pnl=Decimal("0.0"),
            opened_at=datetime.utcnow()
        )
        pos3 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="NQ",
            side="long",
            quantity=1,
            entry_price=Decimal("15000.0"),
            current_price=Decimal("15000.0"),
            unrealized_pnl=Decimal("0.0"),
            opened_at=datetime.utcnow()
        )
        state_manager.add_position(account_id, pos1)
        state_manager.add_position(account_id, pos2)
        state_manager.add_position(account_id, pos3)

        es_count = state_manager.get_position_count_by_symbol(account_id, "ES")
        nq_count = state_manager.get_position_count_by_symbol(account_id, "NQ")

        assert es_count == 5  # 2 + 3
        assert nq_count == 1

    def test_daily_reset_clears_realized_pnl(self, state_manager, account_id):
        """
        Test lines 227-232: daily_reset clears realized PnL.
        """
        # Set some realized PnL
        pos_id = uuid4()
        pos = Position(
            position_id=pos_id,
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500.0"),
            current_price=Decimal("4500.0"),
            unrealized_pnl=Decimal("0.0"),
            opened_at=datetime.utcnow()
        )
        state_manager.add_position(account_id, pos)
        state_manager.close_position(account_id, pos_id, Decimal("100.0"))

        # Perform reset
        state_manager.daily_reset(account_id)

        # Realized PnL should be cleared
        realized = state_manager.get_realized_pnl(account_id)
        assert realized == Decimal("0.0")

    def test_daily_reset_clears_lockout(self, state_manager, account_id):
        """
        Test lines 227-232: daily_reset clears lockout.
        """
        # Set lockout
        future_time = state_manager.clock.now() + timedelta(hours=1)
        state_manager.set_lockout(account_id, future_time, "Test lockout")

        # Perform reset
        state_manager.daily_reset(account_id)

        # Lockout should be cleared
        assert not state_manager.is_locked_out(account_id)

        state = state_manager.get_account_state(account_id)
        assert state.lockout_until is None
        assert state.lockout_reason is None

    def test_daily_reset_sets_last_daily_reset_timestamp(self, state_manager, account_id):
        """
        Test lines 227-232: daily_reset sets last_daily_reset timestamp.
        """
        state = state_manager.get_account_state(account_id)
        assert state.last_daily_reset is None

        # Perform reset
        state_manager.daily_reset(account_id)

        # Timestamp should be set
        assert state.last_daily_reset == state_manager.clock.now()

    def test_daily_reset_preserves_open_positions(self, state_manager, account_id):
        """
        Test lines 227-232: daily_reset does NOT close open positions.
        """
        pos = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500.0"),
            current_price=Decimal("4510.0"),
            unrealized_pnl=Decimal("20.0"),
            opened_at=datetime.utcnow()
        )
        state_manager.add_position(account_id, pos)

        # Perform reset
        state_manager.daily_reset(account_id)

        # Position should still exist
        positions = state_manager.get_open_positions(account_id)
        assert len(positions) == 1
        assert positions[0].unrealized_pnl == Decimal("20.0")
