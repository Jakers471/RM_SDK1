"""
P0-3: Enforcement Idempotency Tests

Tests that enforcement actions are idempotent - duplicate requests don't cause
multiple enforcement actions. Critical for preventing over-enforcement.

Architecture reference: docs/architecture/03-enforcement-actions.md
"""

import pytest
import asyncio
from decimal import Decimal
from uuid import uuid4


# ============================================================================
# INTEGRATION TESTS: Enforcement Idempotency
# ============================================================================


@pytest.mark.integration
@pytest.mark.p0
class TestEnforcementIdempotency:
    """Integration tests for idempotent enforcement actions."""

    @pytest.mark.asyncio
    async def test_duplicate_close_position_requests_ignored(
        self,
        state_manager,
        broker,
        account_id
    ):
        """
        Test: Duplicate close_position requests are idempotent.

        Scenario:
        - Two concurrent events trigger same position close
        - First close executes
        - Second close detected as duplicate and skipped
        - Only ONE broker order placed
        """
        # WILL FAIL: EnforcementEngine idempotency logic doesn't exist yet
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Position

        enforcement = EnforcementEngine(broker, state_manager)

        # Add position
        pos = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=2,
            entry_price=Decimal("18000"),
            current_price=Decimal("17900"),
            unrealized_pnl=Decimal("-200"),
            opened_at=state_manager.clock.now()
        )
        state_manager.add_position(account_id, pos)

        # Simulate concurrent close requests (race condition)
        await asyncio.gather(
            enforcement.close_position(
                account_id=account_id,
                position_id=pos.position_id,
                quantity=2,
                reason="Test concurrent 1"
            ),
            enforcement.close_position(
                account_id=account_id,
                position_id=pos.position_id,
                quantity=2,
                reason="Test concurrent 2"
            )
        )

        # Verify only ONE broker call made
        assert len(broker.close_position_calls) == 1

    @pytest.mark.asyncio
    async def test_position_marked_pending_close_prevents_duplicate(
        self,
        state_manager,
        broker,
        account_id
    ):
        """
        Test: Position marked as pending_close prevents duplicate enforcement.

        Scenario:
        - First enforcement marks position as pending_close
        - Second event arrives before close confirmed
        - Risk engine checks pending_close flag
        - Second enforcement skipped
        """
        # WILL FAIL: pending_close flag logic doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.unrealized_loss import UnrealizedLossRule
        from tests.conftest import Event, Position

        enforcement = EnforcementEngine(broker, state_manager)
        rule = UnrealizedLossRule(limit=Decimal("-200.00"))
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Add position with loss
        pos = Position(
            position_id=uuid4(),
            account_id=account_id,
            symbol="MNQ",
            side="long",
            quantity=1,
            entry_price=Decimal("18000"),
            current_price=Decimal("17900"),
            unrealized_pnl=Decimal("-200"),
            opened_at=state_manager.clock.now(),
            pending_close=False
        )
        state_manager.add_position(account_id, pos)

        # First event triggers close (should mark pending_close)
        event1 = Event(
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
                "unrealized_pnl": Decimal("-200"),
                "quantity": 1,
                "update_time": state_manager.clock.now()
            }
        )
        await risk_engine.process_event(event1)

        # Verify position marked pending_close
        position = state_manager.get_open_positions(account_id)[0]
        assert position.pending_close is True

        # Second event (before close confirmed) should be ignored
        event2 = Event(
            event_id=uuid4(),
            event_type="POSITION_UPDATE",
            timestamp=state_manager.clock.now(),
            priority=2,
            account_id=account_id,
            source="broker",
            data={
                "position_id": pos.position_id,
                "symbol": "MNQ",
                "current_price": Decimal("17895"),
                "unrealized_pnl": Decimal("-210"),
                "quantity": 1,
                "update_time": state_manager.clock.now()
            }
        )
        await risk_engine.process_event(event2)

        # Verify only ONE close call
        assert len(broker.close_position_calls) == 1

    @pytest.mark.asyncio
    async def test_flatten_account_idempotent(
        self,
        state_manager,
        broker,
        account_id
    ):
        """
        Test: Multiple flatten_account requests are idempotent.

        Scenario:
        - Combined PnL triggers daily limit
        - Multiple events arrive simultaneously
        - Only ONE flatten_account call executed
        """
        # WILL FAIL: Idempotency tracking doesn't exist yet
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Position

        enforcement = EnforcementEngine(broker, state_manager)

        # Add multiple positions
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
        pos2 = Position(
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
        state_manager.add_position(account_id, pos1)
        state_manager.add_position(account_id, pos2)

        # Simulate concurrent flatten requests
        await asyncio.gather(
            enforcement.flatten_account(account_id, reason="Test 1"),
            enforcement.flatten_account(account_id, reason="Test 2"),
            enforcement.flatten_account(account_id, reason="Test 3")
        )

        # Verify only ONE flatten call
        assert len(broker.flatten_account_calls) == 1

    @pytest.mark.asyncio
    async def test_lockout_prevents_new_fills_enforcement(
        self,
        state_manager,
        broker,
        account_id,
        clock
    ):
        """
        Test: Lockout flag prevents enforcement on new fills.

        Scenario:
        - Account locked out (daily limit hit)
        - New fill arrives (should be rejected immediately)
        - No rule evaluation performed (early exit)
        """
        # WILL FAIL: Lockout early-exit logic doesn't exist yet
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.rules.max_contracts import MaxContractsRule
        from tests.conftest import Event
        import pytz

        enforcement = EnforcementEngine(broker, state_manager)
        rule = MaxContractsRule(max_contracts=4)
        risk_engine = RiskEngine(
            state_manager=state_manager,
            enforcement_engine=enforcement,
            rules=[rule]
        )

        # Set lockout
        chicago_tz = pytz.timezone("America/Chicago")
        lockout_time = clock.get_chicago_time().replace(hour=17, minute=0)
        state_manager.set_lockout(account_id, lockout_time, "Daily limit exceeded")

        # Verify locked out
        assert state_manager.is_locked_out(account_id) is True

        # New fill event arrives
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

        # Verify fill rejected (closed immediately)
        assert len(broker.close_position_calls) == 1

        # Verify reason indicates lockout
        # (enforcement engine should log this)

    @pytest.mark.asyncio
    async def test_in_flight_action_tracking(
        self,
        state_manager,
        broker,
        account_id
    ):
        """
        Test: In-flight action tracking prevents concurrent duplicates.

        Scenario:
        - Action started, added to in_flight set
        - Duplicate request arrives while first in progress
        - Duplicate detects in_flight, returns immediately
        - First action completes, removed from in_flight
        """
        # WILL FAIL: In-flight tracking doesn't exist yet
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Position

        enforcement = EnforcementEngine(broker, state_manager)

        pos = Position(
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
        state_manager.add_position(account_id, pos)

        # Start first action (should add to in_flight)
        task1 = asyncio.create_task(
            enforcement.close_position(
                account_id=account_id,
                position_id=pos.position_id,
                quantity=1,
                reason="First"
            )
        )

        # Small delay to ensure first task starts
        await asyncio.sleep(0.01)

        # Verify in_flight tracking contains action
        action_key = f"{account_id}_{pos.position_id}_close"
        assert action_key in enforcement._in_flight_actions

        # Second request should detect in_flight
        result2 = await enforcement.close_position(
            account_id=account_id,
            position_id=pos.position_id,
            quantity=1,
            reason="Second (duplicate)"
        )

        # Verify second request skipped
        assert result2.success is False
        assert "already in progress" in result2.error_message.lower()

        # Wait for first to complete
        await task1

        # Verify removed from in_flight
        assert action_key not in enforcement._in_flight_actions

        # Verify only one broker call
        assert len(broker.close_position_calls) == 1

    @pytest.mark.asyncio
    async def test_retry_not_counted_as_duplicate(
        self,
        state_manager,
        broker,
        account_id
    ):
        """
        Test: Retries after failure are NOT considered duplicates.

        Scenario:
        - First attempt fails (network error)
        - Retry logic attempts again after backoff
        - Retry is allowed (not treated as duplicate)
        - Both attempts logged correctly
        """
        # WILL FAIL: Retry logic doesn't exist yet
        from src.core.enforcement_engine import EnforcementEngine
        from tests.conftest import Position

        enforcement = EnforcementEngine(broker, state_manager)

        pos = Position(
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
        state_manager.add_position(account_id, pos)

        # Make first attempt fail
        broker._should_fail_next = True

        result = await enforcement.close_position(
            account_id=account_id,
            position_id=pos.position_id,
            quantity=1,
            reason="Test retry",
            max_retries=2
        )

        # Should eventually succeed after retries
        assert result.success is True

        # Verify multiple attempts (original + retries)
        assert len(broker.close_position_calls) >= 2
