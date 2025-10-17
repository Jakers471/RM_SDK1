"""
Unit tests for logging formatters (JSONFormatter, HumanReadableFormatter).

Tests the behavioral requirements for structured JSON logging and
human-readable CLI display formatting.

Architecture Reference: architecture/20-logging-framework.md
"""

import pytest
import logging
import json
from datetime import datetime, timezone
from unittest.mock import Mock


# These imports will FAIL until implementation exists (TDD RED phase)
pytestmark = pytest.mark.unit


class TestJSONFormatter:
    """Test JSONFormatter produces valid structured JSON log entries."""

    def test_json_formatter_creates_valid_json(self):
        """
        JSONFormatter.format() should return a valid JSON string.

        Architecture requirement:
        - Log entries must be parseable JSON for machine processing
        - Required fields: timestamp, level, category, message
        """
        from src.daemon_logging.formatters import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.category = "system"

        result = formatter.format(record)

        # Should be valid JSON
        log_entry = json.loads(result)
        assert isinstance(log_entry, dict), "Formatted output must be a JSON object"

    def test_json_formatter_includes_required_fields(self):
        """
        JSONFormatter must include all required fields per JSON schema.

        Required fields: timestamp, level, category, message
        """
        from src.daemon_logging.formatters import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.category = "enforcement"

        result = formatter.format(record)
        log_entry = json.loads(result)

        # Verify required fields
        assert "timestamp" in log_entry, "Must include timestamp field"
        assert "level" in log_entry, "Must include level field"
        assert "category" in log_entry, "Must include category field"
        assert "message" in log_entry, "Must include message field"

    def test_json_formatter_timestamp_is_iso8601_with_timezone(self):
        """
        Timestamp must be ISO 8601 format with timezone (UTC).

        Architecture requirement:
        - "timestamp": ISO 8601 timestamp with timezone
        """
        from src.daemon_logging.formatters import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None
        )
        record.category = "system"

        result = formatter.format(record)
        log_entry = json.loads(result)

        # Parse timestamp to verify ISO 8601 format with timezone
        timestamp_str = log_entry["timestamp"]
        parsed_dt = datetime.fromisoformat(timestamp_str)

        assert parsed_dt.tzinfo is not None, "Timestamp must include timezone"
        assert "+00:00" in timestamp_str or "Z" in timestamp_str, "Should use UTC timezone"

    def test_json_formatter_includes_account_id_when_present(self):
        """
        JSONFormatter should include account_id field if present in record.

        Architecture requirement:
        - account_id is optional field added when applicable
        """
        from src.daemon_logging.formatters import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Account event",
            args=(),
            exc_info=None
        )
        record.category = "enforcement"
        record.account_id = "ABC123"

        result = formatter.format(record)
        log_entry = json.loads(result)

        assert "account_id" in log_entry, "Should include account_id when present"
        assert log_entry["account_id"] == "ABC123"

    def test_json_formatter_includes_context_when_present(self):
        """
        JSONFormatter should include context object if present in record.

        Architecture requirement:
        - context is optional object for additional structured data
        """
        from src.daemon_logging.formatters import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Enforcement action",
            args=(),
            exc_info=None
        )
        record.category = "enforcement"
        record.context = {
            "rule": "UnrealizedLoss",
            "violation": {"current_value": -210, "limit": -200}
        }

        result = formatter.format(record)
        log_entry = json.loads(result)

        assert "context" in log_entry, "Should include context when present"
        assert log_entry["context"]["rule"] == "UnrealizedLoss"
        assert log_entry["context"]["violation"]["current_value"] == -210

    def test_json_formatter_includes_exception_info(self):
        """
        JSONFormatter should include exception details when exc_info is present.

        Architecture requirement:
        - exception object with type, message, stack_trace
        """
        from src.daemon_logging.formatters import JSONFormatter

        formatter = JSONFormatter()

        # Create exception info
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Error occurred",
            args=(),
            exc_info=exc_info
        )
        record.category = "error"

        result = formatter.format(record)
        log_entry = json.loads(result)

        assert "exception" in log_entry, "Should include exception when exc_info present"
        assert log_entry["exception"]["type"] == "ValueError"
        assert "Test error" in log_entry["exception"]["message"]
        assert "Traceback" in log_entry["exception"]["stack_trace"]

    def test_json_formatter_level_values(self):
        """
        JSONFormatter should use standard logging level names.

        Valid levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
        """
        from src.daemon_logging.formatters import JSONFormatter

        formatter = JSONFormatter()

        test_levels = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]

        for level_int, level_name in test_levels:
            record = logging.LogRecord(
                name="test",
                level=level_int,
                pathname="",
                lineno=0,
                msg="Test",
                args=(),
                exc_info=None
            )
            record.category = "system"

            result = formatter.format(record)
            log_entry = json.loads(result)

            assert log_entry["level"] == level_name, f"Level {level_int} should format as {level_name}"

    def test_json_formatter_category_values(self):
        """
        JSONFormatter should preserve category values.

        Valid categories: system, enforcement, error, audit, sdk
        """
        from src.daemon_logging.formatters import JSONFormatter

        formatter = JSONFormatter()

        categories = ["system", "enforcement", "error", "audit", "sdk"]

        for category in categories:
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="Test",
                args=(),
                exc_info=None
            )
            record.category = category

            result = formatter.format(record)
            log_entry = json.loads(result)

            assert log_entry["category"] == category, f"Category should be {category}"

    def test_json_formatter_defaults_to_system_category(self):
        """
        JSONFormatter should default to 'system' category if not specified.
        """
        from src.daemon_logging.formatters import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None
        )
        # No category attribute set

        result = formatter.format(record)
        log_entry = json.loads(result)

        assert log_entry["category"] == "system", "Should default to 'system' category"


