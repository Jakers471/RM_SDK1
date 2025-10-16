"""
P0-4: SessionBlockOutside + 17:00 CT Reset Tests

Tests session-based trading restrictions and daily reset at 5pm Chicago Time.
Critical for maintaining daily risk limits and preventing after-hours trading.

Architecture reference:
- docs/architecture/02-risk-engine.md (Rule 10: SessionBlockOutside)
- docs/architecture/04-state-management.md (Daily Reset Logic)
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import datetime, timedelta
import pytz


# ============================================================================
# INTEGRATION TESTS: SessionBlockOutside Rule
# ============================================================================


@pytest.mark.integration
@pytest.mark.p0
class TestSessionBlockOutside:
    """Integration tests for session-based trading restrictions."""

    @pytest.mark.asyncio
    async def test_fill_during_session_allowed(
        self,
        state_manager,
        broker,
        time_service,
        account_id,
        clock
    ):
        """
        Test: Fills during allowed session are permitted.

        Scenario:
        - Session: Mon-Fri, 8am-3pm CT
        - Current time: Tuesday 10am CT
        - Fill arrives
        - Expected: No enforcement action
        """
        # WILL FAIL: SessionBlockOutside rule doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.session_block import SessionBlockOutsideRule
        from tests.conftest import Event

        # Set time to Tuesday 10am CT
        chicago_tz = pytz.timezone("America/Chicago")
        tuesday_10am_ct = chicago_tz.localize(datetime(2025, 10, 14, 10, 0, 0))
        clock.set_time(tuesday_10am_ct.astimezone(pytz.UTC))

        enforcement = EnforcementEngine(broker, state_manager)
        rule = SessionBlockOutsideRule(
            allowed_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            allowed_times=[{"start": "08:00", "end": "15:00"}],
            timezone="America/Chicago"
        )
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Fill event
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
                "order_id": "ORD123",
                "fill_time": clock.now()
            }
        )

        await risk_engine.process_event(fill_event)

        # No enforcement should occur
        assert len(broker.close_position_calls) == 0

    @pytest.mark.asyncio
    async def test_fill_outside_session_rejected(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: Fills outside session are immediately closed.

        Scenario:
        - Session: Mon-Fri, 8am-3pm CT
        - Current time: Tuesday 4:30pm CT (after hours)
        - Fill arrives
        - Expected: Position closed immediately
        """
        # WILL FAIL: SessionBlockOutside rule doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.session_block import SessionBlockOutsideRule
        from tests.conftest import Event

        # Set time to Tuesday 4:30pm CT (after session end)
        chicago_tz = pytz.timezone("America/Chicago")
        tuesday_430pm_ct = chicago_tz.localize(datetime(2025, 10, 14, 16, 30, 0))
        clock.set_time(tuesday_430pm_ct.astimezone(pytz.UTC))

        enforcement = EnforcementEngine(broker, state_manager)
        rule = SessionBlockOutsideRule(
            allowed_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            allowed_times=[{"start": "08:00", "end": "15:00"}],
            timezone="America/Chicago"
        )
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Fill event outside session
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
                "order_id": "ORD123",
                "fill_time": clock.now()
            }
        )

        await risk_engine.process_event(fill_event)

        # Should close position immediately
        assert len(broker.close_position_calls) == 1

    @pytest.mark.asyncio
    async def test_session_end_flattens_all_positions(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: At session end (3pm), all remaining positions flattened.

        Scenario:
        - Positions opened during session
        - Time reaches 3:00pm CT (session end)
        - Expected: All positions flattened automatically
        """
        # WILL FAIL: Session end logic doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.session_block import SessionBlockOutsideRule
        from tests.conftest import Event, Position

        # Set time to 2:55pm CT (5 minutes before session end)
        chicago_tz = pytz.timezone("America/Chicago")
        tuesday_255pm_ct = chicago_tz.localize(datetime(2025, 10, 14, 14, 55, 0))
        clock.set_time(tuesday_255pm_ct.astimezone(pytz.UTC))

        enforcement = EnforcementEngine(broker, state_manager)
        rule = SessionBlockOutsideRule(
            allowed_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            allowed_times=[{"start": "08:00", "end": "15:00"}],
            timezone="America/Chicago"
        )
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Add positions
        pos1 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18010"),
            unrealized_pnl=Decimal("40"),
            opened_at=clock.now()
        )
        pos2 = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="ES",
            side="long",
            quantity=1,
            entry_price=Decimal("4500"),
            current_price=Decimal("4505"),
            unrealized_pnl=Decimal("25"),
            opened_at=clock.now()
        )
        state_manager.add_position(account_id, pos1)
        state_manager.add_position(account_id, pos2)

        # Advance time to 3:00pm CT (session end)
        clock.advance(minutes=5)

        # TIME_TICK event triggers session boundary check
        time_tick_event = Event(
            event_id=uuid4(),
            event_type="TIME_TICK",
            timestamp=clock.now(),
            priority=4,
            account_id="system",
            source="timer",
            data={"tick_time": clock.now()}
        )

        await risk_engine.process_event(time_tick_event)

        # Should flatten all positions
        assert len(broker.flatten_account_calls) == 1
        assert broker.flatten_account_calls[0] == account_id

    @pytest.mark.asyncio
    async def test_weekend_fills_rejected(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: Fills on weekends are immediately closed.

        Scenario:
        - Current time: Saturday 10am CT
        - Fill arrives (shouldn't happen, but test defensive code)
        - Expected: Position closed immediately
        """
        # WILL FAIL: Weekend detection doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.session_block import SessionBlockOutsideRule
        from tests.conftest import Event

        # Set time to Saturday 10am CT
        chicago_tz = pytz.timezone("America/Chicago")
        saturday_10am_ct = chicago_tz.localize(datetime(2025, 10, 18, 10, 0, 0))  # Saturday
        clock.set_time(saturday_10am_ct.astimezone(pytz.UTC))

        enforcement = EnforcementEngine(broker, state_manager)
        rule = SessionBlockOutsideRule(
            allowed_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            allowed_times=[{"start": "08:00", "end": "15:00"}],
            timezone="America/Chicago"
        )
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Fill event on weekend
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
                "order_id": "ORD123",
                "fill_time": clock.now()
            }
        )

        await risk_engine.process_event(fill_event)

        # Should close immediately
        assert len(broker.close_position_calls) == 1


