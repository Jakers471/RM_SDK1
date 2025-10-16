"""
Event Bus for Risk Manager Daemon.

Provides priority-based event processing with async handler execution,
error isolation, and graceful shutdown.
"""

import asyncio
import heapq
import logging
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventBus:
    """
    Priority-based async event bus.

    Features:
    - Priority queue (P1 > P2 > P4 > P5)
    - FIFO within same priority
    - Multiple handlers per event type
    - Concurrent async handler execution
    - Error isolation (handler errors don't crash bus)
    - Graceful shutdown with timeout
    - Queue depth enforcement
    - Wildcard subscriptions ("*" catches all)
    """

    def __init__(self, max_queue_depth: int = 10000):
        """
        Initialize event bus.

        Args:
            max_queue_depth: Maximum number of queued events
        """
        self.max_queue_depth = max_queue_depth
        self._queue: List = []  # Priority queue: (priority, timestamp, event)
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._event_available = asyncio.Event()  # Signals when event added
        self._queue_lock = asyncio.Lock()
        self._sequence_counter = 0  # For FIFO within same priority

    async def start(self) -> None:
        """
        Start the event bus worker.

        Begins processing events from the queue.
        """
        if self._running:
            return

        self._running = True
        self._shutdown_event.clear()

        # Start worker task
        self._worker_task = asyncio.create_task(self._process_events())
        logger.info("Event bus started")

    async def shutdown(self, timeout: float = 5.0) -> None:
        """
        Gracefully shutdown the event bus.

        Waits for queued events to be processed, up to timeout.

        Args:
            timeout: Maximum time to wait for shutdown (seconds)
        """
        if not self._running:
            return

        logger.info("Event bus shutting down...")
        self._running = False
        self._shutdown_event.set()

        if self._worker_task:
            try:
                # Wait for worker to finish processing queue
                await asyncio.wait_for(self._worker_task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Event bus shutdown timed out after {timeout}s")
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    pass

        logger.info("Event bus shutdown complete")

    async def publish(self, event: Dict) -> None:
        """
        Publish an event to the bus.

        Args:
            event: Event dictionary with priority, event_type, etc.

        Raises:
            RuntimeError: If bus is not running or queue is full
        """
        if not self._running:
            raise RuntimeError("Event bus is not running")

        async with self._queue_lock:
            if len(self._queue) >= self.max_queue_depth:
                raise RuntimeError(
                    f"Event queue full (max_queue_depth={self.max_queue_depth})"
                )

            # Get priority (lower number = higher priority)
            priority = event.get("priority", 5)

            # Use timestamp + sequence counter for FIFO within same priority
            # heapq uses min-heap, so we use (priority, sequence, event)
            timestamp = time.time()
            self._sequence_counter += 1

            heapq.heappush(
                self._queue,
                (priority, self._sequence_counter, timestamp, event)
            )

            # Signal that an event is available
            self._event_available.set()

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """
        Subscribe a handler to an event type.

        Args:
            event_type: Event type to listen for (or "*" for all)
            handler: Async or sync callable to handle event
        """
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
            logger.debug(f"Subscribed handler to {event_type}")

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """
        Unsubscribe a handler from an event type.

        Args:
            event_type: Event type to stop listening to
            handler: Handler to remove
        """
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.debug(f"Unsubscribed handler from {event_type}")

    def is_running(self) -> bool:
        """
        Check if event bus is running.

        Returns:
            True if bus is processing events
        """
        return self._running

    def get_queue_depth(self) -> int:
        """
        Get current queue depth.

        Returns:
            Number of events in queue
        """
        return len(self._queue)

    def get_handler_count(self, event_type: Optional[str] = None) -> int:
        """
        Get number of registered handlers.

        Args:
            event_type: Specific event type (None = total across all types)

        Returns:
            Number of handlers
        """
        if event_type is not None:
            return len(self._handlers[event_type])
        else:
            # Total handlers across all event types
            return sum(len(handlers) for handlers in self._handlers.values())

    async def _process_events(self) -> None:
        """
        Worker task that processes events from the queue.

        Runs until shutdown is called.
        """
        while self._running or len(self._queue) > 0:
            try:
                # Get next event from priority queue
                event = await self._get_next_event()

                if event is None:
                    # No events available, wait for signal or timeout
                    try:
                        await asyncio.wait_for(self._event_available.wait(), timeout=0.01)
                        self._event_available.clear()
                    except asyncio.TimeoutError:
                        pass
                    continue

                # Dispatch event to handlers
                await self._dispatch_event(event)

            except Exception as e:
                logger.error(f"Error in event processing loop: {e}", exc_info=True)
                await asyncio.sleep(0.001)

    async def _get_next_event(self) -> Optional[Dict]:
        """
        Get next event from priority queue.

        Returns:
            Event dict or None if queue empty
        """
        async with self._queue_lock:
            if len(self._queue) == 0:
                return None

            # Pop highest priority event (lowest priority number)
            _, _, _, event = heapq.heappop(self._queue)
            return event

    async def _dispatch_event(self, event: Dict) -> None:
        """
        Dispatch event to all registered handlers.

        Args:
            event: Event to dispatch
        """
        event_type = event.get("event_type", "UNKNOWN")

        # Get handlers for this specific event type
        handlers = self._handlers.get(event_type, []).copy()

        # Add wildcard handlers
        wildcard_handlers = self._handlers.get("*", []).copy()
        handlers.extend(wildcard_handlers)

        if not handlers:
            return

        # Execute all handlers concurrently
        tasks = []
        for handler in handlers:
            task = asyncio.create_task(self._execute_handler(handler, event))
            tasks.append(task)

        # Wait for all handlers to complete concurrently
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_handler(self, handler: Callable, event: Dict) -> None:
        """
        Execute a single handler with error isolation.

        Args:
            handler: Handler callable
            event: Event to pass to handler
        """
        try:
            # Check if handler is async
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                # Sync handler - run in executor to avoid blocking
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, handler, event)

        except Exception as e:
            # Log error but don't propagate - error isolation
            logger.error(
                f"Handler {handler.__name__} failed for event {event.get('event_type')}: {e}",
                exc_info=True
            )
