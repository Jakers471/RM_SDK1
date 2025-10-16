"""
NoStopLossGrace Rule - Enforce stop loss attachment within grace period.

MANDATORY CRITICAL RULE (per Product Owner).

After a FILL event, trader has a grace period (default 120 seconds) to attach
a stop loss order. If grace expires without stop loss, position is closed immediately.

Architecture reference: docs/architecture/02-risk-engine.md (Rule 6)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from src.rules.base_rule import RiskRule
from src.state.models import RuleViolation, EnforcementAction


class NoStopLossGraceRule(RiskRule):
    """
    Enforces stop loss attachment within grace period after position opened.

    Configuration:
        grace_period_seconds: Seconds allowed to attach stop loss (default: 120)

    Behavior:
    - On FILL: Initialize grace period tracking
    - On TIME_TICK: Check if grace expired without stop loss
    - Violation: Close position immediately (no lockout)
    """

    def __init__(self, grace_period_seconds: int = 120, enabled: bool = True):
        super().__init__(enabled=enabled)
        self.grace_period_seconds = grace_period_seconds
        self.name = "NoStopLossGrace"

    def evaluate(self, event_data: dict, account_state) -> Optional[RuleViolation]:
        """
        Check for positions with expired grace period and no stop loss.

        Args:
            event_data: Event data (TIME_TICK or FILL)
            account_state: Current account state

        Returns:
            RuleViolation if position has expired grace without stop loss
        """
        if not self.enabled:
            return None

        # Get current time from event or use now
        current_time = event_data.get("current_time", datetime.now(timezone.utc))

        # Check all open positions
        for position in account_state.open_positions:
            # Skip positions that already have stop loss
            if position.stop_loss_attached:
                continue

            # Check if grace period has expired
            if position.stop_loss_grace_expires and current_time >= position.stop_loss_grace_expires:
                # Grace expired without stop loss - VIOLATION
                return RuleViolation(
                    rule_name=self.name,
                    severity="high",
                    reason=f"NoStopLossGrace: Grace period expired for {position.symbol} position without stop loss. Grace expired at {position.stop_loss_grace_expires.isoformat()}.",
                    account_id=account_state.account_id,
                    timestamp=current_time,
                    data={
                        "position_id": position.position_id,
                        "symbol": position.symbol,
                        "quantity": position.quantity,
                        "opened_at": position.opened_at.isoformat(),
                        "grace_expires": position.stop_loss_grace_expires.isoformat(),
                        "grace_period_seconds": self.grace_period_seconds
                    }
                )

        return None

    def get_enforcement_action(self, violation: RuleViolation, account_state=None) -> EnforcementAction:
        """
        Generate action to close position without stop loss.

        Args:
            violation: The NoStopLossGrace violation
            account_state: Account state (unused for this rule)

        Returns:
            EnforcementAction to close position
        """
        position_id = violation.data["position_id"]
        quantity = violation.data["quantity"]
        symbol = violation.data["symbol"]

        return EnforcementAction(
            action_type="close_position",
            account_id=violation.account_id,
            reason=f"NoStopLossGrace: Closing {symbol} position - grace period expired without stop loss",
            timestamp=violation.timestamp,
            position_id=position_id,
            quantity=quantity,
            notification_severity="critical",
            notification_action="close_position"
        )

    def applies_to_event(self, event_type: str) -> bool:
        """Evaluate on TIME_TICK and FILL events."""
        return event_type in ["TIME_TICK", "FILL"]

    @property
    def notification_severity(self) -> str:
        return "critical"

    def format_notification_reason(self, violation: RuleViolation) -> str:
        """Format clear notification message."""
        symbol = violation.data["symbol"]
        grace_seconds = violation.data["grace_period_seconds"]

        return (
            f"NoStopLossGrace violation:\n"
            f"  Symbol: {symbol}\n"
            f"  Quantity: {violation.data['quantity']}\n"
            f"  Grace period: {grace_seconds}s\n"
            f"  Position closed due to missing stop loss."
        )

    def create_violation(
        self,
        position_id,
        symbol: str,
        quantity: int,
        opened_at: datetime,
        grace_expires: datetime,
        grace_period_seconds: int
    ) -> RuleViolation:
        """Helper to create NoStopLossGrace violation."""
        return RuleViolation(
            rule_name=self.name,
            severity="high",
            reason=f"Grace period expired for {symbol} position without stop loss",
            account_id="",  # Will be set by caller
            timestamp=datetime.now(timezone.utc),
            data={
                "position_id": position_id,
                "symbol": symbol,
                "quantity": quantity,
                "opened_at": opened_at.isoformat(),
                "grace_expires": grace_expires.isoformat(),
                "grace_period_seconds": grace_period_seconds
            }
        )
