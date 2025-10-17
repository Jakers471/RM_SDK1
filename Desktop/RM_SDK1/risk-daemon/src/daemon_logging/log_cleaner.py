"""
Log file retention and compression utilities.

Provides automatic cleanup of old rotated log files and gzip compression
to save disk space.

Architecture Reference: architecture/20-logging-framework.md
"""

import gzip
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class LogCleaner:
    """
    Manages log file retention and compression.

    Features:
    - Delete rotated logs older than retention period
    - Gzip compression of rotated logs
    - Graceful error handling (missing dirs, permissions)
    """

    def __init__(self, log_dir: Path, retention_days: int = 90):
        """
        Initialize LogCleaner.

        Args:
            log_dir: Directory containing log files
            retention_days: Days to keep log files (1-365)
        """
        self.log_dir = Path(log_dir) if not isinstance(log_dir, Path) else log_dir
        self.retention_days = retention_days

    def cleanup_old_logs(self) -> None:
        """
        Delete rotated log files older than retention period.

        Only deletes files matching pattern: *.log.* (e.g., system.log.1, system.log.2)
        Never deletes current .log files (e.g., system.log)

        Handles missing directories and permission errors gracefully.
        """
        # Check if log directory exists
        if not self.log_dir.exists():
            return  # Gracefully handle missing directory

        # Calculate cutoff time (retention_days ago)
        cutoff_time = time.time() - (self.retention_days * 24 * 60 * 60)

        # Find rotated log files (*.log.*)
        try:
            rotated_logs = []
            for pattern in ["*.log.*"]:
                rotated_logs.extend(self.log_dir.glob(pattern))

            # Filter to exclude already compressed files
            rotated_logs = [f for f in rotated_logs if not f.name.endswith(".gz")]

            # Delete files older than cutoff
            for log_file in rotated_logs:
                try:
                    # Check modification time
                    if log_file.stat().st_mtime < cutoff_time:
                        log_file.unlink()
                        logger.debug(f"Deleted old log file: {log_file}")
                except PermissionError:
                    # Gracefully handle permission errors
                    logger.warning(f"Permission denied deleting {log_file}")
                except Exception as e:
                    logger.error(f"Error deleting {log_file}: {e}")

        except Exception as e:
            logger.error(f"Error during log cleanup: {e}")

    def compress_old_logs(self) -> None:
        """
        Compress rotated log files using gzip.

        Compresses files matching pattern: *.log.* (e.g., system.log.1)
        Skips already compressed files (*.gz)
        Never compresses current .log files

        Creates: *.log.*.gz files
        Deletes original after successful compression
        """
        # Check if log directory exists
        if not self.log_dir.exists():
            return

        # Find rotated log files (*.log.* but not *.gz)
        try:
            rotated_logs = []
            for log_file in self.log_dir.glob("*.log.*"):
                # Skip already compressed files
                if not log_file.name.endswith(".gz"):
                    rotated_logs.append(log_file)

            # Compress each file
            for log_file in rotated_logs:
                try:
                    self._compress_file(log_file)
                except Exception as e:
                    # Gracefully handle compression errors
                    logger.error(f"Error compressing {log_file}: {e}")
                    # Original file preserved on error

        except Exception as e:
            logger.error(f"Error during log compression: {e}")

    def _compress_file(self, log_file: Path) -> None:
        """
        Compress a single log file with gzip.

        Args:
            log_file: Path to log file to compress

        Raises:
            Exception: If compression fails (original file preserved)
        """
        compressed_file = Path(str(log_file) + ".gz")

        # Read original file
        with open(log_file, "rb") as f_in:
            content = f_in.read()

        # Write compressed file
        with gzip.open(compressed_file, "wb") as f_out:
            f_out.write(content)

        # Verify compressed file was created successfully
        if compressed_file.exists() and compressed_file.stat().st_size > 0:
            # Delete original after successful compression
            log_file.unlink()
            logger.debug(f"Compressed log file: {log_file} -> {compressed_file}")
        else:
            # Clean up failed compression
            if compressed_file.exists():
                compressed_file.unlink()
            raise IOError(f"Failed to create compressed file: {compressed_file}")
