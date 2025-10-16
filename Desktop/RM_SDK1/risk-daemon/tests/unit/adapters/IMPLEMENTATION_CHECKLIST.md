# SDK Adapter Implementation Checklist

**Date**: 2025-10-16
**Status**: Ready for GREEN Phase
**Total Tests**: 87 (all failing, as expected)

---

## Implementation Order (Suggested)

Follow this order to implement the adapter layer incrementally:

### Phase 1: Exceptions & Base Models (Foundation)
**File**: `src/adapters/exceptions.py`
- [ ] Create `SDKAdapterError` base exception
- [ ] Create `ConnectionError` exception
- [ ] Create `QueryError` exception
- [ ] Create `OrderError` exception
- [ ] Create `PriceError` exception
- [ ] Create `InstrumentError` exception

**File**: `src/state/models.py` (add to existing)
- [ ] Add `OrderResult` dataclass (if not exists)

---

### Phase 2: PriceCache (Simplest Component)
**File**: `src/adapters/price_cache.py`
**Tests**: 21 tests in `test_price_cache.py`

Implement in this order:
1. [ ] `PriceCacheEntry` dataclass (price, timestamp)
2. [ ] `PriceCache.__init__(max_age_seconds)`
3. [ ] `PriceCache.update(symbol, price, timestamp)`
4. [ ] `PriceCache.get(symbol, current_time=None)`
5. [ ] `PriceCache.get_entry(symbol)`
6. [ ] `PriceCache.get_age(symbol, current_time)`
7. [ ] `PriceCache.size()`
8. [ ] `PriceCache.get_symbols()`
9. [ ] `PriceCache.clear()`
10. [ ] `PriceCache.cleanup(current_time)`

**Run tests after each method**:
```bash
uv run pytest tests/unit/adapters/test_price_cache.py -v
```

**Expected**: Tests should pass incrementally as you implement each method.

---

### Phase 3: InstrumentCache (Moderate Complexity)
**File**: `src/adapters/instrument_cache.py`
**Tests**: 18 tests in `test_instrument_cache.py`

Implement in this order:
1. [ ] `InstrumentMetadata` dataclass (symbol, tick_value, contract_id)
2. [ ] `InstrumentCache.__init__(client)`
3. [ ] `InstrumentCache._fetch_instrument(symbol)` (private, calls SDK)
4. [ ] `InstrumentCache.get_tick_value(symbol)` (with caching)
5. [ ] `InstrumentCache.get_contract_id(symbol)` (with caching)
6. [ ] `InstrumentCache.clear()`
7. [ ] `InstrumentCache.invalidate(symbol)`
8. [ ] `InstrumentCache.size()`
9. [ ] `InstrumentCache.get_symbols()`
10. [ ] Add query deduplication (optional optimization)

**Run tests after each method**:
```bash
uv run pytest tests/unit/adapters/test_instrument_cache.py -v
```

**Expected**: 18 tests should pass when complete.

---

### Phase 4: EventNormalizer (Most Complex Logic)
**File**: `src/adapters/event_normalizer.py`
**Tests**: 20 tests in `test_event_normalizer.py`

Implement in this order:
1. [ ] `EventNormalizer.__init__(state_manager, instrument_cache)`
2. [ ] `EventNormalizer._extract_symbol(contract_id)` (helper)
3. [ ] `EventNormalizer._calculate_unrealized_pnl(...)` (helper)
4. [ ] Handle `ORDER_FILLED` → `FILL` event
5. [ ] Handle `POSITION_UPDATED` → `POSITION_UPDATE` event
6. [ ] Handle `CONNECTED` → `CONNECTION_CHANGE` event
7. [ ] Handle `DISCONNECTED` → `CONNECTION_CHANGE` event
8. [ ] Handle `RECONNECTING` → `CONNECTION_CHANGE` event
9. [ ] Handle `QUOTE_UPDATE` (cache only, return None)
10. [ ] Handle `POSITION_CLOSED` (state update only, return None)
11. [ ] Handle `ORDER_REJECTED` (log only, return None)
12. [ ] Handle unknown events (return None)
13. [ ] Add `get_cached_price(symbol)` method

**Run tests after each event type**:
```bash
uv run pytest tests/unit/adapters/test_event_normalizer.py -v
```

**Expected**: 20 tests should pass when complete.

---

### Phase 5: SDKAdapter (Core Integration)
**File**: `src/adapters/sdk_adapter.py`
**Tests**: 28 tests in `test_sdk_adapter.py`

Implement in this order:

#### Step 1: Basic Structure (5 tests)
1. [ ] `SDKAdapter.__init__(api_key, username, account_id)`
2. [ ] `async connect()` - Create TradingSuite
3. [ ] `async disconnect()` - Close TradingSuite
4. [ ] `is_connected()` - Return connection status

**Run**:
```bash
uv run pytest tests/unit/adapters/test_sdk_adapter.py::test_connect_establishes_connection_successfully -v
uv run pytest tests/unit/adapters/test_sdk_adapter.py::test_is_connected_returns_false_when_not_connected -v
# etc...
```

#### Step 2: Position Queries (4 tests)
5. [ ] `async get_current_positions(account_id)` - Query & normalize
6. [ ] Handle empty positions
7. [ ] Handle query errors
8. [ ] Use default account_id when None

