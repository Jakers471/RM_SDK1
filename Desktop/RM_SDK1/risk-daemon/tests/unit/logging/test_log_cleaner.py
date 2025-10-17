"""
Unit tests for LogCleaner class.

Tests log file retention and compression functionality.

Architecture Reference: architecture/20-logging-framework.md
"""

import pytest
import tempfile
import time
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch


pytestmark = pytest.mark.unit


class TestLogCleanerRetention:
    """Test log file retention and deletion."""

    def test_log_cleaner_deletes_files_older_than_retention(self):
        """
        LogCleaner should delete log files older than retention_days.

        Architecture requirement:
        - retention_days: 90 (default)
        - Delete files with mtime older than cutoff
        """
        from src.daemon_logging.log_cleaner import LogCleaner

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)

            # Create old log file (100 days old)
            old_log = log_dir / "system.log.5"
            old_log.write_text("old log content")

            # Set modification time to 100 days ago
            old_time = time.time() - (100 * 24 * 60 * 60)
            old_log.touch()
            import os
            os.utime(old_log, (old_time, old_time))

            # Create recent log file (30 days old)
            recent_log = log_dir / "system.log.1"
            recent_log.write_text("recent log content")

            cleaner = LogCleaner(log_dir=log_dir, retention_days=90)
            cleaner.cleanup_old_logs()

            assert not old_log.exists(), "Should delete file older than 90 days"
            assert recent_log.exists(), "Should keep file younger than 90 days"

    def test_log_cleaner_keeps_current_log_files(self):
        """
        LogCleaner should never delete current .log files (without number suffix).
        """
        from src.daemon_logging.log_cleaner import LogCleaner

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)

            # Create current log file
            current_log = log_dir / "system.log"
            current_log.write_text("current log")

            # Set to old mtime
            old_time = time.time() - (100 * 24 * 60 * 60)
            import os
            os.utime(current_log, (old_time, old_time))

            cleaner = LogCleaner(log_dir=log_dir, retention_days=90)
            cleaner.cleanup_old_logs()

            # Current log should NOT be deleted (pattern is *.log.*, not *.log)
            assert current_log.exists(), "Should keep current .log files"

    def test_log_cleaner_retention_days_configurable(self):
        """
        LogCleaner retention period should be configurable.

        Architecture requirement:
        - retention_days: int = Field(90, ge=1, le=365)
        """
        from src.daemon_logging.log_cleaner import LogCleaner

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)

            # Create log file 60 days old
            log_file = log_dir / "system.log.3"
            log_file.write_text("test")

            sixty_days_ago = time.time() - (60 * 24 * 60 * 60)
            import os
            os.utime(log_file, (sixty_days_ago, sixty_days_ago))

            # With 30-day retention: should delete
            cleaner_30 = LogCleaner(log_dir=log_dir, retention_days=30)
            cleaner_30.cleanup_old_logs()

            assert not log_file.exists(), "Should delete with 30-day retention"

            # Recreate for 90-day test
            log_file.write_text("test")
            os.utime(log_file, (sixty_days_ago, sixty_days_ago))

            # With 90-day retention: should keep
            cleaner_90 = LogCleaner(log_dir=log_dir, retention_days=90)
            cleaner_90.cleanup_old_logs()

            assert log_file.exists(), "Should keep with 90-day retention"

    def test_log_cleaner_handles_missing_log_directory(self):
        """
        LogCleaner should handle non-existent log directory gracefully.
        """
        from src.daemon_logging.log_cleaner import LogCleaner

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "nonexistent"

            cleaner = LogCleaner(log_dir=log_dir, retention_days=90)

            # Should not raise exception
            try:
                cleaner.cleanup_old_logs()
            except FileNotFoundError:
                pytest.fail("Should handle missing directory gracefully")

    def test_log_cleaner_handles_permission_errors(self):
        """
        LogCleaner should handle files it cannot delete (permission errors).

        Should log error but continue with other files.
        """
        from src.daemon_logging.log_cleaner import LogCleaner

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)

            # Create old log file
            old_log = log_dir / "system.log.5"
            old_log.write_text("test")

            old_time = time.time() - (100 * 24 * 60 * 60)
            import os
            os.utime(old_log, (old_time, old_time))

            # Mock unlink to raise PermissionError
            with patch.object(Path, 'unlink', side_effect=PermissionError("Access denied")):
                cleaner = LogCleaner(log_dir=log_dir, retention_days=90)

                # Should not raise exception
                try:
                    cleaner.cleanup_old_logs()
                except PermissionError:
                    pytest.fail("Should handle permission errors gracefully")


