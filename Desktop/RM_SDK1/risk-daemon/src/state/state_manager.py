"""
StateManager - Central state management for Risk Manager.

Tracks positions, PnL, lockouts, and account state.
Provides combined PnL calculations and state queries.

Architecture reference: docs/architecture/04-state-management.md
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID


@dataclass
class Position:
    """Position model."""
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


class StateManager:
    """
    Central state manager for all accounts.

    Provides:
    - Position tracking
    - Combined PnL calculation
    - Lockout management
    - Daily reset logic
    """

    def __init__(self, clock=None):
        """
        Initialize state manager.

        Args:
            clock: Clock instance for time queries (optional, uses datetime.utcnow if None)
        """
        self.clock = clock
        self.accounts: Dict[str, AccountState] = {}

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
