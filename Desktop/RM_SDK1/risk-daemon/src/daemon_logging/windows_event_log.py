"""
Windows Event Log integration for Risk Manager Daemon.

Provides critical event logging to Windows Event Log for production monitoring.
Only available on Windows platforms.

Architecture Reference: architecture/20-logging-framework.md
"""

import logging
import platform

# Import Windows-specific modules only on Windows
if platform.system() == "Windows":
    try:
        import win32evtlog
        import win32evtlogutil

        WINDOWS_AVAILABLE = True
    except ImportError:
        WINDOWS_AVAILABLE = False
else:
    WINDOWS_AVAILABLE = False


class WindowsEventLogHandler(logging.Handler):
    """
    Custom handler that writes CRITICAL events to Windows Event Log.

    Only logs CRITICAL level events to avoid cluttering the Windows Event Log.
    Uses win32evtlogutil.ReportEvent() to write events.

    Note: Only functional on Windows platforms with pywin32 installed.
    """

    def __init__(self, app_name: str = "RiskManagerDaemon"):
        """
        Initialize Windows Event Log handler.

        Args:
            app_name: Application name for Event Log source
        """
        super().__init__()
        self.app_name = app_name

        # Only log CRITICAL events
        self.setLevel(logging.CRITICAL)

    def emit(self, record: logging.LogRecord) -> None:
        """
        Write log record to Windows Event Log.

        Args:
            record: LogRecord to emit

        Only emits if:
        - Running on Windows
        - pywin32 is available
        - Record level is CRITICAL
        """
        # Skip if not on Windows or pywin32 not available
        if not WINDOWS_AVAILABLE:
            return

        try:
            # Format the message using configured formatter
            message = self.format(record)

            # Write to Windows Event Log
            win32evtlogutil.ReportEvent(
                self.app_name,
                eventID=1,  # Generic event ID
                eventCategory=0,
                eventType=win32evtlog.EVENTLOG_ERROR_TYPE,
                strings=[message],
                data=None,
            )

        except Exception:
            # Call parent's handleError to log the error
            self.handleError(record)
