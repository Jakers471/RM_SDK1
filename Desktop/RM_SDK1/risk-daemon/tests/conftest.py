"""
Test fixtures and mocks for Risk Manager Daemon tests.

Provides fake implementations based on adapter contracts from docs/integration/.
Does NOT import the SDK - all tests rely on contract-defined interfaces.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Set
from uuid import UUID, uuid4

import pytest
import pytz


# ============================================================================
# Core Data Models (from adapter contracts)
# ============================================================================


@dataclass
class Position:
    """Position model based on adapter contract."""

    position_id: UUID
    account_id: str
    symbol: str
    side: str  # "long" or "short"
    quantity: int
    entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    opened_at: datetime
    pending_close: bool = False
    stop_loss_attached: bool = False
    stop_loss_grace_expires: Optional[datetime] = None


@dataclass
class OrderResult:
    """Order result from adapter contract."""

    success: bool
    order_id: Optional[str]
    error_message: Optional[str]
    contract_id: str
    side: str
    quantity: int
    price: Optional[Decimal]


@dataclass
class Event:
    """Internal event model."""

    event_id: UUID
    event_type: str  # FILL, POSITION_UPDATE, CONNECTION_CHANGE, etc.
    timestamp: datetime
    priority: int
    account_id: str
    source: str
    data: Dict
    correlation_id: Optional[UUID] = None


# ============================================================================
# Fake Clock Service (for time-based testing)
# ============================================================================


class FakeClock:
    """
    Fake clock for time-based testing.

    Allows tests to control time progression and timezone.
    """

    def __init__(self, initial_time: Optional[datetime] = None):
        self._current_time = initial_time or datetime(2025, 10, 15, 10, 0, 0, tzinfo=timezone.utc)
        self.chicago_tz = pytz.timezone("America/Chicago")

    def now(self, tz: Optional[timezone] = None) -> datetime:
        """Get current time."""
        if tz:
            return self._current_time.astimezone(tz)
        return self._current_time

    def advance(self, seconds: int = 0, minutes: int = 0, hours: int = 0):
        """Advance time by delta."""
        delta = timedelta(seconds=seconds, minutes=minutes, hours=hours)
        self._current_time += delta

    def set_time(self, dt: datetime):
        """Set absolute time."""
        self._current_time = dt

    def get_chicago_time(self) -> datetime:
        """Get current time in Chicago timezone."""
        chicago_tz = pytz.timezone("America/Chicago")
        return self._current_time.astimezone(chicago_tz)


# ============================================================================
# Fake State Manager
# ============================================================================


class FakeStateManager:
    """
    Fake state manager based on architecture/04-state-management.md.

    Tracks positions, PnL, lockouts, cooldowns, and frequency windows.
    """

    def __init__(self, clock: FakeClock):
        self.clock = clock
        self.accounts: Dict[str, "AccountState"] = {}

    def get_account_state(self, account_id: str) -> "AccountState":
        """Get or create account state."""
        if account_id not in self.accounts:
            self.accounts[account_id] = AccountState(
                account_id=account_id,
                clock=self.clock
            )
        return self.accounts[account_id]

    def add_position(self, account_id: str, position: Position):
        """Add position to account."""
        state = self.get_account_state(account_id)
        state.open_positions.append(position)

    def update_position_price(self, account_id: str, position_id: UUID, current_price: Decimal):
        """Update position current price and recalculate unrealized PnL."""
        state = self.get_account_state(account_id)
        for pos in state.open_positions:
            if pos.position_id == position_id:
                pos.current_price = current_price
                # Recalculate unrealized PnL
                if pos.side == "long":
                    pos.unrealized_pnl = (current_price - pos.entry_price) * pos.quantity * Decimal("2.0")
                else:
                    pos.unrealized_pnl = (pos.entry_price - current_price) * pos.quantity * Decimal("2.0")
                break

    def close_position(self, account_id: str, position_id: UUID, realized_pnl: Decimal):
        """Close position and update realized PnL."""
        state = self.get_account_state(account_id)
        # Check if position exists before closing (idempotency)
        position_exists = any(p.position_id == position_id for p in state.open_positions)
        if position_exists:
            state.open_positions = [p for p in state.open_positions if p.position_id != position_id]
            state.realized_pnl_today += realized_pnl

    def get_open_positions(self, account_id: str) -> List[Position]:
        """Get all open positions for account."""
        return self.get_account_state(account_id).open_positions

    def get_realized_pnl(self, account_id: str) -> Decimal:
        """Get realized PnL today."""
        return self.get_account_state(account_id).realized_pnl_today

    def get_total_unrealized_pnl(self, account_id: str) -> Decimal:
        """Get total unrealized PnL across all positions."""
        positions = self.get_open_positions(account_id)
        return sum(p.unrealized_pnl for p in positions)

    def get_combined_exposure(self, account_id: str) -> Decimal:
        """Get combined realized + unrealized PnL."""
        realized = self.get_realized_pnl(account_id)
        unrealized = self.get_total_unrealized_pnl(account_id)
        return realized + unrealized

    def set_lockout(self, account_id: str, until: datetime, reason: str):
        """Set account lockout until specified time."""
        state = self.get_account_state(account_id)
        state.lockout_until = until
        state.lockout_reason = reason

    def is_locked_out(self, account_id: str) -> bool:
        """Check if account is locked out."""
        state = self.get_account_state(account_id)
        if state.lockout_until:
            return self.clock.now() < state.lockout_until
        return False

    def start_cooldown(self, account_id: str, duration_seconds: int, reason: str):
        """Start cooldown timer."""
        state = self.get_account_state(account_id)
        state.cooldown_until = self.clock.now() + timedelta(seconds=duration_seconds)

    def is_in_cooldown(self, account_id: str) -> bool:
        """Check if account is in cooldown."""
        state = self.get_account_state(account_id)
        if state.cooldown_until:
            return self.clock.now() < state.cooldown_until
        return False

    def get_position_count(self, account_id: str) -> int:
        """Get total contract count across all positions."""
        positions = self.get_open_positions(account_id)
        return sum(p.quantity for p in positions)

    def get_position_count_by_symbol(self, account_id: str, symbol: str) -> int:
        """Get contract count for specific symbol."""
        positions = self.get_open_positions(account_id)
        return sum(p.quantity for p in positions if p.symbol == symbol)

    def daily_reset(self, account_id: str):
        """Perform daily reset (called at 5pm CT)."""
        state = self.get_account_state(account_id)
        state.realized_pnl_today = Decimal("0.0")
        state.lockout_until = None
        state.lockout_reason = None
        state.last_daily_reset = self.clock.now()


@dataclass
class AccountState:
    """Per-account state."""

    account_id: str
    clock: FakeClock
    open_positions: List[Position] = field(default_factory=list)
    realized_pnl_today: Decimal = Decimal("0.0")
    lockout_until: Optional[datetime] = None
    lockout_reason: Optional[str] = None
    cooldown_until: Optional[datetime] = None
    last_daily_reset: Optional[datetime] = None
    error_state: bool = False


# ============================================================================
# Fake Notifier Service
# ============================================================================


@dataclass
class Notification:
    """Notification sent by system."""

    account_id: str
    title: str
    message: str
    severity: str  # "info", "warning", "critical"
    reason: str
    action: str
    timestamp: datetime


class FakeNotifier:
    """
    Fake notification service.

    Records all notifications sent for test assertions.
    """

    def __init__(self, clock: FakeClock):
        self.clock = clock
        self.notifications: List[Notification] = []

    def send(self, account_id: str, title: str, message: str, severity: str, reason: str, action: str):
        """Send notification."""
        notif = Notification(
            account_id=account_id,
            title=title,
            message=message,
            severity=severity,
            reason=reason,
            action=action,
            timestamp=self.clock.now()
        )
        self.notifications.append(notif)

    def get_notifications(self, account_id: Optional[str] = None) -> List[Notification]:
        """Get all notifications (optionally filtered by account)."""
        if account_id:
            return [n for n in self.notifications if n.account_id == account_id]
        return self.notifications

    def clear(self):
        """Clear all notifications."""
        self.notifications.clear()


# ============================================================================
# Fake Broker Adapter
# ============================================================================


class FakeBrokerAdapter:
    """
    Fake broker adapter based on adapter_contracts.md.

    Simulates order execution without real broker connection.
    """

    def __init__(self, clock: FakeClock, state_manager: Optional['FakeStateManager'] = None):
        self.clock = clock
        self.state_manager = state_manager
        self.orders: List[OrderResult] = []
        self.connected = False
        self.close_position_calls: List[Dict] = []
        self.flatten_account_calls: List[str] = []
        self._should_fail_next = False  # For retry testing
        self._simulate_delay = False  # For in-flight testing

    async def connect(self):
        """Simulate connection."""
        self.connected = True

    async def disconnect(self):
        """Simulate disconnection."""
        self.connected = False

    def is_connected(self) -> bool:
        """Check connection status."""
        return self.connected

    async def close_position(
        self,
        account_id: str,
        position_id: UUID,
        quantity: Optional[int] = None
    ) -> OrderResult:
        """Simulate closing position."""
        # Simulate delay for in-flight testing
        if self._simulate_delay:
            await asyncio.sleep(0.1)

        # Record call BEFORE potentially failing (so retry test can count attempts)
        self.close_position_calls.append({
            "account_id": account_id,
            "position_id": position_id,
            "quantity": quantity,
            "timestamp": self.clock.now()
        })

        # Support failure simulation for retry tests
        if self._should_fail_next:
            self._should_fail_next = False
            raise Exception("Simulated broker failure")

        # If state_manager is connected, handle position closing
        if self.state_manager:
            positions = self.state_manager.get_open_positions(account_id)
            target_pos = next((p for p in positions if p.position_id == position_id), None)

            if target_pos:
                # Check if we're simulating delay for async behavior testing
                # In that case, don't immediately close positions with pending_close
                if self._simulate_delay and target_pos.pending_close:
                    # For idempotency testing: position stays open with pending_close=True
                    # This simulates the broker taking time to process the close
                    pass
                else:
                    # Normal operation: close the position immediately
                    if quantity is None or quantity >= target_pos.quantity:
                        # Close entire position
                        self.state_manager.close_position(account_id, position_id, target_pos.unrealized_pnl)
                    else:
                        # Partial close: reduce quantity
                        target_pos.quantity -= quantity

        result = OrderResult(
            success=True,
            order_id=str(uuid4()),
            error_message=None,
            contract_id=f"CON.F.US.FAKE.{position_id}",
            side="sell",
            quantity=quantity or 1,
            price=None  # Market order
        )
        self.orders.append(result)
        return result

    async def flatten_account(self, account_id: str) -> List[OrderResult]:
        """Simulate flattening all positions."""
        self.flatten_account_calls.append(account_id)

        # If state_manager is connected, close all positions
        results = []
        if self.state_manager:
            positions = list(self.state_manager.get_open_positions(account_id))
            for pos in positions:
                self.state_manager.close_position(account_id, pos.position_id, pos.unrealized_pnl)
                results.append(OrderResult(
                    success=True,
                    order_id=str(uuid4()),
                    error_message=None,
                    contract_id=f"CON.F.US.FAKE.{pos.position_id}",
                    side="sell",
                    quantity=pos.quantity,
                    price=None
                ))
        else:
            # Fallback for tests without state_manager
            results = [
                OrderResult(
                    success=True,
                    order_id=str(uuid4()),
                    error_message=None,
                    contract_id=f"CON.F.US.FAKE.{i}",
                    side="sell",
                    quantity=1,
                    price=None
                )
                for i in range(2)  # Simulate closing 2 positions
            ]

        self.orders.extend(results)
        return results


# ============================================================================
# Fake Storage Service
# ============================================================================


class FakeStorage:
    """
    Fake storage for state persistence testing.

    In-memory storage that simulates disk persistence.
    """

    def __init__(self):
        self.data: Dict[str, Dict] = {}

    def save_account_state(self, account_id: str, state: Dict):
        """Save account state."""
        self.data[account_id] = state.copy()

    def load_account_state(self, account_id: str) -> Optional[Dict]:
        """Load account state."""
        return self.data.get(account_id)

    def clear(self):
        """Clear all saved state."""
        self.data.clear()


# ============================================================================
# Fake Time Service
# ============================================================================


class FakeTimeService:
    """
    Fake time service for session management.

    Handles session boundaries and daily resets.
    """

    def __init__(self, clock: FakeClock):
        self.clock = clock
        self.chicago_tz = pytz.timezone("America/Chicago")
        self.reset_callbacks: List = []

    def is_session_time(self, account_id: str) -> bool:
        """Check if current time is within trading session."""
        ct = self.clock.get_chicago_time()
        # Default session: Mon-Fri, 8am-3pm CT
        if ct.weekday() >= 5:  # Weekend
            return False
        if ct.hour < 8 or ct.hour >= 15:  # Outside hours
            return False
        return True

    def check_daily_reset(self) -> bool:
        """Check if daily reset should occur (5pm CT)."""
        ct = self.clock.get_chicago_time()
        return ct.hour == 17 and ct.minute == 0

    def trigger_reset_if_needed(self, state_manager: FakeStateManager):
        """Trigger daily reset if at 5pm CT OR if missed reset (catch-up)."""
        ct = self.clock.get_chicago_time()
        reset_time = ct.replace(hour=17, minute=0, second=0, microsecond=0)

        for account_id in state_manager.accounts.keys():
            state = state_manager.get_account_state(account_id)

            # Check if reset is needed:
            # 1. No reset today and past reset time (catch-up after downtime)
            # 2. Or exactly at reset time
            if state.last_daily_reset is None or state.last_daily_reset < reset_time:
                if ct >= reset_time:
                    state_manager.daily_reset(account_id)


# ============================================================================
# Pytest Fixtures
# ============================================================================


@pytest.fixture
def clock():
    """Provide fake clock starting at 10am CT on a trading day."""
    # 2025-10-15 10:00:00 CT = 2025-10-15 15:00:00 UTC
    chicago_tz = pytz.timezone("America/Chicago")
    ct_time = chicago_tz.localize(datetime(2025, 10, 15, 10, 0, 0))
    utc_time = ct_time.astimezone(timezone.utc)
    return FakeClock(initial_time=utc_time)


@pytest.fixture
def state_manager(clock):
    """Provide fake state manager."""
    return FakeStateManager(clock)


@pytest.fixture
def notifier(clock):
    """Provide fake notifier."""
    return FakeNotifier(clock)


@pytest.fixture
def broker(clock, state_manager):
    """Provide fake broker adapter."""
    broker = FakeBrokerAdapter(clock, state_manager)
    return broker


@pytest.fixture
def storage():
    """Provide fake storage."""
    return FakeStorage()


@pytest.fixture
def time_service(clock):
    """Provide fake time service."""
    return FakeTimeService(clock)


@pytest.fixture
def account_id():
    """Provide test account ID."""
    return "TEST_ACCOUNT_123"


@pytest.fixture
def sample_position(account_id, clock):
    """Provide sample position for testing."""
    return Position(
        position_id=uuid4(),
        account_id=account_id,
        symbol="MNQ",
        side="long",
        quantity=2,
        entry_price=Decimal("18000.00"),
        current_price=Decimal("18000.00"),
        unrealized_pnl=Decimal("0.00"),
        opened_at=clock.now()
    )
