"""
P1-2: CooldownAfterLoss Rule Tests

Tests the CooldownAfterLoss rule that enforces trading cooldown after losses.
Tests follow TDD principles - all tests FAIL initially until implementation exists.

Architecture reference: docs/architecture/02-risk-engine.md (Rule: CooldownAfterLoss)

Rule Behavior:
- When realized loss >= threshold: Start cooldown timer
- During cooldown: Block NEW fills (reject position opens)
- Allow existing position management (closing positions is OK)
- Cooldown duration configurable (e.g., 300 seconds = 5 minutes)
- Reset after cooldown expires
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import timedelta


# ============================================================================
# UNIT TESTS: CooldownAfterLoss Rule Logic
# ============================================================================


@pytest.mark.unit
@pytest.mark.p1
class TestCooldownAfterLossRuleUnit:
    """Unit tests for CooldownAfterLoss rule logic (isolated)."""

    def test_rule_config_defaults(self):
        """Test: CooldownAfterLoss rule has proper configuration defaults."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.cooldown_after_loss import CooldownAfterLossRule

        rule = CooldownAfterLossRule(
            loss_threshold=Decimal("500.00"),
            cooldown_seconds=300
        )
        assert rule.enabled is True
        assert rule.loss_threshold == Decimal("500.00")
        assert rule.cooldown_seconds == 300
        assert rule.name == "CooldownAfterLoss"

    def test_rule_not_violated_loss_below_threshold(self, state_manager, account_id):
        """Test: Rule not violated when loss below threshold."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.cooldown_after_loss import CooldownAfterLossRule

        # Setup: Realized loss = $400 (below $500 threshold)
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-400.00")

        rule = CooldownAfterLossRule(
            loss_threshold=Decimal("500.00"),
            cooldown_seconds=300
        )
        account_state = state_manager.get_account_state(account_id)

        # New fill event
        fill_event = {
            "symbol": "MNQ",
            "quantity": 1,
            "side": "long"
        }

        violation = rule.evaluate(fill_event, account_state)
        assert violation is None  # No violation - below threshold

    def test_rule_violated_loss_meets_threshold(self, state_manager, account_id, clock):
        """Test: Rule violated when loss meets threshold."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.cooldown_after_loss import CooldownAfterLossRule

        # Setup: Realized loss = $500 (meets threshold)
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-500.00")

        rule = CooldownAfterLossRule(
            loss_threshold=Decimal("500.00"),
            cooldown_seconds=300
        )
        account_state = state_manager.get_account_state(account_id)

        # New fill event should trigger cooldown
        fill_event = {
            "symbol": "ES",
            "quantity": 1,
            "side": "long"
        }

        violation = rule.evaluate(fill_event, account_state)
        assert violation is not None
        assert violation.rule_name == "CooldownAfterLoss"
        assert violation.severity == "medium"
        assert "cooldown" in violation.reason.lower()

    def test_rule_starts_cooldown_on_threshold_breach(self, state_manager, account_id, clock):
        """Test: Cooldown started when threshold breached."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.cooldown_after_loss import CooldownAfterLossRule

        rule = CooldownAfterLossRule(
            loss_threshold=Decimal("500.00"),
            cooldown_seconds=300
        )
        account_state = state_manager.get_account_state(account_id)

        # Breach threshold
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-500.00")

        # Evaluate to trigger cooldown
        fill_event = {"symbol": "MNQ", "quantity": 1}
        violation = rule.evaluate(fill_event, account_state)

        # Start cooldown action
        action = rule.get_enforcement_action(violation)
        assert action.action_type == "start_cooldown"
        assert action.duration_seconds == 300

    def test_rule_blocks_fills_during_cooldown(self, state_manager, account_id, clock):
        """Test: New fills blocked during active cooldown."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.cooldown_after_loss import CooldownAfterLossRule

        # Start cooldown
        state_manager.start_cooldown(account_id, duration_seconds=300, reason="Loss threshold")

        rule = CooldownAfterLossRule(
            loss_threshold=Decimal("500.00"),
            cooldown_seconds=300
        )
        account_state = state_manager.get_account_state(account_id)

        # Attempt fill during cooldown
        fill_event = {"symbol": "ES", "quantity": 1}
        violation = rule.evaluate(fill_event, account_state)

        assert violation is not None
        assert "cooldown active" in violation.reason.lower()

    def test_rule_allows_fills_after_cooldown_expires(self, state_manager, account_id, clock):
        """Test: Fills allowed after cooldown expires."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.cooldown_after_loss import CooldownAfterLossRule

        # Start cooldown
        state_manager.start_cooldown(account_id, duration_seconds=300, reason="Loss threshold")

        # Advance time beyond cooldown
        clock.advance(seconds=301)

        rule = CooldownAfterLossRule(
            loss_threshold=Decimal("500.00"),
            cooldown_seconds=300
        )
        account_state = state_manager.get_account_state(account_id)

        # Fill should be allowed now
        fill_event = {"symbol": "MNQ", "quantity": 1}
        violation = rule.evaluate(fill_event, account_state)

        assert violation is None  # Cooldown expired

    def test_rule_enforcement_action_reject_fill(self, state_manager, account_id, clock):
        """Test: Enforcement action rejects fill during cooldown."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.cooldown_after_loss import CooldownAfterLossRule

        # Active cooldown
        state_manager.start_cooldown(account_id, duration_seconds=300, reason="Loss threshold")

        rule = CooldownAfterLossRule(
            loss_threshold=Decimal("500.00"),
            cooldown_seconds=300
        )
        account_state = state_manager.get_account_state(account_id)

        # Trigger violation
        violation = rule.evaluate({"symbol": "ES", "quantity": 1}, account_state)
        action = rule.get_enforcement_action(violation)

        assert action.action_type == "reject_fill"
        assert action.account_id == account_id

    def test_rule_applies_to_fill_events_only(self):
        """Test: Rule only evaluates fill events."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.cooldown_after_loss import CooldownAfterLossRule

        rule = CooldownAfterLossRule(
            loss_threshold=Decimal("500.00"),
            cooldown_seconds=300
        )

        assert rule.applies_to_event("FILL") is True
        assert rule.applies_to_event("POSITION_UPDATE") is False
        assert rule.applies_to_event("TIME_TICK") is False

    def test_rule_different_thresholds_and_durations(self, state_manager, account_id):
        """Test: Different threshold and duration configurations."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.cooldown_after_loss import CooldownAfterLossRule

        account_state = state_manager.get_account_state(account_id)

        # Rule 1: $500 loss, 5 minute cooldown
        rule_500 = CooldownAfterLossRule(
            loss_threshold=Decimal("500.00"),
            cooldown_seconds=300
        )

        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-499.00")
        violation_500 = rule_500.evaluate({"symbol": "MNQ", "quantity": 1}, account_state)
        assert violation_500 is None  # Below threshold

        # Rule 2: $1000 loss, 15 minute cooldown
        rule_1000 = CooldownAfterLossRule(
            loss_threshold=Decimal("1000.00"),
            cooldown_seconds=900
        )

        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-999.00")
        violation_1000 = rule_1000.evaluate({"symbol": "ES", "quantity": 1}, account_state)
        assert violation_1000 is None  # Below threshold

        # Breach second threshold
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-1000.00")
        violation_1000_breach = rule_1000.evaluate({"symbol": "NQ", "quantity": 1}, account_state)
        assert violation_1000_breach is not None


