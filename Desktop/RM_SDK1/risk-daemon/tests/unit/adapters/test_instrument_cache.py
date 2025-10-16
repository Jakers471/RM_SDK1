"""
Unit tests for InstrumentCache class.

Tests the instrument metadata caching mechanism that stores tick values,
contract IDs, and other instrument properties to avoid repeated SDK queries.

These tests are written FIRST (TDD RED phase) - implementation does not exist yet.
"""

from decimal import Decimal
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

# Import will fail initially - this is expected in RED phase
try:
    from src.adapters.instrument_cache import InstrumentCache, InstrumentMetadata
except ImportError:
    # Mark tests as expected to fail during RED phase
    pytestmark = pytest.mark.xfail(reason="InstrumentCache not implemented yet", strict=False)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_sdk_client():
    """Provide mock SDK client for instrument queries."""
    mock_client = MagicMock()
    mock_client.get_instrument = AsyncMock()
    return mock_client


@pytest.fixture
def instrument_cache(mock_sdk_client):
    """Provide InstrumentCache instance."""
    return InstrumentCache(client=mock_sdk_client)


# ============================================================================
# Tick Value Cache Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_tick_value_queries_sdk_on_first_call(instrument_cache, mock_sdk_client):
    """Test that get_tick_value() queries SDK on first call for a symbol."""
    # Setup: Mock SDK instrument response
    mock_instrument = MagicMock(
        symbol="MNQ",
        tickValue=Decimal("2.0"),
        contractId="CON.F.US.MNQ.U25"
    )
    mock_sdk_client.get_instrument = AsyncMock(return_value=mock_instrument)

    # Execute
    tick_value = await instrument_cache.get_tick_value("MNQ")

    # Assert: SDK queried once
    assert tick_value == Decimal("2.0")
    mock_sdk_client.get_instrument.assert_called_once_with("MNQ")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_tick_value_uses_cache_on_subsequent_calls(instrument_cache, mock_sdk_client):
    """Test that get_tick_value() uses cache on subsequent calls (no SDK query)."""
    # Setup: Mock SDK instrument response
    mock_instrument = MagicMock(
        symbol="MNQ",
        tickValue=Decimal("2.0"),
        contractId="CON.F.US.MNQ.U25"
    )
    mock_sdk_client.get_instrument = AsyncMock(return_value=mock_instrument)

    # Execute: Call twice
    tick_value_1 = await instrument_cache.get_tick_value("MNQ")
    tick_value_2 = await instrument_cache.get_tick_value("MNQ")

    # Assert: SDK queried only once (second call from cache)
    assert tick_value_1 == tick_value_2
    assert mock_sdk_client.get_instrument.call_count == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_tick_value_caches_different_symbols_independently(instrument_cache, mock_sdk_client):
    """Test that get_tick_value() caches different symbols independently."""
    # Setup: Mock responses for different symbols
    async def mock_get_instrument(symbol: str):
        instruments = {
            "MNQ": MagicMock(symbol="MNQ", tickValue=Decimal("2.0")),
            "MES": MagicMock(symbol="MES", tickValue=Decimal("5.0")),
            "MYM": MagicMock(symbol="MYM", tickValue=Decimal("0.5"))
        }
        return instruments[symbol]

    mock_sdk_client.get_instrument = AsyncMock(side_effect=mock_get_instrument)

    # Execute: Query different symbols
    mnq_tick = await instrument_cache.get_tick_value("MNQ")
    mes_tick = await instrument_cache.get_tick_value("MES")
    mym_tick = await instrument_cache.get_tick_value("MYM")

    # Assert: All cached independently with correct values
    assert mnq_tick == Decimal("2.0")
    assert mes_tick == Decimal("5.0")
    assert mym_tick == Decimal("0.5")
    assert mock_sdk_client.get_instrument.call_count == 3


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_tick_value_raises_error_on_sdk_failure(instrument_cache, mock_sdk_client):
    """Test that get_tick_value() propagates SDK errors."""
    # Setup: Mock SDK raises exception
    mock_sdk_client.get_instrument = AsyncMock(
        side_effect=Exception("Instrument not found")
    )

    # Execute & Assert
    with pytest.raises(Exception) as exc_info:
        await instrument_cache.get_tick_value("INVALID")

    assert "not found" in str(exc_info.value)


