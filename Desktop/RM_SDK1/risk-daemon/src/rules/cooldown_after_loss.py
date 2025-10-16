"""
CooldownAfterLoss Rule - Trading cooldown after loss threshold.

Enforces trading pause after significant losses to prevent emotional overtrading.
Blocks new fills during cooldown but allows position management.

Architecture reference: docs/architecture/02-risk-engine.md (Rule: CooldownAfterLoss)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Dict

from src.rules.base_rule import RiskRule
from src.state.models import RuleViolation, EnforcementAction


class CooldownAfterLossRule(RiskRule):
    """
    Enforces trading cooldown after loss threshold is reached.

    Configuration:
        loss_threshold: Loss amount that triggers cooldown (Decimal, e.g., 500.00)
        cooldown_seconds: Duration of cooldown in seconds (e.g., 300 = 5 minutes)
    """

    def __init__(self, loss_threshold: Decimal, cooldown_seconds: int, enabled: bool = True):
        super().__init__(enabled=enabled)
        self.loss_threshold = loss_threshold
        self.cooldown_seconds = cooldown_seconds
        self.name = "CooldownAfterLoss"

        # Track cooldown state per account
        # {account_id: cooldown_start_time}
        self._cooldown_start: Dict[str, datetime] = {}

    def track_disconnection(self, account_id: str, disconnect_time: datetime) -> None:
        """
        Track when cooldown started.

        Args:
            account_id: Account identifier
            disconnect_time: When cooldown began
        """
        self._cooldown_start[account_id] = disconnect_time

    def get_disconnection_duration(self, account_id: str, current_time: datetime) -> Optional[timedelta]:
        """
        Get how long account has been in cooldown.

        Args:
            account_id: Account identifier
            current_time: Current timestamp

        Returns:
            Duration of cooldown or None if not in cooldown
        """
        if account_id not in self._cooldown_start:
            return None
        return current_time - self._cooldown_start[account_id]

    def clear_disconnection(self, account_id: str) -> None:
        """
        Clear cooldown state for account.

        Args:
            account_id: Account identifier
        """
        if account_id in self._cooldown_start:
            del self._cooldown_start[account_id]

    def _is_in_cooldown(self, account_id: str, current_time: datetime, account_state) -> bool:
        """
        Check if account is currently in cooldown.

        Args:
            account_id: Account identifier
            current_time: Current timestamp
            account_state: Account state with cooldown info

        Returns:
            True if in active cooldown
        """
        # Check if state manager has cooldown active
        if hasattr(account_state, 'cooldown_until'):
            if account_state.cooldown_until:
                # Handle timezone-aware comparison
                cooldown_until = account_state.cooldown_until
                if current_time.tzinfo is None and cooldown_until.tzinfo is not None:
                    current_time = current_time.replace(tzinfo=timezone.utc)
                elif current_time.tzinfo is not None and cooldown_until.tzinfo is None:
                    cooldown_until = cooldown_until.replace(tzinfo=timezone.utc)

                if current_time < cooldown_until:
                    return True

        return False

    def evaluate(self, event_data: dict, account_state) -> Optional[RuleViolation]:
        """
        Check if:
        1. Loss threshold reached → Start cooldown
        2. Already in cooldown → Block new fills

        Args:
            event_data: Fill event data
            account_state: Current account state

        Returns:
            RuleViolation if cooldown should start or fill should be blocked
        """
        if not self.enabled:
            return None

        account_id = account_state.account_id
        # Use clock from account_state if available, otherwise use real time
        if hasattr(account_state, 'clock'):
            current_time = account_state.clock.now()
        else:
            current_time = datetime.now(timezone.utc)

        # Check if already in cooldown
        if self._is_in_cooldown(account_id, current_time, account_state):
            return RuleViolation(
                rule_name=self.name,
                severity="medium",
                reason=f"Cooldown active: Cannot open new positions until cooldown expires",
                account_id=account_id,
                timestamp=current_time,
                data={
                    "cooldown_remaining": self.cooldown_seconds,
                    "cooldown_type": "active"
                }
            )

        # Check if loss threshold reached
        realized_loss = abs(account_state.realized_pnl_today)
        if realized_loss >= self.loss_threshold:
            return RuleViolation(
                rule_name=self.name,
                severity="medium",
                reason=f"Loss threshold reached: ${realized_loss:.2f} >= ${self.loss_threshold:.2f}. Starting {self.cooldown_seconds}s cooldown.",
                account_id=account_id,
                timestamp=current_time,
                data={
                    "realized_loss": float(realized_loss),
                    "threshold": float(self.loss_threshold),
                    "cooldown_seconds": self.cooldown_seconds,
                    "cooldown_type": "start"
                }
            )

        return None

    def get_enforcement_action(self, violation: RuleViolation, account_state=None) -> EnforcementAction:
        """
        Generate enforcement action:
        - Start cooldown if threshold breached
        - Reject fill if cooldown active

        Args:
            violation: The CooldownAfterLoss violation
            account_state: Optional account state

        Returns:
            EnforcementAction
        """
        cooldown_type = violation.data.get("cooldown_type", "active")

        if cooldown_type == "start":
            # Start cooldown
            return EnforcementAction(
                action_type="start_cooldown",
                account_id=violation.account_id,
                reason=f"Starting {self.cooldown_seconds}s cooldown due to loss threshold breach",
                timestamp=violation.timestamp,
                duration_seconds=self.cooldown_seconds,
                notification_severity="warning",
                notification_action="start_cooldown"
            )
        else:
            # Reject fill during cooldown
            return EnforcementAction(
                action_type="reject_fill",
                account_id=violation.account_id,
                reason="Rejecting fill: Cooldown active",
                timestamp=violation.timestamp,
                notification_severity="warning",
                notification_action="reject_fill"
            )

    def applies_to_event(self, event_type: str) -> bool:
        """Only evaluate on FILL events."""
        return event_type == "FILL"

    @property
    def notification_severity(self) -> str:
        return "warning"

    def format_notification_reason(self, violation: RuleViolation) -> str:
        """Format clear notification message."""
        cooldown_type = violation.data.get("cooldown_type", "active")

        if cooldown_type == "start":
            realized_loss = violation.data.get("realized_loss", 0)
            threshold = violation.data.get("threshold", 0)
            return (
                f"Cooldown started:\n"
                f"  Loss: ${realized_loss:.2f}\n"
                f"  Threshold: ${threshold:.2f}\n"
                f"  Duration: {self.cooldown_seconds}s ({self.cooldown_seconds // 60} minutes)\n"
                f"New fills blocked until cooldown expires."
            )
        else:
            return f"Fill rejected: Cooldown active for {self.cooldown_seconds // 60} minutes"
