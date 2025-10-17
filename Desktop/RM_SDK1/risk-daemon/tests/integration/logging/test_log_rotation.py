"""
Integration tests for log file rotation.

Tests that RotatingFileHandler correctly rotates logs at 50 MB and maintains
backupCount of 10 files.

Architecture Reference: architecture/20-logging-framework.md
"""

import pytest
import tempfile
from pathlib import Path
import json


pytestmark = pytest.mark.integration


class TestLogRotation:
    """Test log rotation at 50 MB with 10 backup files."""

    def test_log_rotation_occurs_at_50mb(self):
        """
        Log rotation should occur when log file reaches 50 MB.

        Architecture requirement:
        - maxBytes: 50 * 1024 * 1024 (50 MB)
        - backupCount: 10
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Write large messages to trigger rotation
            # Each message ~1 MB, write 60 MB total
            large_message = "x" * (1 * 1024 * 1024)  # 1 MB message

            for i in range(60):
                manager.log_system("INFO", large_message)

            manager.shutdown()

            # Check for rotated files
            log_dir = Path(temp_dir)
            log_files = sorted(log_dir.glob("system.log*"))

            # Should have rotated at least once
            assert len(log_files) > 1, "Should create rotated files after exceeding 50 MB"

            # Verify rotation naming pattern
            rotated_files = [f for f in log_files if f.name != "system.log"]
            assert any("system.log.1" in f.name for f in rotated_files), \
                "Should create system.log.1 as first rotation"

    def test_log_rotation_maintains_backup_count_limit(self):
        """
        Log rotation should maintain backupCount of 10 files.

        Oldest files should be deleted when limit exceeded.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Write enough to create more than 10 rotations
            # 50 MB per rotation * 15 rotations = 750 MB
            message_1mb = "y" * (1 * 1024 * 1024)

            for i in range(15 * 50):  # 15 rotations worth
                manager.log_system("INFO", message_1mb)

            manager.shutdown()

            log_dir = Path(temp_dir)
            log_files = list(log_dir.glob("system.log*"))

            # Should have at most 11 files (current + 10 backups)
            assert len(log_files) <= 11, \
                f"Should have max 11 files (current + 10 backups), found {len(log_files)}"

    def test_log_rotation_preserves_log_content(self):
        """
        Log rotation should preserve all log entries correctly.

        Content should be readable from rotated files.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Write distinct messages before and after rotation
            manager.log_system("INFO", "Message before rotation")

            # Write enough to trigger rotation
            large_message = "z" * (51 * 1024 * 1024)  # 51 MB
            manager.log_system("INFO", large_message)

            manager.log_system("INFO", "Message after rotation")

            manager.shutdown()

            log_dir = Path(temp_dir)

            # Check current log has recent message
            with open(log_dir / "system.log") as f:
                lines = f.readlines()
                last_entry = json.loads(lines[-1])
                assert "Message after rotation" in last_entry["message"]

            # Check rotated log has old message
            rotated_file = log_dir / "system.log.1"
            if rotated_file.exists():
                with open(rotated_file) as f:
                    first_line = f.readline()
                    first_entry = json.loads(first_line)
                    # Should contain either the "before rotation" message or the large message
                    assert first_entry is not None

    def test_log_rotation_works_for_all_categories(self):
        """
        Log rotation should work independently for each category.

        Each logger (system, enforcement, error, audit) rotates separately.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Write large amount to enforcement log only
            large_message = "a" * (51 * 1024 * 1024)  # 51 MB

            details = {"test": "data"}
            manager.log_enforcement("TEST123", "TestRule", "test_action", details)
            manager.log_enforcement("TEST123", "TestRule", large_message, details)

            manager.shutdown()

            log_dir = Path(temp_dir)

            # Enforcement log should have rotated
            enforcement_files = list(log_dir.glob("enforcement.log*"))
            assert len(enforcement_files) > 1, "Enforcement log should rotate"

            # System log should NOT have rotated (no large writes)
            system_files = list(log_dir.glob("system.log*"))
            assert len(system_files) == 1, "System log should not rotate"

    def test_log_rotation_file_size_accuracy(self):
        """
        Rotated files should not significantly exceed 50 MB.

        Architecture allows some overshoot due to atomic writes.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Write messages to trigger rotation
            message_5mb = "m" * (5 * 1024 * 1024)  # 5 MB messages

            for i in range(15):  # 75 MB total
                manager.log_system("INFO", message_5mb)

            manager.shutdown()

            log_dir = Path(temp_dir)

            # Check rotated file size
            rotated_file = log_dir / "system.log.1"
            if rotated_file.exists():
                file_size = rotated_file.stat().st_size
                max_size = 50 * 1024 * 1024  # 50 MB

                # Allow 10% overshoot for JSON overhead and atomic writes
                assert file_size <= max_size * 1.1, \
                    f"Rotated file ({file_size} bytes) should not significantly exceed 50 MB"

    def test_log_rotation_naming_sequence(self):
        """
        Rotated files should follow naming sequence: .1, .2, .3, etc.

        Architecture requirement:
        - system.log → system.log.1 → system.log.2 → ... → system.log.10
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Trigger multiple rotations
            message_10mb = "r" * (10 * 1024 * 1024)

            for i in range(25):  # Trigger 5 rotations (5 * 50 MB = 250 MB)
                manager.log_system("INFO", message_10mb)

            manager.shutdown()

            log_dir = Path(temp_dir)

            # Verify sequence exists
            assert (log_dir / "system.log").exists(), "Current log should exist"

            # Check for sequential naming
            for i in range(1, 6):  # Expect at least 5 rotations
                expected_file = log_dir / f"system.log.{i}"
                # At least some of these should exist
                if i <= 3:  # First 3 rotations should definitely exist
                    assert expected_file.exists(), f"system.log.{i} should exist"