# ============================================================================
# Contract ID Cache Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_contract_id_queries_sdk_on_first_call(instrument_cache, mock_sdk_client):
    """Test that get_contract_id() queries SDK on first call for a symbol."""
    # Setup: Mock SDK response
    mock_instrument = MagicMock(
        symbol="MNQ",
        contractId="CON.F.US.MNQ.U25",
        tickValue=Decimal("2.0")
    )
    mock_sdk_client.get_instrument = AsyncMock(return_value=mock_instrument)

    # Execute
    contract_id = await instrument_cache.get_contract_id("MNQ")

    # Assert: Returns contract ID
    assert contract_id == "CON.F.US.MNQ.U25"
    mock_sdk_client.get_instrument.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_contract_id_uses_cache_on_subsequent_calls(instrument_cache, mock_sdk_client):
    """Test that get_contract_id() uses cache on subsequent calls."""
    # Setup
    mock_instrument = MagicMock(
        symbol="MNQ",
        contractId="CON.F.US.MNQ.U25",
        tickValue=Decimal("2.0")
    )
    mock_sdk_client.get_instrument = AsyncMock(return_value=mock_instrument)

    # Execute: Call twice
    contract_id_1 = await instrument_cache.get_contract_id("MNQ")
    contract_id_2 = await instrument_cache.get_contract_id("MNQ")

    # Assert: Cached (SDK queried once)
    assert contract_id_1 == contract_id_2
    assert mock_sdk_client.get_instrument.call_count == 1


# ============================================================================
# Shared Cache Tests (Tick Value + Contract ID)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_shared_between_tick_value_and_contract_id(instrument_cache, mock_sdk_client):
    """Test that tick value and contract ID queries share the same cache entry."""
    # Setup
    mock_instrument = MagicMock(
        symbol="MNQ",
        contractId="CON.F.US.MNQ.U25",
        tickValue=Decimal("2.0")
    )
    mock_sdk_client.get_instrument = AsyncMock(return_value=mock_instrument)

    # Execute: Query tick value first, then contract ID
    tick_value = await instrument_cache.get_tick_value("MNQ")
    contract_id = await instrument_cache.get_contract_id("MNQ")

    # Assert: SDK queried only once (shared cache)
    assert tick_value == Decimal("2.0")
    assert contract_id == "CON.F.US.MNQ.U25"
    assert mock_sdk_client.get_instrument.call_count == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_shared_reverse_order(instrument_cache, mock_sdk_client):
    """Test that contract ID query first, then tick value, shares cache."""
    # Setup
    mock_instrument = MagicMock(
        symbol="MES",
        contractId="CON.F.US.MES.U25",
        tickValue=Decimal("5.0")
    )
    mock_sdk_client.get_instrument = AsyncMock(return_value=mock_instrument)

    # Execute: Query contract ID first, then tick value
    contract_id = await instrument_cache.get_contract_id("MES")
    tick_value = await instrument_cache.get_tick_value("MES")

    # Assert: SDK queried only once (shared cache)
    assert contract_id == "CON.F.US.MES.U25"
    assert tick_value == Decimal("5.0")
    assert mock_sdk_client.get_instrument.call_count == 1


# ============================================================================
# Cache Management Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_can_be_cleared(instrument_cache, mock_sdk_client):
    """Test that cache can be cleared, forcing re-query on next access."""
    # Setup: Cache some instruments
    mock_instrument = MagicMock(
        symbol="MNQ",
        contractId="CON.F.US.MNQ.U25",
        tickValue=Decimal("2.0")
    )
    mock_sdk_client.get_instrument = AsyncMock(return_value=mock_instrument)

    await instrument_cache.get_tick_value("MNQ")
    assert mock_sdk_client.get_instrument.call_count == 1

    # Execute: Clear cache
    instrument_cache.clear()

    # Query again
    await instrument_cache.get_tick_value("MNQ")

    # Assert: SDK queried again (cache was cleared)
    assert mock_sdk_client.get_instrument.call_count == 2


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_can_invalidate_specific_symbol(instrument_cache, mock_sdk_client):
    """Test that cache can invalidate specific symbol without clearing all."""
    # Setup: Cache multiple symbols
    async def mock_get_instrument(symbol: str):
        instruments = {
            "MNQ": MagicMock(symbol="MNQ", tickValue=Decimal("2.0")),
            "MES": MagicMock(symbol="MES", tickValue=Decimal("5.0"))
        }
        return instruments[symbol]

    mock_sdk_client.get_instrument = AsyncMock(side_effect=mock_get_instrument)

    await instrument_cache.get_tick_value("MNQ")
    await instrument_cache.get_tick_value("MES")
    assert mock_sdk_client.get_instrument.call_count == 2

    # Execute: Invalidate only MNQ
    instrument_cache.invalidate("MNQ")

    # Query again
    await instrument_cache.get_tick_value("MNQ")  # Re-query
    await instrument_cache.get_tick_value("MES")  # From cache

    # Assert: MNQ re-queried, MES still cached
    assert mock_sdk_client.get_instrument.call_count == 3


