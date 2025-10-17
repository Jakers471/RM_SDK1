"""
AuthLossGuard Rule - Connection loss monitoring and alerting.

Monitors CONNECTION_CHANGE events and alerts on disconnection.
NO auto-flatten - alert only for manual intervention.

Architecture reference: docs/architecture/02-risk-engine.md (Rule: AuthLossGuard)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Dict

from src.rules.base_rule import RiskRule
from src.state.models import RuleViolation, EnforcementAction


class AuthLossGuardRule(RiskRule):
    """
    Monitors connection status and alerts on disconnection.

    Configuration:
        auto_flatten: Whether to auto-flatten on disconnect (default: False)
    """

    def __init__(self, auto_flatten: bool = False, enabled: bool = True):
        super().__init__(enabled=enabled)
        self.auto_flatten = auto_flatten
        self.name = "AuthLossGuard"

        # Track disconnection times per account
        # {account_id: disconnect_time}
        self._disconnection_times: Dict[str, datetime] = {}

    def track_disconnection(self, account_id: str, disconnect_time: datetime) -> None:
        """
        Track when disconnection occurred.

        Args:
            account_id: Account identifier
            disconnect_time: When disconnect happened
        """
        self._disconnection_times[account_id] = disconnect_time

    def clear_disconnection(self, account_id: str) -> None:
        """
        Clear disconnection state (on reconnect).

        Args:
            account_id: Account identifier
        """
        if account_id in self._disconnection_times:
            del self._disconnection_times[account_id]

    def get_disconnection_duration(self, account_id: str, current_time: datetime) -> Optional[timedelta]:
        """
        Get how long account has been disconnected.

        Args:
            account_id: Account identifier
            current_time: Current timestamp

        Returns:
            Duration of disconnection or None if not disconnected
        """
        if account_id not in self._disconnection_times:
            return None
        return current_time - self._disconnection_times[account_id]

    def evaluate(self, event_data: dict, account_state) -> Optional[RuleViolation]:
        """
        Check if connection status changed to disconnected.

        Args:
            event_data: CONNECTION_CHANGE event data with 'status' key
            account_state: Current account state

        Returns:
            RuleViolation if disconnected
        """
        if not self.enabled:
            return None

        status = event_data.get("status", "")
        account_id = account_state.account_id

        # Only care about disconnection events
        if status.lower() == "disconnected":
            # Track disconnection
            # Use clock from account_state if available
            if hasattr(account_state, 'clock') and 'timestamp' not in event_data:
                disconnect_time = account_state.clock.now()
            else:
                disconnect_time = event_data.get("timestamp", datetime.now(timezone.utc))
            self.track_disconnection(account_id, disconnect_time)

            # Get info about open positions
            open_positions = account_state.open_positions
            positions_count = len(open_positions)
            symbols = [p.symbol for p in open_positions]

            # Determine severity based on whether there are open positions
            # If no positions, lower severity (info); if positions exist, critical
            severity = "critical" if positions_count > 0 else "info"

            return RuleViolation(
                rule_name=self.name,
                severity=severity,
                reason=f"Connection lost: Authentication or network failure detected. Manual intervention required.",
                account_id=account_id,
                timestamp=disconnect_time,
                data={
                    "status": status,
                    "reason": event_data.get("reason", "Unknown"),
                    "open_positions_count": positions_count,
                    "symbols": symbols,
                    "disconnect_time": disconnect_time
                }
            )
        elif status.lower() == "connected":
            # Clear disconnection on reconnect
            self.clear_disconnection(account_id)
            return None

        return None

    def get_enforcement_action(self, violation: RuleViolation, account_state=None) -> EnforcementAction:
        """
        Generate alert notification (no auto-flatten unless configured).

        Args:
            violation: The AuthLossGuard violation
            account_state: Optional account state

        Returns:
            EnforcementAction to notify (alert only)
        """
        positions_count = violation.data.get("open_positions_count", 0)
        symbols = violation.data.get("symbols", [])
        reason = violation.data.get("reason", "Unknown")

        # Build detailed alert message
        message = (
            f"CRITICAL: Connection lost - {reason}\n"
            f"Open positions: {positions_count}\n"
        )
        if symbols:
            message += f"Symbols: {', '.join(symbols[:5])}"  # Show first 5
            if len(symbols) > 5:
                message += f" (+{len(symbols) - 5} more)"
            message += "\n"

        message += (
            f"ACTION REQUIRED: Manual intervention needed.\n"
            f"Check connection and review open positions."
        )

        # Use "notify" action type for alert-only
        # Use severity from violation (critical if positions, info if no positions)
        return EnforcementAction(
            action_type="notify",
            account_id=violation.account_id,
            reason=violation.reason,
            timestamp=violation.timestamp,
            severity=violation.severity,
            message=message,
            notification_severity=violation.severity,
            notification_action="notify"
        )

    def applies_to_event(self, event_type: str) -> bool:
        """Only evaluate on CONNECTION_CHANGE events."""
        return event_type == "CONNECTION_CHANGE"

    @property
    def notification_severity(self) -> str:
        return "critical"

    def format_notification_reason(self, violation: RuleViolation) -> str:
        """Format clear notification message."""
        positions_count = violation.data.get("open_positions_count", 0)
        symbols = violation.data.get("symbols", [])
        reason = violation.data.get("reason", "Unknown")

        notification = (
            f"AuthLossGuard ALERT:\n"
            f"  Status: CONNECTION LOST\n"
            f"  Reason: {reason}\n"
            f"  Open positions: {positions_count}\n"
        )

        if symbols:
            symbols_str = ", ".join(symbols[:5])
            if len(symbols) > 5:
                symbols_str += f" (+{len(symbols) - 5} more)"
            notification += f"  Symbols: {symbols_str}\n"

        notification += (
            f"\n"
            f"MANUAL INTERVENTION REQUIRED\n"
            f"Please check connection and review positions."
        )

        return notification