**Run**:
```bash
uv run pytest tests/unit/adapters/test_sdk_adapter.py -k "get_current_positions" -v
```

#### Step 3: PnL Queries (2 tests)
9. [ ] `async get_account_pnl(account_id)` - Calculate from positions

**Run**:
```bash
uv run pytest tests/unit/adapters/test_sdk_adapter.py -k "get_account_pnl" -v
```

#### Step 4: Order Execution (6 tests)
10. [ ] `async close_position(account_id, position_id, quantity)`
11. [ ] Handle quantity=None (close all)
12. [ ] Handle order errors
13. [ ] `async flatten_account(account_id)` - Loop positions
14. [ ] Handle empty account
15. [ ] Continue on partial failures

**Run**:
```bash
uv run pytest tests/unit/adapters/test_sdk_adapter.py -k "close_position or flatten" -v
```

#### Step 5: Metadata & Prices (5 tests)
16. [ ] `async get_instrument_tick_value(symbol)` - Use cache
17. [ ] Handle instrument not found
18. [ ] `async get_current_price(symbol)` - Query quote
19. [ ] Calculate mid price
20. [ ] Handle no quote available

**Run**:
```bash
uv run pytest tests/unit/adapters/test_sdk_adapter.py -k "tick_value or current_price" -v
```

#### Step 6: Event Handlers (2 tests)
21. [ ] `register_event_handler(event_type, handler)`
22. [ ] Support multiple handlers

**Run**:
```bash
uv run pytest tests/unit/adapters/test_sdk_adapter.py -k "register_event" -v
```

#### Step 7: Error Handling (4 tests)
23. [ ] Check connection before operations
24. [ ] Detect connection loss
25. [ ] Retry transient errors (3 attempts, exponential backoff)
26. [ ] Don't retry non-transient errors

**Run**:
```bash
uv run pytest tests/unit/adapters/test_sdk_adapter.py -k "error or retry or connected" -v
```

**Expected**: All 28 tests should pass when complete.

---

## Verification Commands

### Run all adapter tests:
```bash
uv run pytest tests/unit/adapters/ -v
```

### Run specific component:
```bash
uv run pytest tests/unit/adapters/test_price_cache.py -v
uv run pytest tests/unit/adapters/test_instrument_cache.py -v
uv run pytest tests/unit/adapters/test_event_normalizer.py -v
uv run pytest tests/unit/adapters/test_sdk_adapter.py -v
```

### Check coverage:
```bash
uv run pytest tests/unit/adapters/ --cov=src/adapters --cov-report=term-missing
```

### Run unit tests only:
```bash
uv run pytest tests/unit/adapters/ -m unit -v
```

---

## Success Criteria

- [ ] All 87 tests pass
- [ ] No tests skipped or xfailed
- [ ] Code coverage > 85% for `src/adapters/`
- [ ] No modifications to test files (except bug fixes)
- [ ] All custom exceptions implemented
- [ ] All 10 SDKAdapter methods implemented
- [ ] Event normalization handles all 9 SDK event types
- [ ] Price cache with configurable TTL
- [ ] Instrument cache with query deduplication

---

## Common Pitfalls to Avoid

### ❌ Don't Do This
1. Writing implementation before running tests
2. Changing tests to match your code
3. Skipping failing tests
4. Implementing features not tested
5. Testing private methods directly
6. Using sleep() for async tests
7. Hardcoding test values in implementation

### ✅ Do This Instead
1. Run test → See it fail (RED) → Write minimal code → See it pass (GREEN)
2. Keep tests unchanged (they define the contract)
3. Fix implementation to pass test
4. Only implement what tests require
5. Test public API only
6. Use AsyncMock for async operations
7. Use parameters and dependency injection

---

## Tips for Success

### Start Small
- Implement one method at a time
- Run tests after each method
- Don't move on until tests pass

### Use TDD Cycle
1. **RED**: Run test → See failure
2. **GREEN**: Write minimal code → See pass
3. **REFACTOR**: Improve code → Keep tests green

### Debug Failing Tests
```bash
# Run single test with full output
uv run pytest tests/unit/adapters/test_sdk_adapter.py::test_connect_establishes_connection_successfully -vv -s

# Run with pdb on failure
uv run pytest tests/unit/adapters/test_sdk_adapter.py --pdb

# Run with print statements visible
uv run pytest tests/unit/adapters/test_sdk_adapter.py -s
```

### Check Test Requirements
Before implementing, read the test to understand:
- What inputs it provides (fixtures, parameters)
- What it expects (assertions)
- What errors it should raise
- What edge cases it covers

---

## Integration with Rest of System

After adapter layer is complete:
1. Update `src/core/risk_engine.py` to use `SDKAdapter`
2. Update `src/core/enforcement_engine.py` to use `SDKAdapter`
3. Connect `EventNormalizer` to internal event bus
4. Update state manager to use normalized events
5. Run full test suite: `uv run pytest -v`

---

**Document Status**: ✅ Ready for Implementation
**Last Updated**: 2025-10-16
**Next Action**: Start Phase 1 (Exceptions & Base Models)
