"""
StateManager - Central state management for Risk Manager.

Tracks positions, PnL, lockouts, and account state.
Provides combined PnL calculations and state queries.

Architecture reference: docs/architecture/04-state-management.md
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, time, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Union
from uuid import UUID


class RealizedPnLTracker:
    """
    Tracks realized P&L from trade fills.

    CRITICAL: SDK does NOT provide account-level P&L tracking.
    Trade.profitAndLoss is None for "half-turn" trades (opening positions).
    Only closing trades have P&L.

    Architecture reference: docs/research/sdk_integration_challenges.md Issue #4
    """

    def __init__(self, market_open_time: time = time(9, 30), clock=None):
        """
        Initialize realized P&L tracker.

        Args:
            market_open_time: Time to reset daily P&L (default 9:30 AM)
            clock: Optional clock instance for testing
        """
        self.daily_pnl: Dict[str, Decimal] = {}  # account_id -> Decimal
        self.last_reset = None  # Will be set on first check
        self.market_open_time = market_open_time
        self.clock = clock

    def add_trade_pnl(self, account_id: str, pnl: float):
        """
        Add realized P&L from a trade fill.

        Args:
            account_id: Account ID
            pnl: Profit/loss from trade (positive = profit, negative = loss)
        """
        # Check for daily reset
        self._check_and_reset()

        # Initialize account if not exists
        if account_id not in self.daily_pnl:
            self.daily_pnl[account_id] = Decimal('0.0')

        # Add trade P&L
        self.daily_pnl[account_id] += Decimal(str(pnl))

    def get_daily_realized_pnl(self, account_id: str) -> Decimal:
        """
        Get total realized P&L for today.

        Args:
            account_id: Account ID

        Returns:
            Daily realized P&L (Decimal)
        """
        self._check_and_reset()
        return self.daily_pnl.get(account_id, Decimal('0.0'))

    def _check_and_reset(self):
        """Check if new trading day and reset P&L if needed."""
        now = self.clock.now() if self.clock else datetime.now()
        today = now.date()

        # First run - initialize last_reset
        if self.last_reset is None:
            self.last_reset = today
            return

        # Check if we've crossed into a new trading day after market open
        if today > self.last_reset and now.time() >= self.market_open_time:
            # New trading day - reset all P&L
            self.daily_pnl.clear()
            self.last_reset = today

    def force_reset(self, account_id: Optional[str] = None):
        """
        Force reset P&L (for testing or manual intervention).

        Args:
            account_id: Account to reset (None = reset all)
        """
        if account_id:
            self.daily_pnl[account_id] = Decimal('0.0')
        else:
            self.daily_pnl.clear()
            now = self.clock.now() if self.clock else datetime.now()
            self.last_reset = now.date()


@dataclass
class Position:
    """Position model."""
    position_id: Union[str, UUID]
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
class AccountState:
    """Per-account state."""
    account_id: str
    open_positions: List[Position] = field(default_factory=list)
    realized_pnl_today: Decimal = Decimal("0.0")
    lockout_until: Optional[datetime] = None
    lockout_reason: Optional[str] = None
    cooldown_until: Optional[datetime] = None
    last_daily_reset: Optional[datetime] = None
    error_state: bool = False
    _closed_position_ids: List[Union[str, UUID]] = field(default_factory=list)  # Track closed positions

    @property
    def positions(self) -> List[Position]:
        """Alias for open_positions (for test compatibility)."""
        return self.open_positions


class StateManager:
    """
    Central state manager for all accounts.

    Provides:
    - Position tracking
    - Combined PnL calculation
    - Lockout management
    - Daily reset logic
    - State persistence and recovery
    """

    def __init__(self, persistence=None, clock=None):
        """
        Initialize state manager.

        Args:
            persistence: StatePersistence instance for durable storage
            clock: Clock instance for time queries (optional, uses datetime.utcnow if None)
        """
        self.clock = clock
        self.persistence = persistence
        self.accounts: Dict[str, AccountState] = {}
        self._initialized = False

    def get_account_state(self, account_id: str) -> AccountState:
        """
        Get or create account state.

        Args:
            account_id: Account ID

        Returns:
            AccountState instance
        """
        if account_id not in self.accounts:
            self.accounts[account_id] = AccountState(account_id=account_id)
        return self.accounts[account_id]

    def add_position(self, account_id: str, position: Position):
        """Add position to account."""
        state = self.get_account_state(account_id)
        state.open_positions.append(position)

    def update_position_price(
        self,
        account_id: str,
        position_id: UUID,
        current_price: Decimal
    ):
        """
        Update position current price and recalculate unrealized PnL.

        Args:
            account_id: Account ID
            position_id: Position ID
            current_price: New current price
        """
        state = self.get_account_state(account_id)
        for pos in state.open_positions:
            if pos.position_id == position_id:
                pos.current_price = current_price
                # Recalculate unrealized PnL (assuming tick value = 2.0 for MNQ)
                if pos.side == "long":
                    pos.unrealized_pnl = (current_price - pos.entry_price) * pos.quantity * Decimal("2.0")
                else:
                    pos.unrealized_pnl = (pos.entry_price - current_price) * pos.quantity * Decimal("2.0")
                break

    def close_position(
        self,
        account_id: str,
        position_id: UUID,
        realized_pnl: Decimal
    ):
        """
        Close position and update realized PnL.

        Args:
            account_id: Account ID
            position_id: Position ID
            realized_pnl: PnL realized from closing position
        """
        state = self.get_account_state(account_id)
        state.open_positions = [
            p for p in state.open_positions
            if p.position_id != position_id
        ]
        state.realized_pnl_today += realized_pnl

    def get_open_positions(self, account_id: str) -> List[Position]:
        """Get all open positions for account."""
        return self.get_account_state(account_id).open_positions

    def get_realized_pnl(self, account_id: str) -> Decimal:
        """Get realized PnL today."""
        return self.get_account_state(account_id).realized_pnl_today

    async def set_realized_pnl(self, account_id: str, pnl: float):
        """
        Set realized PnL (for testing).

        Args:
            account_id: Account ID
            pnl: PnL value to set
        """
        state = self.get_account_state(account_id)
        state.realized_pnl_today = Decimal(str(pnl))

    def get_total_unrealized_pnl(self, account_id: str) -> Decimal:
        """Get total unrealized PnL across all positions."""
        positions = self.get_open_positions(account_id)
        return sum(p.unrealized_pnl for p in positions)

    def get_combined_exposure(self, account_id: str) -> Decimal:
        """
        Get combined realized + unrealized PnL.

        This is the CRITICAL metric for daily loss monitoring.

        Args:
            account_id: Account ID

        Returns:
            Combined exposure (realized + unrealized)
        """
        realized = self.get_realized_pnl(account_id)
        unrealized = self.get_total_unrealized_pnl(account_id)
        return realized + unrealized

    def set_lockout(self, account_id: str, until: datetime, reason: str):
        """
        Set account lockout until specified time.

        Args:
            account_id: Account ID
            until: Lockout until datetime
            reason: Reason for lockout
        """
        state = self.get_account_state(account_id)
        state.lockout_until = until
        state.lockout_reason = reason

    def is_locked_out(self, account_id: str) -> bool:
        """
        Check if account is locked out.

        Args:
            account_id: Account ID

        Returns:
            True if locked out
        """
        state = self.get_account_state(account_id)
        if state.lockout_until:
            current_time = self.clock.now() if self.clock else datetime.utcnow()
            return current_time < state.lockout_until
        return False

    def start_cooldown(self, account_id: str, duration_seconds: int, reason: str):
        """Start cooldown timer."""
        from datetime import timedelta
        state = self.get_account_state(account_id)
        current_time = self.clock.now() if self.clock else datetime.utcnow()
        state.cooldown_until = current_time + timedelta(seconds=duration_seconds)

    def is_in_cooldown(self, account_id: str) -> bool:
        """Check if account is in cooldown."""
        state = self.get_account_state(account_id)
        if state.cooldown_until:
            current_time = self.clock.now() if self.clock else datetime.utcnow()
            return current_time < state.cooldown_until
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
        """
        Perform daily reset (called at 5pm CT).

        Resets:
        - Realized PnL to $0
        - Lockout flags
        - Updates last_daily_reset timestamp

        Does NOT close positions.
        """
        state = self.get_account_state(account_id)
        state.realized_pnl_today = Decimal("0.0")
        state.lockout_until = None
        state.lockout_reason = None
        current_time = self.clock.now() if self.clock else datetime.utcnow()
        state.last_daily_reset = current_time

    # State persistence methods

    async def initialize(self):
        """Initialize state manager and load persisted state."""
        if self._initialized:
            return

        if self.persistence:
            # Load all accounts from persistence
            await self._load_all_accounts()

        self._initialized = True

    async def _load_all_accounts(self):
        """Load all account states from persistence."""
        # For SQLite, we need to query all distinct account IDs
        # Then load each account's state and positions

        # Query all unique account IDs from positions and account_state tables
        account_ids_from_positions = await self._get_account_ids_from_positions()
        account_ids_from_state = await self._get_account_ids_from_account_state()

        # Combine and deduplicate
        all_account_ids = set(account_ids_from_positions + account_ids_from_state)

        # Load each account
        for account_id in all_account_ids:
            await self._load_account(account_id)

    async def _get_account_ids_from_positions(self) -> List[str]:
        """Get all account IDs from positions table."""
        if not self.persistence or not self.persistence._conn:
            return []

        import asyncio
        query = "SELECT DISTINCT account_id FROM positions WHERE is_open = 1"
        cursor = await asyncio.get_event_loop().run_in_executor(
            None, self.persistence._conn.execute, query
        )
        rows = cursor.fetchall()
        return [row[0] for row in rows]

    async def _get_account_ids_from_account_state(self) -> List[str]:
        """Get all account IDs from account_state table."""
        if not self.persistence or not self.persistence._conn:
            return []

        import asyncio
        query = "SELECT account_id FROM account_state"
        cursor = await asyncio.get_event_loop().run_in_executor(
            None, self.persistence._conn.execute, query
        )
        rows = cursor.fetchall()
        return [row[0] for row in rows]

    async def _load_account(self, account_id: str):
        """Load a single account's state and positions."""
        # Load account state
        account_data = await self.persistence.load_account_state(account_id)

        if account_data:
            # Create account state
            state = AccountState(
                account_id=account_id,
                realized_pnl_today=account_data['daily_pnl_realized'],
                lockout_until=datetime.fromisoformat(account_data['lockout_until']) if account_data['lockout_until'] else None,
                lockout_reason=account_data['lockout_reason']
            )
            self.accounts[account_id] = state
        else:
            # Create fresh account state
            state = self.get_account_state(account_id)

        # Load open positions
        positions = await self.persistence.load_open_positions(account_id)

        for pos_data in positions:
            position = Position(
                position_id=pos_data['position_id'],
                account_id=pos_data['account_id'],
                symbol=pos_data['symbol'],
                side=pos_data['side'],
                quantity=pos_data['quantity'],
                entry_price=pos_data['entry_price'],
                current_price=pos_data['current_price'],
                unrealized_pnl=pos_data['unrealized_pnl'],
                opened_at=pos_data['opened_at'],
                stop_loss_attached=pos_data['stop_loss_attached'],
                stop_loss_grace_expires=datetime.fromisoformat(pos_data['stop_loss_grace_expires']) if pos_data['stop_loss_grace_expires'] else None,
                pending_close=pos_data['pending_close']
            )
            state.open_positions.append(position)

    async def shutdown(self):
        """Shutdown state manager and persist state."""
        if self.persistence:
            await self.persist_state()

    async def persist_state(self):
        """Persist current state to storage."""
        if not self.persistence:
            return

        for account_id, state in self.accounts.items():
            # Save account state
            await self.persistence.save_account_state(account_id, {
                'daily_pnl_realized': float(state.realized_pnl_today),
                'lockout_until': state.lockout_until.isoformat() if state.lockout_until else None,
                'lockout_reason': state.lockout_reason,
                'metadata': {}
            })

            # Mark closed positions in database
            for closed_position_id in state._closed_position_ids:
                current_time = self.clock.now() if self.clock else datetime.now(timezone.utc)
                await self.persistence.save_position({
                    'position_id': str(closed_position_id),
                    'account_id': account_id,
                    'symbol': '',
                    'side': '',
                    'quantity': 0,
                    'entry_price': 0.0,
                    'closed_at': current_time.isoformat(),
                    'is_open': False,
                    'opened_at': current_time
                })
            # Clear closed position IDs after persisting
            state._closed_position_ids.clear()

            # Save all open positions
            for position in state.open_positions:
                await self.persistence.save_position({
                    'position_id': position.position_id,
                    'account_id': position.account_id,
                    'symbol': position.symbol,
                    'side': position.side,
                    'quantity': position.quantity,
                    'entry_price': position.entry_price,
                    'current_price': position.current_price,
                    'unrealized_pnl': position.unrealized_pnl,
                    'opened_at': position.opened_at,
                    'is_open': True,
                    'stop_loss_attached': position.stop_loss_attached,
                    'stop_loss_grace_expires': position.stop_loss_grace_expires.isoformat() if position.stop_loss_grace_expires else None,
                    'pending_close': position.pending_close
                })

    async def open_position(
        self,
        account_id: str,
        symbol: str,
        side: str,
        quantity: int,
        entry_price: float,
        position_id: Union[str, UUID]
    ):
        """
        Open a new position.

        Args:
            account_id: Account ID
            symbol: Symbol (e.g., "MNQ", "ES")
            side: "long" or "short"
            quantity: Number of contracts
            entry_price: Entry price
            position_id: Position identifier (string or UUID)
        """
        current_time = self.clock.now() if self.clock else datetime.now(timezone.utc)

        position = Position(
            position_id=position_id,
            account_id=account_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=Decimal(str(entry_price)),
            current_price=Decimal(str(entry_price)),
            unrealized_pnl=Decimal("0.0"),
            opened_at=current_time
        )

        self.add_position(account_id, position)

        # Note: Persistence happens only when persist_state() is explicitly called
        # This allows batching of multiple changes before persisting

    async def close_position(
        self,
        account_id: str,
        position_id: Union[str, UUID],
        realized_pnl: float,
        reason: str = None
    ):
        """
        Close a position.

        Args:
            account_id: Account ID
            position_id: Position ID (string or UUID)
            realized_pnl: Realized PnL from closing
            reason: Reason for closing
        """
        # Close in memory
        state = self.get_account_state(account_id)
        state.open_positions = [
            p for p in state.open_positions
            if p.position_id != position_id
        ]
        state.realized_pnl_today += Decimal(str(realized_pnl))

        # Track closed position ID for persistence
        state._closed_position_ids.append(position_id)

        # Note: Persistence happens only when persist_state() is explicitly called

    def get_all_account_ids(self) -> List[str]:
        """Get list of all account IDs."""
        return list(self.accounts.keys())

    async def set_lockout_async(
        self,
        account_id: str,
        lockout_until: datetime,
        reason: str
    ):
        """
        Set account lockout (async version).

        Args:
            account_id: Account ID
            lockout_until: Lockout expiry time
            reason: Reason for lockout
        """
        state = self.get_account_state(account_id)
        state.lockout_until = lockout_until
        state.lockout_reason = reason

        # Note: Persistence happens only when persist_state() is explicitly called
