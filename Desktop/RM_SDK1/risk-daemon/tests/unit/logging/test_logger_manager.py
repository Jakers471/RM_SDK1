"""
Unit tests for LoggerManager class.

Tests the core logging orchestration functionality including logger creation,
initialization, category-specific logging, and graceful shutdown.

Architecture Reference: architecture/20-logging-framework.md
"""

import pytest
import logging
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


pytestmark = pytest.mark.unit


class TestLoggerManagerInitialization:
    """Test LoggerManager initialization and setup."""

    def test_logger_manager_creates_log_directory(self):
        """
        LoggerManager should create log directory if it doesn't exist.

        Architecture requirement:
        - Log directory created at initialization
        - Default: ~/.risk_manager/logs/
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "new_logs"

            manager = LoggerManager(log_dir=str(log_dir))

            assert log_dir.exists(), "Should create log directory"
            assert log_dir.is_dir(), "Should be a directory"

    def test_logger_manager_expands_tilde_in_path(self):
        """
        LoggerManager should expand ~ to user home directory.

        Architecture requirement:
        - Support paths like ~/.risk_manager/logs/
        """
        from src.daemon_logging.logger_manager import LoggerManager

        manager = LoggerManager(log_dir="~/.test_logs")

        assert manager.log_dir.is_absolute(), "Should expand ~ to absolute path"
        assert "~" not in str(manager.log_dir), "Should not contain ~ after expansion"

    def test_logger_manager_parses_log_level(self):
        """
        LoggerManager should convert string log level to logging constant.

        Valid levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
        """
        from src.daemon_logging.logger_manager import LoggerManager

        test_cases = [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
            ("debug", logging.DEBUG),  # Case-insensitive
            ("info", logging.INFO),
        ]

        for level_str, expected_level in test_cases:
            manager = LoggerManager(log_level=level_str)
            assert manager.log_level == expected_level, \
                f"Level '{level_str}' should map to {expected_level}"

    def test_logger_manager_initialize_creates_all_loggers(self):
        """
        LoggerManager.initialize() should create all category loggers.

        Architecture requirement:
        - system_logger → system.log
        - enforcement_logger → enforcement.log
        - error_logger → error.log
        - audit_logger → audit.log
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            assert manager.system_logger is not None, "Should create system_logger"
            assert manager.enforcement_logger is not None, "Should create enforcement_logger"
            assert manager.error_logger is not None, "Should create error_logger"
            assert manager.audit_logger is not None, "Should create audit_logger"

    def test_logger_manager_creates_log_files(self):
        """
        LoggerManager.initialize() should create log files.

        Files created: system.log, enforcement.log, error.log, audit.log
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Trigger log writes to create files
            manager.log_system("INFO", "Test")
            manager.shutdown()

            log_dir = Path(temp_dir)
            assert (log_dir / "system.log").exists(), "Should create system.log"

    def test_logger_manager_loggers_have_correct_names(self):
        """
        Loggers should be named: risk_manager.<category>

        This prevents conflicts with other Python loggers.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            assert manager.system_logger.name == "risk_manager.system"
            assert manager.enforcement_logger.name == "risk_manager.enforcement"
            assert manager.error_logger.name == "risk_manager.error"
            assert manager.audit_logger.name == "risk_manager.audit"

            manager.shutdown()

    def test_logger_manager_loggers_do_not_propagate(self):
        """
        Loggers should have propagate=False to avoid duplicate logs.

        Architecture requirement:
        - logger.propagate = False
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            assert manager.system_logger.propagate is False
            assert manager.enforcement_logger.propagate is False

            manager.shutdown()


class TestLoggerManagerLogging:
    """Test LoggerManager logging methods."""

    def test_log_system_creates_system_log_entry(self):
        """
        log_system() should write to system.log with correct format.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            manager.log_system("INFO", "System started")
            manager.shutdown()

            log_file = Path(temp_dir) / "system.log"
            with open(log_file) as f:
                line = f.readline()
                log_entry = json.loads(line)

                assert log_entry["category"] == "system"
                assert log_entry["level"] == "INFO"
                assert log_entry["message"] == "System started"

    def test_log_system_with_context(self):
        """
        log_system() should include context dict when provided.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            context = {"connection_id": "conn_123", "retry_count": 3}
            manager.log_system("INFO", "Connection established", context=context)
            manager.shutdown()

            log_file = Path(temp_dir) / "system.log"
            with open(log_file) as f:
                log_entry = json.loads(f.readline())

                assert "context" in log_entry
                assert log_entry["context"]["connection_id"] == "conn_123"
                assert log_entry["context"]["retry_count"] == 3

    def test_log_enforcement_creates_enforcement_log_entry(self):
        """
        log_enforcement() should write to enforcement.log with account_id and rule.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            details = {
                "violation": {"current_value": -210, "limit": -200},
                "position": {"symbol": "MNQ", "quantity": 2}
            }
            manager.log_enforcement("ABC123", "UnrealizedLoss", "close_position", details)
            manager.shutdown()

            log_file = Path(temp_dir) / "enforcement.log"
            with open(log_file) as f:
                log_entry = json.loads(f.readline())

                assert log_entry["category"] == "enforcement"
                assert log_entry["account_id"] == "ABC123"
                assert log_entry["context"]["rule"] == "UnrealizedLoss"
                assert log_entry["context"]["action"] == "close_position"
                assert "violation" in log_entry["context"]

    def test_log_error_without_exception(self):
        """
        log_error() without exception should log error message.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            manager.log_error("Configuration error")
            manager.shutdown()

            log_file = Path(temp_dir) / "error.log"
            with open(log_file) as f:
                log_entry = json.loads(f.readline())

                assert log_entry["category"] == "error"
                assert log_entry["level"] == "ERROR"
                assert log_entry["message"] == "Configuration error"

    def test_log_error_with_exception(self):
        """
        log_error() with exception should include exception details.

        Architecture requirement:
        - exception object with type, message, stack_trace
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            try:
                raise ValueError("Invalid configuration value")
            except ValueError as e:
                manager.log_error("Configuration failed", exception=e)

            manager.shutdown()

            log_file = Path(temp_dir) / "error.log"
            with open(log_file) as f:
                log_entry = json.loads(f.readline())

                assert "exception" in log_entry
                assert log_entry["exception"]["type"] == "ValueError"
                assert "Invalid configuration value" in log_entry["exception"]["message"]
                assert "Traceback" in log_entry["exception"]["stack_trace"]

    def test_log_error_with_context(self):
        """
        log_error() should include context when provided.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            context = {"config_file": "system.json", "line": 42}
            manager.log_error("Parse error", context=context)
            manager.shutdown()

            log_file = Path(temp_dir) / "error.log"
            with open(log_file) as f:
                log_entry = json.loads(f.readline())

                assert "context" in log_entry
                assert log_entry["context"]["config_file"] == "system.json"

    def test_log_audit_creates_audit_log_entry(self):
        """
        log_audit() should write to audit.log with action and actor.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            details = {"config_type": "risk_rules", "changes": ["max_contracts"]}
            manager.log_audit("config_reload", "admin", details)
            manager.shutdown()

            log_file = Path(temp_dir) / "audit.log"
            with open(log_file) as f:
                log_entry = json.loads(f.readline())

                assert log_entry["category"] == "audit"
                assert log_entry["context"]["action"] == "config_reload"
                assert log_entry["context"]["actor"] == "admin"
                assert log_entry["context"]["config_type"] == "risk_rules"

    def test_log_system_accepts_different_levels(self):
        """
        log_system() should accept DEBUG, INFO, WARNING, ERROR, CRITICAL levels.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir, log_level="DEBUG")
            manager.initialize()

            test_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

            for level in test_levels:
                manager.log_system(level, f"Test {level} message")

            manager.shutdown()

            log_file = Path(temp_dir) / "system.log"
            with open(log_file) as f:
                lines = f.readlines()

                assert len(lines) == 5, "Should log all 5 levels"

                for i, level in enumerate(test_levels):
                    log_entry = json.loads(lines[i])
                    assert log_entry["level"] == level


class TestLoggerManagerAsyncQueue:
    """Test async queue handler for non-blocking writes."""

    def test_logger_manager_starts_queue_listener(self):
        """
        LoggerManager should start QueueListener on initialize().

        Architecture requirement:
        - Use QueueHandler and QueueListener for async writes
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            assert manager.queue_listener is not None, "Should create queue listener"

            manager.shutdown()

    def test_logger_manager_shutdown_stops_queue_listener(self):
        """
        LoggerManager.shutdown() should stop QueueListener.

        Ensures all queued logs are flushed before shutdown.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Mock queue listener to track stop() call
            listener_mock = MagicMock()
            manager.queue_listener = listener_mock

            manager.shutdown()

            listener_mock.stop.assert_called_once(), "Should stop queue listener"

    def test_logger_manager_shutdown_closes_all_handlers(self):
        """
        LoggerManager.shutdown() should close all file handlers.

        Ensures files are properly closed and flushed.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Mock handlers to track close() calls
            for logger in [manager.system_logger, manager.enforcement_logger]:
                for handler in logger.handlers:
                    handler.close = MagicMock()

            manager.shutdown()

            # Verify all handlers closed
            for logger in [manager.system_logger, manager.enforcement_logger]:
                for handler in logger.handlers:
                    handler.close.assert_called(), "Should close handler"


