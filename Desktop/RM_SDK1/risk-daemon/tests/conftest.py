"""
Test fixtures and mocks for Risk Manager Daemon tests.

Provides fake implementations based on adapter contracts from docs/integration/.
Does NOT import the SDK - all tests rely on contract-defined interfaces.
"""

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Set
from uuid import UUID, uuid4

import pytest
import pytz


# ============================================================================
# Pytest Hooks - Skip integration tests by default
# ============================================================================

def pytest_collection_modifyitems(config, items):
    """
    Skip integration tests by default unless ENABLE_INTEGRATION=1.

    Integration tests are opt-in to keep test suite fast.
    Run with: ENABLE_INTEGRATION=1 pytest
    """
    enable_integration = os.getenv("ENABLE_INTEGRATION", "0") == "1"
    enable_realtime = os.getenv("ENABLE_REALTIME", "0") == "1"

    skip_integration = pytest.mark.skip(reason="Integration tests require ENABLE_INTEGRATION=1")
    skip_realtime = pytest.mark.skip(reason="Realtime tests require ENABLE_REALTIME=1")

    for item in items:
        # Skip integration tests unless explicitly enabled
        if "integration" in item.keywords and not enable_integration:
            item.add_marker(skip_integration)

        # Skip realtime tests unless explicitly enabled
        if "realtime" in item.keywords and not enable_realtime:
            item.add_marker(skip_realtime)


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


# ============================================================================
# Configuration Test Fixtures
# ============================================================================


@pytest.fixture
def valid_system_config():
    """Provide valid system configuration dictionary for testing."""
    return {
        "version": "1.0",
        "daemon": {
            "auto_start": True,
            "log_level": "info",
            "state_persistence_path": "~/.risk_manager/state",
            "daily_reset_time": "17:00",
            "timezone": "America/Chicago"
        },
        "admin": {
            "password_hash": "$2b$12$" + "a" * 53,  # Valid bcrypt hash format
            "require_auth": True
        },
        "sdk": {
            "connection_timeout": 30,
            "reconnect_attempts": 5,
            "reconnect_delay": 10
        }
    }


@pytest.fixture
def valid_accounts_config():
    """Provide valid accounts configuration dictionary for testing."""
    return {
        "accounts": [
            {
                "account_id": "ACC001",
                "account_name": "Test TopStep Account",
                "enabled": True,
                "broker": "topstepx",
                "credentials": {
                    "api_key": "${TOPSTEP_API_KEY}",
                    "api_secret": "${TOPSTEP_API_SECRET}",
                    "account_number": "TS123456"
                },
                "risk_profile": "conservative"
            }
        ]
    }


@pytest.fixture
def valid_risk_rules_config():
    """Provide valid risk rules configuration dictionary for testing."""
    return {
        "profiles": {
            "conservative": {
                "rules": [
                    {
                        "rule": "MaxContracts",
                        "enabled": True,
                        "params": {"max_contracts": 2}
                    },
                    {
                        "rule": "DailyRealizedLoss",
                        "enabled": True,
                        "params": {"limit": -500.00}
                    },
                    {
                        "rule": "UnrealizedLoss",
                        "enabled": True,
                        "params": {"limit": -200.00}
                    }
                ]
            },
            "aggressive": {
                "rules": [
                    {
                        "rule": "MaxContracts",
                        "enabled": True,
                        "params": {"max_contracts": 10}
                    },
                    {
                        "rule": "DailyRealizedLoss",
                        "enabled": True,
                        "params": {"limit": -2000.00}
                    }
                ]
            }
        },
        "account_overrides": {}
    }


@pytest.fixture
def valid_notifications_config():
    """Provide valid notifications configuration dictionary for testing."""
    return {
        "discord": {
            "enabled": True,
            "webhook_url": "https://discord.com/api/webhooks/123456789/test_token"
        },
        "telegram": {
            "enabled": False,
            "bot_token": "",
            "chat_id": ""
        }
    }


# ============================================================================
# Logging Test Fixtures (for Component 20: Logging Framework)
# ============================================================================


@pytest.fixture
def temp_log_dir():
    """Provide temporary log directory for logging tests."""
    import tempfile
    import shutil

    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def valid_logging_config():
    """Provide valid logging configuration dictionary for testing."""
    return {
        "log_level": "info",
        "log_path": "~/.risk_manager/logs/",
        "rotation": {
            "max_size_mb": 50,
            "max_files": 10,
            "compress": False
        },
        "retention_days": 90,
        "structured_format": True,
        "windows_event_log": {
            "enabled": True,
            "log_critical_only": True
        }
    }


# ============================================================================
# Phase 3: Connection Manager & State Recovery Fixtures
# ============================================================================