# ============================================================================
# INTEGRATION TESTS: 5pm CT Daily Reset
# ============================================================================


@pytest.mark.integration
@pytest.mark.p0
class TestDailyReset:
    """Integration tests for daily reset at 5pm Chicago Time."""

    def test_reset_at_exactly_5pm_ct(
        self,
        state_manager,
        time_service,
        account_id,
        clock
    ):
        """
        Test: Daily reset occurs at exactly 5:00pm CT.

        Scenario:
        - Current time: 4:59pm CT
        - Realized PnL: -$500
        - Time advances to 5:00pm CT
        - Expected: Realized PnL reset to $0
        """
        # WILL FAIL: Daily reset logic doesn't exist yet
        from src.timers.session_timer import SessionTimer

        # Set initial state
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-500.00")

        # Set time to 4:59pm CT
        chicago_tz = pytz.timezone("America/Chicago")
        tuesday_459pm_ct = chicago_tz.localize(datetime(2025, 10, 14, 16, 59, 0))
        clock.set_time(tuesday_459pm_ct.astimezone(pytz.UTC))

        # Verify not reset yet
        assert state_manager.get_realized_pnl(account_id) == Decimal("-500.00")

        # Advance to 5:00pm CT
        clock.advance(minutes=1)

        # Trigger reset check
        time_service.trigger_reset_if_needed(state_manager)

        # Verify reset occurred
        assert state_manager.get_realized_pnl(account_id) == Decimal("0.00")

    def test_reset_clears_lockout_flags(
        self,
        state_manager,
        time_service,
        account_id,
        clock
    ):
        """
        Test: Daily reset clears lockout flags.

        Scenario:
        - Account locked out (daily limit hit)
        - Time reaches 5:00pm CT
        - Expected: Lockout cleared, trading allowed next day
        """
        # WILL FAIL: Daily reset lockout clearing doesn't exist yet

        # Set lockout
        chicago_tz = pytz.timezone("America/Chicago")
        tuesday_2pm_ct = chicago_tz.localize(datetime(2025, 10, 14, 14, 0, 0))
        clock.set_time(tuesday_2pm_ct.astimezone(pytz.UTC))

        lockout_time = clock.get_chicago_time().replace(hour=17, minute=0)
        state_manager.set_lockout(account_id, lockout_time, "Daily limit exceeded")

        # Verify locked out
        assert state_manager.is_locked_out(account_id) is True

        # Advance to 5:00pm CT (reset time)
        clock.set_time(lockout_time.astimezone(pytz.UTC))

        # Trigger reset
        time_service.trigger_reset_if_needed(state_manager)

        # Verify lockout cleared
        assert state_manager.is_locked_out(account_id) is False

    def test_reset_preserves_open_positions(
        self,
        state_manager,
        time_service,
        account_id,
        clock
    ):
        """
        Test: Daily reset does NOT close open positions.

        Scenario:
        - Open positions exist
        - 5:00pm CT reset occurs
        - Expected: Positions remain open, only counters reset
        """
        # WILL FAIL: Reset logic doesn't exist yet
        from tests.conftest import Position

        # Add position
        pos = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("18010"),
            unrealized_pnl=Decimal("40"),
            opened_at=clock.now()
        )
        state_manager.add_position(account_id, pos)

        # Set realized PnL
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-300.00")

        # Advance to 5pm CT
        chicago_tz = pytz.timezone("America/Chicago")
        tuesday_5pm_ct = chicago_tz.localize(datetime(2025, 10, 14, 17, 0, 0))
        clock.set_time(tuesday_5pm_ct.astimezone(pytz.UTC))

        # Trigger reset
        time_service.trigger_reset_if_needed(state_manager)

        # Verify realized PnL reset
        assert state_manager.get_realized_pnl(account_id) == Decimal("0.00")

        # Verify position still open
        positions = state_manager.get_open_positions(account_id)
        assert len(positions) == 1
        assert positions[0].position_id == pos.position_id

    def test_dst_transition_handles_correctly(
        self,
        state_manager,
        time_service,
        account_id,
        clock
    ):
        """
        Test: DST transitions handled correctly for 5pm reset.

        Scenario:
        - DST spring forward (March): 2am -> 3am
        - Verify 5pm CT still detected correctly
        - DST fall back (November): 2am -> 1am
        - Verify 5pm CT still detected correctly
        """
        # WILL FAIL: DST handling doesn't exist yet

        chicago_tz = pytz.timezone("America/Chicago")

        # Test Spring Forward (March 2025)
        # Note: DST transition happens at 2am, but we're testing 5pm
        march_5pm_ct = chicago_tz.localize(datetime(2025, 3, 9, 17, 0, 0))
        clock.set_time(march_5pm_ct.astimezone(pytz.UTC))

        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-100.00")

        time_service.trigger_reset_if_needed(state_manager)

        assert state_manager.get_realized_pnl(account_id) == Decimal("0.00")

        # Reset state for next test
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-200.00")

        # Test Fall Back (November 2025)
        nov_5pm_ct = chicago_tz.localize(datetime(2025, 11, 2, 17, 0, 0))
        clock.set_time(nov_5pm_ct.astimezone(pytz.UTC))

        time_service.trigger_reset_if_needed(state_manager)

        assert state_manager.get_realized_pnl(account_id) == Decimal("0.00")

    def test_reset_only_once_per_day(
        self,
        state_manager,
        time_service,
        account_id,
        clock
    ):
        """
        Test: Reset occurs only once per day, not every minute at 5pm.

        Scenario:
        - Reset occurs at 5:00pm
        - Timer checks again at 5:01pm, 5:02pm, etc.
        - Expected: No duplicate resets
        """
        # WILL FAIL: Reset deduplication doesn't exist yet

        chicago_tz = pytz.timezone("America/Chicago")
        tuesday_5pm_ct = chicago_tz.localize(datetime(2025, 10, 14, 17, 0, 0))
        clock.set_time(tuesday_5pm_ct.astimezone(pytz.UTC))

        # Set initial PnL
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-500.00")

        # First reset at 5:00pm
        time_service.trigger_reset_if_needed(state_manager)
        assert state_manager.get_realized_pnl(account_id) == Decimal("0.00")

        # Add new realized loss after reset
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-50.00")

        # Check again at 5:01pm (should not reset again)
        clock.advance(minutes=1)
        time_service.trigger_reset_if_needed(state_manager)

        # Should still be -$50 (not reset to $0 again)
        assert state_manager.get_realized_pnl(account_id) == Decimal("-50.00")

    def test_reset_after_daemon_downtime(
        self,
        state_manager,
        time_service,
        account_id,
        clock
    ):
        """
        Test: Missed reset handled when daemon restarts after 5pm.

        Scenario:
        - Daemon down at 4pm
        - Daemon restarts at 6pm (missed 5pm reset)
        - Expected: Reset performed on first check after restart
        """
        # WILL FAIL: Missed reset detection doesn't exist yet

        chicago_tz = pytz.timezone("America/Chicago")

        # Set last reset to yesterday
        yesterday_5pm_ct = chicago_tz.localize(datetime(2025, 10, 13, 17, 0, 0))
        state_manager.get_account_state(account_id).last_daily_reset = yesterday_5pm_ct

        # Set realized PnL (from yesterday)
        state_manager.get_account_state(account_id).realized_pnl_today = Decimal("-400.00")

        # Current time is 6pm today (missed 5pm reset)
        tuesday_6pm_ct = chicago_tz.localize(datetime(2025, 10, 14, 18, 0, 0))
        clock.set_time(tuesday_6pm_ct.astimezone(pytz.UTC))

        # Trigger reset check
        time_service.trigger_reset_if_needed(state_manager)

        # Should perform reset even though current time is past 5pm
        assert state_manager.get_realized_pnl(account_id) == Decimal("0.00")
        assert state_manager.get_account_state(account_id).last_daily_reset.date() == tuesday_6pm_ct.date()
