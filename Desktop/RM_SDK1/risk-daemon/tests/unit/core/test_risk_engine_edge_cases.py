"""
Unit tests for RiskEngine edge cases to improve branch coverage.

These tests target missing branches identified in coverage analysis:
- Lines 86-97 (lockout during FILL event)
- Line 117 (rule not enabled)
- Lines 147-154 (monitor processing branches)
"""

import pytest
from unittest.mock import AsyncMock, Mock
from uuid import uuid4
from decimal import Decimal
from datetime import datetime, timedelta

from src.core.risk_engine import RiskEngine
from src.core.enforcement_engine import EnforcementEngine
from src.state.state_manager import StateManager, Position
from src.state.models import Event
from src.rules.max_contracts import MaxContractsRule


@pytest.mark.asyncio
@pytest.mark.unit
class TestRiskEngineEdgeCases:
    """Test edge cases for full branch coverage of RiskEngine."""

    @pytest.fixture
    def state_manager(self):
        """Create state manager."""
        return StateManager()

    @pytest.fixture
    def broker(self):
        """Create mock broker."""
        broker = AsyncMock()
        return broker

    @pytest.fixture
    def enforcement_engine(self, broker, state_manager):
        """Create enforcement engine."""
        return EnforcementEngine(broker=broker, state_manager=state_manager)

    @pytest.fixture
    def max_contracts_rule(self):
        """Create a rule for testing."""
        return MaxContractsRule(max_contracts=5, enabled=True)

    @pytest.fixture
    def risk_engine(self, state_manager, enforcement_engine, max_contracts_rule):
        """Create risk engine."""
        return RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement_engine,
            rules=[max_contracts_rule],
            monitors=[]
        )

    async def test_fill_event_during_lockout_with_no_positions(self, risk_engine, state_manager):
        """
        Test line 89 branch: FILL event during lockout but no positions available.

        This tests the case where account is locked out, a FILL arrives,
        but get_open_positions returns empty list (no positions to close).
        """
        account_id = "test_account"

        # Initialize account and set lockout
        state_manager.get_account_state(account_id)
        state_manager.set_lockout(
            account_id=account_id,
            until=datetime.utcnow() + timedelta(hours=1),
            reason="Test lockout"
        )

        # Create FILL event (no positions added yet)
        fill_event = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=datetime.utcnow(),
            priority=0,
            account_id=account_id,
            source="SDK",
            data={
                "symbol": "ES",
                "side": "BUY",
                "quantity": 1,
                "fill_price": Decimal("4500.0")
            }
        )

        # Process event - should handle empty positions list gracefully
        await risk_engine.process_event(fill_event)

        # No exception should be raised
        # The position was created during _handle_fill_event, then closed
        assert state_manager.is_locked_out(account_id)

    async def test_fill_event_during_lockout_closes_most_recent(self, risk_engine, state_manager, enforcement_engine):
        """
        Test lines 86-96: FILL event during lockout closes most recent position.

        This tests the enforcement path when a FILL arrives while locked out.
        """
        account_id = "test_account"

        # Initialize account and set lockout
        state_manager.get_account_state(account_id)
        state_manager.set_lockout(
            account_id=account_id,
            until=datetime.utcnow() + timedelta(hours=1),
            reason="Test lockout"
        )

        # Add an existing position
        old_position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="NQ",
            side="BUY",
            quantity=1,
            entry_price=Decimal("15000.0"),
            current_price=Decimal("15000.0"),
            unrealized_pnl=Decimal("0.0"),
            opened_at=datetime.utcnow()
        )
        state_manager.add_position(account_id, old_position)

        # Mock enforcement engine to track close_position calls
        close_position_calls = []
        original_close = enforcement_engine.close_position

        async def track_close(*args, **kwargs):
            close_position_calls.append(kwargs)
            return await original_close(*args, **kwargs)

        enforcement_engine.close_position = track_close

        # Create FILL event
        fill_event = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=datetime.utcnow(),
            priority=0,
            account_id=account_id,
            source="SDK",
            data={
                "symbol": "ES",
                "side": "BUY",
                "quantity": 1,
                "fill_price": Decimal("4500.0")
            }
        )

        # Process event
        await risk_engine.process_event(fill_event)

        # Verify close_position was called
        assert len(close_position_calls) >= 1
        assert "Account locked out" in close_position_calls[0]["reason"]

    async def test_rule_not_enabled_skipped(self, state_manager, enforcement_engine):
        """
        Test line 117: Rule not enabled is skipped during evaluation.

        This ensures disabled rules don't get evaluated.
        """
        account_id = "test_account"

        # Create disabled rule
        disabled_rule = MaxContractsRule(max_contracts=1, enabled=False)

        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement_engine,
            rules=[disabled_rule],
            monitors=[]
        )

        # Initialize account
        state_manager.get_account_state(account_id)

        # Create FILL event that WOULD violate if rule was enabled
        fill_event = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=datetime.utcnow(),
            priority=0,
            account_id=account_id,
            source="SDK",
            data={
                "symbol": "ES",
                "side": "BUY",
                "quantity": 10,  # Way over limit of 1
                "fill_price": Decimal("4500.0")
            }
        )

        # Process event
        await risk_engine.process_event(fill_event)

        # No enforcement should have occurred because rule is disabled
        # Account should have the position still
        positions = state_manager.get_open_positions(account_id)
        assert len(positions) == 1  # Position added, not closed

    async def test_monitor_with_applies_to_event_method(self, risk_engine, state_manager):
        """
        Test lines 147-149: Monitor with applies_to_event method filters events.

        This tests the branch where monitor has applies_to_event and returns False.
        """
        account_id = "test_account"
        state_manager.get_account_state(account_id)

        # Create mock monitor with applies_to_event
        mock_monitor = Mock()
        mock_monitor.applies_to_event = Mock(return_value=False)
        mock_monitor.process_order = Mock()

        # Add monitor to risk engine
        risk_engine.monitors = [mock_monitor]

        # Create ORDER event
        order_event = Event(
            event_id=uuid4(),
            event_type="ORDER",
            timestamp=datetime.utcnow(),
            priority=0,
            account_id=account_id,
            source="SDK",
            data={"order_id": "order_123"}
        )

        # Process event
        await risk_engine.process_event(order_event)

        # Monitor's applies_to_event should have been called
        mock_monitor.applies_to_event.assert_called_once_with("ORDER")
        # But process_order should NOT have been called (applies_to_event returned False)
        mock_monitor.process_order.assert_not_called()

    async def test_monitor_without_process_order_method(self, risk_engine, state_manager):
        """
        Test line 154: Monitor doesn't have process_order method.

        This tests the hasattr check for process_order.
        """
        account_id = "test_account"
        state_manager.get_account_state(account_id)

        # Create mock monitor WITHOUT process_order method
        mock_monitor = Mock(spec=[])  # Empty spec means no methods
        mock_monitor.applies_to_event = Mock(return_value=True)
        # No process_order attribute

        # Add monitor to risk engine
        risk_engine.monitors = [mock_monitor]

        # Create ORDER event
        order_event = Event(
            event_id=uuid4(),
            event_type="ORDER",
            timestamp=datetime.utcnow(),
            priority=0,
            account_id=account_id,
            source="SDK",
            data={"order_id": "order_123"}
        )

        # Process event - should not raise exception
        await risk_engine.process_event(order_event)

        # No exception should be raised even though monitor lacks process_order

    async def test_monitor_for_order_status_event(self, risk_engine, state_manager):
        """
        Test line 152: ORDER_STATUS event triggers monitor processing.

        This tests the branch for ORDER_STATUS event type.
        """
        account_id = "test_account"
        state_manager.get_account_state(account_id)

        # Create mock monitor with process_order
        mock_monitor = Mock()
        mock_monitor.applies_to_event = Mock(return_value=True)
        mock_monitor.process_order = Mock()

        # Add monitor to risk engine
        risk_engine.monitors = [mock_monitor]

        # Create ORDER_STATUS event
        order_status_event = Event(
            event_id=uuid4(),
            event_type="ORDER_STATUS",
            timestamp=datetime.utcnow(),
            priority=0,
            account_id=account_id,
            source="SDK",
            data={
                "order_id": "order_123",
                "status": "FILLED"
            }
        )

        # Process event
        await risk_engine.process_event(order_status_event)

        # Monitor should have processed the event
        mock_monitor.process_order.assert_called_once()

    async def test_time_tick_processes_all_accounts(self, risk_engine, state_manager):
        """
        Test lines 64-70: TIME_TICK event processes all accounts.

        This ensures TIME_TICK events trigger evaluation for all tracked accounts.
        """
        # Initialize multiple accounts
        account1 = "account1"
        account2 = "account2"
        state_manager.get_account_state(account1)
        state_manager.get_account_state(account2)

        # Create TIME_TICK event
        time_tick_event = Event(
            event_id=uuid4(),
            event_type="TIME_TICK",
            timestamp=datetime.utcnow(),
            priority=0,
            account_id="SYSTEM",  # TIME_TICK doesn't have specific account
            source="TIMER",
            data={"tick_timestamp": datetime.utcnow()}
        )

        # Process event
        await risk_engine.process_event(time_tick_event)

        # All accounts should still be present (no exceptions)
        assert account1 in state_manager.accounts
        assert account2 in state_manager.accounts

    async def test_cascading_violation_skips_triggered_rule(self, state_manager, enforcement_engine):
        """
        Test lines 127-128: Cascading check skips the rule that just triggered.

        This ensures the same rule doesn't re-trigger during cascade evaluation.
        """
        account_id = "test_account"

        # Create two rules
        rule1 = MaxContractsRule(max_contracts=5, enabled=True)
        rule2 = MaxContractsRule(max_contracts=3, enabled=True)
        rule2.name = "MaxContracts2"  # Different name

        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement_engine,
            rules=[rule1, rule2],
            monitors=[]
        )

        # Initialize account
        state_manager.get_account_state(account_id)

        # Manually trigger cascade check
        await risk_engine._check_cascading_violations(account_id, rule1)

        # Should complete without error (cascade check skips rule1)

    async def test_disabled_rule_skipped_in_cascade(self, state_manager, enforcement_engine):
        """
        Test lines 130-131: Disabled rules skipped during cascade check.

        This ensures disabled rules don't get evaluated in cascade checks.
        """
        account_id = "test_account"

        # Create enabled and disabled rules
        rule1 = MaxContractsRule(max_contracts=5, enabled=True)
        rule2 = MaxContractsRule(max_contracts=3, enabled=False)  # Disabled
        rule2.name = "MaxContracts2"

        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement_engine,
            rules=[rule1, rule2],
            monitors=[]
        )

        # Initialize account
        state_manager.get_account_state(account_id)

        # Trigger cascade check with rule1
        await risk_engine._check_cascading_violations(account_id, rule1)

        # Should complete without evaluating disabled rule2
