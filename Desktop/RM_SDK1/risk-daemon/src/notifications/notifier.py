"""
Production Notifier - Basic notification service.

Logs notifications to file. Future enhancements can add Discord, Telegram, etc.
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class Notifier:
    """
    Production notification service.

    Currently logs notifications to file. Future versions can integrate
    with Discord webhooks, Telegram bots, email, etc.
    """

    def __init__(self):
        """Initialize notifier."""
        self.notification_count = 0

    def send(
        self,
        account_id: str,
        title: str,
        message: str,
        severity: str,
        reason: str,
        action: str
    ):
        """
        Send notification.

        Args:
            account_id: Account that triggered notification
            title: Notification title
            message: Detailed message
            severity: Severity level ("info", "warning", "critical")
            reason: Reason for notification
            action: Action taken
        """
        self.notification_count += 1

        # Log notification
        log_level = {
            "info": logging.INFO,
            "warning": logging.WARNING,
            "critical": logging.CRITICAL
        }.get(severity.lower(), logging.INFO)

        logger.log(
            log_level,
            f"[NOTIFICATION] {title} - Account: {account_id}, "
            f"Reason: {reason}, Action: {action}, Message: {message}"
        )

        # TODO: Future integrations
        # - Send to Discord webhook
        # - Send to Telegram bot
        # - Send email via SMTP
        # - Write to notification database table

    def get_notification_count(self) -> int:
        """Get total notifications sent."""
        return self.notification_count
