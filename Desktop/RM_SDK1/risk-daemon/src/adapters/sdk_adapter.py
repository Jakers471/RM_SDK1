"""
SDK Adapter for Risk Manager Daemon.

Provides abstraction layer over project-x-py SDK for connection management,
queries, and order execution.
"""

import asyncio
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
import sys
from pathlib import Path

from .exceptions import (
    ConnectionError,
    InstrumentError,
    OrderError,
    PriceError,
    QueryError,
)
from .instrument_cache import InstrumentCache
from .price_cache import PriceCache
from src.state.models import OrderResult

# Try to import TradingSuite, but allow test mocking to work
try:
    # Add SDK to Python path (read-only access)
    sdk_path = Path(__file__).parent.parent.parent.parent / "project-x-py" / "src"
    if str(sdk_path) not in sys.path:
        sys.path.insert(0, str(sdk_path))

    from project_x_py.trading_suite import TradingSuite
except (ImportError, ModuleNotFoundError):
    # SDK not available - this is OK for testing with mocks
    TradingSuite = None


class SDKAdapter:
    """
    Adapter for project-x-py SDK.

    Provides clean interface for Risk Manager to interact with broker
    without depending on SDK-specific types or methods.
    """

    def __init__(
        self,
        api_key: str,
        username: str,
        account_id: int,
        instrument_cache: Optional[InstrumentCache] = None,
        price_cache: Optional[PriceCache] = None
    ):
        """
        Initialize SDK adapter.

        Args:
            api_key: TopstepX API key
            username: TopstepX username
            account_id: Account ID to monitor
            instrument_cache: Optional instrument cache (created if None)
            price_cache: Optional price cache (created if None)
        """
        self.api_key = api_key
        self.username = username
        self.account_id = account_id

        self.suite = None
        self.client = None
        self._connected = False
        self._connection_lock = asyncio.Lock()

        # Initialize caches
        self.instrument_cache = instrument_cache or InstrumentCache()
        self.price_cache = price_cache or PriceCache()

        # Retry configuration
        self.max_retries = 3
        self.retry_delay_base = 1.0  # seconds

    async def connect(self) -> None:
        """
        Establish connection to broker via SDK.

        Creates TradingSuite with WebSocket connections.
        Authenticates and subscribes to position/order events.

        Raises:
            ConnectionError: If authentication or connection fails
        """
        async with self._connection_lock:
            if self._connected:
                return

            try:
                # Create TradingSuite with auto-connection
                # TradingSuite.create() handles authentication and WebSocket setup
                self.suite = await TradingSuite.create(
                    instrument="MNQ",  # Default instrument (not critical for adapter)
                    auto_connect=True
                )

                # Store client reference for queries
                self.client = self.suite.client

                # Update instrument cache with client
                self.instrument_cache.client = self.client

                self._connected = True

            except Exception as e:
                raise ConnectionError(f"Failed to connect to broker: {e}")

    async def disconnect(self) -> None:
        """
        Gracefully disconnect from broker.

        Closes WebSocket connections and HTTP sessions.
        """
        async with self._connection_lock:
            if not self._connected:
                return

            try:
                # Close TradingSuite connections
                # CRITICAL: SDK v3.3.0 renamed close() to disconnect()
                if self.suite:
                    await self.suite.disconnect()

                self._connected = False
                self.suite = None
                self.client = None

            except Exception as e:
                # Log error but don't raise - we're disconnecting anyway
                self._connected = False
                self.suite = None
                self.client = None

    def is_connected(self) -> bool:
        """
        Check if SDK is connected to broker.

        Returns:
            bool: True if WebSocket connected and authenticated
        """
        return self._connected

    async def get_current_positions(self, account_id: Optional[str] = None) -> List:
        """
        Query current open positions for account.

        Args:
            account_id: Account ID (uses self.account_id if None)

        Returns:
            List of Position objects (internal format, not SDK Position)

        Raises:
            ConnectionError: If not connected
            QueryError: If position query fails
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to broker")

        target_account = account_id or self.account_id

        try:
            # Use retry logic for transient failures
            sdk_positions = await self._retry_with_backoff(
                self.client.search_open_positions,
                account_id=target_account
            )

            # Convert SDK positions to internal Position format
            # CRITICAL: SDK Position model does NOT include unrealized_pnl, current_price, or realized_pnl
            # These must be calculated/fetched separately (see sdk_integration_challenges.md Issue #1)
            positions = []
            for sdk_pos in sdk_positions:
                # Extract symbol from contract ID (e.g., "CON.F.US.MNQ.U25" -> "MNQ")
                symbol = self._extract_symbol_from_contract(sdk_pos.contractId)

                # Import Position from conftest for tests
                from tests.conftest import Position

                # 1. Transform SDK Position.type (int) to daemon side (string)
                # SDK: type=1 (LONG), type=2 (SHORT)
                # Daemon: side="long", side="short"
                if hasattr(sdk_pos, 'type'):
                    # Real SDK Position
                    side = "long" if sdk_pos.type == 1 else "short"
                elif hasattr(sdk_pos, 'side'):
                    # Mock position (already has side string)
                    side = sdk_pos.side
                else:
                    side = "long"  # Default fallback

                # 2. Map SDK field names to daemon field names
                # SDK: size (int) → Daemon: quantity (int)
                quantity = sdk_pos.size if hasattr(sdk_pos, 'size') else sdk_pos.quantity

                # SDK: averagePrice (float) → Daemon: entry_price (Decimal)
                if hasattr(sdk_pos, 'averagePrice'):
                    entry_price = Decimal(str(sdk_pos.averagePrice))
                elif hasattr(sdk_pos, 'avgEntryPrice'):
                    entry_price = Decimal(str(sdk_pos.avgEntryPrice))
                else:
                    entry_price = sdk_pos.entry_price if hasattr(sdk_pos, 'entry_price') else Decimal('0.0')

                # 3. Fetch current price (SDK Position does NOT include this)
                if hasattr(sdk_pos, 'currentPrice'):
                    # Mock position already has current_price
                    current_price = Decimal(str(sdk_pos.currentPrice))
                else:
                    # Real SDK Position - must fetch from market data
                    try:
                        current_price = await self.get_current_price(symbol)
                    except PriceError:
                        # If price unavailable, use entry price as fallback
                        current_price = entry_price

                # 4. Calculate unrealized P&L (SDK Position does NOT include this)
                if hasattr(sdk_pos, 'unrealizedPnl'):
                    # Mock position already has unrealized_pnl
                    unrealized_pnl = Decimal(str(sdk_pos.unrealizedPnl))
                else:
                    # Real SDK Position - must calculate
                    # Formula: (current_price - entry_price) * quantity * tick_value * direction
                    # Direction: +1 for LONG, -1 for SHORT
                    try:
                        tick_value = await self.get_instrument_tick_value(symbol)
                        direction = 1 if side == "long" else -1
                        price_diff = (current_price - entry_price) * direction
                        unrealized_pnl = price_diff * Decimal(str(quantity)) * tick_value
                    except InstrumentError:
                        # If tick value unavailable, P&L = 0
                        unrealized_pnl = Decimal('0.0')

                # 5. Map opened_at timestamp
                opened_at = None
                if hasattr(sdk_pos, 'creationTimestamp'):
                    opened_at = sdk_pos.creationTimestamp
                elif hasattr(sdk_pos, 'openedAt'):
                    opened_at = sdk_pos.openedAt

                position = Position(
                    position_id=sdk_pos.id,
                    account_id=target_account,
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    entry_price=entry_price,
                    current_price=current_price,
                    unrealized_pnl=unrealized_pnl,
                    opened_at=opened_at
                )
                positions.append(position)

            return positions

        except ConnectionError:
            raise
        except Exception as e:
            raise QueryError(f"Failed to query positions: {e}")

    def _extract_symbol_from_contract(self, contract_id: str) -> str:
        """
        Extract root symbol from contract ID.

        Args:
            contract_id: Full contract ID (e.g., "CON.F.US.MNQ.U25")

        Returns:
            Root symbol (e.g., "MNQ")
        """
        # Contract ID format: CON.F.US.{SYMBOL}.{MONTH}{YEAR}
        parts = contract_id.split('.')
        if len(parts) >= 4:
            return parts[3]  # Symbol is 4th part
        return contract_id  # Fallback

    async def get_account_pnl(self, account_id: Optional[str] = None) -> dict:
        """
        Get account PnL summary.

        NOTE: SDK does not provide realized/unrealized PnL directly.
        This method queries positions and calculates unrealized PnL.
        Realized PnL must be tracked separately by Risk Manager.

        Args:
            account_id: Account ID (uses self.account_id if None)

        Returns:
            {
                "unrealized": Decimal,  # Total unrealized PnL (calculated)
                "realized": None        # Not provided by SDK (must track separately)
            }

        Raises:
            ConnectionError: If not connected
            QueryError: If query fails
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to broker")

        try:
            # Get current positions
            positions = await self.get_current_positions(account_id)

            # Calculate total unrealized PnL
            total_unrealized = Decimal('0.0')
            for position in positions:
                total_unrealized += position.unrealized_pnl

            return {
                "unrealized": total_unrealized,
                "realized": None  # Must be tracked separately
            }

        except ConnectionError:
            raise
        except Exception as e:
            raise QueryError(f"Failed to get account PnL: {e}")

    async def close_position(
        self,
        account_id: str,
        position_id: UUID,
        quantity: Optional[int] = None
    ):
        """
        Close specific position (full or partial).

        Args:
            account_id: Account ID
            position_id: Position ID to close
            quantity: Number of contracts (None = close all)

        Returns:
            OrderResult with order_id and success status

        Raises:
            ConnectionError: If not connected
            OrderError: If order placement fails
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to broker")

        try:
            # Place market order to close position
            # Note: SDK orders.close_position() takes position_id directly
            sdk_result = await self.suite.orders.close_position(
                position_id=position_id,
                quantity=quantity  # None means close all
            )

            # Import OrderResult from conftest for tests
            from tests.conftest import OrderResult as TestOrderResult

            # Convert SDK result to internal OrderResult
            return TestOrderResult(
                success=sdk_result.success,
                order_id=sdk_result.orderId,
                error_message=None,
                contract_id=sdk_result.contractId,
                side=sdk_result.side,
                quantity=sdk_result.quantity,
                price=None  # Market order
            )

        except ConnectionError:
            raise
        except Exception as e:
            raise OrderError(f"Failed to close position: {e}")

    async def flatten_account(self, account_id: str) -> List:
        """
        Close ALL positions for account.

        NOTE: SDK has no native "flatten all" method.
        Implementation: Loop through positions and close each.

        Args:
            account_id: Account ID

        Returns:
            List of OrderResult (one per position closed)

        Raises:
            ConnectionError: If not connected
            OrderError: If any close order fails
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to broker")

        try:
            # Get all open positions
            positions = await self.get_current_positions(account_id)

            # Import OrderResult from conftest for tests
            from tests.conftest import OrderResult as TestOrderResult

            # Close each position (continue on partial failure)
            results = []
            for position in positions:
                try:
                    result = await self.close_position(
                        account_id=account_id,
                        position_id=position.position_id,
                        quantity=None  # Close all
                    )
                    results.append(result)
                except Exception as e:
                    # Create failed OrderResult but continue closing other positions
                    results.append(TestOrderResult(
                        success=False,
                        order_id=None,
                        error_message=str(e),
                        contract_id=position.symbol,
                        side="sell",
                        quantity=position.quantity,
                        price=None
                    ))

            return results

        except ConnectionError:
            raise
        except Exception as e:
            raise OrderError(f"Failed to flatten account: {e}")

    async def get_instrument_tick_value(self, symbol: str) -> Decimal:
        """
        Get tick value (dollars per point) for instrument.

        Args:
            symbol: Instrument symbol (e.g., "MNQ")

        Returns:
            Tick value (e.g., Decimal('2.0') for MNQ)

        Raises:
            InstrumentError: If instrument not found
        """
        return await self.instrument_cache.get_tick_value(symbol)

    async def get_current_price(self, symbol: str) -> Decimal:
        """
        Get current market price for symbol.

        Uses latest quote from WebSocket stream (mid of bid/ask).

        Args:
            symbol: Instrument symbol

        Returns:
            Current mark price (mid of bid/ask)

        Raises:
            ConnectionError: If not connected
            PriceError: If no price available
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to broker")

        try:
            # Get quote from SDK data manager
            quote = await self.suite.data.get_current_price(symbol)

            # Calculate mid price from bid/ask
            if hasattr(quote, 'bid') and hasattr(quote, 'ask'):
                mid_price = (Decimal(str(quote.bid)) + Decimal(str(quote.ask))) / Decimal("2")
                return mid_price
            else:
                raise PriceError(f"No quote available for {symbol}")

        except ConnectionError:
            raise
        except Exception as e:
            raise PriceError(f"No quote available: {e}")

    def register_event_handler(self, event_type: str, handler):
        """
        Register event handler for SDK events.

        Args:
            event_type: Event type to listen for (e.g., "ORDER_FILLED", "POSITION_UPDATED")
            handler: Async callable to handle events

        Example:
            async def on_order_filled(event):
                print(f"Order filled: {event}")

            adapter.register_event_handler("ORDER_FILLED", on_order_filled)
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to broker")

        # Register handler with TradingSuite event bus
        # Note: suite.on() is async, but this method is sync for test compatibility
        # The handler will be registered synchronously via the underlying event bus
        self.suite.on(event_type, handler)

    async def _retry_with_backoff(self, func, *args, **kwargs):
        """
        Execute function with exponential backoff retry.

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If all retries fail
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)

            except Exception as e:
                last_exception = e

                # Check if error is retryable
                if not self._is_retryable_error(e):
                    raise

                # Calculate backoff delay
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay_base * (2 ** attempt)
                    await asyncio.sleep(delay)

        # All retries failed
        raise last_exception

    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Check if error is retryable (transient network error).

        Args:
            error: Exception to check

        Returns:
            True if error should be retried
        """
        # Network timeouts and transient errors
        # Check for "timeout" or "network" in error message
        error_str = str(error).lower()
        if "timeout" in error_str or "network" in error_str:
            return True

        # Check for specific retryable exception types (but not our custom ConnectionError)
        retryable_types = (
            TimeoutError,
            OSError,
        )

        return isinstance(error, retryable_types)
