"""
Stop Loss Detector Tests

Tests the stop loss detector that monitors for stop loss attachment on positions.
Tests follow TDD principles - all tests FAIL initially until implementation exists.

Architecture:
- Monitors ORDER events for stop loss orders
- Updates position.stop_loss_attached flag when detected
- Used by NoStopLossGrace rule to verify compliance
- Detects stop orders by type: "STP", "STPLMT", "TRAIL"
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import timedelta


# ============================================================================
# UNIT TESTS: StopLossDetector Logic
# ============================================================================


@pytest.mark.unit
class TestStopLossDetectorUnit:
    """Unit tests for stop loss detector logic (isolated)."""

    def test_detector_config_defaults(self):
        """Test: StopLossDetector has proper configuration defaults."""
        # WILL FAIL: StopLossDetector class doesn't exist yet
        from src.monitors.stop_loss_detector import StopLossDetector

        detector = StopLossDetector()
        assert detector.enabled is True
        assert detector.name == "StopLossDetector"

    def test_detector_identifies_stop_order(self):
        """Test: Detector correctly identifies stop loss orders."""
        # WILL FAIL: StopLossDetector class doesn't exist yet
        from src.monitors.stop_loss_detector import StopLossDetector

        detector = StopLossDetector()

        # STP order
        stp_order = {
            "order_id": "ORD123",
            "order_type": "STP",
            "symbol": "MNQ",
            "side": "sell",
            "quantity": 2
        }
        assert detector.is_stop_order(stp_order) is True

        # STPLMT order
        stplmt_order = {
            "order_id": "ORD124",
            "order_type": "STPLMT",
            "symbol": "ES",
            "side": "sell",
            "quantity": 1
        }
        assert detector.is_stop_order(stplmt_order) is True

        # TRAIL order
        trail_order = {
            "order_id": "ORD125",
            "order_type": "TRAIL",
            "symbol": "NQ",
            "side": "buy",
            "quantity": 1
        }
        assert detector.is_stop_order(trail_order) is True

    def test_detector_ignores_non_stop_orders(self):
        """Test: Detector ignores non-stop orders."""
        # WILL FAIL: StopLossDetector class doesn't exist yet
        from src.monitors.stop_loss_detector import StopLossDetector

        detector = StopLossDetector()

        # Market order
        market_order = {
            "order_id": "ORD126",
            "order_type": "MKT",
            "symbol": "MNQ",
            "side": "buy",
            "quantity": 2
        }
        assert detector.is_stop_order(market_order) is False

        # Limit order
        limit_order = {
            "order_id": "ORD127",
            "order_type": "LMT",
            "symbol": "ES",
            "side": "sell",
            "quantity": 1
        }
        assert detector.is_stop_order(limit_order) is False

    def test_detector_matches_stop_to_position(self, state_manager, account_id, clock):
        """Test: Detector matches stop orders to positions by symbol."""
        # WILL FAIL: StopLossDetector class doesn't exist yet
        from src.monitors.stop_loss_detector import StopLossDetector
        from tests.conftest import Position

        detector = StopLossDetector()

        # Create position
        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now(),
            stop_loss_attached=False
        )
        state_manager.add_position(account_id, position)

        # Stop order for same symbol
        stop_order = {
            "order_id": "ORD123",
            "order_type": "STP",
            "symbol": "MNQ",
            "side": "sell",
            "quantity": 2
        }

        # Should match
        account_state = state_manager.get_account_state(account_id)
        matched_positions = detector.find_matching_positions(stop_order, account_state)
        assert len(matched_positions) == 1
        assert matched_positions[0].position_id == position.position_id

    def test_detector_updates_position_flag(self, state_manager, account_id, clock):
        """Test: Detector updates position.stop_loss_attached flag."""
        # WILL FAIL: StopLossDetector class doesn't exist yet
        from src.monitors.stop_loss_detector import StopLossDetector
        from tests.conftest import Position

        detector = StopLossDetector()

        # Create position without stop
        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4500"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now(),
            stop_loss_attached=False
        )
        state_manager.add_position(account_id, position)

        # Stop order placed
        stop_order = {
            "order_id": "ORD128",
            "order_type": "STP",
            "symbol": "ES",
            "side": "sell",
            "quantity": 1
        }

        # Process stop detection
        account_state = state_manager.get_account_state(account_id)
        detector.process_order(stop_order, account_state)

        # Verify flag updated
        updated_position = state_manager.get_open_positions(account_id)[0]
        assert updated_position.stop_loss_attached is True

    def test_detector_handles_multiple_positions_same_symbol(
        self,
        state_manager,
        account_id,
        clock
    ):
        """Test: Detector handles multiple positions for same symbol."""
        # WILL FAIL: StopLossDetector class doesn't exist yet
        from src.monitors.stop_loss_detector import StopLossDetector
        from tests.conftest import Position

        detector = StopLossDetector()

        # Create 2 positions for MNQ
        pos1 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now(),
            stop_loss_attached=False
        )
        state_manager.add_position(account_id, pos1)

        pos2 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=1,
            entry_price=Decimal("18100"),
            current_price=Decimal("18100"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now(),
            stop_loss_attached=False
        )
        state_manager.add_position(account_id, pos2)

        # Stop order for 2 contracts (matches pos1)
        stop_order = {
            "order_id": "ORD129",
            "order_type": "STP",
            "symbol": "MNQ",
            "side": "sell",
            "quantity": 2
        }

        account_state = state_manager.get_account_state(account_id)
        matched = detector.find_matching_positions(stop_order, account_state)

        # Should match both positions
        assert len(matched) == 2

    def test_detector_applies_to_order_events_only(self):
        """Test: Detector only processes ORDER events."""
        # WILL FAIL: StopLossDetector class doesn't exist yet
        from src.monitors.stop_loss_detector import StopLossDetector

        detector = StopLossDetector()

        assert detector.applies_to_event("ORDER") is True
        assert detector.applies_to_event("ORDER_STATUS") is True
        assert detector.applies_to_event("FILL") is False
        assert detector.applies_to_event("TIME_TICK") is False


# ============================================================================
# INTEGRATION TESTS: StopLossDetector with Risk Engine
# ============================================================================


@pytest.mark.integration
class TestStopLossDetectorIntegration:
    """Integration tests for stop loss detector with risk engine."""

    @pytest.mark.asyncio
    async def test_stop_detected_prevents_grace_violation(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: Stop loss detection prevents NoStopLossGrace violation.

        Scenario:
        - Position opened at T=0
        - Stop order placed at T=60
        - Grace expires at T=121
        - No violation (stop was detected)
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule
        from src.monitors.stop_loss_detector import StopLossDetector
        from tests.conftest import Position, Event

        enforcement = EnforcementEngine(broker, state_manager)
        rule = NoStopLossGraceRule(grace_period_seconds=120)
        detector = StopLossDetector()
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule],
            monitors=[detector]
        )

        # T=0: Create position
        position = Position(
            position_id=uuid4(),
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

        # T=60: Stop order placed
        clock.advance(seconds=60)
        order_event = Event(
            event_id=uuid4(),
            event_type="ORDER",
            timestamp=clock.now(),
            priority=3,
            account_id=account_id,
            source="broker",
            data={
                "order_id": "ORD123",
                "order_type": "STP",
                "symbol": "MNQ",
                "side": "sell",
                "quantity": 2,
                "stop_price": Decimal("17900")
            }
        )
        await risk_engine.process_event(order_event)

        # T=121: Grace expires, TIME_TICK
        clock.advance(seconds=61)
        tick_event = Event(
            event_id=uuid4(),
            event_type="TIME_TICK",
            timestamp=clock.now(),
            priority=5,
            account_id=account_id,
            source="system",
            data={"current_time": clock.now()}
        )
        await risk_engine.process_event(tick_event)

        # Verify: No enforcement (stop was attached)
        assert len(broker.close_position_calls) == 0

        # Verify: Position flag updated
        updated_position = state_manager.get_open_positions(account_id)[0]
        assert updated_position.stop_loss_attached is True

    @pytest.mark.asyncio
    async def test_detector_processes_order_status_updates(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: Detector processes ORDER_STATUS updates (not just ORDER).

        Scenario:
        - Position opened
        - Stop order submitted (ORDER event)
        - Stop order working (ORDER_STATUS event)
        - Position updated with stop_loss_attached
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.monitors.stop_loss_detector import StopLossDetector
        from tests.conftest import Position, Event

        enforcement = EnforcementEngine(broker, state_manager)
        detector = StopLossDetector()
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[],
            monitors=[detector]
        )

        # Create position
        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4500"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now(),
            stop_loss_attached=False
        )
        state_manager.add_position(account_id, position)

        # ORDER_STATUS: Stop working
        status_event = Event(
            event_id=uuid4(),
            event_type="ORDER_STATUS",
            timestamp=clock.now(),
            priority=3,
            account_id=account_id,
            source="broker",
            data={
                "order_id": "ORD130",
                "order_type": "STP",
                "symbol": "ES",
                "side": "sell",
                "quantity": 1,
                "status": "Working"
            }
        )
        await risk_engine.process_event(status_event)

        # Verify: Flag updated
        updated_position = state_manager.get_open_positions(account_id)[0]
        assert updated_position.stop_loss_attached is True


# ============================================================================
# E2E TESTS: StopLossDetector System Flow
# ============================================================================


@pytest.mark.e2e
class TestStopLossDetectorE2E:
    """End-to-end tests for stop loss detector (full system flow)."""

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
        Test: Happy path - trader attaches stop immediately after fill.

        Flow:
        1. Fill event creates position
        2. Trader submits stop order within 10 seconds
        3. Detector updates position flag
        4. Grace expires with no violation
        5. No notifications sent
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule
        from src.monitors.stop_loss_detector import StopLossDetector
        from tests.conftest import Position, Event

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = NoStopLossGraceRule(grace_period_seconds=120)
        detector = StopLossDetector()
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule],
            monitors=[detector]
        )

        # T=0: Fill creates position
        position = Position(
            position_id=uuid4(),
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

        # T=10: Trader attaches stop
        clock.advance(seconds=10)
        order_event = Event(
            event_id=uuid4(),
            event_type="ORDER",
            timestamp=clock.now(),
            priority=3,
            account_id=account_id,
            source="broker",
            data={
                "order_id": "ORD131",
                "order_type": "STP",
                "symbol": "MNQ",
                "side": "sell",
                "quantity": 2,
                "stop_price": Decimal("17900")
            }
        )
        await risk_engine.process_event(order_event)

        # T=121: Grace expires
        clock.advance(seconds=111)
        tick_event = Event(
            event_id=uuid4(),
            event_type="TIME_TICK",
            timestamp=clock.now(),
            priority=5,
            account_id=account_id,
            source="system",
            data={"current_time": clock.now()}
        )
        await risk_engine.process_event(tick_event)

        # Verify: No enforcement
        assert len(broker.close_position_calls) == 0

        # Verify: No notifications
        assert len(notifier.get_notifications(account_id)) == 0

        # Verify: Position still open
        positions = state_manager.get_open_positions(account_id)
        assert len(positions) == 1

    @pytest.mark.asyncio
    async def test_detector_handles_trailing_stops(
        self,
        state_manager,
        broker,
        notifier,
        account_id,
        clock
    ):
        """
        Test: Detector correctly handles trailing stop orders.

        Flow:
        1. Position opened
        2. Trader submits trailing stop (TRAIL order)
        3. Detector recognizes as stop loss
        4. Position marked as compliant
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule
        from src.monitors.stop_loss_detector import StopLossDetector
        from tests.conftest import Position, Event

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = NoStopLossGraceRule(grace_period_seconds=120)
        detector = StopLossDetector()
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule],
            monitors=[detector]
        )

        # Create position
        position = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="NQ",
            side="long",
            quantity=1,
            entry_price=Decimal("18200"),
            current_price=Decimal("18200"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now(),
            stop_loss_attached=False,
            stop_loss_grace_expires=clock.now() + timedelta(seconds=120)
        )
        state_manager.add_position(account_id, position)

        # Trailing stop order
        trail_order = Event(
            event_id=uuid4(),
            event_type="ORDER",
            timestamp=clock.now(),
            priority=3,
            account_id=account_id,
            source="broker",
            data={
                "order_id": "ORD132",
                "order_type": "TRAIL",
                "symbol": "NQ",
                "side": "sell",
                "quantity": 1,
                "trail_amount": Decimal("100")
            }
        )
        await risk_engine.process_event(trail_order)

        # Verify: Position marked as compliant
        updated_position = state_manager.get_open_positions(account_id)[0]
        assert updated_position.stop_loss_attached is True

    @pytest.mark.asyncio
    async def test_detector_multiple_positions_mixed_stops(
        self,
        state_manager,
        broker,
        notifier,
        account_id,
        clock
    ):
        """
        Test: Detector handles multiple positions with different stop types.

        Flow:
        1. Position 1 (MNQ): STP stop → compliant
        2. Position 2 (ES): STPLMT stop → compliant
        3. Position 3 (NQ): No stop → violation after grace
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule
        from src.monitors.stop_loss_detector import StopLossDetector
        from tests.conftest import Position, Event

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = NoStopLossGraceRule(grace_period_seconds=120)
        detector = StopLossDetector()
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule],
            monitors=[detector]
        )

        # Position 1: MNQ with STP
        pos1 = Position(
            position_id=uuid4(),
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
        state_manager.add_position(account_id, pos1)

        order1 = Event(
            event_id=uuid4(),
            event_type="ORDER",
            timestamp=clock.now(),
            priority=3,
            account_id=account_id,
            source="broker",
            data={
                "order_id": "ORD133",
                "order_type": "STP",
                "symbol": "MNQ",
                "side": "sell",
                "quantity": 2
            }
        )
        await risk_engine.process_event(order1)

        # Position 2: ES with STPLMT
        pos2 = Position(
            position_id=uuid4(),
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
        state_manager.add_position(account_id, pos2)

        order2 = Event(
            event_id=uuid4(),
            event_type="ORDER",
            timestamp=clock.now(),
            priority=3,
            account_id=account_id,
            source="broker",
            data={
                "order_id": "ORD134",
                "order_type": "STPLMT",
                "symbol": "ES",
                "side": "buy",
                "quantity": 1
            }
        )
        await risk_engine.process_event(order2)

        # Position 3: NQ without stop (non-compliant)
        pos3 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="NQ",
            side="long",
            quantity=1,
            entry_price=Decimal("18200"),
            current_price=Decimal("18200"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now() - timedelta(seconds=125),
            stop_loss_attached=False,
            stop_loss_grace_expires=clock.now() - timedelta(seconds=5)
        )
        state_manager.add_position(account_id, pos3)

        # TIME_TICK: Check violations
        tick_event = Event(
            event_id=uuid4(),
            event_type="TIME_TICK",
            timestamp=clock.now(),
            priority=5,
            account_id=account_id,
            source="system",
            data={"current_time": clock.now()}
        )
        await risk_engine.process_event(tick_event)

        # Verify: Only pos3 closed
        assert len(broker.close_position_calls) == 1
        assert broker.close_position_calls[0]["position_id"] == pos3.position_id

        # Verify: Notification only for pos3
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) == 1
