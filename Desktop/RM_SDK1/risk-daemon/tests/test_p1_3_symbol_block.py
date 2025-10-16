"""
P1-3: SymbolBlock Rule Tests

Tests the SymbolBlock rule that enforces symbol blacklisting.
Tests follow TDD principles - all tests FAIL initially until implementation exists.

Architecture reference: docs/architecture/02-risk-engine.md (Rule: SymbolBlock)

Rule Behavior:
- Configurable blacklist of symbols (e.g., ["TSLA", "AAPL", "AMZN"])
- Any fill on blacklisted symbol: Auto-close position immediately
- Can be configured dynamically (add/remove symbols)
- Applies to FILL events
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import timedelta


# ============================================================================
# UNIT TESTS: SymbolBlock Rule Logic
# ============================================================================


@pytest.mark.unit
@pytest.mark.p1
class TestSymbolBlockRuleUnit:
    """Unit tests for SymbolBlock rule logic (isolated)."""

    def test_rule_config_defaults(self):
        """Test: SymbolBlock rule has proper configuration defaults."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.symbol_block import SymbolBlockRule

        rule = SymbolBlockRule(blocked_symbols=["TSLA", "AAPL"])
        assert rule.enabled is True
        assert rule.blocked_symbols == ["TSLA", "AAPL"]
        assert rule.name == "SymbolBlock"

    def test_rule_not_violated_symbol_allowed(self, state_manager, account_id):
        """Test: Rule not violated when symbol is allowed."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.symbol_block import SymbolBlockRule

        rule = SymbolBlockRule(blocked_symbols=["TSLA", "AAPL"])
        account_state = state_manager.get_account_state(account_id)

        # Fill for allowed symbol
        fill_event = {
            "symbol": "MNQ",
            "quantity": 2,
            "side": "long"
        }

        violation = rule.evaluate(fill_event, account_state)
        assert violation is None  # No violation

    def test_rule_violated_symbol_blocked(self, state_manager, account_id):
        """Test: Rule violated when symbol is blocked."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.symbol_block import SymbolBlockRule

        rule = SymbolBlockRule(blocked_symbols=["TSLA", "AAPL", "AMZN"])
        account_state = state_manager.get_account_state(account_id)

        # Fill for blocked symbol
        fill_event = {
            "symbol": "TSLA",
            "quantity": 10,
            "side": "long"
        }

        violation = rule.evaluate(fill_event, account_state)
        assert violation is not None
        assert violation.rule_name == "SymbolBlock"
        assert violation.severity == "high"
        assert "blocked symbol" in violation.reason.lower()
        assert "TSLA" in violation.reason

    def test_rule_enforcement_action_close_position(self, state_manager, account_id, clock):
        """Test: Enforcement action closes position on blocked symbol."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.symbol_block import SymbolBlockRule
        from tests.conftest import Position

        # Create position on blocked symbol
        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="AAPL",
            side="long",
            quantity=10,
            entry_price=Decimal("180.00"),
            current_price=Decimal("180.00"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now()
        )
        state_manager.add_position(account_id, position)

        rule = SymbolBlockRule(blocked_symbols=["AAPL", "TSLA"])
        account_state = state_manager.get_account_state(account_id)

        # Trigger violation
        fill_event = {"symbol": "AAPL", "quantity": 10}
        violation = rule.evaluate(fill_event, account_state)
        action = rule.get_enforcement_action(violation)

        # Should close entire position
        assert action.action_type == "close_position"
        assert action.position_id == position.position_id
        assert action.quantity == 10

    def test_rule_case_insensitive_symbol_matching(self, state_manager, account_id):
        """Test: Symbol matching is case-insensitive."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.symbol_block import SymbolBlockRule

        rule = SymbolBlockRule(blocked_symbols=["TSLA", "aapl", "AmZn"])
        account_state = state_manager.get_account_state(account_id)

        # Test uppercase
        fill1 = {"symbol": "TSLA", "quantity": 1}
        violation1 = rule.evaluate(fill1, account_state)
        assert violation1 is not None

        # Test lowercase
        fill2 = {"symbol": "aapl", "quantity": 1}
        violation2 = rule.evaluate(fill2, account_state)
        assert violation2 is not None

        # Test mixed case
        fill3 = {"symbol": "AmZn", "quantity": 1}
        violation3 = rule.evaluate(fill3, account_state)
        assert violation3 is not None

        # Test non-blocked
        fill4 = {"symbol": "MNQ", "quantity": 1}
        violation4 = rule.evaluate(fill4, account_state)
        assert violation4 is None

    def test_rule_applies_to_fill_events_only(self):
        """Test: Rule only evaluates fill events."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.symbol_block import SymbolBlockRule

        rule = SymbolBlockRule(blocked_symbols=["TSLA"])

        assert rule.applies_to_event("FILL") is True
        assert rule.applies_to_event("POSITION_UPDATE") is False
        assert rule.applies_to_event("TIME_TICK") is False

    def test_rule_dynamic_symbol_management(self):
        """Test: Symbols can be added/removed dynamically."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.symbol_block import SymbolBlockRule

        rule = SymbolBlockRule(blocked_symbols=["TSLA"])

        # Add symbol
        rule.add_blocked_symbol("AAPL")
        assert "AAPL" in rule.blocked_symbols

        # Remove symbol
        rule.remove_blocked_symbol("TSLA")
        assert "TSLA" not in rule.blocked_symbols

        # Verify remaining
        assert rule.blocked_symbols == ["AAPL"]

    def test_rule_empty_blacklist_allows_all(self, state_manager, account_id):
        """Test: Empty blacklist allows all symbols."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.symbol_block import SymbolBlockRule

        rule = SymbolBlockRule(blocked_symbols=[])
        account_state = state_manager.get_account_state(account_id)

        # Any symbol should be allowed
        fill = {"symbol": "TSLA", "quantity": 10}
        violation = rule.evaluate(fill, account_state)
        assert violation is None

    def test_rule_handles_multiple_positions_same_blocked_symbol(
        self,
        state_manager,
        account_id,
        clock
    ):
        """Test: Multiple positions on same blocked symbol all closed."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.symbol_block import SymbolBlockRule
        from tests.conftest import Position

        # Create 2 positions on TSLA
        pos1 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="TSLA",
            side="long",
            quantity=10,
            entry_price=Decimal("180.00"),
            current_price=Decimal("180.00"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now()
        )
        state_manager.add_position(account_id, pos1)

        pos2 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="TSLA",
            side="short",
            quantity=5,
            entry_price=Decimal("185.00"),
            current_price=Decimal("185.00"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now()
        )
        state_manager.add_position(account_id, pos2)

        rule = SymbolBlockRule(blocked_symbols=["TSLA"])
        account_state = state_manager.get_account_state(account_id)

        # Evaluate should detect both positions
        fill_event = {"symbol": "TSLA", "quantity": 10}
        violation = rule.evaluate(fill_event, account_state)

        # Should indicate multiple positions need closing
        assert violation is not None
        assert violation.data.get("positions_count", 0) >= 2


