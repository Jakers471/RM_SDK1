"""
SessionBlockOutside Rule - Session time restrictions.

Prevents trading outside allowed session times.
Closes positions immediately if filled outside session.
Flattens account at session end.

Architecture reference: docs/architecture/02-risk-engine.md (Rule 10)
"""

from datetime import datetime, time
from typing import List, Dict, Optional
import pytz

from src.rules.base_rule import RiskRule
from src.state.models import RuleViolation, EnforcementAction


class SessionBlockOutsideRule(RiskRule):
    """
    Enforces trading session boundaries.

    Configuration:
        allowed_days: List of allowed day names (e.g., ["Monday", "Tuesday", ...])
        allowed_times: List of time ranges (e.g., [{"start": "08:00", "end": "15:00"}])
        timezone: Timezone name (e.g., "America/Chicago")
    """

    def __init__(
        self,
        allowed_days: List[str],
        allowed_times: List[Dict[str, str]],
        timezone: str = "America/Chicago",
        enabled: bool = True
    ):
        super().__init__(enabled=enabled)
        self.allowed_days = allowed_days
        self.allowed_times = allowed_times
        self.timezone = pytz.timezone(timezone)
        self.name = "SessionBlockOutside"

        # Parse time ranges
        self.time_ranges = []
        for time_range in allowed_times:
            start_time = datetime.strptime(time_range["start"], "%H:%M").time()
            end_time = datetime.strptime(time_range["end"], "%H:%M").time()
            self.time_ranges.append((start_time, end_time))

    def is_within_session(self, current_time: datetime) -> bool:
        """
        Check if current time is within allowed session.

        Args:
            current_time: Current datetime (will be converted to configured timezone)

        Returns:
            True if within session, False otherwise
        """
        # Convert to session timezone
        session_time = current_time.astimezone(self.timezone)

        # Check day of week
        day_name = session_time.strftime("%A")
        if day_name not in self.allowed_days:
            return False

        # Check time ranges
        current_time_only = session_time.time()
        for start_time, end_time in self.time_ranges:
            if start_time <= current_time_only < end_time:
                return True

        return False

    def evaluate(self, event_data: dict, account_state) -> Optional[RuleViolation]:
        """
        Check if event occurs outside session boundaries.

        Args:
            event_data: Event data (must include timestamp)
            account_state: Current account state

        Returns:
            RuleViolation if outside session
        """
        if not self.enabled:
            return None

        # Get event time
        event_time = event_data.get("fill_time") or event_data.get("update_time") or datetime.utcnow()

        # Check if within session
        if not self.is_within_session(event_time):
            session_time = event_time.astimezone(self.timezone)
            return RuleViolation(
                rule_name=self.name,
                severity="high",
                reason=f"Fill outside allowed session: {session_time.strftime('%A %H:%M %Z')}",
                account_id=account_state.account_id,
                timestamp=event_time,
                data={
                    "event_time": session_time.isoformat(),
                    "day": session_time.strftime("%A"),
                    "time": session_time.strftime("%H:%M")
                }
            )

        return None

    def get_enforcement_action(self, violation: RuleViolation) -> EnforcementAction:
        """
        Generate action to close position filled outside session.

        Args:
            violation: The SessionBlockOutside violation

        Returns:
            EnforcementAction to close the position
        """
        return EnforcementAction(
            action_type="close_position",
            account_id=violation.account_id,
            reason=f"Position filled outside allowed session ({violation.data['day']} {violation.data['time']})",
            timestamp=violation.timestamp,
            position_id=None,  # Most recent position (will be determined by enforcement engine)
            quantity=None,  # Close entire position
            notification_severity="warning",
            notification_action="close_position"
        )

    def applies_to_event(self, event_type: str) -> bool:
        """Evaluate on FILL events and TIME_TICK events."""
        return event_type in ["FILL", "TIME_TICK"]

    @property
    def notification_severity(self) -> str:
        return "warning"

    def format_notification_reason(self, violation: RuleViolation) -> str:
        """Format clear notification message."""
        day = violation.data["day"]
        time_str = violation.data["time"]
        return f"SessionBlockOutside: Fill occurred outside allowed session ({day} {time_str}). Position closed."
