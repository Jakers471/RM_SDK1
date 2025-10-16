# SDK Adapter Layer Test Suite Summary

**Created**: 2025-10-16
**Status**: RED Phase (Tests Written, Implementation Pending)
**Total Tests**: 87
**TDD Phase**: RED → Implementation must conform to these tests

---

## Overview

This test suite defines the complete specification for the SDK adapter layer, which is the **#1 blocker** for the risk-daemon project. All tests are written following strict TDD principles:

1. ✅ Tests written FIRST (RED phase complete)
2. ⏳ Implementation NEXT (GREEN phase pending)
3. ⏳ Refactoring LAST (REFACTOR phase pending)

**CRITICAL**: Implementation must make these tests pass. Tests define the contract and behavior - code must conform to tests, NOT the other way around.

---

## Test Breakdown by Component

### 1. SDKAdapter Tests (`test_sdk_adapter.py`)
**Total**: 28 tests
**Purpose**: Test the 10 core adapter methods that interface with project-x-py SDK

#### Connection Management (5 tests)
- ✓ `test_connect_establishes_connection_successfully`
- ✓ `test_connect_raises_connection_error_on_authentication_failure`
- ✓ `test_disconnect_closes_connection_gracefully`
- ✓ `test_is_connected_returns_false_when_not_connected`
- ✓ `test_is_connected_returns_true_after_successful_connection`

#### Position Query (4 tests)
- ✓ `test_get_current_positions_returns_normalized_positions`
- ✓ `test_get_current_positions_returns_empty_list_when_no_positions`
- ✓ `test_get_current_positions_raises_query_error_on_sdk_failure`
- ✓ `test_get_current_positions_uses_default_account_id_when_not_provided`

#### PnL Query (2 tests)
- ✓ `test_get_account_pnl_calculates_unrealized_pnl_from_positions`
- ✓ `test_get_account_pnl_returns_zero_when_no_positions`

#### Order Execution (6 tests)
- ✓ `test_close_position_places_market_order_to_close`
- ✓ `test_close_position_closes_full_position_when_quantity_is_none`
- ✓ `test_close_position_raises_order_error_on_failure`
- ✓ `test_flatten_account_closes_all_positions`
- ✓ `test_flatten_account_returns_empty_list_when_no_positions`
- ✓ `test_flatten_account_continues_on_partial_failure`

#### Instrument Metadata (3 tests)
- ✓ `test_get_instrument_tick_value_returns_cached_value`
- ✓ `test_get_instrument_tick_value_caches_result`
- ✓ `test_get_instrument_tick_value_raises_instrument_error_on_not_found`

#### Price Query (2 tests)
- ✓ `test_get_current_price_returns_mid_price_from_quote`
- ✓ `test_get_current_price_raises_price_error_when_no_quote_available`

#### Event Handler Registration (2 tests)
- ✓ `test_register_event_handler_subscribes_to_sdk_events`
- ✓ `test_register_event_handler_supports_multiple_handlers`

#### Error Handling & Edge Cases (4 tests)
- ✓ `test_operations_raise_error_when_not_connected`
- ✓ `test_adapter_handles_connection_loss_during_operation`
- ✓ `test_adapter_retries_transient_errors_with_exponential_backoff`
- ✓ `test_adapter_does_not_retry_non_transient_errors`

---

### 2. EventNormalizer Tests (`test_event_normalizer.py`)
**Total**: 20 tests
**Purpose**: Test SDK event to internal event conversion (9 event types)

#### ORDER_FILLED Event Normalization (3 tests)
- ✓ `test_normalize_order_filled_creates_fill_event`
- ✓ `test_normalize_order_filled_extracts_symbol_from_contract_id`
- ✓ `test_normalize_order_filled_includes_correlation_id`

#### POSITION_UPDATED Event Normalization (3 tests)
- ✓ `test_normalize_position_updated_creates_position_update_event`
- ✓ `test_normalize_position_updated_calculates_pnl_using_tick_value`
- ✓ `test_normalize_position_updated_handles_short_positions`

#### CONNECTION_CHANGE Events (3 tests)
- ✓ `test_normalize_connected_creates_connection_change_event`
- ✓ `test_normalize_disconnected_creates_connection_change_event`
- ✓ `test_normalize_reconnecting_creates_connection_change_event`

#### QUOTE_UPDATE Processing (2 tests)
- ✓ `test_normalize_quote_update_updates_price_cache_without_event`
- ✓ `test_normalize_quote_update_caches_mid_price`

#### POSITION_CLOSED Processing (1 test)
- ✓ `test_normalize_position_closed_updates_state_without_event`

