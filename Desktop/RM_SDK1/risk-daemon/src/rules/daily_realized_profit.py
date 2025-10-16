"""
DailyRealizedProfit Rule - Daily profit target with COMBINED PnL monitoring.

When combined realized + unrealized PnL reaches profit target:
Flatten all positions + lockout until 5pm CT.

This is the inverse of DailyRealizedLoss - for taking profits.

Architecture reference: docs/architecture/02-risk-engine.md (Rule 8)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
import pytz

from src.rules.base_rule import RiskRule
from src.state.models import RuleViolation, EnforcementAction


class DailyRealizedProfitRule(RiskRule):
    """
    Enforces daily profit target using COMBINED exposure calculation.

    Combined Exposure = Realized PnL + Total Unrealized PnL

    Configuration:
        profit_target: Target profit (positive Decimal, e.g., 500.00)
    """

    def __init__(self, profit_target: Decimal, enabled: bool = True):
        super().__init__(enabled=enabled)
        self.profit_target = profit_target  # e.g., Decimal("500.00")
        self.name = "DailyRealizedProfit"

    def evaluate(self, event_data: dict, account_state) -> Optional[RuleViolation]:
        """
        Check if combined PnL has reached profit target.

        Args:
            event_data: Event data
            account_state: Current account state

        Returns:
            RuleViolation if combined PnL >= profit_target
        """
        if not self.enabled:
            return None

        # Calculate combined exposure
        realized = account_state.realized_pnl_today
        unrealized = sum(p.unrealized_pnl for p in account_state.open_positions)
        combined = realized + unrealized

        # Check if profit target reached (combined >= target)
        if combined >= self.profit_target:
            return RuleViolation(
                rule_name=self.name,
                severity="critical",
                reason=f"Daily profit target reached: Combined PnL ${combined:.2f} >= ${self.profit_target:.2f} target (Realized: ${realized:.2f}, Unrealized: ${unrealized:.2f})",
                account_id=account_state.account_id,
                timestamp=datetime.now(timezone.utc),
                data={
                    "realized": float(realized),
                    "unrealized": float(unrealized),
                    "combined": float(combined),
                    "profit_target": float(self.profit_target),
                    "excess": float(combined - self.profit_target)
                }
            )

        return None

    def get_enforcement_action(self, violation: RuleViolation, account_state=None) -> EnforcementAction:
        """
        Generate action to flatten account and set lockout until 5pm CT.

        Args:
            violation: The DailyRealizedProfit violation
            account_state: Optional account state

        Returns:
            EnforcementAction to flatten + lockout
        """
        # Calculate lockout time (5pm CT today, or next day if already past 5pm)
        chicago_tz = pytz.timezone("America/Chicago")
        # Convert violation timestamp to CT
        current_ct = violation.timestamp.astimezone(chicago_tz)
        lockout_time = current_ct.replace(hour=17, minute=0, second=0, microsecond=0)

        # If already past 5pm, lock until tomorrow 5pm
        if current_ct.hour >= 17:
            lockout_time += timedelta(days=1)

        # Build detailed reason with PnL breakdown
        realized = violation.data['realized']
        unrealized = violation.data['unrealized']
        combined = violation.data['combined']
        reason = (
            f"DailyRealizedProfit: Daily profit target reached. "
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
        profit_target = violation.data["profit_target"]

        return (
            f"DailyRealizedProfit target reached:\n"
            f"  Realized: ${realized:.2f}\n"
            f"  Unrealized: ${unrealized:.2f}\n"
            f"  Combined: ${combined:.2f}\n"
            f"  Target: ${profit_target:.2f}\n"
            f"Account flattened and locked until 5pm CT."
        )

    def create_violation(
        self,
        realized: Decimal,
        unrealized: Decimal,
        combined: Decimal,
        profit_target: Decimal
    ) -> RuleViolation:
        """Helper to create DailyRealizedProfit violation."""
        return RuleViolation(
            rule_name=self.name,
            severity="critical",
            reason=f"Combined PnL ${combined:.2f} >= profit target ${profit_target:.2f}",
            account_id="",  # Will be set by caller
            timestamp=datetime.now(timezone.utc),
            data={
                "realized": float(realized),
                "unrealized": float(unrealized),
                "combined": float(combined),
                "profit_target": float(profit_target),
                "excess": float(combined - profit_target)
            }
        )
