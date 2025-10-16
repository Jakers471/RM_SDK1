"""
Core data models for Risk Manager.

Defines violations, enforcement actions, and other shared types.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional
from uuid import UUID


@dataclass
class Event:
    """
    Internal event model for risk manager.
    """
    event_id: UUID
    event_type: str  # FILL, POSITION_UPDATE, CONNECTION_CHANGE, etc.
    timestamp: datetime
    priority: int
    account_id: str
    source: str
    data: Dict
    correlation_id: Optional[UUID] = None


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
    action_type: str  # "close_position", "flatten_account", "set_lockout", "reject_fill", "start_cooldown", "notify"
    account_id: str
    reason: str
    timestamp: datetime

    # For close_position
    position_id: Optional[UUID] = None
    quantity: Optional[int] = None

    # For set_lockout
    lockout_until: Optional[datetime] = None

    # For start_cooldown
    duration_seconds: Optional[int] = None

    # For notify (alert only)
    severity: Optional[str] = None
    message: Optional[str] = None

    # Notification fields
    notification_severity: str = "warning"
    notification_action: str = ""


@dataclass
class OrderResult:
    """
    Result of order execution attempt.

    Returned by SDKAdapter.close_position() and flatten_account().
    """
    success: bool                      # True if order placed successfully
    order_id: Optional[str]            # Broker order ID (if success=True)
    error_message: Optional[str]       # Error details (if success=False)
    contract_id: str                   # Contract that was traded
    side: str                          # "buy" or "sell"
    quantity: int                      # Contracts ordered
    price: Optional[Decimal]           # Limit price (None for market orders)
