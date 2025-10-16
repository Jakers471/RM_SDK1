"""
UnrealizedLoss Rule - Per-trade unrealized loss limit.

Closes individual positions when unrealized loss exceeds limit.
Does NOT cause lockout (only daily limit causes lockout).

Architecture reference: docs/architecture/02-risk-engine.md (Rule 2)
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.rules.base_rule import RiskRule
from src.state.models import RuleViolation, EnforcementAction


class UnrealizedLossRule(RiskRule):
    """
    Enforces per-position unrealized loss limit.

    Configuration:
        limit: Maximum unrealized loss per position (negative Decimal, e.g., -200.00)
    """

    def __init__(self, limit: Decimal, enabled: bool = True):
        super().__init__(enabled=enabled)
        self.limit = limit  # e.g., Decimal("-200.00")
        self.name = "UnrealizedLoss"

    def evaluate(self, event_data: dict, account_state) -> Optional[RuleViolation]:
        """
        Check if any position has unrealized loss exceeding limit.

        Args:
            event_data: Event data (may include position_id for POSITION_UPDATE)
            account_state: Current account state

        Returns:
            RuleViolation if any position exceeds unrealized loss limit
        """
        if not self.enabled:
            return None

        # Check all open positions
        for position in account_state.open_positions:
            # Skip positions already pending close
            if position.pending_close:
                continue

            # Check if unrealized loss exceeds limit
            if position.unrealized_pnl <= self.limit:
                return RuleViolation(
                    rule_name=self.name,
                    severity="warning",
                    reason=f"Position unrealized loss ${position.unrealized_pnl:.2f} exceeds limit ${self.limit:.2f}",
                    account_id=account_state.account_id,
                    timestamp=datetime.utcnow(),
                    data={
                        "position_id": position.position_id,
                        "symbol": position.symbol,
                        "unrealized_pnl": float(position.unrealized_pnl),
                        "limit": float(self.limit),
                        "quantity": position.quantity
                    }
                )

        return None

    def get_enforcement_action(self, violation: RuleViolation) -> EnforcementAction:
        """
        Generate action to close position with excessive loss.

        Args:
            violation: The UnrealizedLoss violation

        Returns:
            EnforcementAction to close the position
        """
        return EnforcementAction(
            action_type="close_position",
            account_id=violation.account_id,
            reason=f"Closing position due to unrealized loss limit (${self.limit:.2f})",
            timestamp=violation.timestamp,
            position_id=violation.data["position_id"],
            quantity=None,  # Close entire position
            notification_severity="warning",
            notification_action="close_position"
        )

    def applies_to_event(self, event_type: str) -> bool:
        """Evaluate on position updates (price changes)."""
        return event_type in ["POSITION_UPDATE", "FILL"]

    @property
    def notification_severity(self) -> str:
        return "warning"

    def format_notification_reason(self, violation: RuleViolation) -> str:
        """Format clear notification message."""
        symbol = violation.data["symbol"]
        unrealized = violation.data["unrealized_pnl"]
        limit = violation.data["limit"]
        return f"UnrealizedLoss limit hit for {symbol}: ${unrealized:.2f} loss > ${limit:.2f} limit. Position closed."
