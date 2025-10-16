"""
Unit tests for PriceCache class.

Tests the price caching mechanism that stores latest market prices
from quote updates for PnL calculations and position pricing.

These tests are written FIRST (TDD RED phase) - implementation does not exist yet.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

import pytest

# Import will fail initially - this is expected in RED phase
try:
    from src.adapters.price_cache import PriceCache, PriceCacheEntry
except ImportError:
    # Mark tests as expected to fail during RED phase
    pytestmark = pytest.mark.xfail(reason="PriceCache not implemented yet", strict=False)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def price_cache():
    """Provide PriceCache instance."""
    return PriceCache(max_age_seconds=60)  # 60 second cache TTL


@pytest.fixture
def current_time():
    """Provide current timestamp for testing."""
    return datetime(2025, 10, 15, 10, 30, 0, tzinfo=timezone.utc)


# ============================================================================
# Basic Cache Operations Tests
# ============================================================================


@pytest.mark.unit
def test_cache_stores_price_for_symbol(price_cache, current_time):
    """Test that cache stores price for a given symbol."""
    # Execute
    price_cache.update("MNQ", Decimal("18000.50"), current_time)

    # Assert: Price stored
    cached_price = price_cache.get("MNQ")
    assert cached_price == Decimal("18000.50")


@pytest.mark.unit
def test_cache_returns_none_for_unknown_symbol(price_cache):
    """Test that cache returns None for symbols that haven't been cached."""
    # Execute
    cached_price = price_cache.get("UNKNOWN")

    # Assert: No price available
    assert cached_price is None


@pytest.mark.unit
def test_cache_updates_existing_price(price_cache, current_time):
    """Test that cache updates price when new quote arrives for same symbol."""
    # Setup: Initial price
    price_cache.update("MNQ", Decimal("18000.00"), current_time)

    # Execute: Update with new price
    new_time = current_time + timedelta(seconds=5)
    price_cache.update("MNQ", Decimal("18005.50"), new_time)

    # Assert: Price updated
    cached_price = price_cache.get("MNQ")
    assert cached_price == Decimal("18005.50")


@pytest.mark.unit
def test_cache_stores_multiple_symbols_independently(price_cache, current_time):
    """Test that cache stores prices for multiple symbols independently."""
    # Execute: Cache multiple symbols
    price_cache.update("MNQ", Decimal("18000.00"), current_time)
    price_cache.update("MES", Decimal("5100.50"), current_time)
    price_cache.update("MYM", Decimal("42000.00"), current_time)

    # Assert: All cached independently
    assert price_cache.get("MNQ") == Decimal("18000.00")
    assert price_cache.get("MES") == Decimal("5100.50")
    assert price_cache.get("MYM") == Decimal("42000.00")


# ============================================================================
# Cache Expiration Tests
# ============================================================================


@pytest.mark.unit
def test_cache_expires_stale_prices(price_cache, current_time):
    """Test that cache expires prices older than max_age_seconds."""
    # Setup: Cache price at T=0
    price_cache.update("MNQ", Decimal("18000.00"), current_time)

    # Execute: Query after cache TTL (60 seconds)
    stale_time = current_time + timedelta(seconds=61)

    # Assert: Price expired (returns None)
    cached_price = price_cache.get("MNQ", current_time=stale_time)
    assert cached_price is None


@pytest.mark.unit
def test_cache_returns_fresh_prices_within_ttl(price_cache, current_time):
    """Test that cache returns prices that are still within TTL."""
    # Setup: Cache price at T=0
    price_cache.update("MNQ", Decimal("18000.00"), current_time)

    # Execute: Query before TTL expires
    fresh_time = current_time + timedelta(seconds=30)  # 30 < 60 TTL

    # Assert: Price still fresh
    cached_price = price_cache.get("MNQ", current_time=fresh_time)
    assert cached_price == Decimal("18000.00")


@pytest.mark.unit
def test_cache_evicts_expired_entries_on_cleanup(price_cache, current_time):
    """Test that cache cleanup removes expired entries."""
    # Setup: Cache multiple prices
    price_cache.update("MNQ", Decimal("18000.00"), current_time)
    price_cache.update("MES", Decimal("5100.00"), current_time)

    # Execute: Advance time past TTL and cleanup
    stale_time = current_time + timedelta(seconds=70)
    price_cache.cleanup(current_time=stale_time)

    # Assert: Expired entries removed
    assert price_cache.size() == 0


# ============================================================================
# Cache Metadata Tests
# ============================================================================


@pytest.mark.unit
def test_cache_tracks_last_update_timestamp(price_cache, current_time):
    """Test that cache tracks when each price was last updated."""
    # Execute
    price_cache.update("MNQ", Decimal("18000.00"), current_time)

    # Assert: Timestamp tracked
    entry = price_cache.get_entry("MNQ")
    assert entry is not None
    assert entry.timestamp == current_time


@pytest.mark.unit
def test_cache_provides_age_of_cached_price(price_cache, current_time):
    """Test that cache can report age of cached price."""
    # Setup: Cache price at T=0
    price_cache.update("MNQ", Decimal("18000.00"), current_time)

    # Execute: Check age at T=30
    check_time = current_time + timedelta(seconds=30)
    age = price_cache.get_age("MNQ", current_time=check_time)

    # Assert: Age is 30 seconds
    assert age == timedelta(seconds=30)


@pytest.mark.unit
def test_cache_returns_none_age_for_unknown_symbol(price_cache, current_time):
    """Test that cache returns None age for symbols not in cache."""
    # Execute
    age = price_cache.get_age("UNKNOWN", current_time=current_time)

    # Assert: No age available
    assert age is None


