"""
Central logging management for Risk Manager Daemon.

Provides unified interface for structured logging across all daemon components.
Manages async writes, log rotation, and category-specific loggers.

Architecture Reference: architecture/20-logging-framework.md
"""

import logging
import logging.handlers
import queue
from pathlib import Path
from typing import Any, Dict, Optional

from .formatters import JSONFormatter


class LoggerManager:
    """
    Central manager for all Risk Manager logging.

    Features:
    - Category-specific loggers (system, enforcement, error, audit)
    - Async log writes via QueueHandler/QueueListener
    - Rotating file handlers (50MB max, 10 backups)
    - Structured JSON logging
    """

    def __init__(self, log_dir: str = "~/.risk_manager/logs/", log_level: str = "INFO"):
        """
        Initialize LoggerManager.

        Args:
            log_dir: Directory for log files (supports ~ expansion)
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        # Expand ~ and convert to Path
        self.log_dir = Path(log_dir).expanduser()

        # Create log directory immediately
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Parse log level string to logging constant
        self.log_level = self._parse_log_level(log_level)

        # Category loggers (initialized by initialize())
        self.system_logger: Optional[logging.Logger] = None
        self.enforcement_logger: Optional[logging.Logger] = None
        self.error_logger: Optional[logging.Logger] = None
        self.audit_logger: Optional[logging.Logger] = None

        # Queue for async writes
        self.queue_listener: Optional[logging.handlers.QueueListener] = None
        self._log_queue: Optional[queue.Queue] = None
        self._handlers: list = []

    def initialize(self) -> None:
        """
        Initialize all loggers and handlers.

        Creates:
        - Category loggers with rotating file handlers
        - Queue listener for async writes
        """
        # Create queue for async logging
        self._log_queue = queue.Queue(-1)  # Unlimited size

        # Create category loggers
        self.system_logger = self._create_logger("system")
        self.enforcement_logger = self._create_logger("enforcement")
        self.error_logger = self._create_logger("error")
        self.audit_logger = self._create_logger("audit")

        # Start queue listener for async writes
        self.queue_listener = logging.handlers.QueueListener(
            self._log_queue, *self._handlers, respect_handler_level=True
        )
        self.queue_listener.start()

    def _create_logger(self, category: str) -> logging.Logger:
        """
        Create a category-specific logger.

        Args:
            category: Logger category (system, enforcement, error, audit)

        Returns:
            Configured Logger instance
        """
        # Create logger with unique name
        logger = logging.getLogger(f"risk_manager.{category}")
        logger.setLevel(self.log_level)
        logger.propagate = False  # Prevent duplicate logs

        # Create rotating file handler
        log_file = self.log_dir / f"{category}.log"
        handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file),
            maxBytes=50 * 1024 * 1024,  # 50 MB
            backupCount=10,
            encoding="utf-8",
        )
        handler.setFormatter(JSONFormatter())

        # Add handler directly to logger for inspection/testing
        # (also added to queue listener for async writes)
        logger.addHandler(handler)

        # Store handler for queue listener
        self._handlers.append(handler)

        return logger

    def _parse_log_level(self, level_str: str) -> int:
        """
        Convert log level string to logging constant.

        Args:
            level_str: Level name (case-insensitive)

        Returns:
            Logging level constant
        """
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        return level_map.get(level_str.upper(), logging.INFO)

    def log_system(
        self,
        level: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        account_id: Optional[str] = None,
    ) -> None:
        """
        Log system events (startup, shutdown, connections, etc.).

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Log message
            context: Optional structured context data
            account_id: Optional account ID
        """
        if not self.system_logger:
            return

        # Parse level
        level_int = self._parse_log_level(level)

        # Create extra dict for custom attributes
        extra = {"category": "system"}
        if account_id:
            extra["account_id"] = account_id
        if context:
            extra["context"] = context

        # Log with appropriate level
        self.system_logger.log(level_int, message, extra=extra)

    def log_enforcement(
        self, account_id: str, rule: str, action: str, details: Dict[str, Any]
    ) -> None:
        """
        Log enforcement actions (rule violations, position closes, etc.).

        Args:
            account_id: Trading account ID
            rule: Rule name that triggered enforcement
            action: Action taken (e.g., "close_position", "flatten_account")
            details: Additional enforcement details
        """
        if not self.enforcement_logger:
            return

        # Build context
        context = {"rule": rule, "action": action, **details}

        extra = {
            "category": "enforcement",
            "account_id": account_id,
            "context": context,
        }

        message = f"Enforcement action: {action} (rule: {rule})"
        self.enforcement_logger.info(message, extra=extra)

    def log_error(
        self,
        message: str,
        exception: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
        account_id: Optional[str] = None,
    ) -> None:
        """
        Log errors and exceptions.

        Args:
            message: Error message
            exception: Optional exception object
            context: Optional error context
            account_id: Optional account ID
        """
        if not self.error_logger:
            return

        extra = {"category": "error"}
        if account_id:
            extra["account_id"] = account_id
        if context:
            extra["context"] = context

        # Include exception info if provided
        # Get the original exception info from sys.exc_info() if available
        exc_info = None
        if exception:
            import sys

            # Check if we're in an exception context
            current_exc = sys.exc_info()
            if current_exc[1] is exception:
                # Same exception, use current context
                exc_info = current_exc
            else:
                # Different/no context, construct exc_info tuple
                exc_info = (type(exception), exception, exception.__traceback__)

        self.error_logger.error(message, exc_info=exc_info, extra=extra)

    def log_audit(
        self,
        action: str,
        actor: str,
        details: Dict[str, Any],
        account_id: Optional[str] = None,
    ) -> None:
        """
        Log audit trail events (config changes, admin actions, etc.).

        Args:
            action: Action performed
            actor: Who performed the action
            details: Additional audit details
            account_id: Optional account ID
        """
        if not self.audit_logger:
            return

        context = {"action": action, "actor": actor, **details}

        extra = {"category": "audit", "context": context}
        if account_id:
            extra["account_id"] = account_id

        message = f"Audit: {action} by {actor}"
        self.audit_logger.info(message, extra=extra)

    def shutdown(self) -> None:
        """
        Gracefully shutdown logging system.

        Stops queue listener (flushes pending messages) and closes all handlers.
        """
        # Stop queue listener (flushes queue)
        if self.queue_listener:
            self.queue_listener.stop()

        # Close all handlers on all loggers
        for logger in [
            self.system_logger,
            self.enforcement_logger,
            self.error_logger,
            self.audit_logger,
        ]:
            if logger:
                for handler in logger.handlers[
                    :
                ]:  # Copy list to avoid modification during iteration
                    try:
                        handler.close()
                        logger.removeHandler(handler)
                    except Exception:
                        pass  # Ignore close errors during shutdown

    def _add_windows_event_log(self, config: Any) -> None:
        """
        Add Windows Event Log handler to system and error loggers.

        Args:
            config: Windows Event Log configuration object
                    (must have .enabled and .log_critical_only attributes)
        """
        # Skip if disabled
        if not config.enabled:
            return

        # Try to import Windows Event Log handler (Windows only)
        try:
            from .windows_event_log import WindowsEventLogHandler

            # Create handler for critical events
            handler = WindowsEventLogHandler(app_name="RiskManagerDaemon")

            # Add to system and error loggers
            if self.system_logger:
                self.system_logger.addHandler(handler)

            if self.error_logger:
                self.error_logger.addHandler(handler)

        except ImportError:
            # Not on Windows, skip silently
            pass
