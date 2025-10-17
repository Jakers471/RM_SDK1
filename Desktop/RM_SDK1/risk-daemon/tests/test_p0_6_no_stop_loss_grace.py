"""
P0-6: NoStopLossGrace Rule Tests

Tests the NoStopLossGrace rule that enforces stop loss attachment within grace period.
Tests follow TDD principles - all tests FAIL initially until implementation exists.

Architecture reference: docs/architecture/02-risk-engine.md (Rule 6: NoStopLossGrace)

Rule Behavior:
- After FILL event, position has 120 second grace period
- During grace: Monitor for stop loss attachment (STOP_DETECTED event or stop_loss_attached flag)
- After grace expires: If no stop loss detected, close position immediately
- Requires TIME_TICK events for grace period tracking
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import timedelta


# ============================================================================
# UNIT TESTS: NoStopLossGrace Rule Logic
# ============================================================================


@pytest.mark.unit
@pytest.mark.p0
class TestNoStopLossGraceRuleUnit:
    """Unit tests for NoStopLossGrace rule logic (isolated)."""

    def test_rule_config_defaults(self):
        """Test: NoStopLossGrace rule has proper configuration defaults."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule

        rule = NoStopLossGraceRule(grace_period_seconds=120)
        assert rule.enabled is True
        assert rule.grace_period_seconds == 120
        assert rule.name == "NoStopLossGrace"

    def test_rule_not_violated_stop_attached_within_grace(self, state_manager, account_id, clock):
        """Test: Rule not violated when stop loss attached within grace period."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule
        from tests.conftest import Position

        # Setup: Position opened 60 seconds ago with stop loss attached
        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now() - timedelta(seconds=60),
            stop_loss_attached=True,  # Stop was attached
            stop_loss_grace_expires=clock.now() + timedelta(seconds=60)
        )
        state_manager.add_position(account_id, position)

        rule = NoStopLossGraceRule(grace_period_seconds=120)
        account_state = state_manager.get_account_state(account_id)

        # TIME_TICK event during grace period
        time_tick_event = {
            "current_time": clock.now()
        }

        violation = rule.evaluate(time_tick_event, account_state)
        assert violation is None  # No violation - stop was attached

    def test_rule_violated_no_stop_after_grace(self, state_manager, account_id, clock):
        """Test: Rule violated when grace period expires without stop loss."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule
        from tests.conftest import Position

        # Setup: Position opened 125 seconds ago, grace expired, no stop
        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now() - timedelta(seconds=125),
            stop_loss_attached=False,  # NO stop loss
            stop_loss_grace_expires=clock.now() - timedelta(seconds=5)  # Grace expired
        )
        state_manager.add_position(account_id, position)

        rule = NoStopLossGraceRule(grace_period_seconds=120)
        account_state = state_manager.get_account_state(account_id)

        # TIME_TICK event after grace expiration
        time_tick_event = {
            "current_time": clock.now()
        }

        violation = rule.evaluate(time_tick_event, account_state)
        assert violation is not None
        assert violation.rule_name == "NoStopLossGrace"
        assert violation.severity == "high"
        assert "grace period expired" in violation.reason.lower()

    def test_rule_enforcement_action_close_position(self, state_manager, account_id, clock):
        """Test: Enforcement action closes position without stop loss."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule
        from tests.conftest import Position

        # Setup: Position with expired grace
        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="short",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4500"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now() - timedelta(seconds=125),
            stop_loss_attached=False,
            stop_loss_grace_expires=clock.now() - timedelta(seconds=5)
        )
        state_manager.add_position(account_id, position)

        rule = NoStopLossGraceRule(grace_period_seconds=120)
        account_state = state_manager.get_account_state(account_id)

        # Trigger violation
        violation = rule.evaluate({"current_time": clock.now()}, account_state)
        action = rule.get_enforcement_action(violation)

        # Should close entire position
        assert action.action_type == "close_position"
        assert action.position_id == position.position_id
        assert action.quantity == position.quantity  # Close all

    def test_rule_applies_to_time_tick_and_fill_events(self):
        """Test: Rule evaluates TIME_TICK and FILL events."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule

        rule = NoStopLossGraceRule(grace_period_seconds=120)

        assert rule.applies_to_event("TIME_TICK") is True
        assert rule.applies_to_event("FILL") is True  # To initialize grace tracking
        assert rule.applies_to_event("POSITION_UPDATE") is False
        assert rule.applies_to_event("CONNECTION_CHANGE") is False

    def test_rule_initializes_grace_on_fill_event(self, state_manager, account_id, clock):
        """Test: FILL event initializes grace period tracking."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule

        rule = NoStopLossGraceRule(grace_period_seconds=120)
        account_state = state_manager.get_account_state(account_id)

        # FILL event
        fill_event = {
            "symbol": "MNQ",
            "quantity": 2,
            "side": "long",
            "fill_price": Decimal("18000"),
            "fill_time": clock.now(),
            "position_id": uuid4()
        }

        # Should not violate on FILL (just initialize tracking)
        violation = rule.evaluate(fill_event, account_state)
        assert violation is None

    def test_rule_handles_multiple_positions_independently(self, state_manager, account_id, clock):
        """Test: Each position tracked independently for grace period."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule
        from tests.conftest import Position

        # Position 1: Grace expired, no stop
        pos1 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now() - timedelta(seconds=125),
            stop_loss_attached=False,
            stop_loss_grace_expires=clock.now() - timedelta(seconds=5)
        )
        state_manager.add_position(account_id, pos1)

        # Position 2: Within grace, has stop
        pos2 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4500"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now() - timedelta(seconds=30),
            stop_loss_attached=True,
            stop_loss_grace_expires=clock.now() + timedelta(seconds=90)
        )
        state_manager.add_position(account_id, pos2)

        rule = NoStopLossGraceRule(grace_period_seconds=120)
        account_state = state_manager.get_account_state(account_id)

        violation = rule.evaluate({"current_time": clock.now()}, account_state)

        # Should violate only for pos1
        assert violation is not None
        assert violation.data["position_id"] == pos1.position_id