# ============================================================================
# INTEGRATION TESTS: SymbolBlock with Enforcement Engine
# ============================================================================


@pytest.mark.integration
@pytest.mark.p1
class TestSymbolBlockIntegration:
    """Integration tests for SymbolBlock rule with enforcement engine."""

    @pytest.mark.asyncio
    async def test_blocked_symbol_position_closed_immediately(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: Position on blocked symbol closed immediately.

        Scenario:
        - Blocked symbols: ["TSLA", "AAPL"]
        - Fill on TSLA
        - Position closed immediately
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.symbol_block import SymbolBlockRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager)
        rule = SymbolBlockRule(blocked_symbols=["TSLA", "AAPL"])
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Create position on TSLA (simulating fill)
        position_id = uuid4()
        position = Position(
            position_id=position_id,
            account_id=account_id,
            symbol="TSLA",
            side="long",
            quantity=10,
            entry_price=Decimal("180.00"),
            current_price=Decimal("180.00"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now()
        )
        state_manager.add_position(account_id, position)

        # Fill event on blocked symbol
        fill_event = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "symbol": "TSLA",
                "side": "long",
                "quantity": 10,
                "fill_price": Decimal("180.00"),
                "order_id": "ORD123"
            }
        )
        await risk_engine.process_event(fill_event)

        # Verify: Position closed immediately
        assert len(broker.close_position_calls) == 1
        close_call = broker.close_position_calls[0]
        assert close_call["position_id"] == position_id
        assert close_call["quantity"] == 10

    @pytest.mark.asyncio
    async def test_allowed_symbols_not_affected(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: Allowed symbols not affected by blacklist.

        Scenario:
        - Blocked: ["TSLA"]
        - Fill on MNQ (allowed)
        - No enforcement
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.symbol_block import SymbolBlockRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager)
        rule = SymbolBlockRule(blocked_symbols=["TSLA"])
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Fill on allowed symbol
        fill_event = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "symbol": "MNQ",
                "side": "long",
                "quantity": 2,
                "fill_price": Decimal("18000.00"),
                "order_id": "ORD124"
            }
        )
        await risk_engine.process_event(fill_event)

        # Verify: No enforcement
        assert len(broker.close_position_calls) == 0

    @pytest.mark.asyncio
    async def test_multiple_blocked_symbols_all_enforced(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: All symbols in blacklist are enforced.

        Scenario:
        - Blocked: ["TSLA", "AAPL", "AMZN"]
        - Fill on each
        - All closed
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.symbol_block import SymbolBlockRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager)
        rule = SymbolBlockRule(blocked_symbols=["TSLA", "AAPL", "AMZN"])
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Fill on each blocked symbol
        for symbol in ["TSLA", "AAPL", "AMZN"]:
            position = Position(
                position_id=uuid4(),
                account_id=account_id,
                symbol=symbol,
                side="long",
                quantity=10,
                entry_price=Decimal("100.00"),
                current_price=Decimal("100.00"),
                unrealized_pnl=Decimal("0"),
                opened_at=clock.now()
            )
            state_manager.add_position(account_id, position)

            fill = Event(
                event_id=uuid4(),
                event_type="FILL",
                timestamp=clock.now(),
                priority=2,
                account_id=account_id,
                source="broker",
                data={
                    "symbol": symbol,
                    "side": "long",
                    "quantity": 10,
                    "fill_price": Decimal("100.00"),
                    "order_id": f"ORD_{symbol}"
                }
            )
            await risk_engine.process_event(fill)

        # Verify: All 3 positions closed
        assert len(broker.close_position_calls) == 3