class TestLogCleanerCompression:
    """Test log file compression."""

    def test_log_cleaner_compresses_rotated_logs(self):
        """
        LogCleaner should compress rotated log files (*.log.*).

        Architecture requirement:
        - Use gzip compression
        - Delete original after successful compression
        """
        from src.daemon_logging.log_cleaner import LogCleaner

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)

            # Create rotated log file
            log_file = log_dir / "system.log.1"
            log_file.write_text("A" * 1000)  # 1000 bytes of 'A'

            cleaner = LogCleaner(log_dir=log_dir, retention_days=90)
            cleaner.compress_old_logs()

            # Original should be deleted
            assert not log_file.exists(), "Should delete original after compression"

            # Compressed file should exist
            compressed_file = log_dir / "system.log.1.gz"
            assert compressed_file.exists(), "Should create .gz compressed file"

    def test_log_cleaner_compressed_file_is_smaller(self):
        """
        Compressed log file should be smaller than original.
        """
        from src.daemon_logging.log_cleaner import LogCleaner
        import gzip

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)

            # Create log with repetitive content (compresses well)
            log_file = log_dir / "system.log.2"
            content = "This is a repeated log line.\n" * 1000
            log_file.write_text(content)

            original_size = log_file.stat().st_size

            cleaner = LogCleaner(log_dir=log_dir, retention_days=90)
            cleaner.compress_old_logs()

            compressed_file = log_dir / "system.log.2.gz"
            compressed_size = compressed_file.stat().st_size

            assert compressed_size < original_size, "Compressed file should be smaller"

            # Verify content integrity
            with gzip.open(compressed_file, 'rt') as f:
                decompressed_content = f.read()

            assert decompressed_content == content, "Decompressed content should match original"

    def test_log_cleaner_skips_already_compressed_files(self):
        """
        LogCleaner should skip files already compressed (*.gz).
        """
        from src.daemon_logging.log_cleaner import LogCleaner
        import gzip

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)

            # Create already compressed file
            compressed_file = log_dir / "system.log.3.gz"
            with gzip.open(compressed_file, 'wt') as f:
                f.write("already compressed")

            original_mtime = compressed_file.stat().st_mtime

            # Wait a moment to ensure mtime would change if file was modified
            time.sleep(0.1)

            cleaner = LogCleaner(log_dir=log_dir, retention_days=90)
            cleaner.compress_old_logs()

            # File should be unchanged
            assert compressed_file.exists()
            assert compressed_file.stat().st_mtime == original_mtime, \
                "Should not re-compress .gz files"

    def test_log_cleaner_compression_preserves_file_content(self):
        """
        Compression should preserve exact file content.
        """
        from src.daemon_logging.log_cleaner import LogCleaner
        import gzip

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)

            # Create log with specific content
            log_file = log_dir / "enforcement.log.1"
            original_content = "Line 1\nLine 2\nLine 3\n"
            log_file.write_text(original_content)

            cleaner = LogCleaner(log_dir=log_dir, retention_days=90)
            cleaner.compress_old_logs()

            # Decompress and verify
            compressed_file = log_dir / "enforcement.log.1.gz"
            with gzip.open(compressed_file, 'rt') as f:
                decompressed = f.read()

            assert decompressed == original_content, "Content must be preserved exactly"

    def test_log_cleaner_handles_compression_errors(self):
        """
        LogCleaner should handle compression errors gracefully.

        If compression fails, original file should be preserved.
        """
        from src.daemon_logging.log_cleaner import LogCleaner

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)

            log_file = log_dir / "system.log.4"
            log_file.write_text("test content")

            # Mock gzip.open to raise an error
            with patch('gzip.open', side_effect=OSError("Disk full")):
                cleaner = LogCleaner(log_dir=log_dir, retention_days=90)

                # Should not raise exception
                try:
                    cleaner.compress_old_logs()
                except OSError:
                    pytest.fail("Should handle compression errors gracefully")

                # Original file should still exist
                assert log_file.exists(), "Should preserve original on compression failure"

    def test_log_cleaner_compression_only_targets_rotated_files(self):
        """
        Compression should only target *.log.* files, not *.log.
        """
        from src.daemon_logging.log_cleaner import LogCleaner

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)

            # Create current log file
            current_log = log_dir / "system.log"
            current_log.write_text("current log")

            # Create rotated log file
            rotated_log = log_dir / "system.log.1"
            rotated_log.write_text("rotated log")

            cleaner = LogCleaner(log_dir=log_dir, retention_days=90)
            cleaner.compress_old_logs()

            # Current log should NOT be compressed
            assert current_log.exists()
            assert not (log_dir / "system.log.gz").exists()

            # Rotated log should be compressed
            assert not rotated_log.exists()
            assert (log_dir / "system.log.1.gz").exists()


class TestLogCleanerIntegration:
    """Test LogCleaner with both retention and compression."""

    def test_log_cleaner_cleanup_then_compress_workflow(self):
        """
        Typical workflow: cleanup old logs, then compress remaining.

        Architecture requirement:
        - Delete logs older than retention period
        - Compress remaining rotated logs
        """
        from src.daemon_logging.log_cleaner import LogCleaner

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)

            # Create very old log (should be deleted)
            very_old = log_dir / "system.log.5"
            very_old.write_text("very old")
            very_old_time = time.time() - (100 * 24 * 60 * 60)
            import os
            os.utime(very_old, (very_old_time, very_old_time))

            # Create old log (should be compressed)
            old_log = log_dir / "system.log.2"
            old_log.write_text("old but kept")
            old_time = time.time() - (30 * 24 * 60 * 60)
            os.utime(old_log, (old_time, old_time))

            # Create recent log (should be kept as-is)
            recent = log_dir / "system.log.1"
            recent.write_text("recent")

            cleaner = LogCleaner(log_dir=log_dir, retention_days=90)

            # Step 1: Cleanup
            cleaner.cleanup_old_logs()

            assert not very_old.exists(), "Very old file should be deleted"
            assert old_log.exists(), "Old file should still exist"
            assert recent.exists(), "Recent file should exist"

            # Step 2: Compress
            cleaner.compress_old_logs()

            # Both remaining logs should be compressed
            assert (log_dir / "system.log.2.gz").exists()
            assert (log_dir / "system.log.1.gz").exists()
