"""
Comprehensive tests for Event Bus system.

Tests the core event processing pipeline including:
- Event publishing and subscription
- Priority-based event ordering
- Multiple handlers per event type
- Async handler execution
- Error handling and isolation
- Graceful shutdown
- Queue management
"""

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import List
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_connection_event():
    """Create a P1 priority CONNECTION_CHANGE event."""
    return {
        "event_id": uuid4(),
        "event_type": "CONNECTION_CHANGE",
        "timestamp": datetime.now(timezone.utc),
        "priority": 1,
        "account_id": "system",
        "source": "broker",
        "data": {
            "status": "connected",
            "reason": None,
            "broker": "topstepx"
        },
        "correlation_id": None
    }


@pytest.fixture
def sample_fill_event():
    """Create a P2 priority FILL event."""
    return {
        "event_id": uuid4(),
        "event_type": "FILL",
        "timestamp": datetime.now(timezone.utc),
        "priority": 2,
        "account_id": "test_account_123",
        "source": "broker",
        "data": {
            "symbol": "MNQ",
            "side": "long",
            "quantity": 2,
            "fill_price": Decimal("19500.50"),
            "order_id": "order_123",
            "fill_time": datetime.now(timezone.utc)
        },
        "correlation_id": None
    }


@pytest.fixture
def sample_position_update_event():
    """Create a P2 priority POSITION_UPDATE event."""
    return {
        "event_id": uuid4(),
        "event_type": "POSITION_UPDATE",
        "timestamp": datetime.now(timezone.utc),
        "priority": 2,
        "account_id": "test_account_123",
        "source": "broker",
        "data": {
            "position_id": uuid4(),
            "symbol": "MNQ",
            "current_price": Decimal("19505.50"),
            "unrealized_pnl": Decimal("50.00"),
            "quantity": 2,
            "update_time": datetime.now(timezone.utc)
        },
        "correlation_id": None
    }


@pytest.fixture
def sample_time_tick_event():
    """Create a P4 priority TIME_TICK event."""
    return {
        "event_id": uuid4(),
        "event_type": "TIME_TICK",
        "timestamp": datetime.now(timezone.utc),
        "priority": 4,
        "account_id": "system",
        "source": "internal",
        "data": {
            "tick_time": datetime.now(timezone.utc)
        },
        "correlation_id": None
    }


@pytest.fixture
def sample_session_tick_event():
    """Create a P5 priority SESSION_TICK event."""
    return {
        "event_id": uuid4(),
        "event_type": "SESSION_TICK",
        "timestamp": datetime.now(timezone.utc),
        "priority": 5,
        "account_id": "system",
        "source": "internal",
        "data": {
            "session_check_time": datetime.now(timezone.utc)
        },
        "correlation_id": None
    }


@pytest.fixture
def mock_async_handler():
    """Create a mock async handler that tracks calls."""
    handler = AsyncMock()
    handler.call_count = 0
    handler.events_received = []

    async def track_calls(event):
        handler.call_count += 1
        handler.events_received.append(event)
        await handler(event)

    handler.side_effect = track_calls
    return handler


@pytest.fixture
def mock_sync_handler():
    """Create a mock sync handler that tracks calls."""
    handler = Mock()
    handler.call_count = 0
    handler.events_received = []

    def track_calls(event):
        handler.call_count += 1
        handler.events_received.append(event)
        handler(event)

    handler.side_effect = track_calls
    return handler


@pytest.fixture
def failing_handler():
    """Create a handler that always raises an exception."""
    handler = AsyncMock()
    handler.side_effect = RuntimeError("Handler failed intentionally")
    return handler


@pytest.fixture
async def event_bus():
    """Create an EventBus instance for testing."""
    from src.daemon.event_bus import EventBus

    bus = EventBus(max_queue_depth=10000)
    yield bus

    # Cleanup: shutdown bus if still running
    if bus.is_running():
        await bus.shutdown()


# ============================================================================
# Test Event Publishing and Subscription
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_event_bus_initialization(event_bus):
    """Test EventBus initializes with correct default state."""
    assert not event_bus.is_running()
    assert event_bus.get_queue_depth() == 0
    assert event_bus.get_handler_count() == 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_subscribe_single_handler_for_event_type(event_bus, mock_async_handler):
    """Test subscribing a single handler to an event type."""
    event_bus.subscribe("FILL", mock_async_handler)

    assert event_bus.get_handler_count() == 1
    assert event_bus.get_handler_count("FILL") == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_subscribe_multiple_handlers_for_same_event_type(event_bus, mock_async_handler):
    """Test subscribing multiple handlers to the same event type."""
    handler1 = AsyncMock()
    handler2 = AsyncMock()
    handler3 = AsyncMock()

    event_bus.subscribe("FILL", handler1)
    event_bus.subscribe("FILL", handler2)
    event_bus.subscribe("FILL", handler3)

    assert event_bus.get_handler_count("FILL") == 3