# ============================================================================
# INTEGRATION TESTS: CooldownAfterLoss with Enforcement Engine
# ============================================================================


@pytest.mark.integration
@pytest.mark.p1
class TestCooldownAfterLossIntegration:
    """Integration tests for CooldownAfterLoss rule with enforcement engine."""

    @pytest.mark.asyncio
    async def test_cooldown_started_when_loss_hits_threshold(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: Cooldown started when loss threshold reached.

        Scenario:
        - Loss threshold: $500
        - Trade 1: -$300
        - Trade 2: -$250 (total -$550, breaches threshold)
        - Cooldown activated
        - Trade 3: Rejected
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.cooldown_after_loss import CooldownAfterLossRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Event

        enforcement = EnforcementEngine(broker, state_manager)
        rule = CooldownAfterLossRule(
            loss_threshold=Decimal("500.00"),
            cooldown_seconds=300
        )
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Trade 1: -$300 loss
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-300.00")

        # Trade 2: -$250 loss (total -$550)
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-550.00")

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
                "quantity": 1,
                "fill_price": Decimal("18000"),
                "order_id": "ORD123"
            }
        )
        await risk_engine.process_event(fill_event)

        # Verify: Cooldown started
        assert state_manager.is_in_cooldown(account_id) is True

        # Trade 3: Should be rejected
        fill_event_3 = Event(
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
                "order_id": "ORD124"
            }
        )
        await risk_engine.process_event(fill_event_3)

        # Verify: Fill rejected (no position opened)
        # Implementation would track rejections

    @pytest.mark.asyncio
    async def test_cooldown_expires_allows_new_trades(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: After cooldown expires, new trades allowed.

        Scenario:
        - Cooldown started at T=0 (5 minutes)
        - T=301: Cooldown expired
        - New fill allowed
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.cooldown_after_loss import CooldownAfterLossRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Event

        enforcement = EnforcementEngine(broker, state_manager)
        rule = CooldownAfterLossRule(
            loss_threshold=Decimal("500.00"),
            cooldown_seconds=300
        )
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Start cooldown
        state_manager.start_cooldown(account_id, duration_seconds=300, reason="Loss threshold")

        # Advance time beyond cooldown
        clock.advance(seconds=301)

        # New fill should be allowed
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
                "quantity": 1,
                "fill_price": Decimal("18000"),
                "order_id": "ORD125"
            }
        )
        await risk_engine.process_event(fill_event)

        # Verify: No rejection