#### ORDER_REJECTED Processing (2 tests)
- ✓ `test_normalize_order_rejected_logs_error_without_event`
- ✓ `test_normalize_order_rejected_includes_rejection_details_in_log`

#### Edge Cases & Error Handling (6 tests)
- ✓ `test_normalize_unknown_event_type_returns_none`
- ✓ `test_normalize_handles_missing_required_fields`
- ✓ `test_normalize_handles_invalid_contract_id_format`
- ✓ `test_normalize_preserves_event_timestamp`
- ✓ `test_normalize_assigns_unique_event_id`
- ✓ `test_normalize_sets_source_as_sdk`

---

### 3. PriceCache Tests (`test_price_cache.py`)
**Total**: 21 tests
**Purpose**: Test price caching mechanism for PnL calculations

#### Basic Cache Operations (4 tests)
- ✓ `test_cache_stores_price_for_symbol`
- ✓ `test_cache_returns_none_for_unknown_symbol`
- ✓ `test_cache_updates_existing_price`
- ✓ `test_cache_stores_multiple_symbols_independently`

#### Cache Expiration (3 tests)
- ✓ `test_cache_expires_stale_prices`
- ✓ `test_cache_returns_fresh_prices_within_ttl`
- ✓ `test_cache_evicts_expired_entries_on_cleanup`

#### Cache Metadata (3 tests)
- ✓ `test_cache_tracks_last_update_timestamp`
- ✓ `test_cache_provides_age_of_cached_price`
- ✓ `test_cache_returns_none_age_for_unknown_symbol`

#### Cache Statistics (3 tests)
- ✓ `test_cache_reports_size`
- ✓ `test_cache_reports_cached_symbols`
- ✓ `test_cache_clear_removes_all_entries`

#### Thread Safety (1 test)
- ✓ `test_cache_handles_concurrent_updates_safely`

#### Edge Cases & Error Handling (7 tests)
- ✓ `test_cache_handles_negative_prices_gracefully`
- ✓ `test_cache_handles_zero_prices`
- ✓ `test_cache_handles_very_large_prices`
- ✓ `test_cache_precision_preserved_for_decimal_prices`
- ✓ `test_cache_handles_empty_symbol_name`
- ✓ `test_cache_configurable_ttl`
- ✓ `test_cache_with_infinite_ttl`

---

### 4. InstrumentCache Tests (`test_instrument_cache.py`)
**Total**: 18 tests
**Purpose**: Test instrument metadata caching (tick values, contract IDs)

#### Tick Value Cache (3 tests)
- ✓ `test_get_tick_value_queries_sdk_on_first_call`
- ✓ `test_get_tick_value_uses_cache_on_subsequent_calls`
- ✓ `test_get_tick_value_caches_different_symbols_independently`
- ✓ `test_get_tick_value_raises_error_on_sdk_failure`

#### Contract ID Cache (2 tests)
- ✓ `test_get_contract_id_queries_sdk_on_first_call`
- ✓ `test_get_contract_id_uses_cache_on_subsequent_calls`

#### Shared Cache (2 tests)
- ✓ `test_cache_shared_between_tick_value_and_contract_id`
- ✓ `test_cache_shared_reverse_order`

#### Cache Management (4 tests)
- ✓ `test_cache_can_be_cleared`
- ✓ `test_cache_can_invalidate_specific_symbol`
- ✓ `test_cache_reports_size`
- ✓ `test_cache_reports_cached_symbols`

#### Edge Cases & Error Handling (7 tests)
- ✓ `test_cache_handles_concurrent_queries_for_same_symbol`
- ✓ `test_cache_handles_empty_symbol_name`
- ✓ `test_cache_preserves_decimal_precision_for_tick_values`
- ✓ `test_cache_handles_sdk_returning_null_tick_value`
- ✓ `test_cache_handles_sdk_timeout`
- ✓ `test_cache_does_not_cache_failed_queries`

---

## Test Quality Standards

All tests follow these TDD best practices:

### ✅ Behavioral Test Names
- Names describe WHAT the code should do, not HOW
- Format: `test_<component>_<behavior>_<condition>`
- Example: `test_close_position_places_market_order_to_close` (good)
- NOT: `test_call_close_method` (bad - implementation detail)

### ✅ Async Testing
- All async tests use `@pytest.mark.asyncio`
- AsyncMock used for async functions
- Proper await syntax throughout

### ✅ Test Isolation
- Each test is independent
- Uses fixtures for setup
- No shared state between tests

### ✅ Comprehensive Coverage
- Happy path tested
- Error cases tested
- Edge cases tested
- Boundary conditions tested