@pytest.fixture
def mock_sdk_adapter():
    """
    Provide mock SDK adapter for connection manager testing.

    Supports connection simulation, failure injection, and reconnection testing.
    """
    from unittest.mock import AsyncMock, Mock

    sdk = AsyncMock()
    sdk.connect = AsyncMock()
    sdk.disconnect = AsyncMock()
    sdk.is_connected = Mock(return_value=True)
    sdk.ping = AsyncMock()
    sdk.ping_http = AsyncMock()
    sdk.is_websocket_connected = Mock(return_value=True)
    sdk.get_all_open_positions = AsyncMock(return_value=[])
    sdk.get_latest_quote = AsyncMock(return_value={"last_price": 5000.00})
    sdk.get_recent_fills = AsyncMock(return_value=[])
    sdk.query_positions_http = AsyncMock(return_value=[])

    # Failure injection support
    sdk.connect_fail_count = 0  # Number of times to fail connection
    sdk.should_fail_ping = False

    async def connect_with_failure():
        if sdk.connect_fail_count > 0:
            sdk.connect_fail_count -= 1
            raise ConnectionError("Simulated connection failure")
        sdk.is_connected.return_value = True

    sdk.connect.side_effect = connect_with_failure

    return sdk


@pytest.fixture
def temp_state_db():
    """
    Provide temporary state database path for testing.

    Creates a unique temp file path and cleans up after test.
    """
    import tempfile
    import os

    # Create temp file path
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)  # Remove the file, just want the path

    yield path

    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def mock_connection_health():
    """
    Provide mock connection health status for partial disconnect testing.
    """
    return {
        'http_connected': True,
        'websocket_connected': True,
        'last_heartbeat': datetime.now(timezone.utc),
        'uptime_seconds': 0.0
    }


@pytest.fixture
def simulated_disconnect_event():
    """
    Provide simulated disconnect event for testing connection manager.
    """
    return {
        'event_type': 'CONNECTION_LOST',
        'timestamp': datetime.now(timezone.utc),
        'reason': 'Network timeout',
        'can_reconnect': True
    }


@pytest.fixture
def crash_simulator():
    """
    Provide crash simulation utility for state recovery testing.

    Allows tests to simulate daemon crashes at specific points.
    """
    class CrashSimulator:
        def __init__(self):
            self.crash_on_next = False
            self.crash_after_calls = 0
            self.call_count = 0

        def inject_crash_after(self, calls: int):
            """Inject crash after N calls."""
            self.crash_after_calls = calls
            self.call_count = 0

        def check_and_crash(self):
            """Check if should crash and raise exception if so."""
            self.call_count += 1
            if self.crash_on_next:
                self.crash_on_next = False
                raise Exception("Simulated crash")
            if self.crash_after_calls > 0 and self.call_count >= self.crash_after_calls:
                raise Exception("Simulated crash after N calls")

    return CrashSimulator()


@pytest.fixture
def state_backup_manager():
    """
    Provide state backup manager for backup/rollback testing.
    """
    class StateBackupManager:
        def __init__(self):
            self.backups = {}

        def create_backup(self, name: str, state: Dict):
            """Create state backup with given name."""
            import copy
            self.backups[name] = copy.deepcopy(state)

        def restore_backup(self, name: str) -> Optional[Dict]:
            """Restore state from backup."""
            return self.backups.get(name)

        def list_backups(self) -> List[str]:
            """List all backup names."""
            return list(self.backups.keys())

        def delete_backup(self, name: str):
            """Delete backup."""
            if name in self.backups:
                del self.backups[name]

    return StateBackupManager()


@pytest.fixture
def frequency_tracker():
    """
    Provide frequency tracker for testing trade frequency persistence.
    """
    class FrequencyTracker:
        def __init__(self):
            self.trades: List[Dict] = []

        def record_trade(self, account_id: str, symbol: str, timestamp: datetime):
            """Record a trade."""
            self.trades.append({
                'account_id': account_id,
                'symbol': symbol,
                'timestamp': timestamp
            })

        def get_trade_count(self, account_id: str, window_seconds: int, current_time: datetime) -> int:
            """Get trade count within sliding window."""
            cutoff = current_time - timedelta(seconds=window_seconds)
            return sum(
                1 for trade in self.trades
                if trade['account_id'] == account_id and trade['timestamp'] >= cutoff
            )

        def clear(self):
            """Clear all trades."""
            self.trades.clear()

    return FrequencyTracker()


@pytest.fixture
def reconnection_metrics():
    """
    Provide reconnection metrics tracker for testing connection statistics.
    """
    @dataclass
    class ReconnectionMetrics:
        total_connections: int = 0
        total_disconnects: int = 0
        total_reconnects: int = 0
        failed_reconnects: int = 0
        event_gaps_detected: int = 0
        reconciliations_performed: int = 0
        connection_start_time: Optional[datetime] = None
        last_disconnect_time: Optional[datetime] = None

    return ReconnectionMetrics()