# ============================================================================
# Cache Statistics Tests
# ============================================================================


@pytest.mark.unit
def test_cache_reports_size(price_cache, current_time):
    """Test that cache reports number of cached entries."""
    # Setup: Cache multiple symbols
    price_cache.update("MNQ", Decimal("18000.00"), current_time)
    price_cache.update("MES", Decimal("5100.00"), current_time)
    price_cache.update("MYM", Decimal("42000.00"), current_time)

    # Assert: Size is 3
    assert price_cache.size() == 3


@pytest.mark.unit
def test_cache_reports_cached_symbols(price_cache, current_time):
    """Test that cache can list all cached symbols."""
    # Setup: Cache symbols
    price_cache.update("MNQ", Decimal("18000.00"), current_time)
    price_cache.update("MES", Decimal("5100.00"), current_time)

    # Execute
    symbols = price_cache.get_symbols()

    # Assert: All symbols listed
    assert set(symbols) == {"MNQ", "MES"}


@pytest.mark.unit
def test_cache_clear_removes_all_entries(price_cache, current_time):
    """Test that clear() removes all cached entries."""
    # Setup: Cache multiple prices
    price_cache.update("MNQ", Decimal("18000.00"), current_time)
    price_cache.update("MES", Decimal("5100.00"), current_time)

    # Execute
    price_cache.clear()

    # Assert: Cache empty
    assert price_cache.size() == 0
    assert price_cache.get("MNQ") is None
    assert price_cache.get("MES") is None


# ============================================================================
# Thread Safety & Concurrency Tests
# ============================================================================


@pytest.mark.unit
def test_cache_handles_concurrent_updates_safely(price_cache, current_time):
    """Test that cache handles concurrent updates to same symbol safely."""
    # Note: This is a behavioral test - implementation should use locks
    # Actual concurrency testing would require threading/asyncio

    # Execute: Rapid updates to same symbol
    for i in range(100):
        price = Decimal(f"18000.{i:02d}")
        timestamp = current_time + timedelta(milliseconds=i)
        price_cache.update("MNQ", price, timestamp)

    # Assert: Last update wins
    cached_price = price_cache.get("MNQ")
    assert cached_price == Decimal("18000.99")


# ============================================================================
# Edge Cases & Error Handling
# ============================================================================


@pytest.mark.unit
def test_cache_handles_negative_prices_gracefully(price_cache, current_time):
    """Test that cache handles negative prices (shouldn't occur, but graceful handling)."""
    # Execute: Store negative price
    price_cache.update("MNQ", Decimal("-100.00"), current_time)

    # Assert: Stored (even if invalid)
    cached_price = price_cache.get("MNQ")
    assert cached_price == Decimal("-100.00")


@pytest.mark.unit
def test_cache_handles_zero_prices(price_cache, current_time):
    """Test that cache handles zero prices."""
    # Execute
    price_cache.update("MNQ", Decimal("0.00"), current_time)

    # Assert: Stored
    cached_price = price_cache.get("MNQ")
    assert cached_price == Decimal("0.00")


@pytest.mark.unit
def test_cache_handles_very_large_prices(price_cache, current_time):
    """Test that cache handles very large prices without overflow."""
    # Execute: Store large price
    large_price = Decimal("999999999.99")
    price_cache.update("MNQ", large_price, current_time)

    # Assert: Stored correctly
    cached_price = price_cache.get("MNQ")
    assert cached_price == large_price


@pytest.mark.unit
def test_cache_precision_preserved_for_decimal_prices(price_cache, current_time):
    """Test that cache preserves Decimal precision (no float conversion)."""
    # Execute: Store price with precise decimals
    precise_price = Decimal("18000.123456789")
    price_cache.update("MNQ", precise_price, current_time)

    # Assert: Precision preserved
    cached_price = price_cache.get("MNQ")
    assert cached_price == precise_price
    assert isinstance(cached_price, Decimal)


@pytest.mark.unit
def test_cache_handles_empty_symbol_name(price_cache, current_time):
    """Test that cache rejects empty symbol names."""
    # Execute & Assert: Should raise ValueError
    with pytest.raises(ValueError) as exc_info:
        price_cache.update("", Decimal("18000.00"), current_time)

    assert "symbol" in str(exc_info.value).lower()


@pytest.mark.unit
def test_cache_configurable_ttl(current_time):
    """Test that cache TTL is configurable at initialization."""
    # Setup: Cache with 30-second TTL
    cache_30s = PriceCache(max_age_seconds=30)
    cache_30s.update("MNQ", Decimal("18000.00"), current_time)

    # Execute: Check at 40 seconds (should be expired)
    check_time = current_time + timedelta(seconds=40)
    cached_price = cache_30s.get("MNQ", current_time=check_time)

    # Assert: Expired (30s TTL)
    assert cached_price is None


@pytest.mark.unit
def test_cache_with_infinite_ttl():
    """Test that cache can be configured with infinite TTL (never expires)."""
    # Setup: Cache with infinite TTL
    cache = PriceCache(max_age_seconds=None)  # None = no expiration
    timestamp = datetime(2025, 10, 15, 10, 0, 0, tzinfo=timezone.utc)

    cache.update("MNQ", Decimal("18000.00"), timestamp)

    # Execute: Check far in the future
    far_future = timestamp + timedelta(days=365)
    cached_price = cache.get("MNQ", current_time=far_future)

    # Assert: Still cached (never expires)
    assert cached_price == Decimal("18000.00")
