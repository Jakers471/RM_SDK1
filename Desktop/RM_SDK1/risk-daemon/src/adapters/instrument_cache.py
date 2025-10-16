"""
Instrument metadata cache for Risk Manager Daemon.

Caches tick values and contract IDs to reduce API calls to the SDK.
"""

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from .exceptions import InstrumentError


@dataclass
class InstrumentMetadata:
    """Instrument metadata."""
    symbol: str
    tick_value: Decimal
    contract_id: str
    tick_size: Decimal


class InstrumentCache:
    """
    Cache for instrument metadata (tick values, contract IDs).

    Reduces API calls by storing instrument data after first query.
    """

    def __init__(self, client=None):
        """
        Initialize instrument cache.

        Args:
            client: ProjectX client instance for querying instruments
        """
        self.client = client
        self._cache: Dict[str, InstrumentMetadata] = {}
        self._pending_queries: Dict[str, asyncio.Future] = {}

    async def get_tick_value(self, symbol: str) -> Decimal:
        """
        Get tick value for symbol (cached).

        Args:
            symbol: Instrument symbol (e.g., "MNQ")

        Returns:
            Tick value in dollars per tick (e.g., Decimal('2.0') for MNQ)

        Raises:
            ValueError: If symbol is empty
            InstrumentError: If instrument not found
        """
        if not symbol or not symbol.strip():
            raise ValueError("Symbol cannot be empty")

        metadata = await self._get_metadata(symbol)
        return metadata.tick_value

    async def get_contract_id(self, symbol: str) -> str:
        """
        Get current contract ID for symbol.

        Args:
            symbol: Root symbol (e.g., "MNQ")

        Returns:
            Full contract ID (e.g., "CON.F.US.MNQ.U25")

        Raises:
            ValueError: If symbol is empty
            InstrumentError: If instrument not found
        """
        if not symbol or not symbol.strip():
            raise ValueError("Symbol cannot be empty")

        metadata = await self._get_metadata(symbol)
        return metadata.contract_id

    async def _get_metadata(self, symbol: str) -> InstrumentMetadata:
        """
        Get instrument metadata (cached).

        Args:
            symbol: Instrument symbol

        Returns:
            InstrumentMetadata

        Raises:
            InstrumentError: If instrument not found
        """
        # Check cache
        if symbol in self._cache:
            return self._cache[symbol]

        # Check if a query is already in progress (deduplication)
        if symbol in self._pending_queries:
            return await self._pending_queries[symbol]

        # Create a future for this query
        future = asyncio.get_event_loop().create_future()
        self._pending_queries[symbol] = future

        try:
            # Fetch from SDK
            metadata = await self._fetch_instrument(symbol)
            self._cache[symbol] = metadata

            # Resolve the future
            future.set_result(metadata)
            return metadata
        except Exception as e:
            # Reject the future
            if not future.done():
                future.set_exception(e)
            raise
        finally:
            # Remove from pending queries
            self._pending_queries.pop(symbol, None)

    async def _fetch_instrument(self, symbol: str) -> InstrumentMetadata:
        """
        Fetch instrument metadata from SDK (uncached).

        Args:
            symbol: Instrument symbol

        Returns:
            InstrumentMetadata

        Raises:
            InstrumentError: If instrument not found or SDK query fails
            ValueError: If tick value is None/null
            asyncio.TimeoutError: If SDK query times out
        """
        if self.client is None:
            raise InstrumentError(f"No client configured for instrument queries")

        try:
            # Query SDK for instrument metadata
            instrument = await self.client.get_instrument(symbol)

            # Helper to safely convert to Decimal
            def to_decimal(value) -> Optional[Decimal]:
                if value is None:
                    return None
                if isinstance(value, Decimal):
                    return value
                if isinstance(value, (int, float)):
                    return Decimal(str(value))
                try:
                    return Decimal(str(value))
                except:
                    return None

            # Extract tick value - required field
            tick_value = None
            if hasattr(instrument, 'tickValue'):
                tick_value = to_decimal(instrument.tickValue)

            if tick_value is None:
                raise ValueError(f"Invalid tick value for instrument {symbol}: tick value cannot be None")

            # Extract contract ID - use contractId field (not id)
            contract_id = None
            if hasattr(instrument, 'contractId'):
                contract_id = instrument.contractId
            elif hasattr(instrument, 'id'):
                contract_id = instrument.id
            else:
                contract_id = f"CON.F.US.{symbol}.U25"

            # Extract tick size (optional, default 0.25)
            tick_size = to_decimal(instrument.tickSize) if hasattr(instrument, 'tickSize') else None
            if tick_size is None:
                tick_size = Decimal("0.25")

            metadata = InstrumentMetadata(
                symbol=symbol,
                tick_value=tick_value,
                contract_id=contract_id,
                tick_size=tick_size
            )

            return metadata

        except asyncio.TimeoutError:
            # Re-raise timeout errors as-is
            raise
        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            if isinstance(e, InstrumentError):
                raise
            raise InstrumentError(f"Instrument {symbol} not found: {e}")

    def clear(self):
        """Clear entire instrument cache (useful for daily reset)."""
        self._cache.clear()
        self._pending_queries.clear()

    def clear_cache(self):
        """Alias for clear() for backward compatibility."""
        self.clear()

    def invalidate(self, symbol: str):
        """
        Invalidate specific symbol in cache.

        Args:
            symbol: Symbol to remove from cache
        """
        self._cache.pop(symbol, None)

    def size(self) -> int:
        """
        Get number of cached instruments.

        Returns:
            Number of instruments in cache
        """
        return len(self._cache)

    def get_symbols(self) -> List[str]:
        """
        Get list of all cached symbols.

        Returns:
            List of symbol strings
        """
        return list(self._cache.keys())

    async def get_cached_price(self, symbol: str) -> Optional[Decimal]:
        """
        Get cached price for symbol (for price cache compatibility).

        Args:
            symbol: Symbol to lookup

        Returns:
            Cached price or None
        """
        # This is a placeholder for price cache compatibility
        return None