# ============================================================================
# Phase 4: CLI Interfaces Fixtures
# ============================================================================


@pytest.fixture
def mock_daemon_api_client():
    """
    Provide mock DaemonAPIClient for CLI testing.

    Simulates HTTP REST API responses from daemon on localhost:5555.
    """
    from unittest.mock import Mock, AsyncMock

    client = Mock()
    client.base_url = "http://127.0.0.1:5555"

    # Health endpoint
    client.get_health = Mock(return_value={
        "status": "healthy",
        "uptime_seconds": 3600,
        "version": "1.0.0",
        "memory_usage_mb": 125.5,
        "cpu_usage_percent": 3.2,
        "accounts": {}
    })

    # Positions endpoint
    client.get_positions = Mock(return_value={
        "account_id": "TEST123",
        "positions": [],
        "total_unrealized_pnl": 0.00
    })

    # PnL endpoint
    client.get_pnl = Mock(return_value={
        "account_id": "TEST123",
        "realized_pnl_today": 0.00,
        "unrealized_pnl": 0.00,
        "combined_pnl": 0.00,
        "daily_loss_limit": -500.00,
        "daily_profit_target": 1000.00,
        "lockout": False
    })

    # Enforcement log endpoint
    client.get_enforcement_log = Mock(return_value={
        "account_id": "TEST123",
        "enforcement_actions": []
    })

    # Authentication endpoint
    client.authenticate_admin = Mock(return_value=True)

    # Daemon control endpoints
    client.stop_daemon = Mock(return_value={
        "status": "shutting_down",
        "shutdown_eta_seconds": 5
    })

    # Config reload endpoint
    client.reload_config = Mock(return_value={
        "status": "success",
        "message": "Configuration reloaded successfully"
    })

    # Close method
    client.close = Mock()

    return client


@pytest.fixture
def mock_rich_console():
    """
    Provide mock Rich console for CLI output testing.

    Captures CLI output for assertions.
    """
    from unittest.mock import Mock

    console = Mock()
    console.print = Mock()
    console.clear = Mock()
    console.output_log = []  # Track all print calls

    def capture_print(*args, **kwargs):
        """Capture print calls for testing."""
        console.output_log.append({
            'args': args,
            'kwargs': kwargs
        })

    console.print.side_effect = capture_print

    return console


@pytest.fixture
def test_account_data():
    """
    Provide test account data for CLI display.
    """
    return {
        "account_id": "TEST123",
        "connected": True,
        "positions": [
            {
                "symbol": "MNQ",
                "side": "long",
                "quantity": 2,
                "entry_price": 5042.50,
                "current_price": 5055.00,
                "unrealized_pnl": 62.50
            }
        ],
        "pnl": {
            "realized_pnl_today": -150.00,
            "unrealized_pnl": 62.50,
            "combined_pnl": -87.50,
            "daily_loss_limit": -500.00,
            "daily_profit_target": 1000.00,
            "lockout": False
        }
    }


@pytest.fixture
def test_enforcement_actions():
    """
    Provide test enforcement actions for log display.
    """
    return [
        {
            "timestamp": "2025-10-17T14:30:00Z",
            "rule": "DailyLossLimit",
            "action": "FLATTEN_ALL",
            "result": "success",
            "breach": True,  # Should display in RED
            "position": {
                "symbol": "MNQ",
                "quantity": 2
            }
        },
        {
            "timestamp": "2025-10-17T14:25:00Z",
            "rule": "MaxContracts",
            "action": "CLOSE_EXCESS",
            "result": "success",
            "breach": False,
            "position": {
                "symbol": "ES",
                "quantity": 1
            }
        }
    ]


@pytest.fixture
def mock_admin_authentication():
    """
    Provide mock admin authentication flow.
    """
    class MockAuth:
        def __init__(self):
            self.attempts = 0
            self.max_attempts = 3
            self.correct_password = "admin_password"
            self.authenticated = False

        def authenticate(self, password: str) -> bool:
            """Simulate authentication."""
            self.attempts += 1
            if password == self.correct_password:
                self.authenticated = True
                return True
            if self.attempts >= self.max_attempts:
                return False
            return False

        def reset(self):
            """Reset authentication state."""
            self.attempts = 0
            self.authenticated = False

    return MockAuth()


@pytest.fixture
def cli_test_environment(mock_daemon_api_client, mock_rich_console, test_account_data):
    """
    Provide complete CLI test environment with mocked dependencies.

    Combines DaemonAPIClient, Rich console, and test data.
    """
    return {
        'daemon_client': mock_daemon_api_client,
        'console': mock_rich_console,
        'account_data': test_account_data
    }
