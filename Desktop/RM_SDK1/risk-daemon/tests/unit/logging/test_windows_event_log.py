"""
Unit tests for WindowsEventLogHandler (Windows-only).

Tests critical event logging to Windows Event Log.

Architecture Reference: architecture/20-logging-framework.md
"""

import pytest
import platform
from unittest.mock import Mock, patch, MagicMock


pytestmark = pytest.mark.unit

# Skip all tests if not on Windows
pytestmark = pytest.mark.skipif(
    platform.system() != "Windows",
    reason="Windows Event Log only available on Windows"
)


class TestWindowsEventLogHandler:
    """Test WindowsEventLogHandler for critical events."""

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
    def test_windows_event_log_handler_initialization(self):
        """
        WindowsEventLogHandler should initialize with app name.

        Architecture requirement:
        - app_name: "RiskManagerDaemon" (default)
        - setLevel(logging.CRITICAL)
        """
        from src.daemon_logging.windows_event_log import WindowsEventLogHandler

        handler = WindowsEventLogHandler(app_name="TestApp")

        assert handler.app_name == "TestApp"
        assert handler.level == pytest.importorskip("logging").CRITICAL

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
    def test_windows_event_log_handler_only_logs_critical(self):
        """
        WindowsEventLogHandler should only log CRITICAL level events.

        Architecture requirement:
        - log_critical_only: true
        """
        from src.daemon_logging.windows_event_log import WindowsEventLogHandler
        import logging

        handler = WindowsEventLogHandler()

        # Handler level should be CRITICAL
        assert handler.level == logging.CRITICAL

        # Lower level events should not be logged
        info_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Info message",
            args=(),
            exc_info=None
        )

        # Should not emit (level too low)
        # Handler's isEnabledFor() would return False for INFO
        assert not handler.isEnabledFor(info_record.levelno)

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
    @patch('win32evtlogutil.ReportEvent')
    def test_windows_event_log_handler_emits_critical_events(self, mock_report_event):
        """
        WindowsEventLogHandler should emit CRITICAL events to Windows Event Log.

        Uses win32evtlogutil.ReportEvent() to write events.
        """
        from src.daemon_logging.windows_event_log import WindowsEventLogHandler
        import logging

        handler = WindowsEventLogHandler(app_name="RiskManagerDaemon")

        # Create CRITICAL log record
        record = logging.LogRecord(
            name="test",
            level=logging.CRITICAL,
            pathname="",
            lineno=0,
            msg="Critical error occurred",
            args=(),
            exc_info=None
        )

        # Emit the record
        handler.emit(record)

        # Should have called ReportEvent
        mock_report_event.assert_called_once()

        # Verify call arguments
        call_args = mock_report_event.call_args
        assert call_args[0][0] == "RiskManagerDaemon"  # App name
        assert "Critical error occurred" in call_args[1]['strings'][0]

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
    def test_windows_event_log_handler_uses_error_event_type(self):
        """
        WindowsEventLogHandler should use EVENTLOG_ERROR_TYPE for all events.

        Architecture requirement:
        - event_type = win32evtlog.EVENTLOG_ERROR_TYPE
        """
        from src.daemon_logging.windows_event_log import WindowsEventLogHandler

        with patch('win32evtlogutil.ReportEvent') as mock_report:
            import win32evtlog
            import logging

            handler = WindowsEventLogHandler()

            record = logging.LogRecord(
                name="test",
                level=logging.CRITICAL,
                pathname="",
                lineno=0,
                msg="Test",
                args=(),
                exc_info=None
            )

            handler.emit(record)

            # Check event type in call
            call_kwargs = mock_report.call_args[1]
            assert call_kwargs['eventType'] == win32evtlog.EVENTLOG_ERROR_TYPE

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
    def test_windows_event_log_handler_formats_message(self):
        """
        WindowsEventLogHandler should format message using configured formatter.
        """
        from src.daemon_logging.windows_event_log import WindowsEventLogHandler
        from src.daemon_logging.formatters import HumanReadableFormatter
        import logging

        with patch('win32evtlogutil.ReportEvent') as mock_report:
            handler = WindowsEventLogHandler()
            handler.setFormatter(HumanReadableFormatter())

            record = logging.LogRecord(
                name="test",
                level=logging.CRITICAL,
                pathname="",
                lineno=0,
                msg="Formatted message",
                args=(),
                exc_info=None
            )
            record.category = "error"

            handler.emit(record)

            # Message should be formatted
            call_args = mock_report.call_args[1]
            message = call_args['strings'][0]

            # Should have human-readable format
            assert "CRITICAL" in message
            assert "Formatted message" in message

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
    def test_windows_event_log_handler_handles_emit_errors(self):
        """
        WindowsEventLogHandler should handle emit() errors gracefully.

        Calls handleError() if ReportEvent fails.
        """
        from src.daemon_logging.windows_event_log import WindowsEventLogHandler
        import logging

        with patch('win32evtlogutil.ReportEvent', side_effect=Exception("Event Log error")):
            handler = WindowsEventLogHandler()
            handler.handleError = MagicMock()  # Mock handleError

            record = logging.LogRecord(
                name="test",
                level=logging.CRITICAL,
                pathname="",
                lineno=0,
                msg="Test",
                args=(),
                exc_info=None
            )

            # Should not raise exception
            handler.emit(record)

            # Should have called handleError
            handler.handleError.assert_called_once()


