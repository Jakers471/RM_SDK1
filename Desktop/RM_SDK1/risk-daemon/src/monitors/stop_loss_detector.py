"""
Stop Loss Detector

Monitors ORDER and ORDER_STATUS events to detect stop loss attachment.
Updates position.stop_loss_attached flag when stop loss orders are detected.

Architecture reference: docs/architecture/02-risk-engine.md
"""

from typing import List, Optional


class StopLossDetector:
    """
    Detects stop loss orders and updates position flags.

    Monitors for stop loss order types:
    - STP: Stop Market
    - STPLMT: Stop Limit
    - TRAIL: Trailing Stop

    When detected, sets position.stop_loss_attached = True
    """

    def __init__(self, enabled: bool = True):
        """
        Initialize stop loss detector.

        Args:
            enabled: Whether detector is active
        """
        self.enabled = enabled
        self.name = "StopLossDetector"
        self._stop_order_types = {"STP", "STPLMT", "TRAIL"}

    def is_stop_order(self, order: dict) -> bool:
        """
        Check if order is a stop loss order.

        Args:
            order: Order data dictionary

        Returns:
            True if order is a stop loss order
        """
        order_type = order.get("order_type", "")
        return order_type in self._stop_order_types

    def find_matching_positions(self, order: dict, account_state) -> List:
        """
        Find positions that match this stop loss order.

        Matches by symbol. Multiple positions for same symbol will all be returned.

        Args:
            order: Stop loss order data
            account_state: Current account state

        Returns:
            List of matching Position objects
        """
        symbol = order.get("symbol")
        if not symbol:
            return []

        # Find all positions with matching symbol
        matching_positions = [
            pos for pos in account_state.open_positions
            if pos.symbol == symbol
        ]

        return matching_positions

    def process_order(self, order: dict, account_state):
        """
        Process order and update position flags if stop loss detected.

        Args:
            order: Order data dictionary
            account_state: Current account state
        """
        if not self.enabled:
            return

        # Check if this is a stop loss order
        if not self.is_stop_order(order):
            return

        # Find matching positions
        matching_positions = self.find_matching_positions(order, account_state)

        # Update stop_loss_attached flag for all matching positions
        for position in matching_positions:
            position.stop_loss_attached = True

    def applies_to_event(self, event_type: str) -> bool:
        """
        Check if detector should process this event type.

        Args:
            event_type: Event type string

        Returns:
            True if detector applies to this event type
        """
        return event_type in ["ORDER", "ORDER_STATUS"]
