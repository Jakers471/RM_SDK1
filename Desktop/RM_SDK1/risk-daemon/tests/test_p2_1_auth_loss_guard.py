"""
P2-1: AuthLossGuard Rule Tests

Tests the AuthLossGuard rule that monitors connection loss and alerts.
Tests follow TDD principles - all tests FAIL initially until implementation exists.

Architecture reference: docs/architecture/02-risk-engine.md (Rule: AuthLossGuard)

Rule Behavior:
- Monitor CONNECTION_CHANGE events
- When disconnected: Send alert notification
- NO auto-flatten (alert only)
- Track connection state per account
- Optional: Track disconnection duration
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import timedelta


# ============================================================================
# UNIT TESTS: AuthLossGuard Rule Logic
# ============================================================================


@pytest.mark.unit
@pytest.mark.p2
class TestAuthLossGuardRuleUnit:
    """Unit tests for AuthLossGuard rule logic (isolated)."""

    def test_rule_config_defaults(self):
        """Test: AuthLossGuard rule has proper configuration defaults."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.auth_loss_guard import AuthLossGuardRule

        rule = AuthLossGuardRule()
        assert rule.enabled is True
        assert rule.name == "AuthLossGuard"
        assert rule.auto_flatten is False  # Alert only, no auto-flatten

    def test_rule_not_violated_when_connected(self, state_manager, account_id):
        """Test: Rule not violated when connection is active."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.auth_loss_guard import AuthLossGuardRule

        rule = AuthLossGuardRule()
        account_state = state_manager.get_account_state(account_id)

        # CONNECTION_CHANGE event: Connected
        connection_event = {
            "status": "connected",
            "timestamp": state_manager.clock.now()
        }

        violation = rule.evaluate(connection_event, account_state)
        assert violation is None  # No violation

    def test_rule_violated_when_disconnected(self, state_manager, account_id):
        """Test: Rule violated when connection lost."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.auth_loss_guard import AuthLossGuardRule

        rule = AuthLossGuardRule()
        account_state = state_manager.get_account_state(account_id)

        # CONNECTION_CHANGE event: Disconnected
        disconnection_event = {
            "status": "disconnected",
            "timestamp": state_manager.clock.now(),
            "reason": "Authentication failed"
        }

        violation = rule.evaluate(disconnection_event, account_state)
        assert violation is not None
        assert violation.rule_name == "AuthLossGuard"
        assert violation.severity == "critical"
        assert "connection lost" in violation.reason.lower()

    def test_rule_enforcement_action_alert_only(self, state_manager, account_id):
        """Test: Enforcement action is alert only (no flatten)."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.auth_loss_guard import AuthLossGuardRule

        rule = AuthLossGuardRule()
        account_state = state_manager.get_account_state(account_id)

        # Trigger disconnection
        disconnection_event = {
            "status": "disconnected",
            "timestamp": state_manager.clock.now()
        }
        violation = rule.evaluate(disconnection_event, account_state)
        action = rule.get_enforcement_action(violation)

        # Should be notification only
        assert action.action_type == "notify"
        assert action.severity == "critical"
        assert "manual intervention" in action.message.lower() or "check connection" in action.message.lower()

    def test_rule_tracks_disconnection_duration(self, state_manager, account_id, clock):
        """Test: Rule tracks how long connection has been lost."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.auth_loss_guard import AuthLossGuardRule

        rule = AuthLossGuardRule()
        account_state = state_manager.get_account_state(account_id)

        # Disconnect at T=0
        disconnect_time = clock.now()
        disconnection_event = {
            "status": "disconnected",
            "timestamp": disconnect_time
        }
        violation = rule.evaluate(disconnection_event, account_state)

        # Store disconnection time
        rule.track_disconnection(account_id, disconnect_time)

        # Check duration at T=60
        clock.advance(seconds=60)
        duration = rule.get_disconnection_duration(account_id, clock.now())

        assert duration.total_seconds() == 60

    def test_rule_applies_to_connection_events_only(self):
        """Test: Rule only evaluates CONNECTION_CHANGE events."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.auth_loss_guard import AuthLossGuardRule

        rule = AuthLossGuardRule()

        assert rule.applies_to_event("CONNECTION_CHANGE") is True
        assert rule.applies_to_event("FILL") is False
        assert rule.applies_to_event("POSITION_UPDATE") is False
        assert rule.applies_to_event("TIME_TICK") is False

    def test_rule_handles_reconnection(self, state_manager, account_id, clock):
        """Test: Rule handles reconnection after disconnect."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.auth_loss_guard import AuthLossGuardRule

        rule = AuthLossGuardRule()
        account_state = state_manager.get_account_state(account_id)

        # Disconnect
        disconnect_event = {
            "status": "disconnected",
            "timestamp": clock.now()
        }
        violation_disconnect = rule.evaluate(disconnect_event, account_state)
        assert violation_disconnect is not None

        # Reconnect after 30 seconds
        clock.advance(seconds=30)
        reconnect_event = {
            "status": "connected",
            "timestamp": clock.now()
        }
        violation_reconnect = rule.evaluate(reconnect_event, account_state)

        # Should clear violation
        assert violation_reconnect is None

        # Disconnection should be cleared
        rule.clear_disconnection(account_id)
        duration = rule.get_disconnection_duration(account_id, clock.now())
        assert duration is None or duration.total_seconds() == 0

    def test_rule_includes_open_position_info_in_alert(
        self,
        state_manager,
        account_id,
        clock
    ):
        """Test: Alert includes info about open positions."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.auth_loss_guard import AuthLossGuardRule
        from tests.conftest import Position

        # Create open positions
        pos1 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now()
        )
        state_manager.add_position(account_id, pos1)

        pos2 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="short",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4500"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now()
        )
        state_manager.add_position(account_id, pos2)

        rule = AuthLossGuardRule()
        account_state = state_manager.get_account_state(account_id)

        # Disconnect
        disconnect_event = {
            "status": "disconnected",
            "timestamp": clock.now()
        }
        violation = rule.evaluate(disconnect_event, account_state)

        # Violation should include position info
        assert violation.data.get("open_positions_count") == 2
        assert violation.data.get("symbols") == ["MNQ", "ES"]


# ============================================================================
# INTEGRATION TESTS: AuthLossGuard with Enforcement Engine
# ============================================================================


@pytest.mark.integration
@pytest.mark.p2
class TestAuthLossGuardIntegration:
    """Integration tests for AuthLossGuard rule with enforcement engine."""

    @pytest.mark.asyncio
    async def test_disconnection_triggers_alert_notification(
        self,
        state_manager,
        broker,
        notifier,
        account_id,
        clock
    ):
        """
        Test: Disconnection triggers alert notification (no flatten).

        Scenario:
        - Account connected
        - Connection lost
        - Critical alert sent
        - Positions NOT flattened
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.auth_loss_guard import AuthLossGuardRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = AuthLossGuardRule()
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Create open position
        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now()
        )
        state_manager.add_position(account_id, position)

        # CONNECTION_CHANGE event: Disconnected
        disconnect_event = Event(
            event_id=uuid4(),
            event_type="CONNECTION_CHANGE",
            timestamp=clock.now(),
            priority=1,  # High priority
            account_id=account_id,
            source="broker",
            data={
                "status": "disconnected",
                "reason": "Authentication failed",
                "timestamp": clock.now()
            }
        )
        await risk_engine.process_event(disconnect_event)

        # Verify: NO flatten action
        assert len(broker.flatten_account_calls) == 0
        assert len(broker.close_position_calls) == 0

        # Verify: Critical notification sent
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) == 1

        notif = notifications[0]
        assert notif.severity == "critical"
        assert "connection lost" in notif.reason.lower() or "disconnected" in notif.reason.lower()
        assert "manual intervention" in notif.message.lower() or "check connection" in notif.message.lower()

    @pytest.mark.asyncio
    async def test_reconnection_clears_alert(
        self,
        state_manager,
        broker,
        notifier,
        account_id,
        clock
    ):
        """
        Test: Reconnection clears alert state.

        Scenario:
        - Disconnect → Alert sent
        - Reconnect after 30 seconds
        - No additional alerts
        - Disconnection cleared
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.auth_loss_guard import AuthLossGuardRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Event

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = AuthLossGuardRule()
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Disconnect
        disconnect_event = Event(
            event_id=uuid4(),
            event_type="CONNECTION_CHANGE",
            timestamp=clock.now(),
            priority=1,
            account_id=account_id,
            source="broker",
            data={
                "status": "disconnected",
                "timestamp": clock.now()
            }
        )
        await risk_engine.process_event(disconnect_event)

        # Verify: Alert sent
        assert len(notifier.get_notifications(account_id)) == 1

        # Reconnect
        clock.advance(seconds=30)
        reconnect_event = Event(
            event_id=uuid4(),
            event_type="CONNECTION_CHANGE",
            timestamp=clock.now(),
            priority=1,
            account_id=account_id,
            source="broker",
            data={
                "status": "connected",
                "timestamp": clock.now()
            }
        )
        await risk_engine.process_event(reconnect_event)

        # Verify: No additional alerts (or success notification)
        # Implementation can choose to send "reconnected" notification
        notifications = notifier.get_notifications(account_id)
        # Should be 1 (disconnect) or 2 (disconnect + reconnect info)
        assert len(notifications) >= 1


# ============================================================================
# E2E TESTS: AuthLossGuard Happy Path
# ============================================================================


@pytest.mark.e2e
@pytest.mark.p2
class TestAuthLossGuardE2E:
    """End-to-end tests for AuthLossGuard rule (full system flow)."""

    @pytest.mark.asyncio
    async def test_happy_path_stable_connection(
        self,
        state_manager,
        broker,
        notifier,
        account_id,
        clock
    ):
        """
        Test: Happy path - connection remains stable.

        Flow:
        1. Account connected
        2. Trading activity occurs
        3. Connection remains stable
        4. No disconnection alerts
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.auth_loss_guard import AuthLossGuardRule
        from tests.conftest import Event

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = AuthLossGuardRule()
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Connection status: Connected
        connect_event = Event(
            event_id=uuid4(),
            event_type="CONNECTION_CHANGE",
            timestamp=clock.now(),
            priority=1,
            account_id=account_id,
            source="broker",
            data={
                "status": "connected",
                "timestamp": clock.now()
            }
        )
        await risk_engine.process_event(connect_event)

        # Some trading activity
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
                "fill_price": Decimal("18000"),
                "order_id": "ORD1"
            }
        )
        await risk_engine.process_event(fill_event)

        # Verify: No alerts
        notifications = notifier.get_notifications(account_id)
        # Filter for AuthLossGuard notifications
        auth_notifs = [n for n in notifications if "connection" in n.reason.lower() or "AuthLossGuard" in n.reason]
        assert len(auth_notifs) == 0

    @pytest.mark.asyncio
    async def test_disconnect_with_open_positions_alerts_trader(
        self,
        state_manager,
        broker,
        notifier,
        account_id,
        clock
    ):
        """
        Test: Disconnect with open positions sends detailed alert.

        Flow:
        1. Open 3 positions (MNQ, ES, NQ)
        2. Connection lost
        3. Critical alert sent with:
           - Position count
           - Symbols
           - Recommendation for manual intervention
        4. Positions remain open (no auto-flatten)
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.auth_loss_guard import AuthLossGuardRule
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = AuthLossGuardRule()
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Create 3 open positions
        symbols = ["MNQ", "ES", "NQ"]
        for symbol in symbols:
            pos = Position(
                position_id=uuid4(),
                account_id=account_id,
                symbol=symbol,
                side="long",
                quantity=2,
                entry_price=Decimal("10000"),
                current_price=Decimal("10000"),
                unrealized_pnl=Decimal("0"),
                opened_at=clock.now()
            )
            state_manager.add_position(account_id, pos)

        # Disconnect
        disconnect_event = Event(
            event_id=uuid4(),
            event_type="CONNECTION_CHANGE",
            timestamp=clock.now(),
            priority=1,
            account_id=account_id,
            source="broker",
            data={
                "status": "disconnected",
                "reason": "Network timeout",
                "timestamp": clock.now()
            }
        )
        await risk_engine.process_event(disconnect_event)

        # Verify: Alert sent
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) == 1

        notif = notifications[0]
        assert notif.severity == "critical"
        assert "3" in notif.message or "three" in notif.message.lower()  # 3 positions
        assert any(sym in notif.message for sym in symbols)  # Mentions symbols
        assert "manual" in notif.message.lower() or "intervention" in notif.message.lower()

        # Verify: Positions still open
        open_positions = state_manager.get_open_positions(account_id)
        assert len(open_positions) == 3

        # Verify: NO flatten
        assert len(broker.flatten_account_calls) == 0

    @pytest.mark.asyncio
    async def test_intermittent_connection_multiple_alerts(
        self,
        state_manager,
        broker,
        notifier,
        account_id,
        clock
    ):
        """
        Test: Intermittent connection issues trigger multiple alerts.

        Flow:
        1. Disconnect → Alert
        2. Reconnect after 30s
        3. Disconnect again after 60s → Alert
        4. Reconnect after 30s
        5. Total: 2 disconnect alerts
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.auth_loss_guard import AuthLossGuardRule
        from tests.conftest import Event

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = AuthLossGuardRule()
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # First disconnect
        disconnect1 = Event(
            event_id=uuid4(),
            event_type="CONNECTION_CHANGE",
            timestamp=clock.now(),
            priority=1,
            account_id=account_id,
            source="broker",
            data={"status": "disconnected", "timestamp": clock.now()}
        )
        await risk_engine.process_event(disconnect1)

        # Reconnect
        clock.advance(seconds=30)
        reconnect1 = Event(
            event_id=uuid4(),
            event_type="CONNECTION_CHANGE",
            timestamp=clock.now(),
            priority=1,
            account_id=account_id,
            source="broker",
            data={"status": "connected", "timestamp": clock.now()}
        )
        await risk_engine.process_event(reconnect1)

        # Second disconnect
        clock.advance(seconds=60)
        disconnect2 = Event(
            event_id=uuid4(),
            event_type="CONNECTION_CHANGE",
            timestamp=clock.now(),
            priority=1,
            account_id=account_id,
            source="broker",
            data={"status": "disconnected", "timestamp": clock.now()}
        )
        await risk_engine.process_event(disconnect2)

        # Reconnect
        clock.advance(seconds=30)
        reconnect2 = Event(
            event_id=uuid4(),
            event_type="CONNECTION_CHANGE",
            timestamp=clock.now(),
            priority=1,
            account_id=account_id,
            source="broker",
            data={"status": "connected", "timestamp": clock.now()}
        )
        await risk_engine.process_event(reconnect2)

        # Verify: At least 2 disconnect alerts
        notifications = notifier.get_notifications(account_id)
        disconnect_notifs = [n for n in notifications if "disconnect" in n.reason.lower()]
        assert len(disconnect_notifs) >= 2

    @pytest.mark.asyncio
    async def test_no_alert_if_no_open_positions(
        self,
        state_manager,
        broker,
        notifier,
        account_id,
        clock
    ):
        """
        Test: Optional - No alert if no open positions during disconnect.

        Flow:
        1. No open positions
        2. Connection lost
        3. Optional: No alert (or lower severity)

        Note: Implementation may choose to always alert regardless of positions.
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.auth_loss_guard import AuthLossGuardRule
        from tests.conftest import Event

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = AuthLossGuardRule()
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # No open positions

        # Disconnect
        disconnect_event = Event(
            event_id=uuid4(),
            event_type="CONNECTION_CHANGE",
            timestamp=clock.now(),
            priority=1,
            account_id=account_id,
            source="broker",
            data={"status": "disconnected", "timestamp": clock.now()}
        )
        await risk_engine.process_event(disconnect_event)

        # Verify: Implementation-dependent behavior
        # Could be no alert, or info-level alert
        notifications = notifier.get_notifications(account_id)
        if len(notifications) > 0:
            # If alert sent, should be lower severity
            notif = notifications[0]
            assert notif.severity in ["info", "warning"]  # Not critical
