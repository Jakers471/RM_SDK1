"""
TIME_TICK Generator Tests

Tests the TIME_TICK event generator that drives time-based rules.
Tests follow TDD principles - all tests FAIL initially until implementation exists.

Architecture:
- TIME_TICK events are generated periodically (e.g., every 1-5 seconds)
- Used by NoStopLossGrace, SessionBlock, and other time-dependent rules
- Should be lightweight and non-blocking
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import timedelta


# ============================================================================
# UNIT TESTS: TimeTickGenerator Logic
# ============================================================================


@pytest.mark.unit
class TestTimeTickGeneratorUnit:
    """Unit tests for TIME_TICK generator logic (isolated)."""

    def test_generator_config_defaults(self):
        """Test: TimeTickGenerator has proper configuration defaults."""
        # WILL FAIL: TimeTickGenerator class doesn't exist yet
        from src.timers.time_tick_generator import TimeTickGenerator

        generator = TimeTickGenerator(interval_seconds=1)
        assert generator.interval_seconds == 1
        assert generator.enabled is True

    def test_generator_creates_tick_event(self, clock):
        """Test: Generator creates properly formatted TIME_TICK event."""
        # WILL FAIL: TimeTickGenerator class doesn't exist yet
        from src.timers.time_tick_generator import TimeTickGenerator

        generator = TimeTickGenerator(interval_seconds=1)
        event = generator.create_tick_event(clock.now())

        assert event.event_type == "TIME_TICK"
        assert event.priority == 5  # Low priority
        assert event.source == "system"
        assert "current_time" in event.data
        assert event.data["current_time"] == clock.now()

    @pytest.mark.asyncio
    async def test_generator_runs_at_interval(self, clock):
        """Test: Generator produces ticks at specified interval."""
        # WILL FAIL: TimeTickGenerator class doesn't exist yet
        from src.timers.time_tick_generator import TimeTickGenerator

        tick_count = 0
        received_ticks = []

        async def tick_callback(event):
            nonlocal tick_count
            tick_count += 1
            received_ticks.append(event.data["current_time"])

        generator = TimeTickGenerator(interval_seconds=1)
        generator.set_callback(tick_callback)

        # Run generator for 3 seconds
        await generator.start()

        # Simulate time passing
        for _ in range(3):
            clock.advance(seconds=1)
            await generator.tick()  # Manual tick for testing

        await generator.stop()

        # Should have received ~3 ticks
        assert tick_count >= 2  # Allow for timing variance
        assert tick_count <= 4

    @pytest.mark.asyncio
    async def test_generator_can_be_paused_and_resumed(self):
        """Test: Generator can be paused and resumed."""
        # WILL FAIL: TimeTickGenerator class doesn't exist yet
        from src.timers.time_tick_generator import TimeTickGenerator

        tick_count = 0

        async def tick_callback(event):
            nonlocal tick_count
            tick_count += 1

        generator = TimeTickGenerator(interval_seconds=1)
        generator.set_callback(tick_callback)

        # Start and run
        await generator.start()
        await generator.tick()
        assert tick_count == 1

        # Pause
        generator.pause()
        await generator.tick()  # Should not increment
        assert tick_count == 1

        # Resume
        generator.resume()
        await generator.tick()
        assert tick_count == 2

        await generator.stop()

    def test_generator_different_intervals(self):
        """Test: Generator supports different interval configurations."""
        # WILL FAIL: TimeTickGenerator class doesn't exist yet
        from src.timers.time_tick_generator import TimeTickGenerator

        gen_1s = TimeTickGenerator(interval_seconds=1)
        assert gen_1s.interval_seconds == 1

        gen_5s = TimeTickGenerator(interval_seconds=5)
        assert gen_5s.interval_seconds == 5

        gen_60s = TimeTickGenerator(interval_seconds=60)
        assert gen_60s.interval_seconds == 60


# ============================================================================
# INTEGRATION TESTS: TimeTickGenerator with Risk Engine
# ============================================================================


@pytest.mark.integration
class TestTimeTickGeneratorIntegration:
    """Integration tests for TIME_TICK generator with risk engine."""

    @pytest.mark.asyncio
    async def test_tick_events_trigger_time_based_rules(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: TIME_TICK events trigger evaluation of time-based rules.

        Scenario:
        - NoStopLossGrace rule active
        - Position with expired grace
        - TIME_TICK event triggers rule evaluation
        - Position closed
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule
        from src.timers.time_tick_generator import TimeTickGenerator
        from tests.conftest import Position, Event

        # Setup enforcement and risk engine
        enforcement = EnforcementEngine(broker, state_manager)
        rule = NoStopLossGraceRule(grace_period_seconds=120)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Create position with expired grace
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
            stop_loss_attached=False,
            stop_loss_grace_expires=clock.now() - timedelta(seconds=5)
        )
        state_manager.add_position(account_id, position)

        # Generate TIME_TICK event
        generator = TimeTickGenerator(interval_seconds=1)
        tick_event = generator.create_tick_event(clock.now())
        tick_event.account_id = account_id

        # Process tick through risk engine
        await risk_engine.process_event(tick_event)

        # Verify: Position closed due to grace expiration
        assert len(broker.close_position_calls) == 1
        assert broker.close_position_calls[0]["position_id"] == position.position_id

    @pytest.mark.asyncio
    async def test_tick_generator_integrates_with_event_loop(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: TimeTickGenerator integrates with async event loop.

        Scenario:
        - Start generator
        - Collect ticks over time
        - Stop generator cleanly
        """
        # WILL FAIL: TimeTickGenerator class doesn't exist yet
        from src.timers.time_tick_generator import TimeTickGenerator

        collected_ticks = []

        async def collect_tick(event):
            collected_ticks.append(event)

        generator = TimeTickGenerator(interval_seconds=1)
        generator.set_callback(collect_tick)

        # Start generator
        await generator.start()

        # Run for a short period (simulate)
        for _ in range(3):
            await generator.tick()

        # Stop generator
        await generator.stop()

        # Verify ticks were collected
        assert len(collected_ticks) >= 2
        assert all(t.event_type == "TIME_TICK" for t in collected_ticks)