# ============================================================================
# INTEGRATION TESTS: NoStopLossGrace with Enforcement Engine
# ============================================================================


@pytest.mark.integration
@pytest.mark.p0
class TestNoStopLossGraceIntegration:
    """Integration tests for NoStopLossGrace rule with enforcement engine."""

    @pytest.mark.asyncio
    async def test_position_closed_after_grace_expires(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: Position closed when grace expires without stop loss.

        Scenario:
        - Fill creates position at T=0
        - Grace period: 120 seconds
        - No stop loss attached
        - At T=121: Position closed automatically
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Position, Event

        enforcement = EnforcementEngine(broker, state_manager)
        rule = NoStopLossGraceRule(grace_period_seconds=120)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # T=0: Add position manually (simulating fill processing)
        # We don't process FILL event here to avoid double creation
        position_id = uuid4()
        position = Position(
            position_id=position_id,
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now(),
            stop_loss_attached=False,
            stop_loss_grace_expires=clock.now() + timedelta(seconds=120)
        )
        state_manager.add_position(account_id, position)

        # T=121: Grace expires, send TIME_TICK
        clock.advance(seconds=121)
        time_tick_event = Event(
            event_id=uuid4(),
            event_type="TIME_TICK",
            timestamp=clock.now(),
            priority=5,
            account_id=account_id,
            source="system",
            data={
                "current_time": clock.now()
            }
        )
        await risk_engine.process_event(time_tick_event)

        # Verify enforcement: position closed
        assert len(broker.close_position_calls) == 1
        close_call = broker.close_position_calls[0]
        assert close_call["position_id"] == position_id
        assert close_call["quantity"] == 2

    @pytest.mark.asyncio
    async def test_no_enforcement_when_stop_attached_in_time(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: No enforcement when stop loss attached within grace period.

        Scenario:
        - Fill creates position at T=0
        - At T=60: Stop loss attached (STOP_DETECTED event)
        - At T=121: TIME_TICK - no violation (stop was attached)
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Position, Event

        enforcement = EnforcementEngine(broker, state_manager)
        rule = NoStopLossGraceRule(grace_period_seconds=120)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # T=0: Create position
        position_id = uuid4()
        position = Position(
            position_id=position_id,
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now(),
            stop_loss_attached=False,
            stop_loss_grace_expires=clock.now() + timedelta(seconds=120)
        )
        state_manager.add_position(account_id, position)

        # T=60: Stop loss attached
        clock.advance(seconds=60)
        position.stop_loss_attached = True

        # T=121: TIME_TICK after grace
        clock.advance(seconds=61)
        time_tick_event = Event(
            event_id=uuid4(),
            event_type="TIME_TICK",
            timestamp=clock.now(),
            priority=5,
            account_id=account_id,
            source="system",
            data={
                "current_time": clock.now()
            }
        )
        await risk_engine.process_event(time_tick_event)

        # Verify: No enforcement (stop was attached in time)
        assert len(broker.close_position_calls) == 0

    @pytest.mark.asyncio
    async def test_multiple_positions_mixed_compliance(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: Multiple positions - some compliant, some violated.

        Scenario:
        - Position 1: Grace expired, no stop → CLOSE
        - Position 2: Grace active, no stop → NO ACTION
        - Position 3: Grace expired, has stop → NO ACTION
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Position, Event

        enforcement = EnforcementEngine(broker, state_manager)
        rule = NoStopLossGraceRule(grace_period_seconds=120)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Position 1: Grace expired, no stop (VIOLATES)
        pos1_id = uuid4()
        pos1 = Position(
            position_id=pos1_id,
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now() - timedelta(seconds=125),
            stop_loss_attached=False,
            stop_loss_grace_expires=clock.now() - timedelta(seconds=5)
        )
        state_manager.add_position(account_id, pos1)

        # Position 2: Grace active, no stop (OK for now)
        pos2_id = uuid4()
        pos2 = Position(
            position_id=pos2_id,
            account_id=account_id,
            symbol="ES",
            side="short",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4500"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now() - timedelta(seconds=30),
            stop_loss_attached=False,
            stop_loss_grace_expires=clock.now() + timedelta(seconds=90)
        )
        state_manager.add_position(account_id, pos2)

        # Position 3: Grace expired, has stop (OK)
        pos3_id = uuid4()
        pos3 = Position(
            position_id=pos3_id,
            account_id=account_id,
            symbol="NQ",
            side="long",
            quantity=1,
            entry_price=Decimal("18100"),
            current_price=Decimal("18100"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now() - timedelta(seconds=180),
            stop_loss_attached=True,
            stop_loss_grace_expires=clock.now() - timedelta(seconds=60)
        )
        state_manager.add_position(account_id, pos3)

        # TIME_TICK event
        time_tick_event = Event(
            event_id=uuid4(),
            event_type="TIME_TICK",
            timestamp=clock.now(),
            priority=5,
            account_id=account_id,
            source="system",
            data={
                "current_time": clock.now()
            }
        )
        await risk_engine.process_event(time_tick_event)

        # Verify: Only pos1 closed
        assert len(broker.close_position_calls) == 1
        assert broker.close_position_calls[0]["position_id"] == pos1_id


# ============================================================================
# E2E TESTS: NoStopLossGrace Happy Path
# ============================================================================


@pytest.mark.e2e
@pytest.mark.p0
class TestNoStopLossGraceE2E:
    """End-to-end tests for NoStopLossGrace rule (full system flow)."""

    @pytest.mark.asyncio
    async def test_happy_path_trader_attaches_stop_immediately(
        self,
        state_manager,
        broker,
        notifier,
        account_id,
        clock
    ):
        """
        Test: Happy path - trader attaches stop loss immediately, no enforcement.

        Flow:
        1. Fill event creates position
        2. Trader attaches stop loss within 10 seconds
        3. Grace period expires (121 seconds)
        4. No enforcement - position remains open
        5. No notifications sent
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = NoStopLossGraceRule(grace_period_seconds=120)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # T=0: Fill creates position
        position_id = uuid4()
        position = Position(
            position_id=position_id,
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now(),
            stop_loss_attached=False,
            stop_loss_grace_expires=clock.now() + timedelta(seconds=120)
        )
        state_manager.add_position(account_id, position)

        # T=10: Stop loss attached
        clock.advance(seconds=10)
        position.stop_loss_attached = True

        # T=121: Grace expires, TIME_TICK
        clock.advance(seconds=111)
        time_tick = Event(
            event_id=uuid4(),
            event_type="TIME_TICK",
            timestamp=clock.now(),
            priority=5,
            account_id=account_id,
            source="system",
            data={"current_time": clock.now()}
        )
        await risk_engine.process_event(time_tick)

        # Verify: No enforcement
        assert len(broker.close_position_calls) == 0
        assert len(broker.flatten_account_calls) == 0

        # Verify: No notifications
        assert len(notifier.get_notifications(account_id)) == 0

        # Verify: Position still open
        positions = state_manager.get_open_positions(account_id)
        assert len(positions) == 1
        assert positions[0].position_id == position_id

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
        Test: When grace expires without stop, position closed AND trader notified.

        Flow:
        1. Fill creates position at T=0
        2. No stop loss attached (trader forgot)
        3. Grace expires at T=121
        4. System closes position immediately
        5. Trader receives critical notification with reason
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = NoStopLossGraceRule(grace_period_seconds=120)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # T=0: Create position
        position_id = uuid4()
        position = Position(
            position_id=position_id,
            account_id=account_id,
            symbol="ES",
            side="short",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4500"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now(),
            stop_loss_attached=False,
            stop_loss_grace_expires=clock.now() + timedelta(seconds=120)
        )
        state_manager.add_position(account_id, position)

        # T=121: Grace expires
        clock.advance(seconds=121)
        time_tick = Event(
            event_id=uuid4(),
            event_type="TIME_TICK",
            timestamp=clock.now(),
            priority=5,
            account_id=account_id,
            source="system",
            data={"current_time": clock.now()}
        )
        await risk_engine.process_event(time_tick)

        # Verify enforcement
        assert len(broker.close_position_calls) == 1
        assert broker.close_position_calls[0]["position_id"] == position_id

        # Verify notification sent
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) == 1

        notif = notifications[0]
        assert notif.severity == "critical"
        assert "NoStopLossGrace" in notif.reason or "stop loss" in notif.reason.lower()
        assert "grace period" in notif.reason.lower()
        assert notif.action == "close_position"
