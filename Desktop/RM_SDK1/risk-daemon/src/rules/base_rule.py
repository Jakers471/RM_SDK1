"""
Base rule interface for all risk rules.

All risk rules must inherit from RiskRule and implement evaluate() method.
"""

from abc import ABC, abstractmethod
from typing import Optional
from src.state.models import RuleViolation, EnforcementAction


class RiskRule(ABC):
    """
    Abstract base class for all risk rules.

    Rules evaluate account state and events, returning violations when detected.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.name = self.__class__.__name__.replace("Rule", "")

    @abstractmethod
    def evaluate(self, event_data: dict, account_state) -> Optional[RuleViolation]:
        """
        Evaluate rule against current state and event.

        Args:
            event_data: Event data dictionary
            account_state: Current account state

        Returns:
            RuleViolation if rule violated, None otherwise
        """
        pass

    @abstractmethod
    def get_enforcement_action(self, violation: RuleViolation, account_state=None) -> EnforcementAction:
        """
        Generate enforcement action for violation.

        Args:
            violation: The rule violation
            account_state: Optional account state for contextual actions

        Returns:
            EnforcementAction to execute
        """
        pass

    def applies_to_event(self, event_type: str) -> bool:
        """
        Check if rule should be evaluated for given event type.

        Args:
            event_type: Event type (FILL, POSITION_UPDATE, etc.)

        Returns:
            True if rule applies to this event type
        """
        # Default: evaluate on FILL and POSITION_UPDATE
        return event_type in ["FILL", "POSITION_UPDATE"]

    @property
    def notification_severity(self) -> str:
        """
        Get notification severity for this rule.

        Returns:
            "info", "warning", or "critical"
        """
        return "warning"

    def format_notification_reason(self, violation: RuleViolation) -> str:
        """
        Format notification reason message.

        Args:
            violation: The rule violation

        Returns:
            Human-readable reason string
        """
        return violation.reason

    def create_violation(self, **kwargs) -> RuleViolation:
        """
        Helper to create violation with common fields.

        Args:
            **kwargs: Violation-specific data

        Returns:
            RuleViolation instance
        """
        # To be overridden by subclasses with specific logic
        raise NotImplementedError("Subclass must implement create_violation")