class TestLoggerManagerRotatingFileHandler:
    """Test rotating file handler configuration."""

    def test_logger_manager_uses_rotating_file_handler(self):
        """
        LoggerManager should use RotatingFileHandler with correct config.

        Architecture requirement:
        - maxBytes: 50 * 1024 * 1024 (50 MB)
        - backupCount: 10
        """
        from src.daemon_logging.logger_manager import LoggerManager
        import logging.handlers

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Check system logger's handler
            handler = manager.system_logger.handlers[0]

            assert isinstance(handler, logging.handlers.RotatingFileHandler), \
                "Should use RotatingFileHandler"
            assert handler.maxBytes == 50 * 1024 * 1024, "Should have 50 MB max size"
            assert handler.backupCount == 10, "Should keep 10 backup files"

            manager.shutdown()

    def test_logger_manager_handler_uses_utf8_encoding(self):
        """
        File handlers should use UTF-8 encoding for Unicode support.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            handler = manager.system_logger.handlers[0]

            assert handler.encoding == 'utf-8', "Should use UTF-8 encoding"

            manager.shutdown()

    def test_logger_manager_handler_uses_json_formatter(self):
        """
        File handlers should use JSONFormatter by default.
        """
        from src.daemon_logging.logger_manager import LoggerManager
        from src.daemon_logging.formatters import JSONFormatter

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            handler = manager.system_logger.handlers[0]

            assert isinstance(handler.formatter, JSONFormatter), \
                "Should use JSONFormatter"

            manager.shutdown()