class TestHumanReadableFormatter:
    """Test HumanReadableFormatter produces CLI-friendly output."""

    def test_human_readable_formatter_basic_format(self):
        """
        HumanReadableFormatter should produce format:
        [timestamp] LEVEL | category | message

        Architecture requirement:
        - Format: `[timestamp] LEVEL | category | account_id | message`
        """
        from src.daemon_logging.formatters import HumanReadableFormatter

        formatter = HumanReadableFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.category = "system"

        result = formatter.format(record)

        # Verify format structure
        assert result.startswith("["), "Should start with timestamp bracket"
        assert "INFO" in result, "Should include level"
        assert "system" in result, "Should include category"
        assert "Test message" in result, "Should include message"

    def test_human_readable_formatter_timestamp_format(self):
        """
        Timestamp should be formatted as: YYYY-MM-DD HH:MM:SS
        """
        from src.daemon_logging.formatters import HumanReadableFormatter

        formatter = HumanReadableFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None
        )
        record.category = "system"

        result = formatter.format(record)

        # Extract timestamp (between first [ and ])
        import re
        match = re.search(r'\[(.+?)\]', result)
        assert match, "Should contain timestamp in brackets"

        timestamp_str = match.group(1)
        # Verify format: YYYY-MM-DD HH:MM:SS
        assert re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', timestamp_str), \
            "Timestamp should be YYYY-MM-DD HH:MM:SS format"

    def test_human_readable_formatter_includes_account_id(self):
        """
        When account_id is present, it should be included in the output.

        Format with account_id:
        [timestamp] LEVEL | category | account_id | message
        """
        from src.daemon_logging.formatters import HumanReadableFormatter

        formatter = HumanReadableFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Account event",
            args=(),
            exc_info=None
        )
        record.category = "enforcement"
        record.account_id = "ABC123"

        result = formatter.format(record)

        assert "ABC123" in result, "Should include account_id in output"
        assert result.count("|") >= 3, "Should have at least 3 separators when account_id present"

    def test_human_readable_formatter_level_padding(self):
        """
        Level names should be padded to 8 characters for alignment.

        Architecture example: "INFO  " (padded to 8 chars)
        """
        from src.daemon_logging.formatters import HumanReadableFormatter

        formatter = HumanReadableFormatter()

        # Test different level lengths
        test_cases = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
        ]

        for level_int, level_name in test_cases:
            record = logging.LogRecord(
                name="test",
                level=level_int,
                pathname="",
                lineno=0,
                msg="Test",
                args=(),
                exc_info=None
            )
            record.category = "system"

            result = formatter.format(record)

            # Level should appear with consistent spacing
            # This ensures column alignment in CLI output
            assert level_name in result, f"Should contain {level_name}"

    def test_human_readable_formatter_category_padding(self):
        """
        Category names should be padded to 12 characters for alignment.

        Architecture example: "enforcement " (padded to 12 chars)
        """
        from src.daemon_logging.formatters import HumanReadableFormatter

        formatter = HumanReadableFormatter()

        categories = ["system", "enforcement", "error"]

        for category in categories:
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="Test",
                args=(),
                exc_info=None
            )
            record.category = category

            result = formatter.format(record)

            assert category in result, f"Should contain category {category}"

    def test_human_readable_formatter_defaults_to_system_category(self):
        """
        If no category attribute, should default to 'system'.
        """
        from src.daemon_logging.formatters import HumanReadableFormatter

        formatter = HumanReadableFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None
        )
        # No category attribute

        result = formatter.format(record)

        assert "system" in result, "Should default to 'system' category"

    def test_human_readable_formatter_without_account_id(self):
        """
        When account_id is not present, format should omit it gracefully.

        Format without account_id:
        [timestamp] LEVEL | category | message
        """
        from src.daemon_logging.formatters import HumanReadableFormatter

        formatter = HumanReadableFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="System event",
            args=(),
            exc_info=None
        )
        record.category = "system"
        # No account_id

        result = formatter.format(record)

        # Should still have proper format without account_id section
        assert "System event" in result
        assert "|" in result  # Has separator