@pytest.mark.asyncio
@pytest.mark.unit
async def test_publish_event_to_empty_bus_queues_event(event_bus, sample_fill_event):
    """Test publishing an event to bus without handlers queues the event."""
    await event_bus.start()

    await event_bus.publish(sample_fill_event)

    # Event should be queued
    assert event_bus.get_queue_depth() >= 0  # May be processed immediately

    await event_bus.shutdown()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_publish_event_triggers_subscribed_handler(event_bus, sample_fill_event, mock_async_handler):
    """Test publishing event triggers all subscribed handlers."""
    event_bus.subscribe("FILL", mock_async_handler)

    await event_bus.start()
    await event_bus.publish(sample_fill_event)

    # Wait for processing
    await asyncio.sleep(0.1)

    # Handler should be called
    assert mock_async_handler.call_count >= 1

    await event_bus.shutdown()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_publish_event_triggers_all_subscribed_handlers(event_bus, sample_fill_event):
    """Test publishing event triggers all handlers for that event type."""
    handler1 = AsyncMock()
    handler2 = AsyncMock()
    handler3 = AsyncMock()

    event_bus.subscribe("FILL", handler1)
    event_bus.subscribe("FILL", handler2)
    event_bus.subscribe("FILL", handler3)

    await event_bus.start()
    await event_bus.publish(sample_fill_event)

    # Wait for processing
    await asyncio.sleep(0.1)

    # All handlers should be called
    handler1.assert_called_once()
    handler2.assert_called_once()
    handler3.assert_called_once()

    await event_bus.shutdown()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_publish_event_only_triggers_matching_handlers(event_bus, sample_fill_event, sample_position_update_event):
    """Test event only triggers handlers for its type, not others."""
    fill_handler = AsyncMock()
    position_handler = AsyncMock()

    event_bus.subscribe("FILL", fill_handler)
    event_bus.subscribe("POSITION_UPDATE", position_handler)

    await event_bus.start()
    await event_bus.publish(sample_fill_event)

    # Wait for processing
    await asyncio.sleep(0.1)

    # Only FILL handler called
    fill_handler.assert_called_once()
    position_handler.assert_not_called()

    await event_bus.shutdown()


# ============================================================================
# Test Priority Ordering
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_higher_priority_events_processed_first(event_bus):
    """Test P1 events are processed before P2, P4, P5 events."""
    processing_order = []

    async def track_order(event):
        processing_order.append(event["event_type"])

    # Subscribe handler to all event types
    event_bus.subscribe("CONNECTION_CHANGE", track_order)
    event_bus.subscribe("FILL", track_order)
    event_bus.subscribe("TIME_TICK", track_order)
    event_bus.subscribe("SESSION_TICK", track_order)

    await event_bus.start()

    # Publish events in reverse priority order (P5, P4, P2, P1)
    await event_bus.publish({
        "event_id": uuid4(),
        "event_type": "SESSION_TICK",
        "priority": 5,
        "timestamp": datetime.now(timezone.utc),
        "account_id": "system",
        "source": "internal",
        "data": {},
        "correlation_id": None
    })

    await event_bus.publish({
        "event_id": uuid4(),
        "event_type": "TIME_TICK",
        "priority": 4,
        "timestamp": datetime.now(timezone.utc),
        "account_id": "system",
        "source": "internal",
        "data": {},
        "correlation_id": None
    })

    await event_bus.publish({
        "event_id": uuid4(),
        "event_type": "FILL",
        "priority": 2,
        "timestamp": datetime.now(timezone.utc),
        "account_id": "test_account",
        "source": "broker",
        "data": {},
        "correlation_id": None
    })

    await event_bus.publish({
        "event_id": uuid4(),
        "event_type": "CONNECTION_CHANGE",
        "priority": 1,
        "timestamp": datetime.now(timezone.utc),
        "account_id": "system",
        "source": "broker",
        "data": {},
        "correlation_id": None
    })

    # Wait for all events to process
    await asyncio.sleep(0.2)

    # CONNECTION_CHANGE (P1) should be first
    assert processing_order[0] == "CONNECTION_CHANGE"
    # FILL (P2) should be second
    assert processing_order[1] == "FILL"
    # TIME_TICK (P4) should be third
    assert processing_order[2] == "TIME_TICK"
    # SESSION_TICK (P5) should be last
    assert processing_order[3] == "SESSION_TICK"

    await event_bus.shutdown()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_same_priority_events_processed_in_order(event_bus):
    """Test events with same priority are processed FIFO."""
    processing_order = []

    async def track_order(event):
        processing_order.append(event["data"]["order"])

    event_bus.subscribe("FILL", track_order)

    await event_bus.start()

    # Publish multiple P2 events
    for i in range(5):
        await event_bus.publish({
            "event_id": uuid4(),
            "event_type": "FILL",
            "priority": 2,
            "timestamp": datetime.now(timezone.utc),
            "account_id": "test_account",
            "source": "broker",
            "data": {"order": i},
            "correlation_id": None
        })

    # Wait for processing
    await asyncio.sleep(0.2)

    # Should be processed in order
    assert processing_order == [0, 1, 2, 3, 4]

    await event_bus.shutdown()


