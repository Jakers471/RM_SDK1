"""
Custom logging formatters for Risk Manager Daemon.

Provides:
- JSONFormatter: Structured JSON logging for machine parsing
- HumanReadableFormatter: CLI-friendly human-readable output

Architecture Reference: architecture/20-logging-framework.md
"""

import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """
    Format log records as JSON for structured logging.

    Output schema:
    {
        "timestamp": "2024-01-15T14:23:45.123456+00:00",  # ISO 8601 with TZ
        "level": "INFO",
        "category": "system",
        "message": "Log message here",
        "account_id": "ABC123",  # optional
        "context": {...},  # optional
        "exception": {  # optional
            "type": "ValueError",
            "message": "Error details",
            "stack_trace": "Traceback..."
        }
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record as JSON.

        Args:
            record: LogRecord to format

        Returns:
            JSON string
        """
        # Build base log entry
        log_entry: Dict[str, Any] = {
            "timestamp": self._format_timestamp(record.created),
            "level": record.levelname,
            "category": getattr(record, "category", "system"),
            "message": record.getMessage(),
        }

        # Add optional fields
        if hasattr(record, "account_id"):
            log_entry["account_id"] = record.account_id

        if hasattr(record, "context"):
            log_entry["context"] = record.context

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self._format_exception(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)

    def _format_timestamp(self, created: float) -> str:
        """
        Format timestamp as ISO 8601 with UTC timezone.

        Args:
            created: Timestamp from LogRecord

        Returns:
            ISO 8601 formatted string with timezone
        """
        dt = datetime.fromtimestamp(created, tz=timezone.utc)
        return dt.isoformat()

    def _format_exception(self, exc_info: Any) -> Dict[str, str]:
        """
        Format exception info as structured dict.

        Args:
            exc_info: Exception info tuple from LogRecord

        Returns:
            Dict with type, message, stack_trace
        """
        exc_type, exc_value, exc_tb = exc_info

        return {
            "type": exc_type.__name__ if exc_type else "Unknown",
            "message": str(exc_value) if exc_value else "",
            "stack_trace": "".join(
                traceback.format_exception(exc_type, exc_value, exc_tb)
            ),
        }


class HumanReadableFormatter(logging.Formatter):
    """
    Format log records for human-readable CLI output.

    Format: [YYYY-MM-DD HH:MM:SS] LEVEL    | category     | [account_id |] message

    Example outputs:
    - [2024-01-15 14:23:45] INFO     | system       | Daemon started
    - [2024-01-15 14:23:50] WARNING  | enforcement  | ABC123 | Rule violation detected
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record as human-readable text.

        Args:
            record: LogRecord to format

        Returns:
            Formatted string
        """
        # Format timestamp
        dt = datetime.fromtimestamp(record.created)
        timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")

        # Format level (pad to 8 characters for alignment)
        level = record.levelname.ljust(8)

        # Format category (pad to 12 characters for alignment)
        category = getattr(record, "category", "system").ljust(12)

        # Build output
        parts = [f"[{timestamp}]", level, "|", category]

        # Add account_id if present
        if hasattr(record, "account_id"):
            parts.extend(["|", record.account_id])

        # Add message
        parts.extend(["|", record.getMessage()])

        return " ".join(parts)
