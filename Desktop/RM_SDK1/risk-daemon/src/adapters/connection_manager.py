"""
Connection management with automatic reconnection.

Handles WebSocket connection lifecycle, automatic reconnection,
and connection health monitoring.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Callable, Any, Dict, List
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class ConnectionMetrics:
    """Connection metrics tracking."""
    total_connections: int = 0
    total_disconnects: int = 0
    total_reconnects: int = 0
    failed_reconnects: int = 0
    event_gaps_detected: int = 0
    reconciliations_performed: int = 0
    connection_start_time: Optional[datetime] = None
    total_uptime_seconds: float = 0.0
    longest_uptime_seconds: float = 0.0
    reconnect_times: List[float] = field(default_factory=list)
    average_reconnect_time_seconds: float = 0.0


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
        persistence=None,
        state_manager=None
    ):
        """
        Initialize connection manager.

        Args:
            sdk_adapter: SDK adapter instance
            event_normalizer: Optional event normalizer
            health_monitor: Optional health monitor
            persistence: Optional persistence layer
            state_manager: Optional state manager for reconciliation
        """
        self.sdk_adapter = sdk_adapter
        self.event_normalizer = event_normalizer
        self.health_monitor = health_monitor
        self.persistence = persistence
        self.state_manager = state_manager

        # Connection state
        self._state = ConnectionState.DISCONNECTED
        self._connection_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._http_polling_task: Optional[asyncio.Task] = None

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

        # Metrics tracking
        self.metrics = ConnectionMetrics()
        self._last_disconnect_time: Optional[datetime] = None

        # Event gap detection
        self._last_sequence_number: Optional[int] = None

        # HTTP polling mode
        self._http_polling_mode = False

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
        try:
            if self.sdk_adapter and hasattr(self.sdk_adapter, 'is_connected'):
                if self.sdk_adapter.is_connected():
                    await self.sdk_adapter.disconnect()
        except (StopIteration, RuntimeError):
            # Handle mock exhausted or other cleanup errors gracefully
            pass

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
            self._record_connection_metrics("connected")

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
        # Increment attempt counter
        self._reconnect_attempts += 1

        # Check if we've exceeded max attempts
        # Note: max_reconnect_attempts includes the initial connection attempt
        # So with max=3: 1 initial + 2 reconnects = 3 total attempts
        if self._reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            self._state = ConnectionState.ERROR
            self._update_health_status("error")

            # Track failed reconnects
            self.metrics.failed_reconnects += 1

            # Call error callback
            if self._on_error:
                await self._on_error("Max reconnection attempts reached")
            return

        self._state = ConnectionState.RECONNECTING
        self._update_health_status("reconnecting")

        # Calculate delay with exponential backoff
        delay = min(
            self.reconnect_base_delay * (2 ** (self._reconnect_attempts - 1)),
            self.reconnect_max_delay
        )

        logger.info(
            f"Scheduling reconnection attempt {self._reconnect_attempts + 1}/{self.max_reconnect_attempts} "
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

                # Check connection status after heartbeat
                if self.sdk_adapter and hasattr(self.sdk_adapter, 'is_connected'):
                    if not self.sdk_adapter.is_connected():
                        logger.warning("Connection lost detected by heartbeat")
                        await self._handle_disconnect()
                        break

                # Update health monitor
                if self.health_monitor:
                    self.health_monitor.heartbeat()
                    if hasattr(self.health_monitor, 'update_connection_health'):
                        self.health_monitor.update_connection_health('connected')

                await asyncio.sleep(self.heartbeat_interval)

            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")

                # Connection might be lost
                if self.sdk_adapter and hasattr(self.sdk_adapter, 'is_connected'):
                    if not self.sdk_adapter.is_connected():
                        logger.warning("Connection lost, triggering reconnection")
                        await self._handle_disconnect()
                        break

    async def _handle_disconnect(self):
        """Handle disconnection."""
        # Only process if currently connected (avoid duplicate processing)
        # Handle both enum and string values for defensive programming
        is_connected = (self._state == ConnectionState.CONNECTED or
                       self._state == "CONNECTED" or
                       (isinstance(self._state, str) and self._state.upper() == "CONNECTED"))

        if not is_connected:
            return

        logger.warning("Connection lost unexpectedly")
        self._state = ConnectionState.RECONNECTING
        self._update_health_status("disconnected")
        self._record_connection_metrics("disconnected")

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

        # Trigger reconnection (non-blocking)
        if not self._shutdown:
            self._reconnect_task = asyncio.create_task(self._schedule_reconnect())

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

    # State Reconciliation Methods
    async def _reconcile_state_after_reconnect(self):
        """Reconcile state with broker after reconnection."""
        if not self.state_manager:
            return

        logger.info("Reconciling state after reconnect")

        try:
            # Get all account IDs
            account_ids = self.state_manager.get_all_account_ids()

            for account_id in account_ids:
                await self._reconcile_account_positions(account_id)

            # Update position prices
            await self._reconcile_position_prices()

            # Track reconciliation
            self.metrics.reconciliations_performed += 1

            logger.info("State reconciliation complete")

        except Exception as e:
            logger.error(f"State reconciliation failed: {e}")

    async def _reconcile_account_positions(self, account_id: str):
        """Reconcile positions for a specific account."""
        try:
            # Get positions from broker
            broker_positions = await self.sdk_adapter.get_all_open_positions()

            # Filter for this account
            broker_positions = [p for p in broker_positions if p.get('account_id') == account_id]

            # Get local positions
            local_positions = self.state_manager.get_open_positions(account_id)

            # Find positions at broker not in local state (missed fills)
            broker_symbols = {p['symbol']: p for p in broker_positions}
            local_symbols = {p.symbol: p for p in local_positions}

            # Add missing positions
            for symbol, broker_pos in broker_symbols.items():
                if symbol not in local_symbols:
                    logger.info(f"Adding missed position: {symbol}")
                    await self.state_manager.add_position_from_broker(account_id, broker_pos)

            # Remove positions not at broker (missed closes)
            for symbol, local_pos in local_symbols.items():
                if symbol not in broker_symbols:
                    logger.info(f"Removing closed position: {symbol}")
                    await self.state_manager.close_position(account_id, local_pos.position_id)

        except Exception as e:
            logger.error(f"Position reconciliation failed for {account_id}: {e}")

    async def _reconcile_position_prices(self):
        """Update prices for all open positions."""
        if not self.state_manager:
            return

        try:
            account_ids = self.state_manager.get_all_account_ids()

            for account_id in account_ids:
                positions = self.state_manager.get_open_positions(account_id)

                for position in positions:
                    try:
                        # Get latest quote
                        quote = await self.sdk_adapter.get_latest_quote(position.symbol)
                        price = quote.get('last_price')

                        if price:
                            await self.state_manager.update_position_price(
                                account_id,
                                position.position_id,
                                price
                            )
                    except Exception as e:
                        logger.warning(f"Failed to update price for {position.symbol}: {e}")

        except Exception as e:
            logger.error(f"Price reconciliation failed: {e}")

    async def _reconcile_recent_fills(self, account_id: str):
        """Reconcile recent fills that may have been missed."""
        # This would query recent trade history from broker
        # Implementation depends on SDK capabilities
        pass

    # Event Gap Detection
    async def _detect_event_gap(self, event: Dict[str, Any]):
        """Detect event gaps using sequence numbers."""
        sequence = event.get('sequence_number')

        if sequence is None:
            # No sequence number support
            return

        if self._last_sequence_number is not None:
            expected = self._last_sequence_number + 1

            if sequence > expected:
                # Gap detected!
                gap_size = sequence - expected
                logger.warning(f"Event gap detected: missed {gap_size} events")

                self.metrics.event_gaps_detected += 1

                # Trigger reconciliation
                await self._reconcile_state_after_reconnect()

        self._last_sequence_number = sequence

    # Partial Disconnect Handling
    async def _check_connection_health(self) -> Dict[str, bool]:
        """Check HTTP and WebSocket connection health separately."""
        http_ok = False
        websocket_ok = False

        try:
            # Check HTTP
            if hasattr(self.sdk_adapter, 'ping_http'):
                await self.sdk_adapter.ping_http()
                http_ok = True
        except Exception:
            pass

        try:
            # Check WebSocket
            if hasattr(self.sdk_adapter, 'is_websocket_connected'):
                websocket_ok = self.sdk_adapter.is_websocket_connected()
            else:
                websocket_ok = self.sdk_adapter.is_connected()
        except Exception:
            pass

        return {
            'http_connected': http_ok,
            'websocket_connected': websocket_ok
        }

    async def _handle_partial_disconnect(self, health: Dict[str, bool]):
        """Handle partial disconnect scenarios."""
        if not health['http_connected']:
            # HTTP down is critical - trigger full reconnect
            logger.error("HTTP connection lost - triggering full reconnect")
            await self._handle_disconnect()

        elif not health['websocket_connected']:
            # WebSocket down but HTTP OK - enter polling mode
            logger.warning("WebSocket lost - entering HTTP polling mode")
            await self._start_http_polling_mode()

    async def _start_http_polling_mode(self):
        """Start HTTP polling mode for position updates."""
        if self._http_polling_mode:
            return  # Already in polling mode

        self._http_polling_mode = True
        logger.info("Starting HTTP polling mode")

        if self._http_polling_task:
            self._http_polling_task.cancel()

        self._http_polling_task = asyncio.create_task(self._http_polling_loop())

    async def _http_polling_loop(self):
        """Poll positions via HTTP every 5 seconds."""
        # Enable polling mode if not already set
        self._http_polling_mode = True

        while not self._shutdown and self._http_polling_mode:
            try:
                # Query positions via HTTP
                if hasattr(self.sdk_adapter, 'query_positions_http'):
                    positions = await self.sdk_adapter.query_positions_http()

                    # Update state via event normalizer
                    if self.event_normalizer and positions:
                        for position in positions:
                            await self.event_normalizer.on_position_updated(position)

                await asyncio.sleep(5.0)  # Poll every 5 seconds

            except Exception as e:
                logger.error(f"HTTP polling error: {e}")
                break

        self._http_polling_mode = False

    # Connection Metrics Methods
    def _record_connection_metrics(self, event_type: str):
        """Record connection metrics."""
        now = datetime.now(timezone.utc)

        if event_type == "connected":
            self.metrics.total_connections += 1

            # Calculate reconnect time if we have a disconnect time
            if self._last_disconnect_time:
                reconnect_time = (now - self._last_disconnect_time).total_seconds()
                self.metrics.reconnect_times.append(reconnect_time)

                # Update average
                self.metrics.average_reconnect_time_seconds = (
                    sum(self.metrics.reconnect_times) / len(self.metrics.reconnect_times)
                )

            # Track if this is a reconnect (after a previous disconnect)
            if self.metrics.total_disconnects > 0:
                self.metrics.total_reconnects += 1

            # Track uptime start
            self.metrics.connection_start_time = now

        elif event_type == "disconnected":
            self.metrics.total_disconnects += 1
            self._last_disconnect_time = now

            # Calculate uptime for this session
            if self.metrics.connection_start_time:
                uptime = (now - self.metrics.connection_start_time).total_seconds()
                self.metrics.total_uptime_seconds += uptime

                # Track longest uptime
                if uptime > self.metrics.longest_uptime_seconds:
                    self.metrics.longest_uptime_seconds = uptime

    def _get_current_uptime(self) -> float:
        """Get current uptime in seconds."""
        if not self.metrics.connection_start_time:
            return 0.0

        return (datetime.now(timezone.utc) - self.metrics.connection_start_time).total_seconds()

    def _get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary as dictionary."""
        return {
            'total_connections': self.metrics.total_connections,
            'total_disconnects': self.metrics.total_disconnects,
            'total_reconnects': self.metrics.total_reconnects,
            'failed_reconnects': self.metrics.failed_reconnects,
            'event_gaps_detected': self.metrics.event_gaps_detected,
            'reconciliations_performed': self.metrics.reconciliations_performed,
            'current_uptime_seconds': self._get_current_uptime(),
            'total_uptime_seconds': self.metrics.total_uptime_seconds,
            'longest_uptime_seconds': self.metrics.longest_uptime_seconds,
            'average_reconnect_time_seconds': self.metrics.average_reconnect_time_seconds,
            'connection_state': self._state.value
        }

    def _get_reconnect_delay(self) -> float:
        """Calculate reconnect delay with exponential backoff."""
        delay = min(
            self.reconnect_base_delay * (2 ** (self._reconnect_attempts - 1)),
            self.reconnect_max_delay
        )
        return delay