"""
Connection management with automatic reconnection.

Handles WebSocket connection lifecycle, automatic reconnection,
and connection health monitoring.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Callable, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection state enum."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    CLOSED = "closed"


class ConnectionManager:
    """
    Manages WebSocket connection with automatic reconnection.

    Features:
    - Automatic reconnection with exponential backoff
    - Connection health monitoring
    - Heartbeat/ping management
    - Graceful shutdown
    - Event callbacks for connection state changes
    """

    def __init__(
        self,
        sdk_adapter,
        event_normalizer=None,
        health_monitor=None,
        persistence=None
    ):
        """
        Initialize connection manager.

        Args:
            sdk_adapter: SDK adapter instance
            event_normalizer: Optional event normalizer
            health_monitor: Optional health monitor
            persistence: Optional persistence layer
        """
        self.sdk_adapter = sdk_adapter
        self.event_normalizer = event_normalizer
        self.health_monitor = health_monitor
        self.persistence = persistence

        # Connection state
        self._state = ConnectionState.DISCONNECTED
        self._connection_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None

        # Reconnection settings
        self.max_reconnect_attempts = 10
        self.reconnect_base_delay = 1.0  # seconds
        self.reconnect_max_delay = 60.0  # seconds
        self.heartbeat_interval = 30.0  # seconds
        self._reconnect_attempts = 0

        # Callbacks
        self._on_connect: Optional[Callable] = None
        self._on_disconnect: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

        # Shutdown flag
        self._shutdown = False

    async def start(self):
        """Start connection manager and establish initial connection."""
        logger.info("Starting connection manager")
        self._shutdown = False
        self._state = ConnectionState.CONNECTING
        await self._connect()

    async def stop(self):
        """Stop connection manager and close connection."""
        logger.info("Stopping connection manager")
        self._shutdown = True

        # Cancel tasks
        for task in [self._connection_task, self._heartbeat_task, self._reconnect_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Disconnect
        if self.sdk_adapter and self.sdk_adapter.is_connected():
            await self.sdk_adapter.disconnect()

        self._state = ConnectionState.CLOSED

    async def _connect(self):
        """Establish connection to broker."""
        try:
            self._state = ConnectionState.CONNECTING
            self._update_health_status("connecting")

            logger.info("Connecting to broker...")
            await self.sdk_adapter.connect()

            self._state = ConnectionState.CONNECTED
            self._reconnect_attempts = 0
            self._update_health_status("connected")

            logger.info("Successfully connected to broker")

            # Register event handlers if event normalizer available
            if self.event_normalizer:
                self._register_event_handlers()

            # Start heartbeat monitoring
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # Call connect callback
            if self._on_connect:
                await self._on_connect()

            # Record successful connection
            if self.persistence:
                await self.persistence.record_enforcement({
                    'account_id': 'system',
                    'action_type': 'connection_established',
                    'reason': 'Connected to broker',
                    'success': True
                })

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self._state = ConnectionState.ERROR
            self._update_health_status("error")

            # Record error
            if self.health_monitor:
                self.health_monitor.record_error(f"Connection failed: {e}")

            # Trigger reconnection
            if not self._shutdown:
                await self._schedule_reconnect()

    async def _schedule_reconnect(self):
        """Schedule reconnection attempt."""
        if self._reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            self._state = ConnectionState.ERROR
            self._update_health_status("error")

            # Call error callback
            if self._on_error:
                await self._on_error("Max reconnection attempts reached")
            return

        self._reconnect_attempts += 1
        self._state = ConnectionState.RECONNECTING
        self._update_health_status("reconnecting")

        # Calculate delay with exponential backoff
        delay = min(
            self.reconnect_base_delay * (2 ** (self._reconnect_attempts - 1)),
            self.reconnect_max_delay
        )

        logger.info(
            f"Scheduling reconnection attempt {self._reconnect_attempts}/{self.max_reconnect_attempts} "
            f"in {delay:.1f} seconds"
        )

        # Record reconnection attempt
        if self.health_monitor:
            self.health_monitor.record_reconnect()

        # Wait and reconnect
        await asyncio.sleep(delay)

        if not self._shutdown:
            await self._connect()

    async def _heartbeat_loop(self):
        """Send periodic heartbeats to maintain connection."""
        while not self._shutdown and self._state == ConnectionState.CONNECTED:
            try:
                # Send heartbeat/ping
                if hasattr(self.sdk_adapter, 'ping'):
                    await self.sdk_adapter.ping()

                # Update health monitor
                if self.health_monitor:
                    self.health_monitor.heartbeat()

                await asyncio.sleep(self.heartbeat_interval)

            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")

                # Connection might be lost
                if self.sdk_adapter and not self.sdk_adapter.is_connected():
                    logger.warning("Connection lost, triggering reconnection")
                    await self._handle_disconnect()
                    break

    async def _handle_disconnect(self):
        """Handle disconnection."""
        if self._state == ConnectionState.CONNECTED:
            logger.warning("Connection lost unexpectedly")
            self._state = ConnectionState.DISCONNECTED
            self._update_health_status("disconnected")

            # Cancel heartbeat
            if self._heartbeat_task:
                self._heartbeat_task.cancel()

            # Call disconnect callback
            if self._on_disconnect:
                await self._on_disconnect()

            # Record disconnection
            if self.persistence:
                await self.persistence.record_enforcement({
                    'account_id': 'system',
                    'action_type': 'connection_lost',
                    'reason': 'Disconnected from broker',
                    'success': False
                })

            # Trigger reconnection
            if not self._shutdown:
                await self._schedule_reconnect()

    def _register_event_handlers(self):
        """Register SDK event handlers with event normalizer."""
        if not self.event_normalizer:
            return

        # Map SDK events to normalizer handlers
        event_mappings = {
            "ORDER_FILLED": self.event_normalizer.on_order_filled,
            "POSITION_UPDATED": self.event_normalizer.on_position_updated,
            "POSITION_CLOSED": self.event_normalizer.on_position_updated,
            "QUOTE_UPDATE": self.event_normalizer.on_quote_update,
            "ORDER_REJECTED": self.event_normalizer.on_order_rejected,
            "ORDER_PLACED": self.event_normalizer.on_order_placed,
            "CONNECTED": self._handle_connected_event,
            "DISCONNECTED": self._handle_disconnected_event,
            "RECONNECTING": self._handle_reconnecting_event,
        }

        for event_type, handler in event_mappings.items():
            self.sdk_adapter.register_event_handler(event_type, handler)

    async def _handle_connected_event(self, sdk_event):
        """Handle connected event from SDK."""
        logger.info("Received CONNECTED event from SDK")
        self._state = ConnectionState.CONNECTED
        self._update_health_status("connected")

        # Forward to event normalizer
        if self.event_normalizer:
            await self.event_normalizer.on_connection_lost(sdk_event)

    async def _handle_disconnected_event(self, sdk_event):
        """Handle disconnected event from SDK."""
        logger.warning("Received DISCONNECTED event from SDK")
        await self._handle_disconnect()

    async def _handle_reconnecting_event(self, sdk_event):
        """Handle reconnecting event from SDK."""
        logger.info("Received RECONNECTING event from SDK")
        self._state = ConnectionState.RECONNECTING
        self._update_health_status("reconnecting")

    def _update_health_status(self, status: str):
        """Update health monitor with connection status."""
        if self.health_monitor:
            self.health_monitor.update_connection_status(status)
            self.health_monitor.update_component_status("broker_connection", status)

    # Public methods
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._state == ConnectionState.CONNECTED

    def get_state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    def on_connect(self, callback: Callable):
        """Register connect callback."""
        self._on_connect = callback

    def on_disconnect(self, callback: Callable):
        """Register disconnect callback."""
        self._on_disconnect = callback

    def on_error(self, callback: Callable):
        """Register error callback."""
        self._on_error = callback

    async def reconnect(self):
        """Force reconnection."""
        logger.info("Forcing reconnection")
        self._reconnect_attempts = 0
        await self._connect()

    def reset_reconnect_attempts(self):
        """Reset reconnection attempt counter."""
        self._reconnect_attempts = 0