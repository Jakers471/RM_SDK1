"""
Integration tests for CLI log streaming functionality.

Tests the stream_logs() async function for real-time log viewing.

Architecture Reference: architecture/20-logging-framework.md
"""

import pytest
import tempfile
import json
import asyncio
from pathlib import Path


pytestmark = pytest.mark.integration


class TestLogStreaming:
    """Test CLI log streaming functionality."""

    @pytest.mark.asyncio
    async def test_stream_logs_reads_existing_log_entries(self):
        """
        stream_logs() should read existing log entries on start.

        Architecture requirement:
        - Read last N lines initially (tail parameter)
        """
        from src.daemon_logging.log_streaming import stream_logs
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create log entries
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            for i in range(10):
                manager.log_system("INFO", f"Existing message {i}")

            manager.shutdown()

            # Stream with tail=5
            log_file = Path(temp_dir) / "system.log"
            stream = stream_logs(log_file, category="all", tail=5)

            # Read initial messages
            messages = []
            count = 0
            async for line in stream:
                if line:
                    messages.append(line)
                    count += 1
                if count >= 5:
                    break

            # Should have read last 5 messages
            assert len(messages) == 5
            assert "Existing message 5" in messages[0] or "Existing message 6" in messages[0]

    @pytest.mark.asyncio
    async def test_stream_logs_follows_new_entries(self):
        """
        stream_logs() should follow file and stream new entries in real-time.

        Architecture requirement:
        - Follow file for new lines (like tail -f)
        """
        from src.daemon_logging.log_streaming import stream_logs
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Initial log entry
            manager.log_system("INFO", "Initial message")

            log_file = Path(temp_dir) / "system.log"
            stream = stream_logs(log_file, category="all", tail=1)

            # Read initial entry
            streamed_messages = []
            first_msg = await anext(stream)
            if first_msg:
                streamed_messages.append(first_msg)

            # Write new message while streaming
            await asyncio.sleep(0.1)
            manager.log_system("INFO", "New streaming message")
            manager.shutdown()

            # Should receive new message
            await asyncio.sleep(0.2)  # Give time for file write
            second_msg = await anext(stream)
            if second_msg:
                streamed_messages.append(second_msg)

            assert any("New streaming message" in msg for msg in streamed_messages), \
                f"Should stream new message, got: {streamed_messages}"

    @pytest.mark.asyncio
    async def test_stream_logs_filters_by_category(self):
        """
        stream_logs() should filter log entries by category.

        Architecture requirement:
        - category parameter: "all", "system", "enforcement", etc.
        """
        from src.daemon_logging.log_streaming import stream_logs
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Write mixed categories to system.log (for testing filter logic)
            # Note: In production, categories go to separate files
            manager.log_system("INFO", "System message 1")
            manager.log_system("INFO", "System message 2")
            manager.log_system("INFO", "System message 3")

            manager.shutdown()

            # Stream with category filter
            log_file = Path(temp_dir) / "system.log"
            stream = stream_logs(log_file, category="system", tail=5)

            messages = []
            count = 0
            async for line in stream:
                if line:
                    messages.append(line)
                    count += 1
                if count >= 3:
                    break

            # All messages should be system category
            assert all("system" in msg.lower() for msg in messages)

    @pytest.mark.asyncio
    async def test_stream_logs_parses_json_to_human_readable(self):
        """
        stream_logs() should parse JSON and format for human reading.

        Architecture requirement:
        - Parse JSON log entry
        - Format as: [timestamp] LEVEL | category | message
        """
        from src.daemon_logging.log_streaming import stream_logs
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            manager.log_system("INFO", "Test streaming message")

            manager.shutdown()

            log_file = Path(temp_dir) / "system.log"
            stream = stream_logs(log_file, category="all", tail=1)

            # Read formatted message
            formatted_msg = await anext(stream)

            # Verify human-readable format
            assert formatted_msg is not None
            assert "[" in formatted_msg  # Timestamp bracket
            assert "INFO" in formatted_msg
            assert "Test streaming message" in formatted_msg

    @pytest.mark.asyncio
    async def test_stream_logs_handles_invalid_json_lines(self):
        """
        stream_logs() should skip/ignore invalid JSON lines gracefully.
        """
        from src.daemon_logging.log_streaming import stream_logs

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"

            # Write mix of valid JSON and invalid lines
            with open(log_file, 'w') as f:
                f.write('{"timestamp": "2025-10-17T10:00:00Z", "level": "INFO", "category": "system", "message": "Valid 1"}\n')
                f.write('Invalid JSON line\n')
                f.write('{"timestamp": "2025-10-17T10:00:01Z", "level": "INFO", "category": "system", "message": "Valid 2"}\n')

            stream = stream_logs(log_file, category="all", tail=5)

            messages = []
            count = 0
            async for line in stream:
                if line:
                    messages.append(line)
                    count += 1
                if count >= 2:
                    break

            # Should have skipped invalid line, got 2 valid messages
            assert len(messages) == 2
            assert "Valid 1" in messages[0]
            assert "Valid 2" in messages[1]

    @pytest.mark.asyncio
    async def test_stream_logs_includes_account_id_when_present(self):
        """
        stream_logs() should include account_id in formatted output when present.

        Format: [timestamp] LEVEL | category | account_id | message
        """
        from src.daemon_logging.log_streaming import stream_logs
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            details = {"test": "data"}
            manager.log_enforcement("ABC123", "TestRule", "test_action", details)

            manager.shutdown()

            log_file = Path(temp_dir) / "enforcement.log"
            stream = stream_logs(log_file, category="all", tail=1)

            formatted_msg = await anext(stream)

            # Should include account_id
            assert "ABC123" in formatted_msg

    @pytest.mark.asyncio
    async def test_stream_logs_tail_parameter_limits_initial_read(self):
        """
        tail parameter should limit how many existing lines are read initially.
        """
        from src.daemon_logging.log_streaming import stream_logs
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Write 100 messages
            for i in range(100):
                manager.log_system("INFO", f"Message {i}")

            manager.shutdown()

            log_file = Path(temp_dir) / "system.log"

            # Stream with tail=10
            stream = stream_logs(log_file, category="all", tail=10)

            messages = []
            count = 0
            async for line in stream:
                if line:
                    messages.append(line)
                    count += 1
                if count >= 10:
                    break

            # Should read exactly 10 messages (last 10)
            assert len(messages) == 10

            # Should be the last 10 messages (90-99)
            # At least the last message should be "Message 99"
            assert any("Message 99" in msg for msg in messages)


