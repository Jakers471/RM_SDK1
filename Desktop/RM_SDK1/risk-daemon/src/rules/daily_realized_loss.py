"""
DailyRealizedLoss Rule - Daily loss limit with COMBINED PnL monitoring.

CRITICAL RULE: Monitors combined realized + unrealized PnL to prevent account blow-ups.
Triggers flatten + lockout until 5pm CT when limit exceeded.

Architecture reference: docs/architecture/02-risk-engine.md (Rule 3)
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
import pytz

from src.rules.base_rule import RiskRule
from src.state.models import RuleViolation, EnforcementAction


class DailyRealizedLossRule(RiskRule):
    """
    Enforces daily loss limit using COMBINED exposure calculation.

    Combined Exposure = Realized PnL + Total Unrealized PnL

    Configuration:
        limit: Maximum daily loss (negative Decimal, e.g., -1000.00)
    """

    def __init__(self, limit: Decimal, enabled: bool = True):
        super().__init__(enabled=enabled)
        self.limit = limit  # e.g., Decimal("-1000.00")
        self.name = "DailyRealizedLoss"

    def evaluate(self, event_data: dict, account_state) -> Optional[RuleViolation]:
        """
        Check if combined PnL exceeds daily limit.

        Args:
            event_data: Event data
            account_state: Current account state

        Returns:
            RuleViolation if combined PnL exceeds limit
        """
        if not self.enabled:
            return None

        # Calculate combined exposure
        realized = account_state.realized_pnl_today
        unrealized = sum(p.unrealized_pnl for p in account_state.open_positions)
        combined = realized + unrealized

        # Check violation (limit is negative, so combined < limit means EXCEEDING threshold)
        if combined < self.limit:
            return RuleViolation(
                rule_name=self.name,
                severity="critical",
                reason=f"Daily loss limit exceeded: Combined PnL ${combined:.2f} exceeds ${self.limit:.2f} limit (Realized: ${realized:.2f}, Unrealized: ${unrealized:.2f})",
                account_id=account_state.account_id,
                timestamp=datetime.utcnow(),
                data={
                    "realized": float(realized),
                    "unrealized": float(unrealized),
                    "combined": float(combined),
                    "limit": float(self.limit),
                    "breach_amount": float(combined - self.limit)
                }
            )

        return None

    def get_enforcement_action(self, violation: RuleViolation) -> EnforcementAction:
        """
        Generate action to flatten account and set lockout until 5pm CT.

        Args:
            violation: The DailyRealizedLoss violation

        Returns:
            EnforcementAction to flatten + lockout
        """
        # Calculate lockout time (5pm CT today, or next day if already past 5pm)
        chicago_tz = pytz.timezone("America/Chicago")
        current_ct = datetime.now(chicago_tz)
        lockout_time = current_ct.replace(hour=17, minute=0, second=0, microsecond=0)

        # If already past 5pm, lock until tomorrow 5pm
        if current_ct.hour >= 17:
            lockout_time += timedelta(days=1)

        # Build detailed reason with PnL breakdown
        realized = violation.data['realized']
        unrealized = violation.data['unrealized']
        combined = violation.data['combined']
        reason = (
            f"DailyRealizedLoss: Daily loss limit exceeded. "
            f"Realized: ${realized:.2f}, Unrealized: ${unrealized:.2f}, Combined: ${combined:.2f}. "
            f"Flattening account and locking until 5pm CT."
        )

        return EnforcementAction(
            action_type="flatten_account",
            account_id=violation.account_id,
            reason=reason,
            timestamp=violation.timestamp,
            lockout_until=lockout_time,
            notification_severity="critical",
            notification_action="flatten_account"
        )

    def applies_to_event(self, event_type: str) -> bool:
        """Evaluate on position updates and fills."""
        return event_type in ["POSITION_UPDATE", "FILL"]

    @property
    def notification_severity(self) -> str:
        return "critical"

    def format_notification_reason(self, violation: RuleViolation) -> str:
        """Format clear notification message with PnL breakdown."""
        realized = violation.data["realized"]
        unrealized = violation.data["unrealized"]
        combined = violation.data["combined"]
        limit = violation.data["limit"]

        return (
            f"DailyRealizedLoss limit exceeded:\n"
            f"  Realized: ${realized:.2f}\n"
            f"  Unrealized: ${unrealized:.2f}\n"
            f"  Combined: ${combined:.2f}\n"
            f"  Limit: ${limit:.2f}\n"
            f"Account flattened and locked until 5pm CT."
        )

    def create_violation(
        self,
        realized: Decimal,
        unrealized: Decimal,
        combined: Decimal,
        limit: Decimal
    ) -> RuleViolation:
        """Helper to create DailyRealizedLoss violation."""
        return RuleViolation(
            rule_name=self.name,
            severity="critical",
            reason=f"Combined PnL ${combined:.2f} exceeds limit ${limit:.2f}",
            account_id="",  # Will be set by caller
            timestamp=datetime.utcnow(),
            data={
                "realized": float(realized),
                "unrealized": float(unrealized),
                "combined": float(combined),
                "limit": float(limit),
                "breach_amount": float(combined - limit)
            }
        )