### ✅ Clear Assertions
- Tests assert outcomes, not internals
- Single clear purpose per test
- Descriptive failure messages

---

## Implementation Requirements

To make these tests pass, you must implement:

### 1. Core Classes
```
src/adapters/
├── __init__.py
├── sdk_adapter.py          # SDKAdapter class (10 methods)
├── event_normalizer.py     # EventNormalizer class
├── price_cache.py          # PriceCache class
├── instrument_cache.py     # InstrumentCache class
└── exceptions.py           # Custom exceptions
```

### 2. SDKAdapter Methods (10 required)
1. `async connect()` - Establish broker connection
2. `async disconnect()` - Graceful shutdown
3. `is_connected()` - Check connection status
4. `async get_current_positions(account_id)` - Query positions
5. `async get_account_pnl(account_id)` - Calculate PnL
6. `async close_position(account_id, position_id, quantity)` - Close position
7. `async flatten_account(account_id)` - Close all positions
8. `async get_instrument_tick_value(symbol)` - Get tick value
9. `async get_current_price(symbol)` - Get market price
10. `register_event_handler(event_type, handler)` - Register handlers

### 3. Event Normalization (9 SDK events)
- ORDER_FILLED → FILL
- POSITION_UPDATED → POSITION_UPDATE
- CONNECTED/DISCONNECTED/RECONNECTING → CONNECTION_CHANGE
- QUOTE_UPDATE → Price cache update (no event)
- POSITION_CLOSED → State update (no event)
- ORDER_REJECTED → Log error (no event)

### 4. Custom Exceptions
```python
- SDKAdapterError (base)
- ConnectionError
- QueryError
- OrderError
- PriceError
- InstrumentError
```

---

## Running the Tests

### Run all adapter tests:
```bash
uv run pytest tests/unit/adapters/ -v
```

### Run specific test file:
```bash
uv run pytest tests/unit/adapters/test_sdk_adapter.py -v
uv run pytest tests/unit/adapters/test_event_normalizer.py -v
uv run pytest tests/unit/adapters/test_price_cache.py -v
uv run pytest tests/unit/adapters/test_instrument_cache.py -v
```

### Run with markers:
```bash
uv run pytest tests/unit/adapters/ -m unit -v
```

### Collect tests (no execution):
```bash
uv run pytest tests/unit/adapters/ --collect-only
```

---

## Current Status

### ✅ RED Phase Complete
- All 87 tests written and validated
- Tests define complete specification
- Tests fail as expected (no implementation yet)

### ⏳ GREEN Phase Pending
- Implementation must make all tests pass
- Follow Test-Driven Development strictly
- Write minimal code to pass each test

### ⏳ REFACTOR Phase Pending
- Improve design while keeping tests green
- Only after all tests pass

---

## Next Steps

1. **PRIORITY 1**: Implement `src/adapters/sdk_adapter.py`
   - Start with connection methods (tests 1-5)
   - Then position queries (tests 6-9)
   - Then order execution (tests 12-17)
   - Then metadata/price (tests 18-22)
   - Finally error handling (tests 25-28)

2. **PRIORITY 2**: Implement `src/adapters/event_normalizer.py`
   - Handle ORDER_FILLED first
   - Then POSITION_UPDATED
   - Then connection events
   - Then cache-only events

3. **PRIORITY 3**: Implement `src/adapters/price_cache.py`
   - Simple cache with TTL
   - Thread-safe operations

4. **PRIORITY 4**: Implement `src/adapters/instrument_cache.py`
   - Query deduplication
   - Shared cache for metadata

5. **PRIORITY 5**: Implement `src/adapters/exceptions.py`
   - Custom exception classes
   - Error wrapping

---

## Success Criteria

Implementation is complete when:
- ✅ All 87 tests pass
- ✅ No tests skipped or xfailed
- ✅ Coverage > 85% for adapter layer
- ✅ No changes to test files (except bug fixes)
- ✅ Code follows adapter contracts in `docs/integration/adapter_contracts.md`

---

## Important Notes

### TDD Violations to Avoid
- ❌ Writing implementation before tests
- ❌ Changing tests to match buggy code
- ❌ Skipping failing tests
- ❌ Testing implementation details
- ❌ Commenting out failing tests

### Acceptable Test Changes
- ✅ Fixing bugs in test logic
- ✅ Adding new tests for missed cases
- ✅ Improving test clarity
- ✅ Updating imports when moving files

---

**Document Status**: ✅ Complete
**Last Updated**: 2025-10-16
**Author**: Test Orchestrator (Claude Code)
**Ready For**: GREEN Phase Implementation
