"""
P0-9: UnrealizedProfit Rule Tests

Tests the UnrealizedProfit rule that automatically takes profit on individual positions.
Tests follow TDD principles - all tests FAIL initially until implementation exists.

Architecture reference: docs/architecture/02-risk-engine.md (Rule 9: UnrealizedProfit)

Rule Behavior:
- Monitors unrealized PnL per position
- When position unrealized >= profit target: Close that position
- Per-position enforcement (not account-wide)
- Triggered on POSITION_UPDATE events
"""

import pytest
from decimal import Decimal
from uuid import uuid4


# ============================================================================
# UNIT TESTS: UnrealizedProfit Rule Logic
# ============================================================================


@pytest.mark.unit
@pytest.mark.p0
class TestUnrealizedProfitRuleUnit:
    """Unit tests for UnrealizedProfit rule logic (isolated)."""

    def test_rule_config_defaults(self):
        """Test: UnrealizedProfit rule has proper configuration defaults."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.unrealized_profit import UnrealizedProfitRule

        rule = UnrealizedProfitRule(profit_target=Decimal("100.00"))
        assert rule.enabled is True
        assert rule.profit_target == Decimal("100.00")
        assert rule.name == "UnrealizedProfit"

    def test_rule_not_violated_below_target(self, state_manager, account_id):
        """Test: Rule not violated when position unrealized < target."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.unrealized_profit import UnrealizedProfitRule
        from tests.conftest import Position

        # Setup: Position with unrealized = $80 < $100 target
        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18020"),
            unrealized_pnl=Decimal("80.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, position)

        rule = UnrealizedProfitRule(profit_target=Decimal("100.00"))
        account_state = state_manager.get_account_state(account_id)

        violation = rule.evaluate({}, account_state)
        assert violation is None  # No violation

    def test_rule_violated_at_target(self, state_manager, account_id):
        """Test: Rule violated when position unrealized >= target."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.unrealized_profit import UnrealizedProfitRule
        from tests.conftest import Position

        # Setup: Position with unrealized = $100 >= $100 target
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

        rule = UnrealizedProfitRule(profit_target=Decimal("100.00"))
        account_state = state_manager.get_account_state(account_id)

        violation = rule.evaluate({}, account_state)
        assert violation is not None
        assert violation.rule_name == "UnrealizedProfit"
        assert violation.severity == "info"
        assert "profit target" in violation.reason.lower()

    def test_rule_enforcement_action_close_position(self, state_manager, account_id):
        """Test: Enforcement action closes the profitable position."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.unrealized_profit import UnrealizedProfitRule
        from tests.conftest import Position

        # Setup: Position at profit target
        position_id = uuid4()
        position = Position(
            position_id=position_id,
            account_id=account_id,
            symbol="ES",
            side="short",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4450"),  # Short profit
            unrealized_pnl=Decimal("100.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, position)

        rule = UnrealizedProfitRule(profit_target=Decimal("100.00"))
        account_state = state_manager.get_account_state(account_id)

        # Trigger violation
        violation = rule.evaluate({}, account_state)
        action = rule.get_enforcement_action(violation)

        # Should close entire position
        assert action.action_type == "close_position"
        assert action.position_id == position_id
        assert action.quantity == position.quantity  # Close all

    def test_rule_applies_to_position_update_events(self):
        """Test: Rule evaluates POSITION_UPDATE events."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.unrealized_profit import UnrealizedProfitRule

        rule = UnrealizedProfitRule(profit_target=Decimal("100.00"))

        assert rule.applies_to_event("POSITION_UPDATE") is True
        assert rule.applies_to_event("FILL") is False
        assert rule.applies_to_event("TIME_TICK") is False
        assert rule.applies_to_event("CONNECTION_CHANGE") is False

    def test_rule_handles_multiple_positions_independently(self, state_manager, account_id):
        """Test: Each position evaluated independently."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.unrealized_profit import UnrealizedProfitRule
        from tests.conftest import Position

        # Position 1: At target ($100)
        pos1_id = uuid4()
        pos1 = Position(
            position_id=pos1_id,
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18025"),
            unrealized_pnl=Decimal("100.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos1)

        # Position 2: Below target ($50)
        pos2 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4525"),
            unrealized_pnl=Decimal("50.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos2)

        rule = UnrealizedProfitRule(profit_target=Decimal("100.00"))
        account_state = state_manager.get_account_state(account_id)

        violation = rule.evaluate({}, account_state)

        # Should violate only for pos1
        assert violation is not None
        assert violation.data["position_id"] == pos1_id

    def test_rule_ignores_negative_unrealized(self, state_manager, account_id):
        """Test: Positions with negative unrealized PnL are ignored."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.unrealized_profit import UnrealizedProfitRule
        from tests.conftest import Position

        # Position with loss (negative unrealized)
        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("17950"),
            unrealized_pnl=Decimal("-100.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, position)

        rule = UnrealizedProfitRule(profit_target=Decimal("100.00"))
        account_state = state_manager.get_account_state(account_id)

        violation = rule.evaluate({}, account_state)
        assert violation is None  # No violation for losses

    def test_rule_configurable_target_levels(self, state_manager, account_id):
        """Test: Different target levels enforced correctly."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.unrealized_profit import UnrealizedProfitRule
        from tests.conftest import Position

        # Position with unrealized = $150
        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18037.50"),
            unrealized_pnl=Decimal("150.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, position)
        account_state = state_manager.get_account_state(account_id)

        # Target $100: Should violate
        rule_100 = UnrealizedProfitRule(profit_target=Decimal("100.00"))
        violation_100 = rule_100.evaluate({}, account_state)
        assert violation_100 is not None

        # Target $200: Should NOT violate
        rule_200 = UnrealizedProfitRule(profit_target=Decimal("200.00"))
        violation_200 = rule_200.evaluate({}, account_state)
        assert violation_200 is None


# ============================================================================
# INTEGRATION TESTS: UnrealizedProfit with Enforcement Engine
# ============================================================================


@pytest.mark.integration
@pytest.mark.p0
class TestUnrealizedProfitIntegration:
    """Integration tests for UnrealizedProfit rule with enforcement engine."""

    @pytest.mark.asyncio
    async def test_position_closed_at_profit_target(
        self,
        state_manager,
        broker,
        account_id
    ):
        """
        Test: Position closed when unrealized profit hits target.

        Scenario:
        - Target: $100
        - Position: MNQ unrealized = $100
        - Expected: Position closed immediately
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.unrealized_profit import UnrealizedProfitRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Position, Event

        enforcement = EnforcementEngine(broker, state_manager)
        rule = UnrealizedProfitRule(profit_target=Decimal("100.00"))
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Add position at profit target
        position_id = uuid4()
        position = Position(
            position_id=position_id,
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

        # Trigger via POSITION_UPDATE
        position_update = Event(
            event_id=uuid4(),
            event_type="POSITION_UPDATE",
            timestamp=state_manager.clock.now(),
            priority=3,
            account_id=account_id,
            source="broker",
            data={
                "position_id": position_id,
                "current_price": Decimal("18025"),
                "unrealized_pnl": Decimal("100.00")
            }
        )
        await risk_engine.process_event(position_update)

        # Verify enforcement: position closed
        assert len(broker.close_position_calls) == 1
        close_call = broker.close_position_calls[0]
        assert close_call["position_id"] == position_id
        assert close_call["quantity"] == 2

    @pytest.mark.asyncio
    async def test_only_profitable_position_closed(
        self,
        state_manager,
        broker,
        account_id
    ):
        """
        Test: Only position at profit target closed, others remain open.

        Scenario:
        - Target: $100
        - Position 1: MNQ unrealized = $100 (at target)
        - Position 2: ES unrealized = $50 (below target)
        - Expected: Only position 1 closed
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.unrealized_profit import UnrealizedProfitRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Position, Event

        enforcement = EnforcementEngine(broker, state_manager)
        rule = UnrealizedProfitRule(profit_target=Decimal("100.00"))
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Position 1: At target
        pos1_id = uuid4()
        pos1 = Position(
            position_id=pos1_id,
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18025"),
            unrealized_pnl=Decimal("100.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos1)

        # Position 2: Below target
        pos2_id = uuid4()
        pos2 = Position(
            position_id=pos2_id,
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4525"),
            unrealized_pnl=Decimal("50.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos2)

        # Trigger position update for pos1
        update = Event(
            event_id=uuid4(),
            event_type="POSITION_UPDATE",
            timestamp=state_manager.clock.now(),
            priority=3,
            account_id=account_id,
            source="broker",
            data={
                "position_id": pos1_id,
                "current_price": Decimal("18025"),
                "unrealized_pnl": Decimal("100.00")
            }
        )
        await risk_engine.process_event(update)

        # Verify: Only pos1 closed
        assert len(broker.close_position_calls) == 1
        assert broker.close_position_calls[0]["position_id"] == pos1_id

        # Verify: pos2 still open
        positions = state_manager.get_open_positions(account_id)
        remaining_ids = [p.position_id for p in positions]
        assert pos2_id in remaining_ids
        assert pos1_id not in remaining_ids

    @pytest.mark.asyncio
    async def test_multiple_positions_reach_target_sequentially(
        self,
        state_manager,
        broker,
        account_id
    ):
        """
        Test: Multiple positions reach target at different times, each closed.

        Scenario:
        - Target: $100
        - T=0: Position 1 reaches $100 → closed
        - T=60: Position 2 reaches $100 → closed
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.unrealized_profit import UnrealizedProfitRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Position, Event

        enforcement = EnforcementEngine(broker, state_manager)
        rule = UnrealizedProfitRule(profit_target=Decimal("100.00"))
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Position 1: At target
        pos1_id = uuid4()
        pos1 = Position(
            position_id=pos1_id,
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18025"),
            unrealized_pnl=Decimal("100.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos1)

        # Position 2: Below target initially
        pos2_id = uuid4()
        pos2 = Position(
            position_id=pos2_id,
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4550"),
            unrealized_pnl=Decimal("50.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos2)

        # T=0: Process pos1 update
        update1 = Event(
            event_id=uuid4(),
            event_type="POSITION_UPDATE",
            timestamp=state_manager.clock.now(),
            priority=3,
            account_id=account_id,
            source="broker",
            data={"position_id": pos1_id}
        )
        await risk_engine.process_event(update1)

        # Close pos1 in state
        state_manager.close_position(account_id, pos1_id, Decimal("100.00"))

        # T=60: pos2 reaches target
        state_manager.clock.advance(seconds=60)
        pos2.current_price = Decimal("4600")
        pos2.unrealized_pnl = Decimal("100.00")

        update2 = Event(
            event_id=uuid4(),
            event_type="POSITION_UPDATE",
            timestamp=state_manager.clock.now(),
            priority=3,
            account_id=account_id,
            source="broker",
            data={"position_id": pos2_id}
        )
        await risk_engine.process_event(update2)

        # Verify: Both positions closed
        assert len(broker.close_position_calls) == 2
        closed_ids = [call["position_id"] for call in broker.close_position_calls]
        assert pos1_id in closed_ids
        assert pos2_id in closed_ids


# ============================================================================
# E2E TESTS: UnrealizedProfit Happy Path
# ============================================================================


@pytest.mark.e2e
@pytest.mark.p0
class TestUnrealizedProfitE2E:
    """End-to-end tests for UnrealizedProfit rule (full system flow)."""

    @pytest.mark.asyncio
    async def test_happy_path_positions_stay_below_target(
        self,
        state_manager,
        broker,
        notifier,
        account_id
    ):
        """
        Test: Happy path - positions stay below profit target, no enforcement.

        Flow:
        1. Target: $100
        2. Position 1: MNQ unrealized = $80
        3. Position 2: ES unrealized = $60
        4. No enforcement actions taken
        5. No notifications sent
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.unrealized_profit import UnrealizedProfitRule
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = UnrealizedProfitRule(profit_target=Decimal("100.00"))
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Position 1: $80 unrealized
        pos1 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18020"),
            unrealized_pnl=Decimal("80.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos1)

        # Position 2: $60 unrealized
        pos2 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4530"),
            unrealized_pnl=Decimal("60.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos2)

        # Trigger updates
        for pos in [pos1, pos2]:
            update = Event(
                event_id=uuid4(),
                event_type="POSITION_UPDATE",
                timestamp=state_manager.clock.now(),
                priority=3,
                account_id=account_id,
                source="broker",
                data={"position_id": pos.position_id}
            )
            await risk_engine.process_event(update)

        # Verify: No enforcement
        assert len(broker.close_position_calls) == 0
        assert len(broker.flatten_account_calls) == 0

        # Verify: No notifications
        assert len(notifier.get_notifications(account_id)) == 0

    @pytest.mark.asyncio
    async def test_enforcement_with_notification(
        self,
        state_manager,
        broker,
        notifier,
        account_id
    ):
        """
        Test: When profit target hit, position closed AND trader notified.

        Flow:
        1. Target: $100
        2. Position moves to unrealized $105
        3. System closes position immediately
        4. Trader receives info notification (positive event)
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.unrealized_profit import UnrealizedProfitRule
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = UnrealizedProfitRule(profit_target=Decimal("100.00"))
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Position at profit target
        position_id = uuid4()
        position = Position(
            position_id=position_id,
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18026.25"),
            unrealized_pnl=Decimal("105.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, position)

        # Trigger position update
        update = Event(
            event_id=uuid4(),
            event_type="POSITION_UPDATE",
            timestamp=state_manager.clock.now(),
            priority=3,
            account_id=account_id,
            source="broker",
            data={"position_id": position_id}
        )
        await risk_engine.process_event(update)

        # Verify enforcement
        assert len(broker.close_position_calls) == 1
        assert broker.close_position_calls[0]["position_id"] == position_id

        # Verify notification sent
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) == 1

        notif = notifications[0]
        assert notif.severity == "info"  # Positive event
        assert "profit" in notif.reason.lower() or "UnrealizedProfit" in notif.reason
        assert notif.action == "close_position"
