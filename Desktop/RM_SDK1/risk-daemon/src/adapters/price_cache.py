"""
Price cache for Risk Manager Daemon.

Maintains current market prices for unrealized PnL calculations.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional, Tuple

from .exceptions import PriceError


@dataclass
class PriceData:
    """Cached price data."""
    price: Decimal
    timestamp: datetime
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None


class PriceCache:
    """
    Cache for current market prices.

    Updates from QUOTE_UPDATE events and provides prices for PnL calculations.
    Detects stale prices (>60s old) and provides warnings.
    """

    def __init__(self, stale_threshold_seconds: int = 60):
        """
        Initialize price cache.

        Args:
            stale_threshold_seconds: Age in seconds after which price is considered stale
        """
        self._prices: Dict[str, PriceData] = {}
        self.stale_threshold = stale_threshold_seconds

    async def update_from_quote(
        self,
        symbol: str,
        bid: Decimal,
        ask: Decimal,
        timestamp: Optional[datetime] = None
    ):
        """
        Update price from quote event.

        Uses mid-price (average of bid/ask) for mark price.

        Args:
            symbol: Instrument symbol
            bid: Bid price
            ask: Ask price
            timestamp: Quote timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        mid_price = (bid + ask) / Decimal("2")

        self._prices[symbol] = PriceData(
            price=mid_price,
            timestamp=timestamp,
            bid=bid,
            ask=ask
        )

    def get_price(self, symbol: str, allow_stale: bool = False) -> Optional[Decimal]:
        """
        Get current price for symbol.

        Args:
            symbol: Instrument symbol
            allow_stale: If False, returns None for stale prices

        Returns:
            Current mark price, or None if not available or stale

        Raises:
            PriceError: If allow_stale=False and price is stale
        """
        if symbol not in self._prices:
            return None

        price_data = self._prices[symbol]
        age_seconds = (datetime.now(timezone.utc) - price_data.timestamp).total_seconds()

        if age_seconds > self.stale_threshold and not allow_stale:
            raise PriceError(
                f"Stale price for {symbol} ({age_seconds:.1f}s old, threshold: {self.stale_threshold}s)"
            )

        return price_data.price

    def get_price_age(self, symbol: str) -> Optional[float]:
        """
        Get age of cached price in seconds.

        Args:
            symbol: Instrument symbol

        Returns:
            Age in seconds, or None if no price cached
        """
        if symbol not in self._prices:
            return None

        price_data = self._prices[symbol]
        return (datetime.now(timezone.utc) - price_data.timestamp).total_seconds()

    def is_price_fresh(self, symbol: str) -> bool:
        """
        Check if price is fresh (not stale).

        Args:
            symbol: Instrument symbol

        Returns:
            True if price exists and is fresh
        """
        age = self.get_price_age(symbol)
        if age is None:
            return False
        return age <= self.stale_threshold

    def get_bid_ask(self, symbol: str) -> Optional[Tuple[Decimal, Decimal]]:
        """
        Get bid/ask prices for symbol.

        Args:
            symbol: Instrument symbol

        Returns:
            Tuple of (bid, ask), or None if not available
        """
        if symbol not in self._prices:
            return None

        price_data = self._prices[symbol]
        if price_data.bid is None or price_data.ask is None:
            return None

        return (price_data.bid, price_data.ask)

    def clear_cache(self):
        """Clear all cached prices."""
        self._prices.clear()

    def remove_symbol(self, symbol: str):
        """
        Remove specific symbol from cache.

        Args:
            symbol: Instrument symbol to remove
        """
        if symbol in self._prices:
            del self._prices[symbol]
