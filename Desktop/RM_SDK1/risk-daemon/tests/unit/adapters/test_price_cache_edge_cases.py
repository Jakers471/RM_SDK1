"""
Unit tests for PriceCache edge cases to improve branch coverage.

These tests target missing branches in the ACTUAL implementation:
- Line 61: timestamp None fallback (defaults to now)
- Line 87: Symbol not in cache (returns None)
- Line 93: Stale price raises PriceError when allow_stale=False
- Lines 109-113: get_price_age for unknown symbol
- Lines 125-128: is_price_fresh when symbol doesn't exist
- Lines 140-147: get_bid_ask for unknown symbol and missing bid/ask
- Line 151: clear_cache removes all prices
- Lines 160-161: remove_symbol for symbol that exists/doesn't exist
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from src.adapters.price_cache import PriceCache, PriceData
from src.adapters.exceptions import PriceError


@pytest.mark.asyncio
@pytest.mark.unit
class TestPriceCacheEdgeCases:
    """Test edge cases for full branch coverage of PriceCache."""

    @pytest.fixture
    def price_cache(self):
        """Create price cache with 60-second threshold."""
        return PriceCache(stale_threshold_seconds=60)

    @pytest.fixture
    def current_time(self):
        """Current time for testing."""
        return datetime(2025, 10, 16, 10, 0, 0, tzinfo=timezone.utc)

    # ===================================================================
    # update_from_quote Branch Coverage
    # ===================================================================

    async def test_update_from_quote_with_none_timestamp_uses_now(self, price_cache):
        """
        Test line 61: When timestamp is None, uses datetime.now(timezone.utc).

        This covers the timestamp default fallback.
        """
        # Execute: update without timestamp (should use current time)
        await price_cache.update_from_quote(
            symbol="MNQ",
            bid=Decimal("18000.0"),
            ask=Decimal("18002.0"),
            timestamp=None  # Should use datetime.now()
        )

        # Assert: Price was cached (timestamp defaulted successfully)
        price = price_cache.get_price("MNQ", allow_stale=True)
        assert price == Decimal("18001.0")  # Mid-price

        # Verify price is very fresh (just added)
        age = price_cache.get_price_age("MNQ")
        assert age is not None
        assert age < 1  # Less than 1 second old

    async def test_update_from_quote_calculates_mid_price(self, price_cache, current_time):
        """
        Test line 63: Calculates mid-price from bid/ask.

        Ensures mid = (bid + ask) / 2.
        """
        # Execute
        await price_cache.update_from_quote(
            symbol="MNQ",
            bid=Decimal("18000.0"),
            ask=Decimal("18002.0"),
            timestamp=current_time
        )

        # Assert: Mid-price = (18000 + 18002) / 2 = 18001
        price = price_cache.get_price("MNQ", allow_stale=True)
        assert price == Decimal("18001.0")

    # ===================================================================
    # get_price Branch Coverage
    # ===================================================================

    async def test_get_price_for_unknown_symbol_returns_none(self, price_cache):
        """
        Test line 87: get_price returns None when symbol not in cache.

        This covers the symbol not found branch.
        """
        # Execute: Query non-existent symbol
        result = price_cache.get_price("UNKNOWN_SYMBOL", allow_stale=True)

        # Assert: Returns None
        assert result is None

    async def test_get_price_raises_price_error_for_stale_price(self, price_cache, current_time):
        """
        Test line 93: get_price raises PriceError when price is stale and allow_stale=False.

        This covers the stale price exception path.
        """
        # Setup: Add price 70 seconds old (stale threshold is 60s)
        old_time = current_time - timedelta(seconds=70)
        await price_cache.update_from_quote(
            symbol="MNQ",
            bid=Decimal("18000.0"),
            ask=Decimal("18002.0"),
            timestamp=old_time
        )

        # Mock current time to make price stale
        with patch('src.adapters.price_cache.datetime') as mock_datetime:
            mock_datetime.now.return_value = current_time

            # Execute & Assert: Should raise PriceError
            with pytest.raises(PriceError) as exc_info:
                price_cache.get_price("MNQ", allow_stale=False)

            # Verify error message
            assert "Stale price" in str(exc_info.value)
            assert "MNQ" in str(exc_info.value)

    async def test_get_price_returns_stale_price_when_allow_stale_true(self, price_cache, current_time):
        """
        Test line 92: get_price returns price even if stale when allow_stale=True.

        This covers the happy path for stale prices.
        """
        # Setup: Add old price (70 seconds old)
        old_time = current_time - timedelta(seconds=70)
        await price_cache.update_from_quote(
            symbol="MNQ",
            bid=Decimal("18000.0"),
            ask=Decimal("18002.0"),
            timestamp=old_time
        )

        # Mock current time
        with patch('src.adapters.price_cache.datetime') as mock_datetime:
            mock_datetime.now.return_value = current_time

            # Execute: allow_stale=True should return price
            result = price_cache.get_price("MNQ", allow_stale=True)

            # Assert: Returns price despite being stale
            assert result == Decimal("18001.0")

    # ===================================================================
    # get_price_age Branch Coverage
    # ===================================================================

    async def test_get_price_age_for_unknown_symbol_returns_none(self, price_cache):
        """
        Test line 109: get_price_age returns None for unknown symbol.

        This covers the symbol not found branch.
        """
        # Execute
        result = price_cache.get_price_age("UNKNOWN_SYMBOL")

        # Assert: Returns None
        assert result is None

    async def test_get_price_age_returns_seconds_for_known_symbol(self, price_cache, current_time):
        """
        Test line 113: get_price_age calculates age in seconds.

        This covers the happy path for age calculation.
        """
        # Setup: Add price 30 seconds ago
        old_time = current_time - timedelta(seconds=30)
        await price_cache.update_from_quote(
            symbol="MNQ",
            bid=Decimal("18000.0"),
            ask=Decimal("18002.0"),
            timestamp=old_time
        )

        # Mock current time
        with patch('src.adapters.price_cache.datetime') as mock_datetime:
            mock_datetime.now.return_value = current_time

            # Execute
            age = price_cache.get_price_age("MNQ")

            # Assert: Age is approximately 30 seconds
            assert age is not None
            assert 29 <= age <= 31  # Allow slight floating point variance

    # ===================================================================
    # is_price_fresh Branch Coverage
    # ===================================================================

    async def test_is_price_fresh_returns_false_for_unknown_symbol(self, price_cache):
        """
        Test line 127: is_price_fresh returns False when age is None (symbol not found).

        This covers the missing symbol branch.
        """
        # Execute
        result = price_cache.is_price_fresh("UNKNOWN_SYMBOL")

        # Assert: Returns False
        assert result is False

    async def test_is_price_fresh_returns_true_for_fresh_price(self, price_cache, current_time):
        """
        Test line 128: is_price_fresh returns True when age <= threshold.

        This covers the fresh price branch.
        """
        # Setup: Add recent price (30 seconds old, threshold=60)
        old_time = current_time - timedelta(seconds=30)
        await price_cache.update_from_quote(
            symbol="MNQ",
            bid=Decimal("18000.0"),
            ask=Decimal("18002.0"),
            timestamp=old_time
        )

        # Mock current time
        with patch('src.adapters.price_cache.datetime') as mock_datetime:
            mock_datetime.now.return_value = current_time

            # Execute
            result = price_cache.is_price_fresh("MNQ")

            # Assert: Fresh (30s < 60s threshold)
            assert result is True

    async def test_is_price_fresh_returns_false_for_stale_price(self, price_cache, current_time):
        """
        Test line 128: is_price_fresh returns False when age > threshold.

        This covers the stale price branch.
        """
        # Setup: Add old price (70 seconds old, threshold=60)
        old_time = current_time - timedelta(seconds=70)
        await price_cache.update_from_quote(
            symbol="MNQ",
            bid=Decimal("18000.0"),
            ask=Decimal("18002.0"),
            timestamp=old_time
        )

        # Mock current time
        with patch('src.adapters.price_cache.datetime') as mock_datetime:
            mock_datetime.now.return_value = current_time

            # Execute
            result = price_cache.is_price_fresh("MNQ")

            # Assert: Not fresh (70s > 60s threshold)
            assert result is False

    # ===================================================================
    # get_bid_ask Branch Coverage
    # ===================================================================

    async def test_get_bid_ask_for_unknown_symbol_returns_none(self, price_cache):
        """
        Test line 140: get_bid_ask returns None for unknown symbol.

        This covers the symbol not found branch.
        """
        # Execute
        result = price_cache.get_bid_ask("UNKNOWN_SYMBOL")

        # Assert: Returns None
        assert result is None

    async def test_get_bid_ask_returns_none_when_bid_or_ask_missing(self, price_cache):
        """
        Test line 145: get_bid_ask returns None when bid or ask is None.

        This covers the incomplete bid/ask data branch.
        """
        # Manually create price data with missing bid/ask
        price_cache._prices["MNQ"] = PriceData(
            price=Decimal("18001.0"),
            timestamp=datetime.now(timezone.utc),
            bid=None,  # Missing bid
            ask=Decimal("18002.0")
        )

        # Execute
        result = price_cache.get_bid_ask("MNQ")

        # Assert: Returns None (incomplete data)
        assert result is None

    async def test_get_bid_ask_returns_tuple_for_complete_data(self, price_cache, current_time):
        """
        Test line 147: get_bid_ask returns (bid, ask) tuple for complete data.

        This covers the happy path.
        """
        # Setup: Add price with bid/ask
        await price_cache.update_from_quote(
            symbol="MNQ",
            bid=Decimal("18000.0"),
            ask=Decimal("18002.0"),
            timestamp=current_time
        )

        # Execute
        result = price_cache.get_bid_ask("MNQ")

        # Assert: Returns tuple
        assert result is not None
        assert result == (Decimal("18000.0"), Decimal("18002.0"))

    # ===================================================================
    # clear_cache Branch Coverage
    # ===================================================================

    async def test_clear_cache_removes_all_prices(self, price_cache, current_time):
        """
        Test line 151: clear_cache removes all cached prices.

        This covers the cache clearing functionality.
        """
        # Setup: Add multiple prices
        await price_cache.update_from_quote("MNQ", Decimal("18000.0"), Decimal("18002.0"), current_time)
        await price_cache.update_from_quote("MES", Decimal("5100.0"), Decimal("5102.0"), current_time)
        await price_cache.update_from_quote("MYM", Decimal("42000.0"), Decimal("42002.0"), current_time)

        # Verify prices cached
        assert price_cache.get_price("MNQ", allow_stale=True) is not None
        assert price_cache.get_price("MES", allow_stale=True) is not None
        assert price_cache.get_price("MYM", allow_stale=True) is not None

        # Execute
        price_cache.clear_cache()

        # Assert: All prices removed
        assert price_cache.get_price("MNQ", allow_stale=True) is None
        assert price_cache.get_price("MES", allow_stale=True) is None
        assert price_cache.get_price("MYM", allow_stale=True) is None

    # ===================================================================
    # remove_symbol Branch Coverage
    # ===================================================================

    async def test_remove_symbol_removes_price_from_cache(self, price_cache, current_time):
        """
        Test line 161: remove_symbol deletes symbol from cache when it exists.

        This covers the symbol removal branch.
        """
        # Setup: Add price
        await price_cache.update_from_quote("MNQ", Decimal("18000.0"), Decimal("18002.0"), current_time)
        assert price_cache.get_price("MNQ", allow_stale=True) is not None

        # Execute
        price_cache.remove_symbol("MNQ")

        # Assert: Price removed
        assert price_cache.get_price("MNQ", allow_stale=True) is None

    async def test_remove_symbol_for_unknown_symbol_no_error(self, price_cache):
        """
        Test line 160: remove_symbol handles unknown symbol gracefully.

        This covers the condition check when symbol doesn't exist.
        """
        # Execute: Remove non-existent symbol
        price_cache.remove_symbol("UNKNOWN_SYMBOL")

        # Assert: No error raised (graceful handling)
        # This is a no-op, but should not crash

    # ===================================================================
    # Additional Edge Cases
    # ===================================================================

    async def test_custom_stale_threshold(self, current_time):
        """
        Test line 40: Custom stale threshold initialization.

        Ensures stale_threshold parameter is respected.
        """
        # Create cache with 30-second threshold
        cache = PriceCache(stale_threshold_seconds=30)
        assert cache.stale_threshold == 30

        # Setup: Add price 35 seconds old
        old_time = current_time - timedelta(seconds=35)
        await cache.update_from_quote("MNQ", Decimal("18000.0"), Decimal("18002.0"), old_time)

        # Mock current time
        with patch('src.adapters.price_cache.datetime') as mock_datetime:
            mock_datetime.now.return_value = current_time

            # Execute & Assert: Should raise PriceError (35s > 30s threshold)
            with pytest.raises(PriceError):
                cache.get_price("MNQ", allow_stale=False)

    async def test_price_data_stores_bid_ask(self, price_cache, current_time):
        """
        Test lines 68-69: PriceData stores bid and ask values.

        Ensures bid/ask are preserved in cache.
        """
        # Execute
        await price_cache.update_from_quote(
            symbol="MNQ",
            bid=Decimal("17999.5"),
            ask=Decimal("18000.5"),
            timestamp=current_time
        )

        # Assert: Bid and ask stored
        bid_ask = price_cache.get_bid_ask("MNQ")
        assert bid_ask is not None
        assert bid_ask[0] == Decimal("17999.5")  # bid
        assert bid_ask[1] == Decimal("18000.5")  # ask
