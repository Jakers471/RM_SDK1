"""
Logging module for Risk Manager Daemon.

Provides structured JSON logging with async writes, log rotation, and compression.

Public API:
- LoggerManager: Central logging orchestrator
- JSONFormatter: Structured JSON log formatter
- HumanReadableFormatter: CLI-friendly log formatter
- LogCleaner: Log retention and compression utilities
- WindowsEventLogHandler: Windows Event Log integration (Windows only)

Architecture Reference: architecture/20-logging-framework.md
"""

from .formatters import JSONFormatter, HumanReadableFormatter
from .log_cleaner import LogCleaner
from .log_streaming import stream_logs
from .logger_manager import LoggerManager
from .windows_event_log import WindowsEventLogHandler

__all__ = [
    "LoggerManager",
    "JSONFormatter",
    "HumanReadableFormatter",
    "LogCleaner",
    "WindowsEventLogHandler",
    "stream_logs",
]