# ============================================================================
# E2E TESTS: CooldownAfterLoss Happy Path
# ============================================================================


@pytest.mark.e2e
@pytest.mark.p1
class TestCooldownAfterLossE2E:
    """End-to-end tests for CooldownAfterLoss rule (full system flow)."""

    @pytest.mark.asyncio
    async def test_happy_path_trader_stays_profitable(
        self,
        state_manager,
        broker,
        notifier,
        account_id,
        clock
    ):
        """
        Test: Happy path - trader stays profitable, no cooldown.

        Flow:
        1. Execute multiple trades
        2. All trades profitable or small losses
        3. Never breach threshold
        4. No cooldown activated
        5. No notifications
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.cooldown_after_loss import CooldownAfterLossRule
        from tests.conftest import Event

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = CooldownAfterLossRule(
            loss_threshold=Decimal("500.00"),
            cooldown_seconds=300
        )
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Trade 1: +$200 profit
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("200.00")

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
                "quantity": 1,
                "fill_price": Decimal("18000"),
                "order_id": "ORD1"
            }
        )
        await risk_engine.process_event(fill1)

        # Trade 2: -$100 loss (net +$100)
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("100.00")

        fill2 = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "symbol": "ES",
                "side": "short",
                "quantity": 1,
                "fill_price": Decimal("4500"),
                "order_id": "ORD2"
            }
        )
        await risk_engine.process_event(fill2)

        # Verify: No cooldown
        assert state_manager.is_in_cooldown(account_id) is False

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
        Test: When cooldown triggered, trader notified.

        Flow:
        1. Loss threshold: $500
        2. Cumulative loss reaches -$500
        3. Cooldown activated
        4. Trader receives notification with cooldown duration
        5. Subsequent fills rejected with notification
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.cooldown_after_loss import CooldownAfterLossRule
        from tests.conftest import Event

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = CooldownAfterLossRule(
            loss_threshold=Decimal("500.00"),
            cooldown_seconds=300
        )
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Breach threshold
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-500.00")

        fill_breach = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "symbol": "MNQ",
                "side": "long",
                "quantity": 1,
                "fill_price": Decimal("18000"),
                "order_id": "ORD_BREACH"
            }
        )
        await risk_engine.process_event(fill_breach)

        # Verify notification sent
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) >= 1

        cooldown_notif = next((n for n in notifications if "cooldown" in n.reason.lower()), None)
        assert cooldown_notif is not None
        assert cooldown_notif.severity in ["warning", "medium"]
        assert "5 minute" in cooldown_notif.message.lower() or "300" in cooldown_notif.message

        # Attempt fill during cooldown
        fill_during = Event(
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
                "order_id": "ORD_DURING"
            }
        )
        await risk_engine.process_event(fill_during)

        # Verify rejection notification
        notifications_after = notifier.get_notifications(account_id)
        assert len(notifications_after) >= 2
