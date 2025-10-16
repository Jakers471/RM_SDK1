"""
MaxContracts Rule - Universal contract limit enforcement.

Prevents trader from holding more than specified number of contracts.
Closes excess contracts immediately (LIFO - Last In First Out).

Architecture reference: docs/architecture/02-risk-engine.md (Rule 1)
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from src.rules.base_rule import RiskRule
from src.state.models import RuleViolation, EnforcementAction


class MaxContractsRule(RiskRule):
    """
    Enforces maximum total contract limit across all positions.

    Configuration:
        max_contracts: Maximum number of contracts allowed
    """

    def __init__(self, max_contracts: int, enabled: bool = True):
        super().__init__(enabled=enabled)
        self.max_contracts = max_contracts
        self.name = "MaxContracts"

    def evaluate(self, event_data: dict, account_state) -> Optional[RuleViolation]:
        """
        Check if total contracts exceed limit.

        Args:
            event_data: Event data (includes new fill quantity if FILL event)
            account_state: Current account state

        Returns:
            RuleViolation if limit exceeded
        """
        if not self.enabled:
            return None

        # Get current contract count
        current_total = sum(p.quantity for p in account_state.open_positions)

        # Add new fill quantity if this is a FILL event
        if "quantity" in event_data:
            current_total += event_data.get("quantity", 0)

        # Check violation
        if current_total > self.max_contracts:
            excess = current_total - self.max_contracts
            return RuleViolation(
                rule_name=self.name,
                severity="high",
                reason=f"MaxContracts: {current_total} contracts exceeds limit of {self.max_contracts} (excess: {excess})",
                account_id=account_state.account_id,
                timestamp=datetime.utcnow(),
                data={
                    "current_total": current_total,
                    "limit": self.max_contracts,
                    "excess": excess,
                    "account_state": account_state  # Store for enforcement action
                }
            )

        return None

    def get_enforcement_action(self, violation: RuleViolation, account_state=None) -> EnforcementAction:
        """
        Generate action to close excess contracts (LIFO).

        Strategy: Close most recently opened position by excess quantity.

        Args:
            violation: The MaxContracts violation
            account_state: Account state (optional, for determining LIFO position)

        Returns:
            EnforcementAction to close excess contracts
        """
        excess = violation.data["excess"]

        # Get account_state from violation data if not provided
        if account_state is None:
            account_state = violation.data.get("account_state")

        # Find most recent position (LIFO) if account_state available
        position_id = None
        if account_state and account_state.open_positions:
            most_recent = max(account_state.open_positions, key=lambda p: p.opened_at)
            position_id = most_recent.position_id

        return EnforcementAction(
            action_type="close_position",
            account_id=violation.account_id,
            reason=f"Closing {excess} excess contracts (MaxContracts limit: {self.max_contracts})",
            timestamp=violation.timestamp,
            position_id=position_id,
            quantity=excess,
            notification_severity="warning",
            notification_action="close_position"
        )

    def applies_to_event(self, event_type: str) -> bool:
        """Only evaluate on FILL events."""
        return event_type == "FILL"

    @property
    def notification_severity(self) -> str:
        return "warning"

    def format_notification_reason(self, violation: RuleViolation) -> str:
        """Format clear notification message."""
        current = violation.data["current_total"]
        limit = violation.data["limit"]
        excess = violation.data["excess"]
        return f"MaxContracts limit exceeded: {current} contracts > {limit} limit. Closing {excess} excess contracts."

    def create_violation(self, current_total: int, limit: int, excess: int) -> RuleViolation:
        """Helper to create MaxContracts violation."""
        return RuleViolation(
            rule_name=self.name,
            severity="high",
            reason=f"MaxContracts limit exceeded: {current_total} contracts > {limit} limit",
            account_id="",  # Will be set by caller
            timestamp=datetime.utcnow(),
            data={
                "current_total": current_total,
                "limit": limit,
                "excess": excess
            }
        )
