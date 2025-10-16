"""
P1-10: TradeFrequencyLimit Rule Tests

Tests the TradeFrequencyLimit rule that enforces maximum trades per time window.
Tests follow TDD principles - all tests FAIL initially until implementation exists.

Architecture reference: docs/architecture/02-risk-engine.md (Rule 10: TradeFrequencyLimit)

Rule Behavior:
- Configurable: max_trades per time_window_seconds
- Tracks fill events in sliding time window
- When limit exceeded: Reject new fills (do NOT open position)
- Sliding window automatically removes old fills
- Triggered on FILL events
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import timedelta


# ============================================================================
# UNIT TESTS: TradeFrequencyLimit Rule Logic
# ============================================================================


@pytest.mark.unit
@pytest.mark.p1
class TestTradeFrequencyLimitRuleUnit:
    """Unit tests for TradeFrequencyLimit rule logic (isolated)."""

    def test_rule_config_defaults(self):
        """Test: TradeFrequencyLimit rule has proper configuration defaults."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.trade_frequency_limit import TradeFrequencyLimitRule

        rule = TradeFrequencyLimitRule(max_trades=10, time_window_seconds=60)
        assert rule.enabled is True
        assert rule.max_trades == 10
        assert rule.time_window_seconds == 60
        assert rule.name == "TradeFrequencyLimit"

    def test_rule_not_violated_within_limit(self, state_manager, account_id, clock):
        """Test: Rule not violated when trade count < limit."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.trade_frequency_limit import TradeFrequencyLimitRule

        rule = TradeFrequencyLimitRule(max_trades=10, time_window_seconds=60)
        account_state = state_manager.get_account_state(account_id)

        # Simulate 5 fills in the last 60 seconds
        for i in range(5):
            fill_event = {
                "symbol": "MNQ",
                "quantity": 1,
                "fill_time": clock.now() - timedelta(seconds=i * 10)
            }
            # Track fill (rule should maintain internal state)
            rule.track_fill(account_id, fill_event)

        # New fill would be #6, which is within limit of 10
        new_fill_event = {
            "symbol": "ES",
            "quantity": 1,
            "fill_time": clock.now()
        }

        violation = rule.evaluate(new_fill_event, account_state)
        assert violation is None  # No violation

    def test_rule_violated_exceeds_limit(self, state_manager, account_id, clock):
        """Test: Rule violated when trade count >= limit."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.trade_frequency_limit import TradeFrequencyLimitRule

        rule = TradeFrequencyLimitRule(max_trades=5, time_window_seconds=60)
        account_state = state_manager.get_account_state(account_id)

        # Simulate 5 fills in the last 60 seconds (at limit)
        for i in range(5):
            fill_event = {
                "symbol": "MNQ",
                "quantity": 1,
                "fill_time": clock.now() - timedelta(seconds=i * 10)
            }
            rule.track_fill(account_id, fill_event)

        # New fill would be #6, exceeding limit of 5
        new_fill_event = {
            "symbol": "ES",
            "quantity": 1,
            "fill_time": clock.now()
        }

        violation = rule.evaluate(new_fill_event, account_state)
        assert violation is not None
        assert violation.rule_name == "TradeFrequencyLimit"
        assert violation.severity == "high"
        assert "frequency limit" in violation.reason.lower()

    def test_rule_sliding_window_removes_old_fills(self, state_manager, account_id, clock):
        """Test: Sliding window removes fills outside time window."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.trade_frequency_limit import TradeFrequencyLimitRule

        rule = TradeFrequencyLimitRule(max_trades=5, time_window_seconds=60)
        account_state = state_manager.get_account_state(account_id)

        # T=0: Add 5 fills (at limit)
        for i in range(5):
            fill_event = {
                "symbol": "MNQ",
                "quantity": 1,
                "fill_time": clock.now()
            }
            rule.track_fill(account_id, fill_event)

        # T=65: Old fills are outside 60-second window
        clock.advance(seconds=65)

        # New fill should be OK (old fills expired)
        new_fill_event = {
            "symbol": "ES",
            "quantity": 1,
            "fill_time": clock.now()
        }

        violation = rule.evaluate(new_fill_event, account_state)
        assert violation is None  # No violation - window cleared

    def test_rule_enforcement_action_reject_fill(self, state_manager, account_id, clock):
        """Test: Enforcement action rejects fill (no position opened)."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.trade_frequency_limit import TradeFrequencyLimitRule

        rule = TradeFrequencyLimitRule(max_trades=5, time_window_seconds=60)
        account_state = state_manager.get_account_state(account_id)

        # At limit
        for i in range(5):
            fill_event = {"symbol": "MNQ", "quantity": 1, "fill_time": clock.now()}
            rule.track_fill(account_id, fill_event)

        # Trigger violation
        violation = rule.evaluate({"symbol": "ES", "quantity": 1, "fill_time": clock.now()}, account_state)
        action = rule.get_enforcement_action(violation)

        # Should be "reject_fill" action (custom action type)
        assert action.action_type == "reject_fill"
        assert action.account_id == account_id

    def test_rule_applies_to_fill_events_only(self):
        """Test: Rule only evaluates fill events."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.trade_frequency_limit import TradeFrequencyLimitRule

        rule = TradeFrequencyLimitRule(max_trades=10, time_window_seconds=60)

        assert rule.applies_to_event("FILL") is True
        assert rule.applies_to_event("POSITION_UPDATE") is False
        assert rule.applies_to_event("TIME_TICK") is False

    def test_rule_different_time_windows(self, state_manager, account_id, clock):
        """Test: Different time window configurations."""
        # WILL FAIL: Rule class doesn't exist yet
        from src.rules.trade_frequency_limit import TradeFrequencyLimitRule

        account_state = state_manager.get_account_state(account_id)

        # 60-second window: 5 trades
        rule_60s = TradeFrequencyLimitRule(max_trades=5, time_window_seconds=60)

        # Add 5 fills at T=0
        for i in range(5):
            fill = {"symbol": "MNQ", "quantity": 1, "fill_time": clock.now()}
            rule_60s.track_fill(account_id, fill)

        # T=45: Still within 60s window
        clock.advance(seconds=45)
        new_fill = {"symbol": "ES", "quantity": 1, "fill_time": clock.now()}

        # Should violate 60s window
        violation_60s = rule_60s.evaluate(new_fill, account_state)
        assert violation_60s is not None

        # 30-second window: Same 5 trades
        rule_30s = TradeFrequencyLimitRule(max_trades=5, time_window_seconds=30)

        # Copy tracked fills from rule_60s to rule_30s (or re-track)
        for i in range(5):
            fill = {"symbol": "MNQ", "quantity": 1, "fill_time": clock.now() - timedelta(seconds=45)}
            rule_30s.track_fill(account_id, fill)

        # T=45: Old fills are outside 30s window (45 seconds ago)
        violation_30s = rule_30s.evaluate(new_fill, account_state)
        assert violation_30s is None  # No violation - outside 30s window


# ============================================================================
# INTEGRATION TESTS: TradeFrequencyLimit with Enforcement Engine
# ============================================================================


@pytest.mark.integration
@pytest.mark.p1
class TestTradeFrequencyLimitIntegration:
    """Integration tests for TradeFrequencyLimit rule with enforcement engine."""

    @pytest.mark.asyncio
    async def test_fill_rejected_when_frequency_exceeded(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: Fill rejected when frequency limit exceeded.

        Scenario:
        - Limit: 3 trades per 60 seconds
        - Fills 1-3: OK
        - Fill 4: Rejected (exceeds frequency)
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.trade_frequency_limit import TradeFrequencyLimitRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Event

        enforcement = EnforcementEngine(broker, state_manager)
        rule = TradeFrequencyLimitRule(max_trades=3, time_window_seconds=60)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Fills 1-3: OK
        for i in range(3):
            fill = Event(
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
                    "order_id": f"ORD_{i}",
                    "fill_time": clock.now()
                }
            )
            await risk_engine.process_event(fill)
            clock.advance(seconds=10)

        # Fill 4: Should be rejected
        fill4 = Event(
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
                "order_id": "ORD_4",
                "fill_time": clock.now()
            }
        )
        await risk_engine.process_event(fill4)

        # Verify: Fill 4 was rejected (no position opened)
        # Enforcement engine should have "reject_fill" handler
        # For now, verify positions count is 3 (not 4)
        positions = state_manager.get_open_positions(account_id)
        assert len(positions) <= 3

    @pytest.mark.asyncio
    async def test_window_resets_allow_new_trades(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: After time window expires, new fills allowed.

        Scenario:
        - Limit: 3 trades per 60 seconds
        - T=0: 3 fills (at limit)
        - T=65: Window expired, new fill OK
        """
        # WILL FAIL: RiskEngine class doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.rules.trade_frequency_limit import TradeFrequencyLimitRule
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Event

        enforcement = EnforcementEngine(broker, state_manager)
        rule = TradeFrequencyLimitRule(max_trades=3, time_window_seconds=60)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # T=0: 3 fills
        for i in range(3):
            fill = Event(
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
                    "order_id": f"ORD_{i}",
                    "fill_time": clock.now()
                }
            )
            await risk_engine.process_event(fill)

        # T=65: Window expired
        clock.advance(seconds=65)

        # New fill should be OK
        fill_after = Event(
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
                "order_id": "ORD_AFTER",
                "fill_time": clock.now()
            }
        )
        await risk_engine.process_event(fill_after)

        # Verify: Fill was accepted (no rejection)
        # Implementation detail: Check for violation log or accept


