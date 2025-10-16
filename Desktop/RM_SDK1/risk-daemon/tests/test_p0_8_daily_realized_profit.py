"""
P0-8: DailyRealizedProfit Rule Tests

Tests the DailyRealizedProfit rule that enforces daily profit target with flatten + lockout.
Tests follow TDD principles - all tests FAIL initially until implementation exists.

Architecture reference: docs/architecture/02-risk-engine.md (Rule 8: DailyRealizedProfit)

Rule Behavior:
- Monitors realized PnL + unrealized PnL combined
- When combined >= profit target: Flatten all positions + lockout until 5pm CT
- Triggered on FILL and POSITION_UPDATE events
- Lockout prevents new fills
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import timedelta


# ============================================================================
# UNIT TESTS: DailyRealizedProfit Rule Logic
# ============================================================================


@pytest.mark.unit
@pytest.mark.p0
class TestDailyRealizedProfitRuleUnit:
    """Unit tests for DailyRealizedProfit rule logic (isolated)."""

    def test_rule_config_defaults(self):
        """Test: DailyRealizedProfit rule has proper configuration defaults."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.daily_realized_profit import DailyRealizedProfitRule

        rule = DailyRealizedProfitRule(profit_target=Decimal("500.00"))
        assert rule.enabled is True
        assert rule.profit_target == Decimal("500.00")
        assert rule.name == "DailyRealizedProfit"

    def test_rule_not_violated_below_target(self, state_manager, account_id):
        """Test: Rule not violated when combined PnL < target."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.daily_realized_profit import DailyRealizedProfitRule
        from tests.conftest import Position

        # Setup: Realized = $300, Unrealized = $100 (combined = $400 < $500)
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("300.00")

        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18025"),  # +$50 per contract * 2 contracts * $2/point = $100
            unrealized_pnl=Decimal("100.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, position)

        rule = DailyRealizedProfitRule(profit_target=Decimal("500.00"))
        account_state = state_manager.get_account_state(account_id)

        violation = rule.evaluate({}, account_state)
        assert violation is None  # No violation

    def test_rule_violated_at_target(self, state_manager, account_id):
        """Test: Rule violated when combined PnL >= target."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.daily_realized_profit import DailyRealizedProfitRule
        from tests.conftest import Position

        # Setup: Realized = $400, Unrealized = $100 (combined = $500 >= $500)
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("400.00")

        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18025"),
            unrealized_pnl=Decimal("100.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, position)

        rule = DailyRealizedProfitRule(profit_target=Decimal("500.00"))
        account_state = state_manager.get_account_state(account_id)

        violation = rule.evaluate({}, account_state)
        assert violation is not None
        assert violation.rule_name == "DailyRealizedProfit"
        assert violation.severity == "critical"
        assert "profit target" in violation.reason.lower()

    def test_rule_enforcement_action_flatten_and_lockout(self, state_manager, account_id, clock):
        """Test: Enforcement action flattens all positions and sets lockout until 5pm CT."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.daily_realized_profit import DailyRealizedProfitRule
        from tests.conftest import Position

        # Setup: Combined PnL >= target
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("400.00")

        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18025"),
            unrealized_pnl=Decimal("100.00"),
            opened_at=clock.now()
        )
        state_manager.add_position(account_id, position)

        rule = DailyRealizedProfitRule(profit_target=Decimal("500.00"))
        account_state = state_manager.get_account_state(account_id)

        # Trigger violation
        violation = rule.evaluate({}, account_state)
        action = rule.get_enforcement_action(violation)

        # Should flatten all positions
        assert action.action_type == "flatten_account"
        assert action.account_id == account_id

        # Should set lockout until 5pm CT
        assert action.lockout_until is not None
        # Verify lockout time is 5pm CT today (17:00)
        lockout_ct = action.lockout_until.astimezone(clock.chicago_tz)
        assert lockout_ct.hour == 17
        assert lockout_ct.minute == 0

    def test_rule_applies_to_fill_and_position_update_events(self):
        """Test: Rule evaluates FILL and POSITION_UPDATE events."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.daily_realized_profit import DailyRealizedProfitRule

        rule = DailyRealizedProfitRule(profit_target=Decimal("500.00"))

        assert rule.applies_to_event("FILL") is True
        assert rule.applies_to_event("POSITION_UPDATE") is True
        assert rule.applies_to_event("TIME_TICK") is False
        assert rule.applies_to_event("CONNECTION_CHANGE") is False

    def test_rule_combined_pnl_calculation(self, state_manager, account_id):
        """Test: Combined PnL correctly sums realized + all unrealized positions."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.daily_realized_profit import DailyRealizedProfitRule
        from tests.conftest import Position

        # Setup: Realized = $200
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("200.00")

        # Position 1: Unrealized = $150
        state_manager.add_position(account_id, Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18037.50"),
            unrealized_pnl=Decimal("150.00"),
            opened_at=state_manager.clock.now()
        ))

        # Position 2: Unrealized = $100
        state_manager.add_position(account_id, Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4525"),
            unrealized_pnl=Decimal("100.00"),
            opened_at=state_manager.clock.now()
        ))

        # Combined = $200 + $150 + $100 = $450 < $500 target
        rule = DailyRealizedProfitRule(profit_target=Decimal("500.00"))
        account_state = state_manager.get_account_state(account_id)

        violation = rule.evaluate({}, account_state)
        assert violation is None  # Not yet at target

        # Update Position 2 to increase unrealized to $150
        # Combined = $200 + $150 + $150 = $500 >= $500 target
        account_state.open_positions[1].current_price = Decimal("4537.50")
        account_state.open_positions[1].unrealized_pnl = Decimal("150.00")

        violation = rule.evaluate({}, account_state)
        assert violation is not None  # Now at target

    def test_rule_handles_negative_unrealized(self, state_manager, account_id):
        """Test: Negative unrealized PnL reduces combined total."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.daily_realized_profit import DailyRealizedProfitRule
        from tests.conftest import Position

        # Setup: Realized = $600 (above target)
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("600.00")

        # Position with negative unrealized = -$150
        # Combined = $600 - $150 = $450 < $500
        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("17962.50"),
            unrealized_pnl=Decimal("-150.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, position)

        rule = DailyRealizedProfitRule(profit_target=Decimal("500.00"))
        account_state = state_manager.get_account_state(account_id)

        violation = rule.evaluate({}, account_state)
        assert violation is None  # Below target due to negative unrealized


# ============================================================================
# INTEGRATION TESTS: DailyRealizedProfit with Enforcement Engine
# ============================================================================


@pytest.mark.integration
@pytest.mark.p0
class TestDailyRealizedProfitIntegration:
    """Integration tests for DailyRealizedProfit rule with enforcement engine."""

    @pytest.mark.asyncio
    async def test_flatten_and_lockout_on_profit_target(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: When profit target hit, flatten all + lockout.

        Scenario:
        - Target: $500
        - Realized: $450
        - Position: MNQ with unrealized = $60
        - Combined = $510 >= $500
        - Expected: Flatten all, lockout until 5pm CT
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.daily_realized_profit import DailyRealizedProfitRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Position, Event

        enforcement = EnforcementEngine(broker, state_manager)
        rule = DailyRealizedProfitRule(profit_target=Decimal("500.00"))
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Setup: Realized = $450
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("450.00")

        # Add position with unrealized = $60
        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18015"),  # +$30 profit
            unrealized_pnl=Decimal("60.00"),
            opened_at=clock.now()
        )
        state_manager.add_position(account_id, position)

        # Trigger evaluation via POSITION_UPDATE
        position_update = Event(
            event_id=uuid4(),
            event_type="POSITION_UPDATE",
            timestamp=clock.now(),
            priority=3,
            account_id=account_id,
            source="broker",
            data={
                "position_id": position.position_id,
                "current_price": Decimal("18015"),
                "unrealized_pnl": Decimal("60.00")
            }
        )
        await risk_engine.process_event(position_update)

        # Verify enforcement: flatten all
        assert len(broker.flatten_account_calls) == 1
        assert broker.flatten_account_calls[0] == account_id

        # Verify lockout set
        assert state_manager.is_locked_out(account_id)

    @pytest.mark.asyncio
    async def test_lockout_prevents_new_fills(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: After profit target hit, lockout prevents new fills.

        Scenario:
        - Profit target hit, lockout active
        - New fill arrives
        - Expected: Fill rejected, position not opened
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.daily_realized_profit import DailyRealizedProfitRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Event

        enforcement = EnforcementEngine(broker, state_manager)
        rule = DailyRealizedProfitRule(profit_target=Decimal("500.00"))
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Setup: Lockout active (profit target was hit earlier)
        import pytz
        chicago_tz = pytz.timezone("America/Chicago")
        ct_now = clock.get_chicago_time()
        lockout_time = ct_now.replace(hour=17, minute=0, second=0, microsecond=0)
        state_manager.set_lockout(
            account_id,
            lockout_time.astimezone(clock._current_time.tzinfo),
            "DailyRealizedProfit target hit"
        )

        # New fill arrives
        fill_event = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "symbol": "ES",
                "side": "long",
                "quantity": 1,
                "fill_price": Decimal("4500"),
                "order_id": "ORD_AFTER_LOCKOUT",
                "fill_time": clock.now()
            }
        )

        # Process fill (should be rejected by lockout check)
        await risk_engine.process_event(fill_event)

        # Verify: No new positions opened
        positions = state_manager.get_open_positions(account_id)
        assert len(positions) == 0

    @pytest.mark.asyncio
    async def test_lockout_clears_at_5pm_reset(
        self,
        state_manager,
        broker,
        account_id,
        clock,
        time_service
    ):
        """
        Test: Lockout clears during 5pm CT daily reset.

        Scenario:
        - Profit target hit at 2pm CT, lockout set until 5pm
        - Time advances to 5pm CT
        - Daily reset triggers
        - Lockout cleared, realized PnL reset to $0
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.daily_realized_profit import DailyRealizedProfitRule
        from src.core.enforcement_engine import EnforcementEngine

        enforcement = EnforcementEngine(broker, state_manager)
        rule = DailyRealizedProfitRule(profit_target=Decimal("500.00"))
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Setup: 2pm CT, lockout active
        import pytz
        chicago_tz = pytz.timezone("America/Chicago")
        ct_2pm = chicago_tz.localize(clock.get_chicago_time().replace(hour=14, minute=0, second=0, microsecond=0))
        clock.set_time(ct_2pm.astimezone(clock._current_time.tzinfo))

        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("500.00")
        ct_5pm = ct_2pm.replace(hour=17, minute=0)
        state_manager.set_lockout(
            account_id,
            ct_5pm.astimezone(clock._current_time.tzinfo),
            "DailyRealizedProfit target hit"
        )

        assert state_manager.is_locked_out(account_id)

        # Advance to 5pm CT
        clock.set_time(ct_5pm.astimezone(clock._current_time.tzinfo))

        # Trigger daily reset
        time_service.trigger_reset_if_needed(state_manager)

        # Verify lockout cleared
        assert not state_manager.is_locked_out(account_id)

        # Verify realized PnL reset
        assert state_manager.get_realized_pnl(account_id) == Decimal("0.00")


# ============================================================================
# E2E TESTS: DailyRealizedProfit Happy Path
# ============================================================================


@pytest.mark.e2e
@pytest.mark.p0
class TestDailyRealizedProfitE2E:
    """End-to-end tests for DailyRealizedProfit rule (full system flow)."""

    @pytest.mark.asyncio
    async def test_happy_path_stays_below_target(
        self,
        state_manager,
        broker,
        notifier,
        account_id,
        clock
    ):
        """
        Test: Happy path - trader stays below profit target, no enforcement.

        Flow:
        1. Target: $500
        2. Trade 1: Realize $200 profit
        3. Trade 2: Realize $150 profit (total: $350)
        4. Open position with unrealized $100 (combined: $450)
        5. No enforcement - still below target
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.daily_realized_profit import DailyRealizedProfitRule
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = DailyRealizedProfitRule(profit_target=Decimal("500.00"))
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Trade 1: Realize $200
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("200.00")

        # Trade 2: Realize $150
        clock.advance(minutes=30)
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("350.00")

        # Open position with unrealized $100
        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18025"),
            unrealized_pnl=Decimal("100.00"),
            opened_at=clock.now()
        )
        state_manager.add_position(account_id, position)

        # Trigger evaluation
        update_event = Event(
            event_id=uuid4(),
            event_type="POSITION_UPDATE",
            timestamp=clock.now(),
            priority=3,
            account_id=account_id,
            source="broker",
            data={"position_id": position.position_id}
        )
        await risk_engine.process_event(update_event)

        # Verify: No enforcement
        assert len(broker.flatten_account_calls) == 0
        assert not state_manager.is_locked_out(account_id)

        # Verify: No notifications
        assert len(notifier.get_notifications(account_id)) == 0

    @pytest.mark.asyncio
    async def test_enforcement_with_notification(
        self,
        state_manager,
        broker,
        notifier,
        account_id,
        clock
    ):
        """
        Test: When profit target hit, flatten + lockout + notification.

        Flow:
        1. Target: $500
        2. Realized: $480
        3. Position moves to unrealized $25
        4. Combined = $505 >= $500
        5. System flattens all, sets lockout
        6. Trader receives critical notification
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.daily_realized_profit import DailyRealizedProfitRule
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = DailyRealizedProfitRule(profit_target=Decimal("500.00"))
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Setup: Realized = $480
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("480.00")

        # Add position with unrealized = $25
        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4512.50"),
            unrealized_pnl=Decimal("25.00"),
            opened_at=clock.now()
        )
        state_manager.add_position(account_id, position)

        # Trigger via position update
        update_event = Event(
            event_id=uuid4(),
            event_type="POSITION_UPDATE",
            timestamp=clock.now(),
            priority=3,
            account_id=account_id,
            source="broker",
            data={"position_id": position.position_id}
        )
        await risk_engine.process_event(update_event)

        # Verify enforcement
        assert len(broker.flatten_account_calls) == 1
        assert state_manager.is_locked_out(account_id)

        # Verify notification sent
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) == 1

        notif = notifications[0]
        assert notif.severity == "critical"
        assert "profit target" in notif.reason.lower() or "DailyRealizedProfit" in notif.reason
        assert notif.action == "flatten_account"