@pytest.mark.unit
def test_cache_reports_size(instrument_cache, mock_sdk_client):
    """Test that cache reports number of cached instruments."""
    # This test is synchronous since size() should be sync
    # We'll need to populate cache first using asyncio.run or similar

    # For now, test the interface exists
    size = instrument_cache.size()
    assert size == 0  # Empty initially


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_reports_cached_symbols(instrument_cache, mock_sdk_client):
    """Test that cache can list all cached symbols."""
    # Setup: Cache multiple symbols
    async def mock_get_instrument(symbol: str):
        return MagicMock(symbol=symbol, tickValue=Decimal("2.0"))

    mock_sdk_client.get_instrument = AsyncMock(side_effect=mock_get_instrument)

    await instrument_cache.get_tick_value("MNQ")
    await instrument_cache.get_tick_value("MES")

    # Execute
    symbols = instrument_cache.get_symbols()

    # Assert: All cached symbols listed
    assert set(symbols) == {"MNQ", "MES"}


# ============================================================================
# Edge Cases & Error Handling
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_handles_concurrent_queries_for_same_symbol(instrument_cache, mock_sdk_client):
    """Test that cache handles concurrent queries for same symbol (deduplication)."""
    # Setup: Mock SDK with slow response
    mock_instrument = MagicMock(
        symbol="MNQ",
        contractId="CON.F.US.MNQ.U25",
        tickValue=Decimal("2.0")
    )

    # Simulate slow SDK call
    async def slow_get_instrument(symbol: str):
        await asyncio.sleep(0.1)  # 100ms delay
        return mock_instrument

    mock_sdk_client.get_instrument = AsyncMock(side_effect=slow_get_instrument)

    # Execute: Fire multiple concurrent queries
    import asyncio
    results = await asyncio.gather(
        instrument_cache.get_tick_value("MNQ"),
        instrument_cache.get_tick_value("MNQ"),
        instrument_cache.get_tick_value("MNQ")
    )

    # Assert: All return same value, SDK queried only once (deduplication)
    assert all(r == Decimal("2.0") for r in results)
    assert mock_sdk_client.get_instrument.call_count == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_handles_empty_symbol_name(instrument_cache):
    """Test that cache rejects empty symbol names."""
    # Execute & Assert
    with pytest.raises(ValueError) as exc_info:
        await instrument_cache.get_tick_value("")

    assert "symbol" in str(exc_info.value).lower()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_preserves_decimal_precision_for_tick_values(instrument_cache, mock_sdk_client):
    """Test that cache preserves Decimal precision for tick values."""
    # Setup: Mock instrument with precise tick value
    mock_instrument = MagicMock(
        symbol="MNQ",
        tickValue=Decimal("2.000000001"),  # Very precise
        contractId="CON.F.US.MNQ.U25"
    )
    mock_sdk_client.get_instrument = AsyncMock(return_value=mock_instrument)

    # Execute
    tick_value = await instrument_cache.get_tick_value("MNQ")

    # Assert: Precision preserved
    assert tick_value == Decimal("2.000000001")
    assert isinstance(tick_value, Decimal)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_handles_sdk_returning_null_tick_value(instrument_cache, mock_sdk_client):
    """Test that cache handles SDK returning None/null for tick value."""
    # Setup: Mock SDK returns instrument with None tick value
    mock_instrument = MagicMock(
        symbol="INVALID",
        tickValue=None,  # Missing tick value
        contractId="CON.F.US.INVALID.U25"
    )
    mock_sdk_client.get_instrument = AsyncMock(return_value=mock_instrument)

    # Execute & Assert: Should raise ValueError
    with pytest.raises(ValueError) as exc_info:
        await instrument_cache.get_tick_value("INVALID")

    assert "tick value" in str(exc_info.value).lower()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_handles_sdk_timeout(instrument_cache, mock_sdk_client):
    """Test that cache handles SDK timeout gracefully."""
    # Setup: Mock SDK timeout
    import asyncio
    mock_sdk_client.get_instrument = AsyncMock(
        side_effect=asyncio.TimeoutError("SDK query timeout")
    )

    # Execute & Assert: Should propagate timeout
    with pytest.raises(asyncio.TimeoutError):
        await instrument_cache.get_tick_value("MNQ")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_does_not_cache_failed_queries(instrument_cache, mock_sdk_client):
    """Test that cache does NOT cache failed SDK queries."""
    # Setup: SDK fails first time, succeeds second time
    call_count = 0

    async def mock_get_instrument(symbol: str):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Temporary failure")
        return MagicMock(symbol=symbol, tickValue=Decimal("2.0"))

    mock_sdk_client.get_instrument = AsyncMock(side_effect=mock_get_instrument)

    # Execute: First call fails
    with pytest.raises(Exception):
        await instrument_cache.get_tick_value("MNQ")

    # Second call should retry (not cached)
    tick_value = await instrument_cache.get_tick_value("MNQ")

    # Assert: Second call succeeded, SDK queried twice
    assert tick_value == Decimal("2.0")
    assert call_count == 2