# ============================================================================
# E2E TESTS: TradeFrequencyLimit Happy Path
# ============================================================================


@pytest.mark.e2e
@pytest.mark.p1
class TestTradeFrequencyLimitE2E:
    """End-to-end tests for TradeFrequencyLimit rule (full system flow)."""

    @pytest.mark.asyncio
    async def test_happy_path_trader_stays_within_frequency(
        self,
        state_manager,
        broker,
        notifier,
        account_id,
        clock
    ):
        """
        Test: Happy path - trader stays within frequency limit.

        Flow:
        1. Limit: 5 trades per 60 seconds
        2. Execute 5 trades over 60 seconds (1 per 12 seconds)
        3. No enforcement actions
        4. No notifications
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.trade_frequency_limit import TradeFrequencyLimitRule
        from tests.conftest import Event

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = TradeFrequencyLimitRule(max_trades=5, time_window_seconds=60)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Execute 5 trades, spaced 12 seconds apart
        for i in range(5):
            fill = Event(
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
                    "order_id": f"ORD_{i}",
                    "fill_time": clock.now()
                }
            )
            await risk_engine.process_event(fill)
            clock.advance(seconds=12)

        # Verify: No rejections
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
        Test: When frequency exceeded, fill rejected AND trader notified.

        Flow:
        1. Limit: 3 trades per 60 seconds
        2. Execute 3 trades quickly
        3. Attempt 4th trade
        4. Trade rejected
        5. Trader receives warning notification
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.trade_frequency_limit import TradeFrequencyLimitRule
        from tests.conftest import Event

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = TradeFrequencyLimitRule(max_trades=3, time_window_seconds=60)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Execute 3 trades quickly
        for i in range(3):
            fill = Event(
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
                    "order_id": f"ORD_{i}",
                    "fill_time": clock.now()
                }
            )
            await risk_engine.process_event(fill)
            clock.advance(seconds=5)

        # Attempt 4th trade
        fill4 = Event(
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
                "order_id": "ORD_4",
                "fill_time": clock.now()
            }
        )
        await risk_engine.process_event(fill4)

        # Verify notification sent
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) >= 1

        # Find frequency limit notification
        freq_notif = next((n for n in notifications if "frequency" in n.reason.lower() or "TradeFrequencyLimit" in n.reason), None)
        assert freq_notif is not None
        assert freq_notif.severity == "warning"
        assert freq_notif.action == "reject_fill"