# ============================================================================
# E2E TESTS: TimeTickGenerator System Flow
# ============================================================================


@pytest.mark.e2e
class TestTimeTickGeneratorE2E:
    """End-to-end tests for TIME_TICK generator (full system flow)."""

    @pytest.mark.asyncio
    async def test_happy_path_continuous_monitoring(
        self,
        state_manager,
        broker,
        notifier,
        account_id,
        clock
    ):
        """
        Test: Happy path - continuous monitoring via TIME_TICK events.

        Flow:
        1. System starts with TimeTickGenerator
        2. Multiple positions open
        3. Generator produces ticks every second
        4. Rules evaluated on each tick
        5. Violations detected and enforced
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule
        from src.timers.time_tick_generator import TimeTickGenerator
        from tests.conftest import Position

        enforcement = EnforcementEngine(broker, state_manager, notifier)
        rule = NoStopLossGraceRule(grace_period_seconds=120)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Position 1: Compliant (has stop)
        pos1 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18000"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now() - timedelta(seconds=60),
            stop_loss_attached=True,
            stop_loss_grace_expires=clock.now() + timedelta(seconds=60)
        )
        state_manager.add_position(account_id, pos1)

        # Position 2: Non-compliant (grace expired, no stop)
        pos2 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4500"),
            unrealized_pnl=Decimal("0"),
            opened_at=clock.now() - timedelta(seconds=130),
            stop_loss_attached=False,
            stop_loss_grace_expires=clock.now() - timedelta(seconds=10)
        )
        state_manager.add_position(account_id, pos2)

        # Setup generator
        generator = TimeTickGenerator(interval_seconds=1)

        async def process_tick(event):
            event.account_id = account_id
            await risk_engine.process_event(event)

        generator.set_callback(process_tick)

        # Start and tick
        await generator.start()
        await generator.tick()
        await generator.stop()

        # Verify: Only pos2 closed
        assert len(broker.close_position_calls) == 1
        assert broker.close_position_calls[0]["position_id"] == pos2.position_id

        # Verify: Notification sent for pos2
        notifications = notifier.get_notifications(account_id)
        assert len(notifications) == 1
        assert notifications[0].severity == "critical"

    @pytest.mark.asyncio
    async def test_generator_handles_errors_gracefully(
        self,
        state_manager,
        clock
    ):
        """
        Test: Generator continues running even if callback raises error.

        Flow:
        1. Start generator with failing callback
        2. First tick fails
        3. Generator continues
        4. Second tick succeeds
        """
        # WILL FAIL: TimeTickGenerator class doesn't exist yet
        from src.timers.time_tick_generator import TimeTickGenerator

        tick_count = 0
        error_count = 0

        async def failing_callback(event):
            nonlocal tick_count, error_count
            tick_count += 1
            if tick_count == 1:
                error_count += 1
                raise Exception("Simulated error")
            # Succeed on subsequent ticks

        generator = TimeTickGenerator(interval_seconds=1)
        generator.set_callback(failing_callback)

        await generator.start()

        # First tick fails
        try:
            await generator.tick()
        except:
            pass  # Expected

        # Second tick succeeds
        await generator.tick()

        await generator.stop()

        # Verify generator continued after error
        assert tick_count == 2
        assert error_count == 1

    @pytest.mark.asyncio
    async def test_generator_performance_under_load(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: Generator performs well with many positions and rules.

        Flow:
        1. Create 100 positions
        2. Generate TIME_TICK events
        3. Verify reasonable processing time
        """
        # WILL FAIL: Full system doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.no_stop_loss_grace import NoStopLossGraceRule
        from src.timers.time_tick_generator import TimeTickGenerator
        from tests.conftest import Position
        import time

        enforcement = EnforcementEngine(broker, state_manager)
        rule = NoStopLossGraceRule(grace_period_seconds=120)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Create 100 positions
        for i in range(100):
            pos = Position(
                position_id=uuid4(),
                account_id=account_id,
                symbol=f"SYMBOL_{i}",
                side="long",
                quantity=1,
                entry_price=Decimal("1000"),
                current_price=Decimal("1000"),
                unrealized_pnl=Decimal("0"),
                opened_at=clock.now() - timedelta(seconds=60),
                stop_loss_attached=True,
                stop_loss_grace_expires=clock.now() + timedelta(seconds=60)
            )
            state_manager.add_position(account_id, pos)

        # Generate and process tick
        generator = TimeTickGenerator(interval_seconds=1)

        async def process_tick(event):
            event.account_id = account_id
            await risk_engine.process_event(event)

        generator.set_callback(process_tick)

        # Measure performance
        start = time.time()
        await generator.start()
        await generator.tick()
        await generator.stop()
        elapsed = time.time() - start

        # Should complete in reasonable time (< 1 second)
        assert elapsed < 1.0, f"Processing took too long: {elapsed}s"

        # Verify: No enforcement (all positions compliant)
        assert len(broker.close_position_calls) == 0
