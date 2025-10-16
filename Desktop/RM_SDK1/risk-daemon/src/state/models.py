"""
Core data models for Risk Manager.

Defines violations, enforcement actions, and other shared types.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID


@dataclass
class RuleViolation:
    """
    Represents a rule violation detected by risk engine.
    """
    rule_name: str
    severity: str  # "info", "warning", "critical"
    reason: str
    account_id: str
    timestamp: datetime
    data: dict


@dataclass
class EnforcementAction:
    """
    Enforcement action to be executed.
    """
    action_type: str  # "close_position", "flatten_account", "set_lockout"
    account_id: str
    reason: str
    timestamp: datetime

    # For close_position
    position_id: Optional[UUID] = None
    quantity: Optional[int] = None

    # For set_lockout
    lockout_until: Optional[datetime] = None

    # Notification fields
    notification_severity: str = "warning"
    notification_action: str = ""


@dataclass
class OrderResult:
    """
    Result of order execution attempt.
    """
    success: bool
    order_id: Optional[str]
    error_message: Optional[str]
    contract_id: str
    side: str
    quantity: int
    price: Optional[Decimal]
