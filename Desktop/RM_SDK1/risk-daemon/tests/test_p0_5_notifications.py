"""
P0-5: Notifications with Reason + Action Tests

Tests that all enforcement actions send notifications with clear reason and action.
Critical for trader transparency - must know WHY positions were closed.

Architecture reference: docs/architecture/07-notifications-logging.md
"""

import pytest
from decimal import Decimal
from uuid import uuid4


# ============================================================================
# UNIT TESTS: Notification Content
# ============================================================================


@pytest.mark.unit
@pytest.mark.p0
class TestNotificationContent:
    """Unit tests for notification content (reason + action)."""

    def test_notification_has_required_fields(self, notifier, account_id, clock):
        """Test: Notification contains all required fields."""
        # WILL FAIL: Notification structure doesn't exist yet

        notifier.send(
            account_id=account_id,
            title="Risk Enforcement",
            message="Position closed",
            severity="warning",
            reason="MaxContracts limit exceeded: 5 contracts > 4 limit",
            action="close_position"
        )

        notifications = notifier.get_notifications(account_id)
        assert len(notifications) == 1

        notif = notifications[0]
        assert notif.account_id == account_id
        assert notif.title is not None
        assert notif.message is not None
        assert notif.severity in ["info", "warning", "critical"]
        assert notif.reason is not None  # WHY action taken
        assert notif.action is not None  # WHAT action taken
        assert notif.timestamp is not None

    def test_max_contracts_notification_reason_clear(self):
        """Test: MaxContracts notification has clear reason."""
        # WILL FAIL: MaxContracts notification generation doesn't exist yet
        from src.rules.max_contracts import MaxContractsRule

        rule = MaxContractsRule(max_contracts=4)

        # Simulate violation
        violation = rule.create_violation(
            current_total=6,
            limit=4,
            excess=2
        )

        # Generate notification message
        reason = rule.format_notification_reason(violation)

        # Verify clarity
        assert "MaxContracts" in reason
        assert "6" in reason  # Current total
        assert "4" in reason  # Limit
        assert "2" in reason  # Excess
        assert "limit" in reason.lower()

    def test_daily_loss_notification_includes_combined_pnl(self):
        """Test: DailyRealizedLoss notification shows combined PnL breakdown."""
        # WILL FAIL: DailyRealizedLoss notification doesn't exist yet
        from src.rules.daily_realized_loss import DailyRealizedLossRule

        rule = DailyRealizedLossRule(limit=Decimal("-1000.00"))

        # Simulate violation with combined PnL
        violation = rule.create_violation(
            realized=Decimal("-850.00"),
            unrealized=Decimal("-200.00"),
            combined=Decimal("-1050.00"),
            limit=Decimal("-1000.00")
        )

        reason = rule.format_notification_reason(violation)

        # Verify breakdown shown
        assert "DailyRealizedLoss" in reason
        assert "-850" in reason  # Realized component
        assert "-200" in reason  # Unrealized component
        assert "-1050" in reason  # Combined total
        assert "-1000" in reason  # Limit
        assert "combined" in reason.lower()

    def test_notification_severity_matches_rule_criticality(self):
        """Test: Notification severity matches rule criticality."""
        # WILL FAIL: Severity mapping doesn't exist yet

        # Daily limits are CRITICAL (lockout)
        from src.rules.daily_realized_loss import DailyRealizedLossRule
        daily_rule = DailyRealizedLossRule(limit=Decimal("-1000.00"))
        assert daily_rule.notification_severity == "critical"

        # Per-trade limits are WARNING (no lockout)
        from src.rules.unrealized_loss import UnrealizedLossRule
        pertrade_rule = UnrealizedLossRule(limit=Decimal("-200.00"))
        assert pertrade_rule.notification_severity == "warning"

        # Contract limits are WARNING
        from src.rules.max_contracts import MaxContractsRule
        contracts_rule = MaxContractsRule(max_contracts=4)
        assert contracts_rule.notification_severity == "warning"

    def test_notification_action_field_accurate(self):
        """Test: Notification action field accurately describes enforcement."""
        # WILL FAIL: Action field mapping doesn't exist yet
        from src.core.enforcement_engine import EnforcementEngine

        # close_position action
        action1 = EnforcementEngine.create_action(
            action_type="close_position",
            position_id=uuid4(),
            quantity=1
        )
        assert action1.notification_action == "close_position"

        # flatten_account action
        action2 = EnforcementEngine.create_action(
            action_type="flatten_account"
        )
        assert action2.notification_action == "flatten_account"

        # set_lockout action
        action3 = EnforcementEngine.create_action(
            action_type="set_lockout"
        )
        assert action3.notification_action == "set_lockout"


# ============================================================================
# INTEGRATION TESTS: End-to-End Notification Flow
# ============================================================================


