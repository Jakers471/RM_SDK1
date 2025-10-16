"""
TradeFrequencyLimit Rule - Maximum trades per time window enforcement.

Prevents overtrading by limiting number of fills in a sliding time window.
Rejects fills exceeding frequency limit.

Architecture reference: docs/architecture/02-risk-engine.md (Rule 10)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Dict, List
from collections import defaultdict

from src.rules.base_rule import RiskRule
from src.state.models import RuleViolation, EnforcementAction


class TradeFrequencyLimitRule(RiskRule):
    """
    Enforces maximum trade frequency using sliding time window.

    Configuration:
        max_trades: Maximum number of trades allowed
        time_window_seconds: Time window in seconds (e.g., 60 for 1 minute)
    """

    def __init__(self, max_trades: int, time_window_seconds: int, enabled: bool = True):
        super().__init__(enabled=enabled)
        self.max_trades = max_trades
        self.time_window_seconds = time_window_seconds
        self.name = "TradeFrequencyLimit"

        # Track fills per account in sliding window
        # {account_id: [(fill_time, event_data), ...]}
        self._fill_history: Dict[str, List[tuple]] = defaultdict(list)

    def track_fill(self, account_id: str, fill_event: dict) -> None:
        """
        Track a fill event for frequency monitoring.

        Args:
            account_id: Account identifier
            fill_event: Fill event data with 'fill_time' key
        """
        fill_time = fill_event.get("fill_time", datetime.now(timezone.utc))
        self._fill_history[account_id].append((fill_time, fill_event))
        self._cleanup_old_fills(account_id, fill_time)

    def _cleanup_old_fills(self, account_id: str, current_time: datetime) -> None:
        """
        Remove fills outside the time window.

        Args:
            account_id: Account identifier
            current_time: Current timestamp
        """
        window_start = current_time - timedelta(seconds=self.time_window_seconds)
        self._fill_history[account_id] = [
            (fill_time, event)
            for fill_time, event in self._fill_history[account_id]
            if fill_time >= window_start
        ]

    def _get_fills_in_window(self, account_id: str, current_time: datetime) -> int:
        """
        Count fills within the time window.

        Args:
            account_id: Account identifier
            current_time: Current timestamp

        Returns:
            Number of fills in the window
        """
        self._cleanup_old_fills(account_id, current_time)
        return len(self._fill_history[account_id])

    def evaluate(self, event_data: dict, account_state) -> Optional[RuleViolation]:
        """
        Check if adding this fill would exceed frequency limit.

        Args:
            event_data: Fill event data (should include 'fill_time')
            account_state: Current account state

        Returns:
            RuleViolation if frequency limit would be exceeded
        """
        if not self.enabled:
            return None

        account_id = account_state.account_id
        # Use clock from account_state if available, otherwise use real time
        if hasattr(account_state, 'clock') and 'fill_time' not in event_data:
            fill_time = account_state.clock.now()
        else:
            fill_time = event_data.get("fill_time", datetime.now(timezone.utc))

        # Get current fill count in window
        current_count = self._get_fills_in_window(account_id, fill_time)

        # Check if adding this fill would exceed limit
        if current_count >= self.max_trades:
            return RuleViolation(
                rule_name=self.name,
                severity="high",
                reason=f"Trade frequency limit exceeded: {current_count + 1} trades would exceed {self.max_trades} trades per {self.time_window_seconds}s window",
                account_id=account_id,
                timestamp=fill_time,
                data={
                    "current_count": current_count,
                    "max_trades": self.max_trades,
                    "time_window_seconds": self.time_window_seconds,
                    "symbol": event_data.get("symbol", ""),
                    "quantity": event_data.get("quantity", 0)
                }
            )

        # If no violation, track this fill for future checks
        self.track_fill(account_id, event_data)
        return None

    def get_enforcement_action(self, violation: RuleViolation, account_state=None) -> EnforcementAction:
        """
        Generate action to reject fill.

        Args:
            violation: The TradeFrequencyLimit violation
            account_state: Optional account state

        Returns:
            EnforcementAction to reject fill
        """
        current_count = violation.data["current_count"]
        symbol = violation.data.get("symbol", "")
        quantity = violation.data.get("quantity", 0)

        reason = (
            f"TradeFrequencyLimit: Rejecting fill for {quantity} {symbol}. "
            f"Already executed {current_count} trades in last {self.time_window_seconds}s "
            f"(limit: {self.max_trades})"
        )

        return EnforcementAction(
            action_type="reject_fill",
            account_id=violation.account_id,
            reason=reason,
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
        current_count = violation.data["current_count"]
        return (
            f"Trade frequency limit exceeded:\n"
            f"  Current: {current_count} trades in {self.time_window_seconds}s\n"
            f"  Limit: {self.max_trades} trades per {self.time_window_seconds}s\n"
            f"Fill rejected to prevent overtrading."
        )