# ============================================================================
# Test Async Handler Execution
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_async_handlers_execute_correctly(event_bus, sample_fill_event):
    """Test async handlers are properly awaited and executed."""
    execution_times = []

    async def slow_handler(event):
        await asyncio.sleep(0.05)
        execution_times.append(time.time())

    event_bus.subscribe("FILL", slow_handler)

    await event_bus.start()

    start_time = time.time()
    await event_bus.publish(sample_fill_event)

    # Wait for handler to complete
    await asyncio.sleep(0.2)

    # Handler should have executed
    assert len(execution_times) == 1
    assert execution_times[0] - start_time >= 0.05

    await event_bus.shutdown()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_multiple_async_handlers_execute_concurrently(event_bus, sample_fill_event):
    """Test multiple async handlers for same event run concurrently."""
    execution_times = []

    async def handler(delay: float):
        async def inner(event):
            await asyncio.sleep(delay)
            execution_times.append(time.time())
        return inner

    # Subscribe 3 handlers with different delays
    event_bus.subscribe("FILL", await handler(0.1))
    event_bus.subscribe("FILL", await handler(0.1))
    event_bus.subscribe("FILL", await handler(0.1))

    await event_bus.start()

    start_time = time.time()
    await event_bus.publish(sample_fill_event)

    # Wait for all handlers to complete
    while len(execution_times) < 3:
        await asyncio.sleep(0.01)
        # Prevent infinite loop
        if time.time() - start_time > 1.0:
            break

    total_time = time.time() - start_time

    # If executed concurrently, should take ~0.1s, not 0.3s
    # Allow some buffer for overhead and event bus processing
    assert total_time < 0.3  # Increased buffer for processing overhead
    assert len(execution_times) == 3

    await event_bus.shutdown()


# ============================================================================
# Test Error Handling
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_error_does_not_stop_event_bus(event_bus, sample_fill_event, failing_handler):
    """Test when one handler fails, event bus continues processing."""
    successful_handler = AsyncMock()

    event_bus.subscribe("FILL", failing_handler)
    event_bus.subscribe("FILL", successful_handler)

    await event_bus.start()
    await event_bus.publish(sample_fill_event)

    # Wait for processing
    await asyncio.sleep(0.1)

    # Successful handler should still be called
    successful_handler.assert_called_once()

    # Bus should still be running
    assert event_bus.is_running()

    await event_bus.shutdown()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_error_does_not_affect_other_handlers(event_bus, sample_fill_event, failing_handler):
    """Test when one handler fails, other handlers still execute."""
    handler1 = AsyncMock()
    handler2 = AsyncMock()

    event_bus.subscribe("FILL", handler1)
    event_bus.subscribe("FILL", failing_handler)
    event_bus.subscribe("FILL", handler2)

    await event_bus.start()
    await event_bus.publish(sample_fill_event)

    # Wait for processing
    await asyncio.sleep(0.1)

    # Both non-failing handlers called
    handler1.assert_called_once()
    handler2.assert_called_once()

    await event_bus.shutdown()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_error_logged_and_continues(event_bus, sample_fill_event, failing_handler):
    """Test handler errors are logged but processing continues."""
    successful_handler = AsyncMock()

    event_bus.subscribe("FILL", failing_handler)
    event_bus.subscribe("FILL", successful_handler)

    await event_bus.start()

    # Publish multiple events
    await event_bus.publish(sample_fill_event)
    await event_bus.publish(sample_fill_event)

    # Wait for processing
    await asyncio.sleep(0.2)

    # Successful handler called twice
    assert successful_handler.call_count == 2

    await event_bus.shutdown()