@pytest.mark.integration
@pytest.mark.p0
class TestNotificationIntegration:
    """Integration tests for full notification flow."""

    @pytest.mark.asyncio
    async def test_max_contracts_enforcement_sends_notification(
        self,
        state_manager,
        broker,
        notifier,
        account_id
    ):
        """
        Test: MaxContracts enforcement sends notification with reason.

        Scenario:
        - Limit: 4 contracts
        - Fill exceeds limit
        - Enforcement closes excess
        - Notification sent with reason
        """
        # WILL FAIL: Full notification flow doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.max_contracts import MaxContractsRule
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = MaxContractsRule(max_contracts=4)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Existing: 3 contracts
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

        # New fill: 2 more (total would be 5)
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
                "quantity": 2,
                "fill_price": Decimal("4500"),
                "order_id": "ORD123",
                "fill_time": state_manager.clock.now()
            }
        )

        await risk_engine.process_event(fill_event)

        # Verify notification sent
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) == 1

        notif = notifications[0]
        assert notif.severity == "warning"
        assert "MaxContracts" in notif.reason
        assert "5" in notif.reason  # Total exceeded
        assert "4" in notif.reason  # Limit
        assert notif.action == "close_position"

    @pytest.mark.asyncio
    async def test_daily_loss_lockout_sends_critical_notification(
        self,
        state_manager,
        broker,
        notifier,
        account_id
    ):
        """
        Test: Daily loss lockout sends CRITICAL notification with breakdown.

        Scenario:
        - Combined PnL exceeds limit
        - Account flattened + locked out
        - CRITICAL notification sent
        - Reason includes realized, unrealized, combined
        """
        # WILL FAIL: Critical notification flow doesn't exist yet
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

        # Setup combined PnL breach
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-800.00")

        pos = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=1,
            entry_price=Decimal("18000"),
            current_price=Decimal("17875"),
            unrealized_pnl=Decimal("-250.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos)

        # Position update triggers rule
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
                "current_price": Decimal("17875"),
                "unrealized_pnl": Decimal("-250.00"),
                "quantity": 1,
                "update_time": state_manager.clock.now()
            }
        )

        await risk_engine.process_event(update_event)

        # Verify CRITICAL notification
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) == 1

        notif = notifications[0]
        assert notif.severity == "critical"
        assert "DailyRealizedLoss" in notif.reason
        assert "-800" in notif.reason  # Realized
        assert "-250" in notif.reason  # Unrealized
        assert "-1050" in notif.reason  # Combined
        assert "flatten" in notif.action.lower()

    @pytest.mark.asyncio
    async def test_multiple_rules_violated_multiple_notifications(
        self,
        state_manager,
        broker,
        notifier,
        account_id
    ):
        """
        Test: Multiple rule violations send separate notifications.

        Scenario:
        - Per-trade limit violated
        - Daily limit violated (cascading)
        - Expected: 2 notifications sent
        """
        # WILL FAIL: Multiple notification handling doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.daily_realized_loss import DailyRealizedLossRule
        from src.rules.unrealized_loss import UnrealizedLossRule
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        pertrade_rule = UnrealizedLossRule(limit=Decimal("-200.00"))
        daily_rule = DailyRealizedLossRule(limit=Decimal("-1000.00"))

        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[pertrade_rule, daily_rule]
        )

        # Setup cascading violation
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-850.00")

        pos = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=1,
            entry_price=Decimal("18000"),
            current_price=Decimal("17900"),
            unrealized_pnl=Decimal("-200.00"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos)

        # Trigger cascading violation
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
                "current_price": Decimal("17900"),
                "unrealized_pnl": Decimal("-200.00"),
                "quantity": 1,
                "update_time": state_manager.clock.now()
            }
        )

        await risk_engine.process_event(update_event)

        # Simulate position close updating realized PnL
        state_manager.close_position(account_id, pos.position_id, Decimal("-200.00"))

        # Verify 2 notifications
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) >= 2

        # First: per-trade limit
        assert any("UnrealizedLoss" in n.reason for n in notifications)

        # Second: daily limit
        assert any("DailyRealizedLoss" in n.reason for n in notifications)

    @pytest.mark.asyncio
    async def test_notification_timestamp_accuracy(
        self,
        state_manager,
        broker,
        notifier,
        account_id,
        clock
    ):
        """
        Test: Notification timestamps are accurate.

        Scenario:
        - Enforcement at specific time
        - Notification timestamp matches enforcement time
        """
        # WILL FAIL: Timestamp handling doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.max_contracts import MaxContractsRule
        from tests.conftest import Event

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = MaxContractsRule(max_contracts=1)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Record enforcement time
        enforcement_time = clock.now()

        # Trigger violation
        fill_event = Event(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=enforcement_time,
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "symbol": "MNQ",
                "side": "long",
                "quantity": 2,
                "fill_price": Decimal("18000"),
                "order_id": "ORD123",
                "fill_time": enforcement_time
            }
        )

        await risk_engine.process_event(fill_event)

        # Verify notification timestamp
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) == 1

        notif = notifications[0]
        # Timestamp should be within 1 second of enforcement time
        time_diff = abs((notif.timestamp - enforcement_time).total_seconds())
        assert time_diff < 1.0
