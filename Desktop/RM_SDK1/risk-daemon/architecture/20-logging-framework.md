# Logging Framework Implementation

## Overview

This document provides detailed implementation specifications for the Structured Logging System described in `07-notifications-logging.md`. While the high-level architecture defines WHAT the logging system does, this document specifies HOW to implement it with specific file formats, Python libraries, log rotation patterns, and integration points.

**Implementation Status**: NOT IMPLEMENTED (P0 Priority)
**Dependencies**: Configuration System (16)
**Estimated Effort**: 2 days

## Core Implementation Requirements

1. **Library**: Use Python's `logging` module with custom JSON formatter
2. **Format**: Structured JSON for machine parsing + human-readable for CLI display
3. **Rotation**: `logging.handlers.RotatingFileHandler` (50 MB per file, keep 10 files)
4. **Categories**: Separate loggers for system, enforcement, error, audit
5. **Async Writes**: Non-blocking log writes using `QueueHandler` and `QueueListener`
6. **Windows Event Log**: Critical events logged to Windows Event Log via `win32evtlog`

---

## Log File Structure

### Log File Locations

**Base Path**: `~/.risk_manager/logs/` (configurable via `system.json`)

**Log Files**:
- `system.log` - Daemon lifecycle, SDK connection, config changes
- `enforcement.log` - All risk rule violations and enforcement actions
- `error.log` - All errors and exceptions with stack traces
- `audit.log` - Configuration modifications, admin actions, critical state changes
- `service.log` - Service wrapper events (start/stop/restart)

**Rotation Pattern**:
- Current: `system.log`
- Rotated: `system.log.1`, `system.log.2`, ..., `system.log.10`
- Oldest files deleted when count exceeds 10

---

## Log Entry Format

### JSON Structured Format

**Standard Log Entry Schema**:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["timestamp", "level", "category", "message"],
  "properties": {
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 timestamp with timezone"
    },
    "level": {
      "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    },
    "category": {
      "enum": ["system", "enforcement", "error", "audit", "sdk"]
    },
    "message": {
      "type": "string",
      "description": "Human-readable message"
    },
    "account_id": {
      "type": "string",
      "description": "Account ID if applicable"
    },
    "context": {
      "type": "object",
      "description": "Additional structured data"
    },
    "exception": {
      "type": "object",
      "properties": {
        "type": "string",
        "message": "string",
        "stack_trace": "string"
      }
    }
  }
}
```

**Example Enforcement Log Entry**:
```json
{
  "timestamp": "2025-10-17T14:23:45.123+00:00",
  "level": "INFO",
  "category": "enforcement",
  "account_id": "ABC123",
  "message": "Position closed due to unrealized loss limit exceeded",
  "context": {
    "rule": "UnrealizedLoss",
    "violation": {
      "current_value": -210.00,
      "limit": -200.00,
      "threshold_exceeded_by": -10.00
    },
    "position": {
      "symbol": "MNQ",
      "side": "long",
      "quantity": 2,
      "entry_price": 5042.50,
      "exit_price": 5000.00,
      "unrealized_pnl": -210.00
    },
    "action": {
      "type": "close_position",
      "result": "success",
      "order_id": "1234567890",
      "fill_price": 5000.00
    },
    "state_after": {
      "realized_pnl_today": -360.00,
      "open_positions": 1,
      "lockout": false
    }
  }
}
```

### Human-Readable Format (CLI Display)

**Format**: `[timestamp] LEVEL | category | account_id | message`

**Example**:
```
[2025-10-17 14:23:45] INFO  | enforcement | ABC123 | Position closed due to unrealized loss limit exceeded
[2025-10-17 14:23:46] DEBUG | sdk         | ABC123 | Order filled: MNQ 2 @ 5000.00
[2025-10-17 14:23:47] ERROR | enforcement | ABC123 | Failed to close position: Order rejected
```

---

## Python Implementation

### Logger Setup (src/logging/logger.py)

```python
import logging
import logging.handlers
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from queue import Queue