class TestLoggerManagerWindowsIntegration:
    """Test LoggerManager integration with Windows Event Log."""

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
    def test_logger_manager_adds_windows_event_log_handler(self):
        """
        LoggerManager should add WindowsEventLogHandler when enabled.

        Architecture requirement:
        - windows_event_log.enabled: true
        - Add to system_logger and error_logger only
        """
        from src.daemon_logging.logger_manager import LoggerManager
        from src.daemon_logging.windows_event_log import WindowsEventLogHandler
        import tempfile

        # Mock Windows Event Log config
        class MockConfig:
            enabled = True
            log_critical_only = True

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Add Windows Event Log handler
            manager._add_windows_event_log(MockConfig())

            # Check system logger has WindowsEventLogHandler
            has_windows_handler = any(
                isinstance(h, WindowsEventLogHandler)
                for h in manager.system_logger.handlers
            )

            assert has_windows_handler, "System logger should have WindowsEventLogHandler"

            manager.shutdown()

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
    def test_logger_manager_skips_windows_handler_when_disabled(self):
        """
        LoggerManager should skip WindowsEventLogHandler when disabled.

        Architecture requirement:
        - windows_event_log.enabled: false
        """
        from src.daemon_logging.logger_manager import LoggerManager
        from src.daemon_logging.windows_event_log import WindowsEventLogHandler
        import tempfile

        class MockConfig:
            enabled = False
            log_critical_only = True

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Try to add (should be skipped)
            manager._add_windows_event_log(MockConfig())

            # Should NOT have WindowsEventLogHandler
            has_windows_handler = any(
                isinstance(h, WindowsEventLogHandler)
                for h in manager.system_logger.handlers
            )

            assert not has_windows_handler, "Should not add handler when disabled"

            manager.shutdown()


# Non-Windows platform tests
class TestWindowsEventLogSkipOnNonWindows:
    """Test that Windows Event Log is skipped on non-Windows platforms."""

    @pytest.mark.skipif(platform.system() == "Windows", reason="Test for non-Windows")
    def test_windows_event_log_skipped_on_linux(self):
        """
        Windows Event Log should be skipped on non-Windows platforms.
        """
        from src.daemon_logging.logger_manager import LoggerManager
        import tempfile

        class MockConfig:
            enabled = True
            log_critical_only = True

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Should not raise ImportError for win32evtlog
            # Should gracefully skip Windows Event Log
            try:
                manager._add_windows_event_log(MockConfig())
            except ImportError:
                pytest.fail("Should not raise ImportError on non-Windows platforms")

            manager.shutdown()
