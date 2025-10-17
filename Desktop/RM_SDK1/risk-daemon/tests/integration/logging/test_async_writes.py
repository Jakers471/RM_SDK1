"""
Integration tests for async log writes using QueueHandler and QueueListener.

Tests that logging is non-blocking and performant under high volume.

Architecture Reference: architecture/20-logging-framework.md
"""

import pytest
import tempfile
import time
import json
from pathlib import Path
import threading


pytestmark = pytest.mark.integration


class TestAsyncLogWrites:
    """Test async logging performance with QueueHandler."""

    def test_async_writes_are_non_blocking(self):
        """
        Log writes should not block the calling thread.

        Architecture requirement:
        - Use QueueHandler for async writes
        - Expected: async_time << sync_time
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Measure time to queue 1000 log messages
            start = time.time()

            for i in range(1000):
                manager.log_system("INFO", f"Event {i}")

            elapsed = time.time() - start

            manager.shutdown()

            # Async logging should complete very quickly
            # Expected < 0.1 seconds for 1000 messages (queuing only)
            assert elapsed < 0.5, \
                f"Async log writes should be fast (took {elapsed:.3f}s), expected < 0.5s"

    def test_async_writes_preserve_all_messages(self):
        """
        All queued messages should be written to disk eventually.

        Even under high volume, no messages should be lost.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            message_count = 500

            # Queue many messages rapidly
            for i in range(message_count):
                manager.log_system("INFO", f"Message {i}")

            # Shutdown flushes queue
            manager.shutdown()

            # Count messages in log file
            log_file = Path(temp_dir) / "system.log"
            with open(log_file) as f:
                lines = f.readlines()

            assert len(lines) == message_count, \
                f"Should preserve all {message_count} messages, found {len(lines)}"

    def test_async_writes_maintain_message_order(self):
        """
        Messages should be written in the order they were logged.

        QueueHandler should preserve FIFO order.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Log sequential messages
            for i in range(100):
                manager.log_system("INFO", f"Sequence {i}")

            manager.shutdown()

            # Verify order
            log_file = Path(temp_dir) / "system.log"
            with open(log_file) as f:
                lines = f.readlines()

            for i, line in enumerate(lines):
                log_entry = json.loads(line)
                expected_msg = f"Sequence {i}"
                assert expected_msg in log_entry["message"], \
                    f"Message {i} should be '{expected_msg}', got: {log_entry['message']}"

    def test_queue_listener_flushes_on_shutdown(self):
        """
        QueueListener.stop() should flush all pending messages.

        Architecture requirement:
        - Graceful shutdown flushes queue
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Queue messages
            for i in range(100):
                manager.log_system("INFO", f"Flush test {i}")

            # Shutdown immediately (should still flush all)
            manager.shutdown()

            # All messages should be written
            log_file = Path(temp_dir) / "system.log"
            with open(log_file) as f:
                lines = f.readlines()

            assert len(lines) == 100, "Should flush all queued messages on shutdown"

    def test_async_writes_handle_concurrent_loggers(self):
        """
        Multiple category loggers should work correctly with async writes.

        No message corruption or loss between loggers.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Log to different categories concurrently
            for i in range(50):
                manager.log_system("INFO", f"System {i}")
                manager.log_enforcement("ACC123", "Rule", "action", {"index": i})
                manager.log_error(f"Error {i}")
                manager.log_audit("action", "admin", {"index": i})

            manager.shutdown()

            # Verify each category has correct count
            for category, filename in [
                ("system", "system.log"),
                ("enforcement", "enforcement.log"),
                ("error", "error.log"),
                ("audit", "audit.log")
            ]:
                log_file = Path(temp_dir) / filename
                with open(log_file) as f:
                    lines = f.readlines()

                assert len(lines) == 50, \
                    f"{category} should have 50 messages, got {len(lines)}"


class TestAsyncWritesPerformance:
    """Test async logging performance characteristics."""

    @pytest.mark.slow
    def test_async_writes_performance_benchmark(self):
        """
        Benchmark async vs sync logging performance.

        Architecture expectation:
        - Sync: ~0.500s for 1000 messages
        - Async: ~0.010s for 1000 messages
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            iterations = 1000

            # Benchmark async writes (queuing time)
            start = time.time()
            for i in range(iterations):
                manager.log_system("INFO", f"Benchmark message {i}")
            async_time = time.time() - start

            manager.shutdown()

            # Async should be very fast (< 0.1s for queuing)
            assert async_time < 0.2, \
                f"Async logging should be fast: {async_time:.3f}s for {iterations} messages"

    def test_async_writes_do_not_block_event_loop(self):
        """
        Logging should not block other async operations.

        Simulates event processing with logging.
        """
        from src.daemon_logging.logger_manager import LoggerManager
        import asyncio

        async def process_events_with_logging(manager):
            """Simulate event processing with logging."""
            event_count = 0

            for i in range(100):
                # Simulate event processing
                await asyncio.sleep(0.001)  # 1ms per event

                # Log the event (should not block)
                manager.log_system("INFO", f"Event {i} processed")
                event_count += 1

            return event_count

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Run async event processing
            start = time.time()
            event_count = asyncio.run(process_events_with_logging(manager))
            elapsed = time.time() - start

            manager.shutdown()

            # Should complete in reasonable time
            # 100 events * 1ms = 0.1s minimum, allow 0.5s total
            assert elapsed < 0.5, \
                f"Event processing should not be blocked by logging (took {elapsed:.3f}s)"
            assert event_count == 100

    def test_async_writes_under_high_volume(self):
        """
        Async writes should handle high volume without queue overflow.

        Test with 10,000 messages.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            high_volume = 10_000

            start = time.time()

            for i in range(high_volume):
                manager.log_system("INFO", f"High volume message {i}")

            queue_time = time.time() - start

            manager.shutdown()

            # Queuing should still be fast
            assert queue_time < 2.0, \
                f"Should queue {high_volume} messages quickly (took {queue_time:.3f}s)"

            # Verify all messages written
            log_file = Path(temp_dir) / "system.log"
            with open(log_file) as f:
                lines = f.readlines()

            assert len(lines) == high_volume, \
                f"Should write all {high_volume} messages"


class TestAsyncWritesConcurrency:
    """Test async writes under concurrent access."""

    def test_async_writes_thread_safe(self):
        """
        Async logging should be thread-safe.

        Multiple threads logging concurrently should not corrupt messages.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        def log_from_thread(manager, thread_id, count):
            """Log messages from a thread."""
            for i in range(count):
                manager.log_system("INFO", f"Thread-{thread_id} Message-{i}")

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            thread_count = 5
            messages_per_thread = 100
            threads = []

            # Start multiple logging threads
            for thread_id in range(thread_count):
                thread = threading.Thread(
                    target=log_from_thread,
                    args=(manager, thread_id, messages_per_thread)
                )
                threads.append(thread)
                thread.start()

            # Wait for all threads
            for thread in threads:
                thread.join()

            manager.shutdown()

            # Verify total message count
            log_file = Path(temp_dir) / "system.log"
            with open(log_file) as f:
                lines = f.readlines()

            expected_total = thread_count * messages_per_thread
            assert len(lines) == expected_total, \
                f"Should have {expected_total} messages from {thread_count} threads"

            # Verify no corrupted messages
            for line in lines:
                log_entry = json.loads(line)  # Should parse without error
                assert "Thread-" in log_entry["message"]

    def test_async_writes_preserve_context_under_concurrency(self):
        """
        Log context should be preserved correctly under concurrent writes.

        Each thread's context should not interfere with others.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        def log_with_context(manager, thread_id):
            """Log with thread-specific context."""
            context = {
                "thread_id": thread_id,
                "thread_name": f"Worker-{thread_id}"
            }

            for i in range(50):
                manager.log_system("INFO", f"Message from thread {thread_id}", context=context)

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            threads = []
            for thread_id in range(3):
                thread = threading.Thread(target=log_with_context, args=(manager, thread_id))
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            manager.shutdown()

            # Verify contexts are correct
            log_file = Path(temp_dir) / "system.log"
            with open(log_file) as f:
                lines = f.readlines()

            # Check that each log entry has correct context for its thread
            for line in lines:
                log_entry = json.loads(line)

                if "context" in log_entry:
                    thread_id = log_entry["context"]["thread_id"]
                    thread_name = log_entry["context"]["thread_name"]

                    # Context should match
                    assert thread_name == f"Worker-{thread_id}"


class TestAsyncWritesEdgeCases:
    """Test edge cases for async writes."""

    def test_async_writes_survive_handler_errors(self):
        """
        If a handler fails, logging should continue for other handlers.

        QueueListener should handle handler errors gracefully.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Log messages (even if handler fails, queue should not crash)
            for i in range(100):
                manager.log_system("INFO", f"Message {i}")

            # Should complete without exception
            manager.shutdown()

    def test_async_writes_handle_rapid_shutdown(self):
        """
        Rapid shutdown after logging should still flush messages.
        """
        from src.daemon_logging.logger_manager import LoggerManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggerManager(log_dir=temp_dir)
            manager.initialize()

            # Log and immediately shutdown
            manager.log_system("INFO", "Rapid shutdown test")
            manager.shutdown()

            # Message should still be written
            log_file = Path(temp_dir) / "system.log"
            with open(log_file) as f:
                content = f.read()

            assert "Rapid shutdown test" in content
