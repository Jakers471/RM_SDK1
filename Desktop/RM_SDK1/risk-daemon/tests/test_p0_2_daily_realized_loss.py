"""
P0-2: DailyRealizedLoss with Combined PnL Tests

Tests the DailyRealizedLoss rule with CRITICAL combined PnL monitoring.
This is the most important rule - prevents account blow-ups.

Architecture reference: docs/architecture/02-risk-engine.md (Rule 3: DailyRealizedLoss)
Key concept: Combined Exposure = Realized PnL + Unrealized PnL
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import timedelta


# ============================================================================
# UNIT TESTS: DailyRealizedLoss Rule Logic
# ============================================================================


@pytest.mark.unit
@pytest.mark.p0
class TestDailyRealizedLossRuleUnit:
    """Unit tests for DailyRealizedLoss rule with combined PnL logic."""

    def test_rule_config_defaults(self):
        """Test: DailyRealizedLoss rule has proper configuration."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.daily_realized_loss import DailyRealizedLossRule

        rule = DailyRealizedLossRule(limit=Decimal("-1000.00"))
        assert rule.enabled is True
        assert rule.limit == Decimal("-1000.00")
        assert rule.name == "DailyRealizedLoss"

    def test_realized_only_within_limit(self, state_manager, account_id):
        """Test: No violation when realized loss within limit (no open positions)."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.daily_realized_loss import DailyRealizedLossRule

        # Setup: realized loss = -$800, limit = -$1000
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-800.00")

        rule = DailyRealizedLossRule(limit=Decimal("-1000.00"))
        account_state = state_manager.get_account_state(account_id)

        violation = rule.evaluate({}, account_state)
        assert violation is None  # No violation

    def test_realized_only_exceeds_limit(self, state_manager, account_id):
        """Test: Violation when realized loss exceeds limit."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.daily_realized_loss import DailyRealizedLossRule

        # Setup: realized loss = -$1050, limit = -$1000
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-1050.00")

        rule = DailyRealizedLossRule(limit=Decimal("-1000.00"))
        account_state = state_manager.get_account_state(account_id)

        violation = rule.evaluate({}, account_state)
        assert violation is not None
        assert violation.rule_name == "DailyRealizedLoss"
        assert violation.severity == "critical"

    def test_combined_pnl_within_limit(self, state_manager, account_id, sample_position):
        """
        Test: CRITICAL - Combined PnL within limit.

        Scenario:
        - Realized: -$900
        - Unrealized: -$50
        - Combined: -$950
        - Limit: -$1000
        - Expected: No violation
        """
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.daily_realized_loss import DailyRealizedLossRule
        from tests.conftest import Position

        # Setup realized loss
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-900.00")

        # Setup open position with unrealized loss
        pos = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=1,
            entry_price=Decimal("18000.00"),
            current_price=Decimal("17975.00"),  # Down $25 per point
            unrealized_pnl=Decimal("-50.00"),  # -$25 * 2 (tick value) = -$50
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos)

        rule = DailyRealizedLossRule(limit=Decimal("-1000.00"))
        account_state = state_manager.get_account_state(account_id)

        violation = rule.evaluate({}, account_state)
        assert violation is None  # Combined = -$950, within limit

    def test_combined_pnl_exceeds_limit(self, state_manager, account_id):
        """
        Test: CRITICAL - Combined PnL exceeds limit triggers violation.

        Scenario:
        - Realized: -$800
        - Unrealized: -$250
        - Combined: -$1050
        - Limit: -$1000
        - Expected: VIOLATION (flatten all + lockout)
        """
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.daily_realized_loss import DailyRealizedLossRule
        from tests.conftest import Position

        # Setup realized loss
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-800.00")

        # Setup open position with large unrealized loss
        pos = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=1,
            entry_price=Decimal("18000.00"),
            current_price=Decimal("17875.00"),  # Down $125 per point
            unrealized_pnl=Decimal("-250.00"),  # -$125 * 2 = -$250
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos)

        rule = DailyRealizedLossRule(limit=Decimal("-1000.00"))
        account_state = state_manager.get_account_state(account_id)

        violation = rule.evaluate({}, account_state)
        assert violation is not None
        assert violation.rule_name == "DailyRealizedLoss"
        assert violation.severity == "critical"
        assert "-1050" in violation.reason  # Shows combined amount

    def test_enforcement_action_flatten_and_lockout(self, state_manager, account_id, clock):
        """Test: Enforcement action is flatten all + lockout until 5pm CT."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.daily_realized_loss import DailyRealizedLossRule
        import pytz

        # Setup violation
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-1100.00")

        rule = DailyRealizedLossRule(limit=Decimal("-1000.00"))
        account_state = state_manager.get_account_state(account_id)

        violation = rule.evaluate({}, account_state)
        action = rule.get_enforcement_action(violation)

        # Should flatten all
        assert action.action_type == "flatten_account"
        assert action.account_id == account_id

        # Should set lockout until 5pm CT
        chicago_tz = pytz.timezone("America/Chicago")
        current_ct = clock.get_chicago_time()
        expected_lockout = current_ct.replace(hour=17, minute=0, second=0, microsecond=0)

        # If already past 5pm, lockout until next day 5pm
        if current_ct.hour >= 17:
            expected_lockout += timedelta(days=1)

        assert action.lockout_until is not None
        assert action.lockout_until.hour == 17  # 5pm

    def test_rule_applies_to_position_update_events(self):
        """Test: Rule evaluates on position updates (price changes)."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.daily_realized_loss import DailyRealizedLossRule

        rule = DailyRealizedLossRule(limit=Decimal("-1000.00"))

        assert rule.applies_to_event("POSITION_UPDATE") is True
        assert rule.applies_to_event("FILL") is True  # Also check on fills
        assert rule.applies_to_event("CONNECTION_CHANGE") is False


