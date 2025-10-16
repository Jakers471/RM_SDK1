"""
UnrealizedProfit Rule - Auto take-profit per position.

Monitors unrealized PnL for each position. When a position's unrealized profit
reaches the target, automatically close that position to lock in gains.

Per-position enforcement (not account-wide).

Architecture reference: docs/architecture/02-risk-engine.md (Rule 9)
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from src.rules.base_rule import RiskRule
from src.state.models import RuleViolation, EnforcementAction


class UnrealizedProfitRule(RiskRule):
    """
    Enforces per-position unrealized profit targets.

    When a position's unrealized PnL >= profit_target, close that position.

    Configuration:
        profit_target: Target profit per position (positive Decimal, e.g., 100.00)
    """

    def __init__(self, profit_target: Decimal, enabled: bool = True):
        super().__init__(enabled=enabled)
        self.profit_target = profit_target  # e.g., Decimal("100.00")
        self.name = "UnrealizedProfit"

    def evaluate(self, event_data: dict, account_state) -> Optional[RuleViolation]:
        """
        Check if any position has reached profit target.

        Args:
            event_data: Event data
            account_state: Current account state

        Returns:
            RuleViolation if position unrealized >= profit_target
        """
        if not self.enabled:
            return None

        # Check each position
        for position in account_state.open_positions:
            # Only check positions with positive unrealized PnL
            if position.unrealized_pnl >= self.profit_target:
                return RuleViolation(
                    rule_name=self.name,
                    severity="info",  # Positive event - taking profits
                    reason=f"UnrealizedProfit: Position {position.symbol} has reached profit target ${position.unrealized_pnl:.2f} >= ${self.profit_target:.2f}",
                    account_id=account_state.account_id,
                    timestamp=datetime.now(timezone.utc),
                    data={
                        "position_id": position.position_id,
                        "symbol": position.symbol,
                        "quantity": position.quantity,
                        "unrealized_pnl": float(position.unrealized_pnl),
                        "profit_target": float(self.profit_target),
                        "entry_price": float(position.entry_price),
                        "current_price": float(position.current_price)
                    }
                )

        return None

    def get_enforcement_action(self, violation: RuleViolation, account_state=None) -> EnforcementAction:
        """
        Generate action to close profitable position.

        Args:
            violation: The UnrealizedProfit violation
            account_state: Optional account state

        Returns:
            EnforcementAction to close position
        """
        position_id = violation.data["position_id"]
        quantity = violation.data["quantity"]
        symbol = violation.data["symbol"]
        unrealized = violation.data["unrealized_pnl"]

        return EnforcementAction(
            action_type="close_position",
            account_id=violation.account_id,
            reason=f"Taking profit on {symbol} position: ${unrealized:.2f} profit reached",
            timestamp=violation.timestamp,
            position_id=position_id,
            quantity=quantity,  # Close entire position
            notification_severity="info",
            notification_action="close_position"
        )

    def applies_to_event(self, event_type: str) -> bool:
        """Only evaluate on POSITION_UPDATE events."""
        return event_type == "POSITION_UPDATE"

    @property
    def notification_severity(self) -> str:
        return "info"  # Positive event - taking profits

    def format_notification_reason(self, violation: RuleViolation) -> str:
        """Format clear notification message."""
        symbol = violation.data["symbol"]
        unrealized = violation.data["unrealized_pnl"]
        profit_target = violation.data["profit_target"]

        return (
            f"UnrealizedProfit target reached:\n"
            f"  Symbol: {symbol}\n"
            f"  Unrealized PnL: ${unrealized:.2f}\n"
            f"  Target: ${profit_target:.2f}\n"
            f"Position closed to lock in gains."
        )

    def create_violation(
        self,
        position_id,
        symbol: str,
        quantity: int,
        unrealized_pnl: Decimal,
        profit_target: Decimal
    ) -> RuleViolation:
        """Helper to create UnrealizedProfit violation."""
        return RuleViolation(
            rule_name=self.name,
            severity="info",
            reason=f"{symbol} position reached profit target ${unrealized_pnl:.2f}",
            account_id="",  # Will be set by caller
            timestamp=datetime.now(timezone.utc),
            data={
                "position_id": position_id,
                "symbol": symbol,
                "quantity": quantity,
                "unrealized_pnl": float(unrealized_pnl),
                "profit_target": float(profit_target)
            }
        )