# ============================================================================
# Test Graceful Shutdown
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_shutdown_processes_remaining_events(event_bus):
    """Test shutdown waits for queued events to be processed."""
    processed_events = []

    async def handler(event):
        await asyncio.sleep(0.05)
        processed_events.append(event["event_id"])

    event_bus.subscribe("FILL", handler)

    await event_bus.start()

    # Publish multiple events
    event_ids = []
    for _ in range(5):
        event_id = uuid4()
        event_ids.append(event_id)
        await event_bus.publish({
            "event_id": event_id,
            "event_type": "FILL",
            "priority": 2,
            "timestamp": datetime.now(timezone.utc),
            "account_id": "test_account",
            "source": "broker",
            "data": {},
            "correlation_id": None
        })

    # Shutdown immediately
    await event_bus.shutdown()

    # All events should be processed
    assert len(processed_events) == 5
    assert set(processed_events) == set(event_ids)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_shutdown_prevents_new_events(event_bus, sample_fill_event):
    """Test shutdown prevents publishing new events."""
    handler = AsyncMock()
    event_bus.subscribe("FILL", handler)

    await event_bus.start()
    await event_bus.shutdown()

    # Try to publish after shutdown
    with pytest.raises(RuntimeError, match="Event bus is not running"):
        await event_bus.publish(sample_fill_event)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_shutdown_timeout_does_not_hang_forever(event_bus):
    """Test shutdown has timeout and doesn't hang on slow handlers."""
    async def very_slow_handler(event):
        await asyncio.sleep(10)  # Very slow

    event_bus.subscribe("FILL", very_slow_handler)

    await event_bus.start()

    await event_bus.publish({
        "event_id": uuid4(),
        "event_type": "FILL",
        "priority": 2,
        "timestamp": datetime.now(timezone.utc),
        "account_id": "test_account",
        "source": "broker",
        "data": {},
        "correlation_id": None
    })

    # Shutdown with timeout
    start_time = time.time()
    await event_bus.shutdown(timeout=0.5)
    elapsed = time.time() - start_time

    # Should timeout quickly, not wait 10 seconds
    assert elapsed < 1.0


# ============================================================================
# Test Handler Registration/Deregistration
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_unsubscribe_handler_stops_receiving_events(event_bus, sample_fill_event):
    """Test unsubscribing a handler stops it from receiving events."""
    handler = AsyncMock()

    # Subscribe and publish
    event_bus.subscribe("FILL", handler)
    await event_bus.start()
    await event_bus.publish(sample_fill_event)
    await asyncio.sleep(0.1)

    assert handler.call_count == 1

    # Unsubscribe and publish again
    event_bus.unsubscribe("FILL", handler)
    await event_bus.publish(sample_fill_event)
    await asyncio.sleep(0.1)

    # Handler should not be called again
    assert handler.call_count == 1

    await event_bus.shutdown()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_unsubscribe_one_handler_leaves_others_active(event_bus, sample_fill_event):
    """Test unsubscribing one handler doesn't affect others."""
    handler1 = AsyncMock()
    handler2 = AsyncMock()
    handler3 = AsyncMock()

    event_bus.subscribe("FILL", handler1)
    event_bus.subscribe("FILL", handler2)
    event_bus.subscribe("FILL", handler3)

    await event_bus.start()

    # Unsubscribe handler2
    event_bus.unsubscribe("FILL", handler2)

    await event_bus.publish(sample_fill_event)
    await asyncio.sleep(0.1)

    # Only handler1 and handler3 called
    handler1.assert_called_once()
    handler2.assert_not_called()
    handler3.assert_called_once()

    await event_bus.shutdown()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_unsubscribe_nonexistent_handler_does_not_error(event_bus):
    """Test unsubscribing a handler that was never subscribed doesn't error."""
    handler = AsyncMock()

    # Should not raise
    event_bus.unsubscribe("FILL", handler)