# ============================================================================
# E2E TESTS: SymbolBlock Happy Path
# ============================================================================


@pytest.mark.e2e
@pytest.mark.p1
class TestSymbolBlockE2E:
    """End-to-end tests for SymbolBlock rule (full system flow)."""

    @pytest.mark.asyncio
    async def test_happy_path_trader_avoids_blocked_symbols(
        self,
        state_manager,
        broker,
        notifier,
        account_id,
        clock
    ):
        """
        Test: Happy path - trader only trades allowed symbols.

        Flow:
        1. Blacklist: ["TSLA", "AAPL"]
        2. Trader opens MNQ, ES, NQ (all allowed)
        3. No enforcement actions
        4. No notifications
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.symbol_block import SymbolBlockRule
        from tests.conftest import Event

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = SymbolBlockRule(blocked_symbols=["TSLA", "AAPL"])
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Fill 1: MNQ (allowed)
        fill1 = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "symbol": "MNQ",
                "side": "long",
                "quantity": 2,
                "fill_price": Decimal("18000.00"),
                "order_id": "ORD1"
            }
        )
        await risk_engine.process_event(fill1)

        # Fill 2: ES (allowed)
        fill2 = Event(
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
                "fill_price": Decimal("4500.00"),
                "order_id": "ORD2"
            }
        )
        await risk_engine.process_event(fill2)

        # Verify: No enforcement
        assert len(broker.close_position_calls) == 0

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
        Test: When blocked symbol traded, position closed AND trader notified.

        Flow:
        1. Blacklist: ["TSLA"]
        2. Fill on TSLA (10 shares)
        3. Position closed immediately
        4. Trader receives critical notification
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.symbol_block import SymbolBlockRule
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = SymbolBlockRule(blocked_symbols=["TSLA"])
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Create position on TSLA
        position_id = uuid4()
        position = Position(
            position_id=position_id,
            account_id=account_id,
            symbol="TSLA",
            side="long",
            quantity=10,
            entry_price=Decimal("180.00"),
            current_price=Decimal("180.00"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now()
        )
        state_manager.add_position(account_id, position)

        # Fill event
        fill_event = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "symbol": "TSLA",
                "side": "long",
                "quantity": 10,
                "fill_price": Decimal("180.00"),
                "order_id": "ORD_TSLA"
            }
        )
        await risk_engine.process_event(fill_event)

        # Verify enforcement
        assert len(broker.close_position_calls) == 1
        assert broker.close_position_calls[0]["position_id"] == position_id

        # Verify notification
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) == 1

        notif = notifications[0]
        assert notif.severity == "critical"
        assert "SymbolBlock" in notif.reason or "blocked symbol" in notif.reason.lower()
        assert "TSLA" in notif.reason
        assert notif.action == "close_position"

    @pytest.mark.asyncio
    async def test_dynamic_blacklist_update(
        self,
        state_manager,
        broker,
        notifier,
        account_id,
        clock
    ):
        """
        Test: Blacklist can be updated dynamically during operation.

        Flow:
        1. Initial blacklist: ["TSLA"]
        2. Fill on AAPL (allowed) → OK
        3. Add AAPL to blacklist
        4. Fill on AAPL → Blocked
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.symbol_block import SymbolBlockRule
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = SymbolBlockRule(blocked_symbols=["TSLA"])
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Fill on AAPL (currently allowed)
        fill1 = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "symbol": "AAPL",
                "side": "long",
                "quantity": 10,
                "fill_price": Decimal("170.00"),
                "order_id": "ORD1"
            }
        )
        await risk_engine.process_event(fill1)

        # Verify: No enforcement
        assert len(broker.close_position_calls) == 0

        # Add AAPL to blacklist
        rule.add_blocked_symbol("AAPL")

        # Create position on AAPL
        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="AAPL",
            side="long",
            quantity=10,
            entry_price=Decimal("170.00"),
            current_price=Decimal("170.00"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now()
        )
        state_manager.add_position(account_id, position)

        # Fill on AAPL (now blocked)
        fill2 = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "symbol": "AAPL",
                "side": "long",
                "quantity": 10,
                "fill_price": Decimal("171.00"),
                "order_id": "ORD2"
            }
        )
        await risk_engine.process_event(fill2)

        # Verify: Enforcement triggered
        assert len(broker.close_position_calls) == 1

        # Verify: Notification sent
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) >= 1