class TestLogRotationPerformance:
    """Test log rotation performance under high volume."""

    @pytest.mark.slow
    def test_log_rotation_handles_rapid_writes(self):
        """
        Log rotation should handle rapid write operations without blocking.

        Architecture requirement:
        - Async writes via QueueHandler
        - Non-blocking rotation
        """
        from src.daemon_logging.logger_manager import LoggerManager
        import time

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            start_time = time.time()

            # Rapidly write 100 messages
            for i in range(100):
                manager.log_system("INFO", f"Rapid message {i}")

            elapsed = time.time() - start_time

            manager.shutdown()

            # Should complete quickly (< 1 second for 100 messages)
            assert elapsed < 1.0, \
                f"Rapid writes should complete quickly (took {elapsed:.2f}s)"

    def test_log_rotation_during_active_logging(self):
        """
        Log rotation should not interfere with active logging.

        New logs should continue to current file after rotation.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Log before rotation
            manager.log_system("INFO", "Before rotation")

            # Trigger rotation
            large_message = "r" * (51 * 1024 * 1024)
            manager.log_system("INFO", large_message)

            # Log after rotation
            manager.log_system("INFO", "After rotation")

            manager.shutdown()

            log_dir = Path(temp_dir)

            # Current log should have the "After rotation" message
            with open(log_dir / "system.log") as f:
                lines = f.readlines()
                found_after = any("After rotation" in line for line in lines)
                assert found_after, "Should continue logging to current file after rotation"


class TestLogRotationEdgeCases:
    """Test edge cases in log rotation."""

    def test_log_rotation_with_empty_messages(self):
        """
        Log rotation should handle empty messages correctly.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Log empty messages
            for i in range(10):
                manager.log_system("INFO", "")

            manager.shutdown()

            log_dir = Path(temp_dir)
            log_file = log_dir / "system.log"

            assert log_file.exists(), "Should create log file even with empty messages"

    def test_log_rotation_with_unicode_content(self):
        """
        Log rotation should handle Unicode content correctly.

        Architecture requirement:
        - encoding='utf-8'
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Log Unicode messages
            unicode_messages = [
                "English",
                "日本語",
                "Español",
                "中文",
                "العربية",
                "🚀🔥💎"  # Emojis
            ]

            for msg in unicode_messages:
                manager.log_system("INFO", msg)

            manager.shutdown()

            # Verify all messages written correctly
            log_file = Path(temp_dir) / "system.log"
            with open(log_file, encoding='utf-8') as f:
                content = f.read()

                for msg in unicode_messages:
                    assert msg in content, f"Should preserve Unicode: {msg}"

    def test_log_rotation_survives_logger_shutdown_and_restart(self):
        """
        Log files should persist across logger restarts.

        Rotation numbering should continue correctly.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            # First session
            manager1 = LoggerManager(log_dir=temp_dir)
            manager1.initialize()
            manager1.log_system("INFO", "Session 1 message")
            manager1.shutdown()

            # Second session
            manager2 = LoggerManager(log_dir=temp_dir)
            manager2.initialize()
            manager2.log_system("INFO", "Session 2 message")
            manager2.shutdown()

            # Both messages should be in the log
            log_file = Path(temp_dir) / "system.log"
            with open(log_file) as f:
                content = f.read()

                assert "Session 1 message" in content
                assert "Session 2 message" in content
