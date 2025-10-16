"""
P0-1: MaxContracts Rule Tests

Tests the MaxContracts universal cap enforcement rule.
Tests follow TDD principles - all tests FAIL initially until implementation exists.

Architecture reference: docs/architecture/02-risk-engine.md (Rule 1: MaxContracts)
"""

import pytest
from decimal import Decimal
from uuid import uuid4


# ============================================================================
# UNIT TESTS: MaxContracts Rule Logic
# ============================================================================


@pytest.mark.unit
@pytest.mark.p0
class TestMaxContractsRuleUnit:
    """Unit tests for MaxContracts rule logic (isolated)."""

    def test_rule_config_defaults(self):
        """Test: MaxContracts rule has proper configuration defaults."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.max_contracts import MaxContractsRule

        rule = MaxContractsRule(max_contracts=4)
        assert rule.enabled is True
        assert rule.max_contracts == 4
        assert rule.name == "MaxContracts"

    def test_rule_not_violated_within_limit(self, state_manager, account_id):
        """Test: Rule not violated when total contracts <= limit."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.max_contracts import MaxContractsRule
        from tests.conftest import Position

        # Setup: 3 contracts open, limit is 4
        state_manager.add_position(account_id, Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=state_manager.clock.now()
        ))
        state_manager.add_position(account_id, Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4500"),
            unrealized_pnl=Decimal("0"),
            opened_at=state_manager.clock.now()
        ))

        rule = MaxContractsRule(max_contracts=4)
        account_state = state_manager.get_account_state(account_id)

        # New fill would add 1 more (total = 4, exactly at limit)
        new_fill_event = {
            "symbol": "MNQ",
            "quantity": 1,
            "side": "long"
        }

        violation = rule.evaluate(new_fill_event, account_state)
        assert violation is None  # No violation

    def test_rule_violated_exceeds_limit(self, state_manager, account_id):
        """Test: Rule violated when total contracts > limit."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.max_contracts import MaxContractsRule
        from tests.conftest import Position

        # Setup: 3 contracts open, limit is 4
        state_manager.add_position(account_id, Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=3,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=state_manager.clock.now()
        ))

        rule = MaxContractsRule(max_contracts=4)
        account_state = state_manager.get_account_state(account_id)

        # New fill adds 2 more (total would be 5, exceeds limit by 1)
        new_fill_event = {
            "symbol": "ES",
            "quantity": 2,
            "side": "long"
        }

        violation = rule.evaluate(new_fill_event, account_state)
        assert violation is not None
        assert violation.rule_name == "MaxContracts"
        assert violation.severity == "high"
        assert "exceeds limit" in violation.reason.lower()

    def test_rule_enforcement_action_close_excess(self, state_manager, account_id):
        """Test: Enforcement action closes excess contracts (LIFO)."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.max_contracts import MaxContractsRule
        from tests.conftest import Position

        # Setup: limit is 4, but we have 5 contracts
        pos1 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=3,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos1)

        # Advance time 1 minute
        state_manager.clock.advance(minutes=1)

        pos2 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=2,
            entry_price=Decimal("4500"),
            current_price=Decimal("4500"),
            unrealized_pnl=Decimal("0"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos2)

        rule = MaxContractsRule(max_contracts=4)
        account_state = state_manager.get_account_state(account_id)

        # Trigger violation
        violation = rule.evaluate({"symbol": "ES", "quantity": 0}, account_state)
        action = rule.get_enforcement_action(violation)

        # Should close most recent position (pos2) by 1 contract (LIFO)
        assert action.action_type == "close_position"
        assert action.position_id == pos2.position_id
        assert action.quantity == 1  # Close 1 contract to bring total to 4

    def test_rule_applies_to_fill_events_only(self):
        """Test: Rule only evaluates fill events, ignores others."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.max_contracts import MaxContractsRule

        rule = MaxContractsRule(max_contracts=4)

        assert rule.applies_to_event("FILL") is True
        assert rule.applies_to_event("POSITION_UPDATE") is False
        assert rule.applies_to_event("CONNECTION_CHANGE") is False


# ============================================================================
# INTEGRATION TESTS: MaxContracts with Enforcement Engine
# ============================================================================


@pytest.mark.integration
@pytest.mark.p0
class TestMaxContractsIntegration:
    """Integration tests for MaxContracts rule with enforcement engine."""

    @pytest.mark.asyncio
    async def test_excess_contracts_closed_automatically(
        self,
        state_manager,
        broker,
        account_id
    ):
        """
        Test: When fill causes total to exceed limit, excess is closed.

        Scenario:
        - Limit: 4 contracts
        - Current: 2 MNQ long
        - New fill: 3 ES long
        - Expected: 1 ES closed immediately (total = 4)
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.max_contracts import MaxContractsRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Position, Event

        # Setup enforcement engine
        enforcement = EnforcementEngine(broker, state_manager)

        # Setup risk engine with MaxContracts rule
        rule = MaxContractsRule(max_contracts=4)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Add existing position: 2 MNQ
        pos1 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos1)

        # Simulate fill event: 3 ES long (would make total = 5)
        fill_event = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=state_manager.clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "symbol": "ES",
                "side": "long",
                "quantity": 3,
                "fill_price": Decimal("4500"),
                "order_id": "ORD123",
                "fill_time": state_manager.clock.now()
            }
        )

        # Process event through risk engine
        await risk_engine.process_event(fill_event)

        # Verify enforcement: should close 1 ES contract
        assert len(broker.close_position_calls) == 1
        close_call = broker.close_position_calls[0]
        assert close_call["quantity"] == 1

        # Verify total contracts now at limit
        total_contracts = state_manager.get_position_count(account_id)
        assert total_contracts == 4

    @pytest.mark.asyncio
    async def test_multiple_excess_contracts_all_closed(
        self,
        state_manager,
        broker,
        account_id
    ):
        """
        Test: When fill causes multiple excess contracts, all are closed.

        Scenario:
        - Limit: 4 contracts
        - Current: 2 MNQ long
        - New fill: 5 ES long (would make total = 7, excess = 3)
        - Expected: Close 3 ES contracts (total = 4)
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.max_contracts import MaxContractsRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Position, Event

        enforcement = EnforcementEngine(broker, state_manager)
        rule = MaxContractsRule(max_contracts=4)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Existing: 2 MNQ
        pos1 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos1)

        # New fill: 5 ES (total would be 7)
        fill_event = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=state_manager.clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "symbol": "ES",
                "side": "long",
                "quantity": 5,
                "fill_price": Decimal("4500"),
                "order_id": "ORD124",
                "fill_time": state_manager.clock.now()
            }
        )

        await risk_engine.process_event(fill_event)

        # Should close 3 contracts to bring total to 4
        assert len(broker.close_position_calls) == 1
        close_call = broker.close_position_calls[0]
        assert close_call["quantity"] == 3

        total_contracts = state_manager.get_position_count(account_id)
        assert total_contracts == 4


# ============================================================================
# E2E TESTS: MaxContracts Happy Path
# ============================================================================


@pytest.mark.e2e
@pytest.mark.p0
class TestMaxContractsE2E:
    """End-to-end tests for MaxContracts rule (full system flow)."""

    @pytest.mark.asyncio
    async def test_happy_path_trader_stays_within_limit(
        self,
        state_manager,
        broker,
        notifier,
        account_id
    ):
        """
        Test: Happy path - trader opens positions within limit, no enforcement.

        Flow:
        1. Trader opens 2 MNQ
        2. Trader opens 1 ES (total = 3, within limit of 4)
        3. No enforcement actions taken
        4. No notifications sent
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.max_contracts import MaxContractsRule
        from tests.conftest import Event

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = MaxContractsRule(max_contracts=4)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Fill 1: 2 MNQ
        fill1 = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=state_manager.clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "symbol": "MNQ",
                "side": "long",
                "quantity": 2,
                "fill_price": Decimal("18000"),
                "order_id": "ORD1",
                "fill_time": state_manager.clock.now()
            }
        )
        await risk_engine.process_event(fill1)

        # Fill 2: 1 ES
        state_manager.clock.advance(seconds=30)
        fill2 = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=state_manager.clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "symbol": "ES",
                "side": "long",
                "quantity": 1,
                "fill_price": Decimal("4500"),
                "order_id": "ORD2",
                "fill_time": state_manager.clock.now()
            }
        )
        await risk_engine.process_event(fill2)

        # Verify: No enforcement actions
        assert len(broker.close_position_calls) == 0
        assert len(broker.flatten_account_calls) == 0

        # Verify: No notifications
        assert len(notifier.get_notifications(account_id)) == 0

        # Verify: Total contracts = 3
        total = state_manager.get_position_count(account_id)
        assert total == 3

    @pytest.mark.asyncio
    async def test_enforcement_with_notification(
        self,
        state_manager,
        broker,
        notifier,
        account_id
    ):
        """
        Test: When rule violated, enforcement occurs AND trader notified.

        Flow:
        1. Limit: 4 contracts
        2. Open 3 MNQ
        3. Open 3 ES (total would be 6, excess = 2)
        4. System closes 2 ES immediately
        5. Trader receives notification with reason
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.max_contracts import MaxContractsRule
        from tests.conftest import Event

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = MaxContractsRule(max_contracts=4)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Existing: 3 MNQ
        fill1 = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=state_manager.clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "symbol": "MNQ",
                "side": "long",
                "quantity": 3,
                "fill_price": Decimal("18000"),
                "order_id": "ORD1",
                "fill_time": state_manager.clock.now()
            }
        )
        await risk_engine.process_event(fill1)

        # New fill: 3 ES (would exceed)
        state_manager.clock.advance(seconds=60)
        fill2 = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=state_manager.clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "symbol": "ES",
                "side": "long",
                "quantity": 3,
                "fill_price": Decimal("4500"),
                "order_id": "ORD2",
                "fill_time": state_manager.clock.now()
            }
        )
        await risk_engine.process_event(fill2)

        # Verify enforcement
        assert len(broker.close_position_calls) == 1
        assert broker.close_position_calls[0]["quantity"] == 2

        # Verify notification sent
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) == 1

        notif = notifications[0]
        assert notif.severity == "warning"
        assert "MaxContracts" in notif.reason
        assert "limit" in notif.reason.lower()
        assert notif.action == "close_position"