# ============================================================================
# INTEGRATION TESTS: DailyRealizedLoss with Combined PnL
# ============================================================================


@pytest.mark.integration
@pytest.mark.p0
class TestDailyRealizedLossIntegration:
    """Integration tests for combined PnL monitoring."""

    @pytest.mark.asyncio
    async def test_combined_pnl_triggers_flatten(
        self,
        state_manager,
        broker,
        notifier,
        account_id
    ):
        """
        Test: Combined PnL breach triggers flatten + lockout.

        Scenario:
        - Limit: -$1000
        - Realized: -$850
        - Position opens at 18000
        - Price drops to 17925 (unrealized = -$150)
        - Combined = -$850 + -$150 = -$1000 (AT LIMIT, should not trigger)
        - Price drops to 17900 (unrealized = -$200)
        - Combined = -$850 + -$200 = -$1050 (BREACH)
        - Expected: Flatten all + lockout
        """
        # WILL FAIL: RiskEngine and EnforcementEngine don't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.daily_realized_loss import DailyRealizedLossRule
        from tests.conftest import Event, Position

        # Setup
        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = DailyRealizedLossRule(limit=Decimal("-1000.00"))
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Set realized loss
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-850.00")

        # Add position
        pos = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=1,
            entry_price=Decimal("18000.00"),
            current_price=Decimal("18000.00"),
            unrealized_pnl=Decimal("0.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos)

        # First price update: down to 17925 (unrealized = -$150, combined = -$1000)
        state_manager.update_position_price(pos.account_id, pos.position_id, Decimal("17925.00"))

        update_event1 = Event(
            event_id=uuid4(),
            event_type="POSITION_UPDATE",
            timestamp=state_manager.clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "position_id": pos.position_id,
                "symbol": "MNQ",
                "current_price": Decimal("17925.00"),
                "unrealized_pnl": Decimal("-150.00"),
                "quantity": 1,
                "update_time": state_manager.clock.now()
            }
        )
        await risk_engine.process_event(update_event1)

        # At limit but not exceeded - no enforcement yet
        assert len(broker.flatten_account_calls) == 0

        # Second price update: down to 17900 (unrealized = -$200, combined = -$1050)
        state_manager.update_position_price(pos.account_id, pos.position_id, Decimal("17900.00"))

        update_event2 = Event(
            event_id=uuid4(),
            event_type="POSITION_UPDATE",
            timestamp=state_manager.clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "position_id": pos.position_id,
                "symbol": "MNQ",
                "current_price": Decimal("17900.00"),
                "unrealized_pnl": Decimal("-200.00"),
                "quantity": 1,
                "update_time": state_manager.clock.now()
            }
        )
        await risk_engine.process_event(update_event2)

        # Now should flatten
        assert len(broker.flatten_account_calls) == 1
        assert broker.flatten_account_calls[0] == account_id

        # Verify lockout set
        assert state_manager.is_locked_out(account_id) is True

        # Verify notification sent
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) == 1
        notif = notifications[0]
        assert notif.severity == "critical"
        assert "DailyRealizedLoss" in notif.reason
        assert "-1050" in notif.reason

    @pytest.mark.asyncio
    async def test_cascading_rule_interaction(
        self,
        state_manager,
        broker,
        notifier,
        account_id
    ):
        """
        Test: CRITICAL - Cascading rule interaction.

        Scenario (from architecture/02-risk-engine.md):
        - Per-trade unrealized limit: -$200
        - Daily loss limit: -$1000
        - Realized: -$850
        - Position hits -$200 unrealized (per-trade limit)
        - Per-trade rule closes position → realized becomes -$1050
        - Daily limit rule then triggers → lockout

        This tests that closing a position for per-trade limit can cascade
        to daily limit violation.
        """
        # WILL FAIL: Multiple rules and cascading logic don't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.daily_realized_loss import DailyRealizedLossRule
        from src.rules.unrealized_loss import UnrealizedLossRule
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        per_trade_rule = UnrealizedLossRule(limit=Decimal("-200.00"))
        daily_rule = DailyRealizedLossRule(limit=Decimal("-1000.00"))

        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[per_trade_rule, daily_rule]
        )

        # Setup: realized = -$850
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-850.00")

        # Add position with -$200 unrealized loss
        pos = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=1,
            entry_price=Decimal("18000.00"),
            current_price=Decimal("17900.00"),  # Down $100 per point
            unrealized_pnl=Decimal("-200.00"),  # Exactly at per-trade limit
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos)

        # Position update triggers per-trade rule
        update_event = Event(
            event_id=uuid4(),
            event_type="POSITION_UPDATE",
            timestamp=state_manager.clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "position_id": pos.position_id,
                "symbol": "MNQ",
                "current_price": Decimal("17900.00"),
                "unrealized_pnl": Decimal("-200.00"),
                "quantity": 1,
                "update_time": state_manager.clock.now()
            }
        )

        await risk_engine.process_event(update_event)

        # Verify per-trade rule closed position
        assert len(broker.close_position_calls) >= 1

        # Simulate position close → realized PnL updated
        state_manager.close_position(account_id, pos.position_id, Decimal("-200.00"))

        # Now realized = -$1050, should trigger daily limit
        # Risk engine should automatically re-evaluate after closure
        assert state_manager.get_realized_pnl(account_id) == Decimal("-1050.00")
        assert state_manager.is_locked_out(account_id) is True

        # Verify both notifications sent
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) == 2  # One for per-trade, one for daily

    @pytest.mark.asyncio
    async def test_multiple_positions_combined_pnl(
        self,
        state_manager,
        broker,
        notifier,
        account_id
    ):
        """
        Test: Combined PnL calculated across multiple open positions.

        Scenario:
        - Realized: -$700
        - Position A: MNQ with -$150 unrealized
        - Position B: ES with -$200 unrealized
        - Combined: -$700 + -$150 + -$200 = -$1050
        - Limit: -$1000
        - Expected: Flatten all + lockout
        """
        # WILL FAIL: Multi-position handling doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.daily_realized_loss import DailyRealizedLossRule
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = DailyRealizedLossRule(limit=Decimal("-1000.00"))
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Set realized loss
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-700.00")

        # Add position A: MNQ with -$150 unrealized
        pos_a = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=1,
            entry_price=Decimal("18000.00"),
            current_price=Decimal("17925.00"),
            unrealized_pnl=Decimal("-150.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos_a)

        # Add position B: ES with -$200 unrealized
        pos_b = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500.00"),
            current_price=Decimal("4460.00"),
            unrealized_pnl=Decimal("-200.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos_b)

        # Update event (any position triggers combined PnL check)
        update_event = Event(
            event_id=uuid4(),
            event_type="POSITION_UPDATE",
            timestamp=state_manager.clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "position_id": pos_b.position_id,
                "symbol": "ES",
                "current_price": Decimal("4460.00"),
                "unrealized_pnl": Decimal("-200.00"),
                "quantity": 1,
                "update_time": state_manager.clock.now()
            }
        )

        await risk_engine.process_event(update_event)

        # Verify flatten called
        assert len(broker.flatten_account_calls) == 1

        # Verify lockout
        assert state_manager.is_locked_out(account_id) is True