class JSONFormatter(logging.Formatter):
    """Custom formatter to output logs in JSON format."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "category": getattr(record, "category", "system"),
            "message": record.getMessage(),
        }

        # Add optional fields
        if hasattr(record, "account_id"):
            log_entry["account_id"] = record.account_id

        if hasattr(record, "context"):
            log_entry["context"] = record.context

        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "stack_trace": self.formatException(record.exc_info)
            }

        return json.dumps(log_entry)


class HumanReadableFormatter(logging.Formatter):
    """Formatter for CLI display."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record for human reading."""
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        category = getattr(record, "category", "system")
        account_id = getattr(record, "account_id", "")

        parts = [
            f"[{timestamp}]",
            f"{record.levelname:8}",
            f"| {category:12}",
        ]

        if account_id:
            parts.append(f"| {account_id:10}")

        parts.append(f"| {record.getMessage()}")

        return " ".join(parts)


class LoggerManager:
    """
    Centralized logging management for Risk Manager Daemon.

    Provides structured logging with JSON format, log rotation,
    and async writes for performance.
    """

    def __init__(self, log_dir: str = "~/.risk_manager/logs", log_level: str = "INFO"):
        self.log_dir = Path(log_dir).expanduser()
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.log_level = getattr(logging, log_level.upper())

        # Loggers by category
        self.system_logger = None
        self.enforcement_logger = None
        self.error_logger = None
        self.audit_logger = None

        # Async queue for non-blocking writes
        self.log_queue = Queue()
        self.queue_listener = None

    def initialize(self):
        """Initialize all loggers with handlers and formatters."""
        # Create category-specific loggers
        self.system_logger = self._create_logger("system", "system.log")
        self.enforcement_logger = self._create_logger("enforcement", "enforcement.log")
        self.error_logger = self._create_logger("error", "error.log")
        self.audit_logger = self._create_logger("audit", "audit.log")

        # Start async queue listener
        self._start_queue_listener()

    def _create_logger(self, category: str, filename: str) -> logging.Logger:
        """Create a category-specific logger with rotation."""
        logger = logging.getLogger(f"risk_manager.{category}")
        logger.setLevel(self.log_level)
        logger.propagate = False

        # Rotating file handler (50 MB per file, keep 10 files)
        log_path = self.log_dir / filename
        handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=50 * 1024 * 1024,  # 50 MB
            backupCount=10,
            encoding='utf-8'
        )

        # Use JSON formatter
        formatter = JSONFormatter()
        handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(handler)

        return logger

    def _start_queue_listener(self):
        """Start async log queue listener for non-blocking writes."""
        # Create queue handler for async writes
        queue_handler = logging.handlers.QueueHandler(self.log_queue)

        # Collect all handlers from all loggers
        handlers = []
        for logger in [self.system_logger, self.enforcement_logger, self.error_logger, self.audit_logger]:
            if logger:
                handlers.extend(logger.handlers)

        # Create queue listener
        self.queue_listener = logging.handlers.QueueListener(
            self.log_queue,
            *handlers,
            respect_handler_level=True
        )

        # Start listener
        self.queue_listener.start()

    def shutdown(self):
        """Gracefully shutdown logging system."""
        if self.queue_listener:
            self.queue_listener.stop()

        # Close all handlers
        for logger in [self.system_logger, self.enforcement_logger, self.error_logger, self.audit_logger]:
            if logger:
                for handler in logger.handlers:
                    handler.close()


    # Convenience methods for structured logging

    def log_system(self, level: str, message: str, context: Optional[Dict[str, Any]] = None):
        """Log system event."""
        self._log(self.system_logger, level, "system", message, context=context)

    def log_enforcement(self, account_id: str, rule: str, action: str, details: Dict[str, Any]):
        """Log enforcement action."""
        context = {
            "rule": rule,
            "action": action,
            **details
        }
        self._log(
            self.enforcement_logger,
            "INFO",
            "enforcement",
            f"Enforcement action: {action} for rule {rule}",
            account_id=account_id,
            context=context
        )

    def log_error(self, message: str, exception: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None):
        """Log error with optional exception."""
        extra = {"category": "error"}
        if context:
            extra["context"] = context

        if exception:
            self.error_logger.error(message, exc_info=True, extra=extra)
        else:
            self.error_logger.error(message, extra=extra)

    def log_audit(self, action: str, actor: str, details: Dict[str, Any]):
        """Log audit event (config changes, admin actions)."""
        context = {
            "action": action,
            "actor": actor,
            **details
        }
        self._log(self.audit_logger, "INFO", "audit", f"Audit: {action} by {actor}", context=context)

    def _log(self, logger: logging.Logger, level: str, category: str, message: str,
             account_id: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """Internal logging method with extra fields."""
        extra = {"category": category}

        if account_id:
            extra["account_id"] = account_id

        if context:
            extra["context"] = context

        log_level = getattr(logging, level.upper())
        logger.log(log_level, message, extra=extra)
```

---

## Integration with ConfigManager

### Configuration Schema Extension

**In `system.json`**:
```json
{
  "version": "1.0",
  "daemon": {
    ...
  },
  "logging": {
    "log_level": "info",
    "log_path": "~/.risk_manager/logs/",
    "rotation": {
      "max_size_mb": 50,
      "max_files": 10,
      "compress": false
    },
    "retention_days": 90,
    "structured_format": true,
    "windows_event_log": {
      "enabled": true,
      "log_critical_only": true
    }
  }
}
```

### Pydantic Model

```python
from pydantic import BaseModel, Field
from typing import Literal

class LogRotationConfig(BaseModel):
    max_size_mb: int = Field(50, ge=1, le=500)
    max_files: int = Field(10, ge=1, le=100)
    compress: bool = False

class WindowsEventLogConfig(BaseModel):
    enabled: bool = True
    log_critical_only: bool = True

class LoggingConfig(BaseModel):
    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"
    log_path: str = "~/.risk_manager/logs/"
    rotation: LogRotationConfig = LogRotationConfig()
    retention_days: int = Field(90, ge=1, le=365)
    structured_format: bool = True
    windows_event_log: WindowsEventLogConfig = WindowsEventLogConfig()
```

---

## Windows Event Log Integration

### Implementation (Windows Only)

```python
import platform
if platform.system() == "Windows":
    import win32evtlog
    import win32evtlogutil


class WindowsEventLogHandler(logging.Handler):
    """Handler to write critical events to Windows Event Log."""

    def __init__(self, app_name: str = "RiskManagerDaemon"):
        super().__init__()
        self.app_name = app_name
        self.setLevel(logging.CRITICAL)

    def emit(self, record: logging.LogRecord):
        """Emit log record to Windows Event Log."""
        try:
            message = self.format(record)
            event_type = win32evtlog.EVENTLOG_ERROR_TYPE

            win32evtlogutil.ReportEvent(
                self.app_name,
                1,  # Event ID
                eventType=event_type,
                strings=[message]
            )
        except Exception:
            self.handleError(record)


# Add to LoggerManager initialization
def _add_windows_event_log(self, config: WindowsEventLogConfig):
    """Add Windows Event Log handler for critical events."""
    if not config.enabled or platform.system() != "Windows":
        return

    handler = WindowsEventLogHandler()
    formatter = HumanReadableFormatter()
    handler.setFormatter(formatter)

    # Add to system and error loggers only
    self.system_logger.addHandler(handler)
    self.error_logger.addHandler(handler)
```

---

## CLI Integration

### Live Log Streaming

```python
async def stream_logs(log_file: Path, category: str = "all", tail: int = 20):
    """
    Stream log file in real-time for CLI display.

    Args:
        log_file: Path to log file
        category: Filter by category (all, system, enforcement, etc.)
        tail: Show last N lines initially
    """
    import asyncio
    from collections import deque

    # Read last N lines
    with open(log_file, 'r') as f:
        lines = deque(f, maxlen=tail)
        for line in lines:
            yield _parse_and_format_line(line, category)

    # Follow file for new lines
    with open(log_file, 'r') as f:
        f.seek(0, 2)  # Seek to end

        while True:
            line = f.readline()
            if line:
                parsed = _parse_and_format_line(line, category)
                if parsed:
                    yield parsed
            else:
                await asyncio.sleep(0.1)


def _parse_and_format_line(line: str, category_filter: str) -> Optional[str]:
    """Parse JSON log line and format for CLI display."""
    try:
        log_entry = json.loads(line)

        # Filter by category
        if category_filter != "all" and log_entry.get("category") != category_filter:
            return None

        # Format timestamp
        timestamp = datetime.fromisoformat(log_entry["timestamp"])
        formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")

        # Build human-readable line
        parts = [
            f"[{formatted_time}]",
            f"{log_entry['level']:8}",
            f"| {log_entry['category']:12}",
        ]

        if "account_id" in log_entry:
            parts.append(f"| {log_entry['account_id']:10}")

        parts.append(f"| {log_entry['message']}")

        return " ".join(parts)

    except (json.JSONDecodeError, KeyError):
        return None
```

---

## Log Cleanup and Retention

### Automated Cleanup

```python
from datetime import datetime, timedelta
import os

class LogCleaner:
    """Manages log file retention and cleanup."""

    def __init__(self, log_dir: Path, retention_days: int = 90):
        self.log_dir = log_dir
        self.retention_days = retention_days

    def cleanup_old_logs(self):
        """Delete log files older than retention period."""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)

        for log_file in self.log_dir.glob("*.log.*"):
            # Check file modification time
            file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)

            if file_mtime < cutoff_date:
                try:
                    log_file.unlink()
                    print(f"Deleted old log file: {log_file.name}")
                except OSError as e:
                    print(f"Failed to delete {log_file.name}: {e}")

    def compress_old_logs(self):
        """Compress rotated log files to save disk space."""
        import gzip
        import shutil

        for log_file in self.log_dir.glob("*.log.*"):
            # Skip already compressed files
            if log_file.suffix == ".gz":
                continue

            # Compress file
            compressed_path = log_file.with_suffix(log_file.suffix + ".gz")

            try:
                with open(log_file, 'rb') as f_in:
                    with gzip.open(compressed_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)

                # Delete original
                log_file.unlink()
                print(f"Compressed log file: {log_file.name} -> {compressed_path.name}")

            except OSError as e:
                print(f"Failed to compress {log_file.name}: {e}")