class TestLogStreamingPerformance:
    """Test log streaming performance under various conditions."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_stream_logs_handles_high_volume_file(self):
        """
        stream_logs() should handle large log files efficiently.

        Test with 10,000 log entries.
        """
        from src.daemon_logging.log_streaming import stream_logs
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Write 10,000 log entries
            for i in range(10_000):
                manager.log_system("INFO", f"Volume test {i}")

            manager.shutdown()

            log_file = Path(temp_dir) / "system.log"

            # Stream with small tail
            stream = stream_logs(log_file, category="all", tail=20)

            messages = []
            count = 0
            async for line in stream:
                if line:
                    messages.append(line)
                    count += 1
                if count >= 20:
                    break

            # Should efficiently read last 20
            assert len(messages) == 20

    @pytest.mark.asyncio
    async def test_stream_logs_low_latency_for_new_entries(self):
        """
        New log entries should appear in stream with low latency.

        Architecture: polls every 0.1 seconds
        """
        from src.daemon_logging.log_streaming import stream_logs
        from src.daemon_logging.logger_manager import LoggerManager
        import time

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            manager.log_system("INFO", "Initial")

            log_file = Path(temp_dir) / "system.log"
            stream = stream_logs(log_file, category="all", tail=1)

            # Read initial
            await anext(stream)

            # Write new message and measure time to stream
            start = time.time()
            manager.log_system("INFO", "Latency test")
            manager.shutdown()

            # Wait for streamed message
            await asyncio.sleep(0.15)  # Give polling time
            new_msg = await anext(stream)

            latency = time.time() - start

            # Should receive within ~200ms (0.1s poll interval + overhead)
            assert latency < 0.5, f"Latency should be low, was {latency:.3f}s"
            assert "Latency test" in new_msg if new_msg else False


class TestLogStreamingEdgeCases:
    """Test edge cases for log streaming."""

    @pytest.mark.asyncio
    async def test_stream_logs_handles_nonexistent_file(self):
        """
        stream_logs() should handle nonexistent log file gracefully.

        Should wait for file to be created or raise appropriate error.
        """
        from src.daemon_logging.log_streaming import stream_logs

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "nonexistent.log"

            # Should not crash immediately
            try:
                stream = stream_logs(log_file, category="all", tail=5)
                # Try to read (may raise FileNotFoundError, which is expected)
                await anext(stream)
            except (FileNotFoundError, StopIteration):
                # Expected behavior
                pass

    @pytest.mark.asyncio
    async def test_stream_logs_handles_empty_file(self):
        """
        stream_logs() should handle empty log file gracefully.
        """
        from src.daemon_logging.log_streaming import stream_logs

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "empty.log"
            log_file.touch()  # Create empty file

            stream = stream_logs(log_file, category="all", tail=5)

            # Should not raise, just yield nothing initially
            # Then wait for new entries
            messages = []
            count = 0

            # Try to read a few times
            try:
                for _ in range(3):
                    msg = await asyncio.wait_for(anext(stream), timeout=0.1)
                    if msg:
                        messages.append(msg)
                        count += 1
            except asyncio.TimeoutError:
                pass  # Expected for empty file

            # No messages from empty file
            assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_stream_logs_category_all_shows_all_entries(self):
        """
        category="all" should show all log entries regardless of category.
        """
        from src.daemon_logging.log_streaming import stream_logs
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Write different categories (all to system.log for this test)
            manager.log_system("INFO", "System entry")
            manager.log_system("WARNING", "Warning entry")
            manager.log_system("ERROR", "Error entry")

            manager.shutdown()

            log_file = Path(temp_dir) / "system.log"
            stream = stream_logs(log_file, category="all", tail=5)

            messages = []
            count = 0
            async for line in stream:
                if line:
                    messages.append(line)
                    count += 1
                if count >= 3:
                    break

            # Should show all 3 entries
            assert len(messages) == 3

    @pytest.mark.asyncio
    async def test_stream_logs_formats_timestamp_correctly(self):
        """
        Streamed logs should format timestamp as YYYY-MM-DD HH:MM:SS.
        """
        from src.daemon_logging.log_streaming import stream_logs
        from src.daemon_logging.logger_manager import LoggerManager
        import re

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            manager.log_system("INFO", "Timestamp test")

            manager.shutdown()

            log_file = Path(temp_dir) / "system.log"
            stream = stream_logs(log_file, category="all", tail=1)

            formatted_msg = await anext(stream)

            # Extract timestamp from formatted message
            match = re.search(r'\[(.+?)\]', formatted_msg)
            assert match, "Should have timestamp in brackets"

            timestamp_str = match.group(1)

            # Verify format: YYYY-MM-DD HH:MM:SS
            assert re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', timestamp_str), \
                f"Timestamp should be YYYY-MM-DD HH:MM:SS format, got: {timestamp_str}"
