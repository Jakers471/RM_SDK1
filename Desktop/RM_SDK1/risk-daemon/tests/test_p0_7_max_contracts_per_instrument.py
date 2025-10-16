"""
P0-7: MaxContractsPerInstrument Rule Tests

Tests the MaxContractsPerInstrument rule that enforces per-symbol position limits.
Tests follow TDD principles - all tests FAIL initially until implementation exists.

Architecture reference: docs/architecture/02-risk-engine.md (Rule 7: MaxContractsPerInstrument)

Rule Behavior:
- Configured per-symbol limits (e.g., MNQ: 2, ES: 1, NQ: 1)
- Checks total quantity for each symbol independently
- LIFO closing of excess contracts for that specific symbol
- Triggered on FILL events
"""

import pytest
from decimal import Decimal
from uuid import uuid4


# ============================================================================
# UNIT TESTS: MaxContractsPerInstrument Rule Logic
# ============================================================================


@pytest.mark.unit
@pytest.mark.p0
class TestMaxContractsPerInstrumentRuleUnit:
    """Unit tests for MaxContractsPerInstrument rule logic (isolated)."""

    def test_rule_config_defaults(self):
        """Test: MaxContractsPerInstrument rule has proper configuration defaults."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.max_contracts_per_instrument import MaxContractsPerInstrumentRule

        symbol_limits = {
            "MNQ": 2,
            "ES": 1,
            "NQ": 1
        }
        rule = MaxContractsPerInstrumentRule(symbol_limits=symbol_limits)
        assert rule.enabled is True
        assert rule.symbol_limits == symbol_limits
        assert rule.name == "MaxContractsPerInstrument"

    def test_rule_not_violated_within_limit(self, state_manager, account_id):
        """Test: Rule not violated when symbol quantity <= limit."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.max_contracts_per_instrument import MaxContractsPerInstrumentRule
        from tests.conftest import Position

        # Setup: 1 MNQ open, limit is 2
        state_manager.add_position(account_id, Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=1,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=state_manager.clock.now()
        ))

        symbol_limits = {"MNQ": 2, "ES": 1}
        rule = MaxContractsPerInstrumentRule(symbol_limits=symbol_limits)
        account_state = state_manager.get_account_state(account_id)

        # New fill would add 1 more MNQ (total = 2, exactly at limit)
        new_fill_event = {
            "symbol": "MNQ",
            "quantity": 1,
            "side": "long"
        }

        violation = rule.evaluate(new_fill_event, account_state)
        assert violation is None  # No violation

    def test_rule_violated_exceeds_symbol_limit(self, state_manager, account_id):
        """Test: Rule violated when symbol quantity > limit."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.max_contracts_per_instrument import MaxContractsPerInstrumentRule
        from tests.conftest import Position

        # Setup: 1 ES open, limit is 1
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

        symbol_limits = {"MNQ": 2, "ES": 1}
        rule = MaxContractsPerInstrumentRule(symbol_limits=symbol_limits)
        account_state = state_manager.get_account_state(account_id)

        # New fill adds 1 more ES (total would be 2, exceeds limit of 1)
        new_fill_event = {
            "symbol": "ES",
            "quantity": 1,
            "side": "long"
        }

        violation = rule.evaluate(new_fill_event, account_state)
        assert violation is not None
        assert violation.rule_name == "MaxContractsPerInstrument"
        assert violation.severity == "high"
        assert "ES" in violation.reason
        assert "exceeds limit" in violation.reason.lower()

    def test_rule_enforcement_action_close_excess_lifo(self, state_manager, account_id):
        """Test: Enforcement action closes excess contracts (LIFO) for specific symbol."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.max_contracts_per_instrument import MaxContractsPerInstrumentRule
        from tests.conftest import Position

        # Setup: limit is 2 for MNQ, but we have 3 MNQ contracts across 2 positions
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

        # Advance time 1 minute
        state_manager.clock.advance(minutes=1)

        pos2 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=1,
            entry_price=Decimal("18010"),
            current_price=Decimal("18010"),
            unrealized_pnl=Decimal("0"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos2)

        symbol_limits = {"MNQ": 2, "ES": 1}
        rule = MaxContractsPerInstrumentRule(symbol_limits=symbol_limits)
        account_state = state_manager.get_account_state(account_id)

        # Trigger violation
        violation = rule.evaluate({"symbol": "MNQ", "quantity": 0}, account_state)
        action = rule.get_enforcement_action(violation)

        # Should close most recent MNQ position (pos2) by 1 contract (LIFO)
        assert action.action_type == "close_position"
        assert action.position_id == pos2.position_id
        assert action.quantity == 1

    def test_rule_applies_to_fill_events_only(self):
        """Test: Rule only evaluates fill events, ignores others."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.max_contracts_per_instrument import MaxContractsPerInstrumentRule

        symbol_limits = {"MNQ": 2, "ES": 1}
        rule = MaxContractsPerInstrumentRule(symbol_limits=symbol_limits)

        assert rule.applies_to_event("FILL") is True
        assert rule.applies_to_event("POSITION_UPDATE") is False
        assert rule.applies_to_event("CONNECTION_CHANGE") is False

    def test_rule_handles_unconfigured_symbol(self, state_manager, account_id):
        """Test: Symbols without configured limits are allowed (no restriction)."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.max_contracts_per_instrument import MaxContractsPerInstrumentRule

        # Limits only define MNQ and ES
        symbol_limits = {"MNQ": 2, "ES": 1}
        rule = MaxContractsPerInstrumentRule(symbol_limits=symbol_limits)
        account_state = state_manager.get_account_state(account_id)

        # Fill for unconfigured symbol (NQ) - should not violate
        new_fill_event = {
            "symbol": "NQ",  # Not in limits
            "quantity": 10,
            "side": "long"
        }

        violation = rule.evaluate(new_fill_event, account_state)
        assert violation is None  # No violation for unconfigured symbols

    def test_rule_different_symbols_independent(self, state_manager, account_id):
        """Test: Limits for different symbols are independent."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.max_contracts_per_instrument import MaxContractsPerInstrumentRule
        from tests.conftest import Position

        # Setup: 2 MNQ, 1 ES (both at their respective limits)
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

        symbol_limits = {"MNQ": 2, "ES": 1}
        rule = MaxContractsPerInstrumentRule(symbol_limits=symbol_limits)
        account_state = state_manager.get_account_state(account_id)

        # Adding another MNQ would violate MNQ limit
        mnq_fill = {"symbol": "MNQ", "quantity": 1, "side": "long"}
        violation_mnq = rule.evaluate(mnq_fill, account_state)
        assert violation_mnq is not None

        # Adding another ES would violate ES limit
        es_fill = {"symbol": "ES", "quantity": 1, "side": "long"}
        violation_es = rule.evaluate(es_fill, account_state)
        assert violation_es is not None


# ============================================================================
# INTEGRATION TESTS: MaxContractsPerInstrument with Enforcement Engine
# ============================================================================


@pytest.mark.integration
@pytest.mark.p0
class TestMaxContractsPerInstrumentIntegration:
    """Integration tests for MaxContractsPerInstrument rule with enforcement engine."""

    @pytest.mark.asyncio
    async def test_excess_symbol_contracts_closed_automatically(
        self,
        state_manager,
        broker,
        account_id
    ):
        """
        Test: When fill causes symbol total to exceed limit, excess is closed.

        Scenario:
        - Limit: MNQ = 2
        - Current: 1 MNQ long
        - New fill: 2 MNQ long
        - Expected: 1 MNQ closed immediately (total = 2)
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.max_contracts_per_instrument import MaxContractsPerInstrumentRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Position, Event

        enforcement = EnforcementEngine(broker, state_manager)
        symbol_limits = {"MNQ": 2, "ES": 1}
        rule = MaxContractsPerInstrumentRule(symbol_limits=symbol_limits)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Add existing position: 1 MNQ
        pos1 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=1,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos1)

        # Simulate fill event: 2 MNQ long (would make total = 3)
        fill_event = Event(
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
                "fill_price": Decimal("18010"),
                "order_id": "ORD123",
                "fill_time": state_manager.clock.now()
            }
        )

        await risk_engine.process_event(fill_event)

        # Verify enforcement: should close 1 MNQ contract
        assert len(broker.close_position_calls) == 1
        close_call = broker.close_position_calls[0]
        assert close_call["quantity"] == 1

        # Verify total MNQ contracts now at limit
        total_mnq = state_manager.get_position_count_by_symbol(account_id, "MNQ")
        assert total_mnq == 2

    @pytest.mark.asyncio
    async def test_multiple_symbols_enforced_independently(
        self,
        state_manager,
        broker,
        account_id
    ):
        """
        Test: Different symbols have independent limits.

        Scenario:
        - Limits: MNQ = 2, ES = 1
        - Current: 2 MNQ (at limit), 0 ES
        - Fill 1: 1 ES → OK (ES now at limit)
        - Fill 2: 1 ES → Violates, close 1 ES
        - MNQ positions unaffected
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.max_contracts_per_instrument import MaxContractsPerInstrumentRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Position, Event

        enforcement = EnforcementEngine(broker, state_manager)
        symbol_limits = {"MNQ": 2, "ES": 1}
        rule = MaxContractsPerInstrumentRule(symbol_limits=symbol_limits)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Existing: 2 MNQ (at limit)
        pos_mnq = Position(
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
        state_manager.add_position(account_id, pos_mnq)

        # Fill 1: 1 ES (OK)
        fill1 = Event(
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
                "order_id": "ORD1",
                "fill_time": state_manager.clock.now()
            }
        )
        await risk_engine.process_event(fill1)

        # No enforcement yet
        assert len(broker.close_position_calls) == 0

        # Add ES position
        pos_es1 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4500"),
            unrealized_pnl=Decimal("0"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos_es1)

        # Fill 2: 1 more ES (would exceed)
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
                "fill_price": Decimal("4505"),
                "order_id": "ORD2",
                "fill_time": state_manager.clock.now()
            }
        )
        await risk_engine.process_event(fill2)

        # Should close 1 ES contract
        assert len(broker.close_position_calls) == 1
        close_call = broker.close_position_calls[0]
        assert close_call["quantity"] == 1

        # Verify: MNQ unaffected, ES at limit
        total_mnq = state_manager.get_position_count_by_symbol(account_id, "MNQ")
        total_es = state_manager.get_position_count_by_symbol(account_id, "ES")
        assert total_mnq == 2
        assert total_es == 1

    @pytest.mark.asyncio
    async def test_lifo_closing_correct_position(
        self,
        state_manager,
        broker,
        account_id
    ):
        """
        Test: LIFO ensures most recent position for symbol is closed.

        Scenario:
        - Limit: ES = 2
        - T=0: Open ES position A (1 contract)
        - T=60: Open ES position B (1 contract)
        - T=120: Open ES position C (2 contracts)
        - Total: 4 ES (excess: 2)
        - Expected: Close position C (most recent) by 2 contracts
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.max_contracts_per_instrument import MaxContractsPerInstrumentRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Position, Event

        enforcement = EnforcementEngine(broker, state_manager)
        symbol_limits = {"ES": 2}
        rule = MaxContractsPerInstrumentRule(symbol_limits=symbol_limits)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Position A: T=0
        pos_a = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4500"),
            unrealized_pnl=Decimal("0"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos_a)

        # Position B: T=60
        state_manager.clock.advance(seconds=60)
        pos_b = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4502"),
            current_price=Decimal("4502"),
            unrealized_pnl=Decimal("0"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos_b)

        # Position C: T=120 (2 contracts - would exceed)
        state_manager.clock.advance(seconds=60)
        fill_c = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=state_manager.clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "symbol": "ES",
                "side": "long",
                "quantity": 2,
                "fill_price": Decimal("4505"),
                "order_id": "ORD_C",
                "fill_time": state_manager.clock.now()
            }
        )

        pos_c_id = uuid4()
        pos_c = Position(
            position_id=pos_c_id,
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=2,
            entry_price=Decimal("4505"),
            current_price=Decimal("4505"),
            unrealized_pnl=Decimal("0"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos_c)

        await risk_engine.process_event(fill_c)

        # Should close position C (most recent) by 2 contracts
        assert len(broker.close_position_calls) == 1
        close_call = broker.close_position_calls[0]
        assert close_call["position_id"] == pos_c_id
        assert close_call["quantity"] == 2


# ============================================================================
# E2E TESTS: MaxContractsPerInstrument Happy Path
# ============================================================================


@pytest.mark.e2e
@pytest.mark.p0
class TestMaxContractsPerInstrumentE2E:
    """End-to-end tests for MaxContractsPerInstrument rule (full system flow)."""

    @pytest.mark.asyncio
    async def test_happy_path_trader_stays_within_symbol_limits(
        self,
        state_manager,
        broker,
        notifier,
        account_id
    ):
        """
        Test: Happy path - trader respects per-symbol limits, no enforcement.

        Flow:
        1. Limits: MNQ = 2, ES = 1
        2. Open 2 MNQ (at limit)
        3. Open 1 ES (at limit)
        4. No enforcement actions taken
        5. No notifications sent
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.max_contracts_per_instrument import MaxContractsPerInstrumentRule
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        symbol_limits = {"MNQ": 2, "ES": 1}
        rule = MaxContractsPerInstrumentRule(symbol_limits=symbol_limits)
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

        # Add position
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

        # Add position
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

        # Verify: No enforcement actions
        assert len(broker.close_position_calls) == 0
        assert len(broker.flatten_account_calls) == 0

        # Verify: No notifications
        assert len(notifier.get_notifications(account_id)) == 0

        # Verify: Positions at limits
        total_mnq = state_manager.get_position_count_by_symbol(account_id, "MNQ")
        total_es = state_manager.get_position_count_by_symbol(account_id, "ES")
        assert total_mnq == 2
        assert total_es == 1

    @pytest.mark.asyncio
    async def test_enforcement_with_notification(
        self,
        state_manager,
        broker,
        notifier,
        account_id
    ):
        """
        Test: When symbol limit violated, enforcement occurs AND trader notified.

        Flow:
        1. Limit: MNQ = 2
        2. Open 2 MNQ
        3. Open 2 more MNQ (total would be 4, excess = 2)
        4. System closes 2 MNQ immediately
        5. Trader receives notification with symbol-specific reason
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.max_contracts_per_instrument import MaxContractsPerInstrumentRule
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        symbol_limits = {"MNQ": 2}
        rule = MaxContractsPerInstrumentRule(symbol_limits=symbol_limits)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Existing: 2 MNQ
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

        # New fill: 2 more MNQ (would exceed)
        state_manager.clock.advance(seconds=60)
        fill = Event(
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
                "fill_price": Decimal("18010"),
                "order_id": "ORD2",
                "fill_time": state_manager.clock.now()
            }
        )

        # Add position
        state_manager.add_position(account_id, Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18010"),
            current_price=Decimal("18010"),
            unrealized_pnl=Decimal("0"),
            opened_at=state_manager.clock.now()
        ))

        await risk_engine.process_event(fill)

        # Verify enforcement
        assert len(broker.close_position_calls) == 1
        assert broker.close_position_calls[0]["quantity"] == 2

        # Verify notification sent
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) == 1

        notif = notifications[0]
        assert notif.severity == "warning"
        assert "MaxContractsPerInstrument" in notif.reason or "MNQ" in notif.reason
        assert "limit" in notif.reason.lower()
        assert notif.action == "close_position"