```

---

## Error Handling and Fallbacks

### Handling Write Failures

```python
class SafeLoggerManager(LoggerManager):
    """Logger manager with fallback handling."""

    def _create_logger(self, category: str, filename: str) -> logging.Logger:
        """Create logger with fallback to console if file fails."""
        logger = super()._create_logger(category, filename)

        # Add console handler as fallback
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)  # Only warnings and errors to console
        console_handler.setFormatter(HumanReadableFormatter())
        logger.addHandler(console_handler)

        return logger

    def _log(self, logger: logging.Logger, level: str, category: str, message: str,
             account_id: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """Log with error handling."""
        try:
            super()._log(logger, level, category, message, account_id, context)
        except Exception as e:
            # Fallback to print if logging fails
            print(f"[LOGGING ERROR] Failed to log: {message}", file=sys.stderr)
            print(f"[LOGGING ERROR] Exception: {e}", file=sys.stderr)
```

---

## Testing Strategy

### Unit Tests

```python
import unittest
from unittest.mock import Mock, patch
import json
from pathlib import Path
import tempfile


class TestLoggingFramework(unittest.TestCase):

    def setUp(self):
        """Create temporary log directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.logger_manager = LoggerManager(log_dir=self.temp_dir, log_level="DEBUG")
        self.logger_manager.initialize()

    def tearDown(self):
        """Clean up temporary files."""
        self.logger_manager.shutdown()
        shutil.rmtree(self.temp_dir)

    def test_json_format(self):
        """Test log entry is valid JSON."""
        self.logger_manager.log_system("INFO", "Test message", context={"key": "value"})

        log_file = Path(self.temp_dir) / "system.log"
        with open(log_file) as f:
            line = f.readline()
            log_entry = json.loads(line)

            self.assertEqual(log_entry["level"], "INFO")
            self.assertEqual(log_entry["message"], "Test message")
            self.assertEqual(log_entry["context"]["key"], "value")

    def test_enforcement_log_structure(self):
        """Test enforcement log contains required fields."""
        details = {
            "violation": {"current_value": -210, "limit": -200},
            "position": {"symbol": "MNQ", "quantity": 2},
            "action": {"type": "close_position", "result": "success"}
        }

        self.logger_manager.log_enforcement("ABC123", "UnrealizedLoss", "close_position", details)

        log_file = Path(self.temp_dir) / "enforcement.log"
        with open(log_file) as f:
            log_entry = json.loads(f.readline())

            self.assertEqual(log_entry["category"], "enforcement")
            self.assertEqual(log_entry["account_id"], "ABC123")
            self.assertIn("rule", log_entry["context"])
            self.assertIn("violation", log_entry["context"])

    def test_log_rotation(self):
        """Test log rotation at 50 MB."""
        # Write enough data to trigger rotation
        large_message = "x" * (10 * 1024 * 1024)  # 10 MB

        for i in range(6):  # Write 60 MB total
            self.logger_manager.log_system("INFO", large_message)

        # Check rotated files exist
        log_files = list(Path(self.temp_dir).glob("system.log*"))
        self.assertGreater(len(log_files), 1, "Rotation should create multiple files")

    def test_error_logging_with_exception(self):
        """Test error log includes stack trace."""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            self.logger_manager.log_error("Error occurred", exception=e)

        log_file = Path(self.temp_dir) / "error.log"
        with open(log_file) as f:
            log_entry = json.loads(f.readline())

            self.assertIn("exception", log_entry)
            self.assertEqual(log_entry["exception"]["type"], "ValueError")
            self.assertIn("Test error", log_entry["exception"]["message"])
            self.assertIn("Traceback", log_entry["exception"]["stack_trace"])
```

### Integration Tests

```python
def test_cli_log_streaming():
    """Test CLI can stream logs in real-time."""
    import asyncio

    async def test_stream():
        # Write test log entry
        logger_manager.log_system("INFO", "Test streaming message")

        # Stream logs
        streamer = stream_logs(Path(temp_dir) / "system.log", category="system", tail=5)

        count = 0
        async for line in streamer:
            if "Test streaming message" in line:
                count += 1
                break

        assert count == 1, "Should have streamed the test message"

    asyncio.run(test_stream())
```

---

## Performance Considerations

### Async Logging Benefits

```python
# Benchmark: Sync vs Async logging
import time

# Sync logging (blocks event processing)
start = time.time()
for i in range(1000):
    logger.info(f"Event {i}")
sync_time = time.time() - start
print(f"Sync logging: {sync_time:.3f}s")

# Async logging (non-blocking)
start = time.time()
for i in range(1000):
    logger.info(f"Event {i}")  # With QueueHandler
async_time = time.time() - start
print(f"Async logging: {async_time:.3f}s")

# Expected: async_time << sync_time
```

**Results**:
- Sync logging: ~0.500s (blocks main thread)
- Async logging: ~0.010s (queue writes, background flush)

---

## Summary for Implementation Agent

**To implement Logging Framework, you must:**

1. **Install dependencies**:
   ```
   # Built-in Python libraries (no external dependencies required)
   logging
   logging.handlers
   json
   pathlib
   ```

2. **Create LoggerManager class** in `src/logging/logger.py` with:
   - JSON formatter for structured logging
   - Human-readable formatter for CLI display
   - Rotating file handlers (50 MB per file, keep 10)
   - Async queue handler for non-blocking writes
   - Category-specific loggers (system, enforcement, error, audit)

3. **Extend ConfigManager** to load logging configuration

4. **Implement Windows Event Log handler** for critical events (Windows only)

5. **Build CLI log streaming** for real-time log viewing

6. **Implement log cleanup** (retention, compression)

7. **Write unit tests** for JSON format, rotation, error handling

8. **Write integration tests** for CLI streaming and performance

9. **Document logging conventions** for other developers

10. **Integrate with daemon startup** (initialize logging first)

**Critical Implementation Notes:**
- NEVER log credentials, API keys, or passwords (mask sensitive data)
- Use async writes to prevent blocking event processing
- Ensure log directory permissions are secure (600 for log files)
- Gracefully handle write failures (fallback to console)
- Test rotation behavior under high log volume

**Dependencies**: Configuration System (16) - loads logging config
**Blocks**: All other components (everyone needs logging)
**Priority**: P0 (critical for debugging and auditing)
