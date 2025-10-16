"""
SymbolBlock Rule - Symbol blacklist enforcement.

Blocks trading on specific symbols and auto-closes any fills on blocked symbols.
Case-insensitive symbol matching with dynamic blacklist management.

Architecture reference: docs/architecture/02-risk-engine.md (Rule: SymbolBlock)
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from src.rules.base_rule import RiskRule
from src.state.models import RuleViolation, EnforcementAction


class SymbolBlockRule(RiskRule):
    """
    Enforces symbol blacklist with auto-close on violation.

    Configuration:
        blocked_symbols: List of blocked symbol strings (e.g., ["TSLA", "AAPL"])
    """

    def __init__(self, blocked_symbols: List[str], enabled: bool = True):
        super().__init__(enabled=enabled)
        # Store symbols in uppercase for case-insensitive matching
        self.blocked_symbols = [s.upper() for s in blocked_symbols]
        self.name = "SymbolBlock"

    def add_blocked_symbol(self, symbol: str) -> None:
        """
        Add symbol to blacklist dynamically.

        Args:
            symbol: Symbol to block
        """
        symbol_upper = symbol.upper()
        if symbol_upper not in self.blocked_symbols:
            self.blocked_symbols.append(symbol_upper)

    def remove_blocked_symbol(self, symbol: str) -> None:
        """
        Remove symbol from blacklist dynamically.

        Args:
            symbol: Symbol to unblock
        """
        symbol_upper = symbol.upper()
        if symbol_upper in self.blocked_symbols:
            self.blocked_symbols.remove(symbol_upper)

    def _is_blocked(self, symbol: str) -> bool:
        """
        Check if symbol is blocked (case-insensitive).

        Args:
            symbol: Symbol to check

        Returns:
            True if symbol is blocked
        """
        return symbol.upper() in self.blocked_symbols

    def evaluate(self, event_data: dict, account_state) -> Optional[RuleViolation]:
        """
        Check if fill is for a blocked symbol.

        Args:
            event_data: Fill event data with 'symbol' key
            account_state: Current account state

        Returns:
            RuleViolation if symbol is blocked
        """
        if not self.enabled:
            return None

        # Empty blacklist allows all symbols
        if not self.blocked_symbols:
            return None

        symbol = event_data.get("symbol", "")
        if not symbol:
            return None

        # Check if symbol is blocked
        if self._is_blocked(symbol):
            # Count positions on this symbol
            positions_on_symbol = [
                p for p in account_state.open_positions
                if p.symbol.upper() == symbol.upper()
            ]
            positions_count = len(positions_on_symbol)

            # Use clock from account_state if available
            if hasattr(account_state, 'clock'):
                timestamp = account_state.clock.now()
            else:
                timestamp = datetime.now(timezone.utc)

            return RuleViolation(
                rule_name=self.name,
                severity="high",
                reason=f"Blocked symbol: {symbol} is on blacklist. Position must be closed immediately.",
                account_id=account_state.account_id,
                timestamp=timestamp,
                data={
                    "symbol": symbol,
                    "quantity": event_data.get("quantity", 0),
                    "positions_count": positions_count,
                    "positions": positions_on_symbol
                }
            )

        return None

    def get_enforcement_action(self, violation: RuleViolation, account_state=None) -> EnforcementAction:
        """
        Generate action to close position on blocked symbol.

        Args:
            violation: The SymbolBlock violation
            account_state: Optional account state

        Returns:
            EnforcementAction to close position
        """
        symbol = violation.data["symbol"]
        positions = violation.data.get("positions", [])

        # Find position to close
        position_id = None
        quantity = violation.data.get("quantity", 0)

        if positions:
            # Close the first/most recent position on this symbol
            target_position = positions[0]
            position_id = target_position.position_id
            quantity = target_position.quantity

        return EnforcementAction(
            action_type="close_position",
            account_id=violation.account_id,
            reason=f"SymbolBlock: Closing {quantity} {symbol} - symbol is blacklisted",
            timestamp=violation.timestamp,
            position_id=position_id,
            quantity=quantity,
            notification_severity="critical",
            notification_action="close_position"
        )

    def applies_to_event(self, event_type: str) -> bool:
        """Only evaluate on FILL events."""
        return event_type == "FILL"

    @property
    def notification_severity(self) -> str:
        return "critical"

    def format_notification_reason(self, violation: RuleViolation) -> str:
        """Format clear notification message."""
        symbol = violation.data["symbol"]
        quantity = violation.data.get("quantity", 0)
        positions_count = violation.data.get("positions_count", 0)

        return (
            f"SymbolBlock violation:\n"
            f"  Symbol: {symbol}\n"
            f"  Status: BLACKLISTED\n"
            f"  Open positions: {positions_count}\n"
            f"  Action: Auto-closing {quantity} contracts\n"
            f"This symbol is prohibited from trading."
        )