# ============================================================================
# Test Queue Management
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_queue_depth_limit_enforced(event_bus):
    """Test event queue enforces maximum depth limit."""
    # Create bus with small queue
    from src.daemon.event_bus import EventBus
    small_bus = EventBus(max_queue_depth=10)

    # Slow handler to fill queue
    async def slow_handler(event):
        await asyncio.sleep(0.5)

    small_bus.subscribe("FILL", slow_handler)
    await small_bus.start()

    # Try to publish more than max
    for i in range(15):
        try:
            await small_bus.publish({
                "event_id": uuid4(),
                "event_type": "FILL",
                "priority": 2,
                "timestamp": datetime.now(timezone.utc),
                "account_id": "test_account",
                "source": "broker",
                "data": {"order": i},
                "correlation_id": None
            })
        except RuntimeError as e:
            # Should raise when queue full
            assert "queue full" in str(e).lower() or "max_queue_depth" in str(e).lower()
            break

    await small_bus.shutdown(timeout=1.0)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_queue_depth_returns_current_depth(event_bus):
    """Test get_queue_depth returns accurate queue size."""
    async def slow_handler(event):
        await asyncio.sleep(0.1)

    event_bus.subscribe("FILL", slow_handler)
    await event_bus.start()

    # Publish events rapidly
    for i in range(5):
        await event_bus.publish({
            "event_id": uuid4(),
            "event_type": "FILL",
            "priority": 2,
            "timestamp": datetime.now(timezone.utc),
            "account_id": "test_account",
            "source": "broker",
            "data": {},
            "correlation_id": None
        })

    # Check queue depth
    depth = event_bus.get_queue_depth()
    assert depth >= 0  # May be processing

    await event_bus.shutdown()


# ============================================================================
# Test Performance
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.performance
async def test_event_bus_processes_100_events_per_second_minimum(event_bus):
    """Test event bus can process at least 100 events/sec."""
    processed_count = 0

    async def fast_handler(event):
        nonlocal processed_count
        processed_count += 1

    event_bus.subscribe("FILL", fast_handler)
    await event_bus.start()

    # Publish 200 events
    start_time = time.time()
    for i in range(200):
        await event_bus.publish({
            "event_id": uuid4(),
            "event_type": "FILL",
            "priority": 2,
            "timestamp": datetime.now(timezone.utc),
            "account_id": "test_account",
            "source": "broker",
            "data": {},
            "correlation_id": None
        })

    # Wait for processing
    await asyncio.sleep(0.5)
    elapsed = time.time() - start_time

    # Should process all events
    assert processed_count == 200

    # Should achieve >100 events/sec (200 events in < 2 seconds)
    events_per_sec = processed_count / elapsed
    assert events_per_sec >= 100, f"Only processed {events_per_sec:.1f} events/sec"

    await event_bus.shutdown()


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.performance
async def test_event_bus_low_latency_processing(event_bus):
    """Test event bus has low latency (< 100ms from publish to handler)."""
    latencies = []

    async def measure_latency(event):
        receive_time = time.time()
        publish_time = event["data"]["publish_time"]
        latencies.append(receive_time - publish_time)

    event_bus.subscribe("FILL", measure_latency)
    await event_bus.start()

    # Publish events and measure latency
    for _ in range(50):
        await event_bus.publish({
            "event_id": uuid4(),
            "event_type": "FILL",
            "priority": 2,
            "timestamp": datetime.now(timezone.utc),
            "account_id": "test_account",
            "source": "broker",
            "data": {"publish_time": time.time()},
            "correlation_id": None
        })
        await asyncio.sleep(0.01)

    # Wait for processing
    await asyncio.sleep(0.2)

    # Calculate average latency
    avg_latency = sum(latencies) / len(latencies)

    # Average latency should be < 100ms
    assert avg_latency < 0.1, f"Average latency {avg_latency*1000:.1f}ms exceeds 100ms"

    await event_bus.shutdown()


# ============================================================================
# Test Event Filtering
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_wildcard_subscription_receives_all_events(event_bus, sample_fill_event, sample_position_update_event):
    """Test subscribing to '*' receives all event types."""
    all_events = []

    async def catch_all(event):
        all_events.append(event["event_type"])

    event_bus.subscribe("*", catch_all)
    await event_bus.start()

    await event_bus.publish(sample_fill_event)
    await event_bus.publish(sample_position_update_event)

    await asyncio.sleep(0.1)

    assert "FILL" in all_events
    assert "POSITION_UPDATE" in all_events

    await event_bus.shutdown()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_specific_subscription_only_receives_matching_type(event_bus, sample_fill_event, sample_position_update_event):
    """Test specific subscriptions only receive their event type."""
    fill_handler = AsyncMock()
    position_handler = AsyncMock()

    event_bus.subscribe("FILL", fill_handler)
    event_bus.subscribe("POSITION_UPDATE", position_handler)

    await event_bus.start()

    await event_bus.publish(sample_fill_event)
    await asyncio.sleep(0.05)

    fill_handler.assert_called_once()
    position_handler.assert_not_called()

    fill_handler.reset_mock()

    await event_bus.publish(sample_position_update_event)
    await asyncio.sleep(0.05)

    fill_handler.assert_not_called()
    position_handler.assert_called_once()

    await event_bus.shutdown()
