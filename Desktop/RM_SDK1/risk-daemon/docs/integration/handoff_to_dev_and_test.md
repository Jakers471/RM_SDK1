# Handoff to Developer and Test-Orchestrator

## Executive Summary

**Integration Status**: ✅ **READY TO BUILD**

The project-x-py SDK analysis is complete. All required capabilities are either:
- ✅ Provided by SDK (75% of features)
- ✅ Buildable with documented approach (25% of features)

**Key Findings**:
1. SDK provides excellent event-driven architecture that aligns with Risk Manager design
2. Pre-trade rejection is impossible (architectural limitation) → enforce post-fill
3. Must build: PnL tracking, daily reset, state reconciliation, notifications
4. Expected integration effort: **4-6 days** for Developer + **2-3 days** for Test-Orchestrator

---

## For Developer: What to Implement

### Phase 1: Core SDK Integration (Day 1-2)

**Priority**: P0 (Critical Path)

#### 1.1 SDK Adapter (`src/adapters/sdk_adapter.py`)

**Purpose**: Abstract project-x-py SDK for Risk Manager

**Interface**: See [adapter_contracts.md](adapter_contracts.md#1-sdkadapter-class)

**Key Methods to Implement**:
```python
async def connect() → None
async def disconnect() → None
def is_connected() → bool
async def get_current_positions(account_id) → List[Position]
async def get_account_pnl(account_id) → dict
async def close_position(account_id, position_id, quantity) → OrderResult
async def flatten_account(account_id) → List[OrderResult]
async def get_instrument_tick_value(symbol) → Decimal
async def get_current_price(symbol) → Decimal
```

**SDK Dependencies**:
- `TradingSuite.create()` for initialization
- `client.search_open_positions()` for position queries
- `suite.orders.close_position()` for enforcement
- `suite.data.get_current_price()` for price data
- `client.get_instrument()` for tick values

**Error Handling**:
- Wrap all SDK exceptions in custom exceptions (see [adapter_contracts.md](adapter_contracts.md#5-error-handling))
- Retry transient errors (network timeouts) 3x with exponential backoff
- Log all errors with full context

**Testing**:
- Unit tests with mock SDK
- Integration tests with TopstepX sandbox (if available)

**Estimated Effort**: 1-1.5 days

---

#### 1.2 Event Normalizer (`src/adapters/event_normalizer.py`)

**Purpose**: Convert SDK events to internal Risk Manager events

**Interface**: See [adapter_contracts.md](adapter_contracts.md#2-eventnormalizer-class)

**Key Method**:
```python
async def normalize(sdk_event: SDKEvent) → Optional[Event]
```

**Event Mappings**: See [event_mapping.md](event_mapping.md#event-type-mappings)

| SDK Event | Internal Event | Fields to Extract |
|-----------|---------------|-------------------|
| `ORDER_FILLED` | `FILL` | symbol, side, quantity, fill_price, order_id, fill_time |
| `POSITION_UPDATED` | `POSITION_UPDATE` | position_id, symbol, current_price, unrealized_pnl, quantity |
| `CONNECTED`/`DISCONNECTED` | `CONNECTION_CHANGE` | status, reason, broker |

**Challenges**:
- POSITION_UPDATED doesn't include current price → must cache from QUOTE_UPDATE
- Must calculate unrealized PnL ourselves (SDK doesn't provide)

**Testing**:
- Test each event mapping with sample SDK payloads
- Verify data type conversions (float → Decimal, ISO string → datetime)

**Estimated Effort**: 0.5-1 day

---

#### 1.3 Instrument Cache (`src/adapters/instrument_cache.py`)

**Purpose**: Cache tick values to reduce API calls

**Interface**:
```python
async def get_tick_value(symbol: str) → Decimal
async def get_contract_id(symbol: str) → str
```

**Implementation**:
- Query SDK once per instrument
- Store in dict: `{symbol: InstrumentMetadata}`
- Refresh daily at 5pm CT

**Estimated Effort**: 0.25 days

---

### Phase 2: Custom Components (Day 3-4)

**Priority**: P0 (Core Features)

#### 2.1 Realized PnL Tracker (`src/state/pnl_tracker.py`)

**Purpose**: Track realized PnL with daily 5pm CT reset

**Requirements**:
- Maintain `realized_pnl_today` per account
- Update on position close (query trades, sum PnL)
- Reset at 5pm CT daily
- Persist across daemon restarts

**Implementation Guide**: See [gaps_and_build_plan.md](gaps_and_build_plan.md#gap-3-realized-pnl-tracking)

**Testing**:
- Verify PnL calculation matches broker
- Test daily reset timing (±5 seconds of 5pm CT)
- Test DST transitions

**Estimated Effort**: 1 day

---

#### 2.2 Session Timer (`src/timers/session_timer.py`)

**Purpose**: Generate SESSION_TICK events for daily reset

**Requirements**:
- Emit event at 5pm CT exactly once per day
- Handle DST transitions correctly (use pytz)
- Handle missed resets (daemon down during 5pm)

**Implementation Guide**: See [gaps_and_build_plan.md](gaps_and_build_plan.md#gap-5-daily-reset-logic-5pm-ct)

**Testing**:
- Unit test: verify 5pm detection logic
- Integration test: run for 48 hours, verify exactly 2 resets
- DST test: mock system time for March/November transitions

**Estimated Effort**: 0.5 days

---

#### 2.3 Time Tick Generator (`src/timers/time_tick.py`)

**Purpose**: Generate TIME_TICK events every 1 second

**Implementation**: See [gaps_and_build_plan.md](gaps_and_build_plan.md#gap-6-time_tick-events-1-second-interval)

**Estimated Effort**: 0.25 days

---

#### 2.4 Price Cache (`src/adapters/price_cache.py`)

**Purpose**: Maintain current prices for PnL calculations

**Requirements**:
- Update from QUOTE_UPDATE events (mid of bid/ask)
- Provide `get_price(symbol)` for unrealized PnL calc
- Detect stale prices (>60s old) → query REST API

**Implementation**:
```python
class PriceCache:
    def __init__(self):
        self._prices: Dict[str, Tuple[Decimal, datetime]] = {}

    async def update_from_quote(self, symbol: str, bid: Decimal, ask: Decimal):
        mid_price = (bid + ask) / 2
        self._prices[symbol] = (mid_price, datetime.utcnow())

    def get_price(self, symbol: str) → Optional[Decimal]:
        if symbol in self._prices:
            price, timestamp = self._prices[symbol]
            age = (datetime.utcnow() - timestamp).total_seconds()
            if age < 60:  # Fresh price
                return price
            logger.warning(f"Stale price for {symbol} ({age}s old)")
        return None
```

**Estimated Effort**: 0.25 days

---

### Phase 3: Reliability Features (Day 5)

**Priority**: P1 (Important)

#### 3.1 State Reconciliation (`src/adapters/state_reconciler.py`)

**Purpose**: Reconcile state after WebSocket disconnect/reconnect

**Implementation Guide**: See [gaps_and_build_plan.md](gaps_and_build_plan.md#gap-8-state-reconciliation-after-reconnect)

**Trigger**: On `CONNECTION_CHANGE` event with status="connected" (after disconnect)

**Estimated Effort**: 0.5 days

---

#### 3.2 Stop Loss Detector (`src/adapters/stop_loss_detector.py`)

**Purpose**: Detect if positions have stop loss attached

**Approach**:
1. Track SDK-placed brackets internally (100% accurate)
2. Poll orders every 30s for manually-placed stops

**Implementation Guide**: See [gaps_and_build_plan.md](gaps_and_build_plan.md#gap-7-stop-loss-detection)

**Estimated Effort**: 1 day

---

### Phase 4: Optional Features (Day 6)

**Priority**: P2 (Nice to Have)

#### 4.1 Notification Service (`src/notifications/`)

**Purpose**: Send alerts to Discord/Telegram

**Implementation**: See [gaps_and_build_plan.md](gaps_and_build_plan.md#gap-9-discordtelegram-notifications)

**Estimated Effort**: 0.5 days

---

## For Test-Orchestrator: What to Test

### Test Phase 1: Unit Tests (Day 1)

**Scope**: Test adapters in isolation with mocks

#### Mock SDK
Create `tests/mocks/mock_sdk.py`:
```python
class MockTradingSuite:
    def __init__(self):
        self.positions = []
        self.orders = []
        self.events = []

    async def on(self, event_type, handler):
        self.events.append((event_type, handler))

    # ... implement minimal SDK interface
```

#### Test Cases

**Test 1**: SDKAdapter.get_current_positions()
- Mock SDK returns 2 positions
- Verify correct conversion to internal Position type
- Verify symbol extraction from contractId

**Test 2**: EventNormalizer.normalize(ORDER_FILLED)
- Mock SDK event with fill data
- Verify internal FILL event created
- Verify all fields mapped correctly

**Test 3**: PnL Calculation
- Given position (long MNQ, entry=18000, size=1, current=18010)
- Verify unrealized PnL = (18010-18000) * 1 * $2 = $20

**Estimated Effort**: 1 day (10-15 unit tests)

---

### Test Phase 2: Integration Tests (Day 2)

**Scope**: Test with real SDK (TopstepX sandbox if available)

#### Setup
1. **TopstepX Sandbox Account** (if available)
   - Or: Paper trading account
2. **SDK Credentials**:
   - `PROJECT_X_API_KEY=sandbox_key`
   - `PROJECT_X_USERNAME=test_user`

#### Test Cases

**Test 1**: Full Connection Flow
1. Initialize SDK Adapter
2. Connect to broker
3. Verify WebSocket connected
4. Subscribe to events
5. Receive heartbeat/connection events
6. Disconnect gracefully

**Test 2**: Position Query
1. Manually open position via TopstepX web UI
2. Query positions via SDK Adapter
3. Verify position appears
4. Verify fields (symbol, size, entry price)

**Test 3**: Enforcement Flow (End-to-End)
1. Open position manually (1 contract MNQ)
2. Trigger rule violation (e.g., price moves to loss limit)
3. Verify POSITION_UPDATE event received
4. Verify rule evaluation triggered
5. Verify close order placed
6. Verify ORDER_FILLED event received
7. Verify position closed

**Test 4**: Daily Reset
1. Mock system time to 4:59pm CT
2. Wait 2 minutes
3. Verify SESSION_TICK event emitted at 5:00pm
4. Verify realized PnL reset to $0

**Test 5**: State Reconciliation
1. Open 2 positions
2. Disconnect WebSocket (simulate network loss)
3. Close 1 position manually (via web UI)
4. Reconnect WebSocket
5. Verify reconciliation detects closed position
6. Verify state updated correctly

**Estimated Effort**: 2 days (integration tests + debugging)

---

### Test Phase 3: Performance & Load Tests (Day 3)

**Scope**: Verify performance targets met

#### Performance Targets

| Metric | Target | Test |
|--------|--------|------|
| Enforcement latency | <500ms (95th percentile) | Simulate fills, measure time to close |
| Event processing | <10ms per event | Feed 1000 events, measure total time |
| Memory usage | <100MB steady state | Run for 24 hours, monitor RSS |
| State reconciliation | <5s | Disconnect, reconcile, measure time |

**Estimated Effort**: 1 day

---

## SDK Setup Instructions

### Installation

```bash
# In risk-daemon project
cd risk-daemon
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install SDK
pip install project-x-py==3.5.9

# Or with uv (faster)
uv add project-x-py
```

### Configuration

**Environment Variables** (`.env` file):
```bash
PROJECT_X_API_KEY=your_topstepx_api_key
PROJECT_X_USERNAME=your_username
PROJECT_X_ACCOUNT_ID=123456
```

**Or Config File** (`~/.config/risk-manager/config.json`):
```json
{
  "broker": {
    "platform": "topstepx",
    "api_key": "your_key",
    "username": "your_username"
  },
  "accounts": [
    {
      "account_id": 123456,
      "account_name": "My TopstepX Account",
      "enabled": true
    }
  ]
}
```

### Verify SDK Installation

```bash
python -c "import project_x_py; print(project_x_py.__version__)"
# Should print: 3.5.9
```

### Test Connection

```python
import asyncio
from project_x_py import TradingSuite

async def test_connection():
    suite = await TradingSuite.create("MNQ")
    print(f"Connected: {suite.client.account_info.name}")
    await suite.disconnect()

asyncio.run(test_connection())
```

---

## Sandbox/Test Environment

### TopstepX Sandbox

**Status**: ⚠️ **UNKNOWN** - Must verify with TopstepX support

**Questions for Product Owner**:
1. Does TopstepX provide sandbox environment for testing?
2. If not, can we use paper trading account?
3. What are rate limits for test accounts?

**Alternatives**:
1. **Mock SDK** for unit tests (Test-Orchestrator creates)
2. **Paper Trading Account** for integration tests (requires real credentials)
3. **Replay Test Data** (record SDK events, replay for testing)

---

## Development Workflow

### Day-by-Day Plan

**Day 1 (Developer + Test-Orchestrator)**:
- Developer: Implement SDKAdapter + EventNormalizer
- Test-Orchestrator: Create mock SDK + unit tests

**Day 2 (Developer)**:
- Developer: Implement InstrumentCache + PriceCache
- Test-Orchestrator: Continue unit tests

**Day 3 (Developer)**:
- Developer: Implement PnL Tracker + Session Timer
- Test-Orchestrator: Setup integration test environment

**Day 4 (Developer)**:
- Developer: Implement State Reconciliation + Stop Loss Detector
- Test-Orchestrator: Run integration tests

**Day 5 (Test-Orchestrator)**:
- Developer: Code review + bug fixes
- Test-Orchestrator: Performance tests + load tests

**Day 6 (Both)**:
- Developer: Implement optional features (notifications)
- Test-Orchestrator: Final regression tests
- **Code Freeze**: Hand off to Product Owner for UAT

---

## Success Criteria

### For Developer

✅ All adapter methods implemented per [adapter_contracts.md](adapter_contracts.md)
✅ All custom components built per [gaps_and_build_plan.md](gaps_and_build_plan.md)
✅ All unit tests passing (>80% code coverage)
✅ Integration tests passing with real SDK
✅ No known bugs or regressions
✅ Code reviewed and approved

### For Test-Orchestrator

✅ 100% of adapter methods have unit tests
✅ Integration tests verify end-to-end flows
✅ Performance targets met (enforcement <500ms)
✅ Edge cases tested (disconnect, DST, race conditions)
✅ Test report documents all findings
✅ Mock SDK suitable for CI/CD pipeline

---

## Key Documents Reference

1. **[sdk_survey.md](sdk_survey.md)** - SDK overview and capabilities
2. **[capabilities_matrix.md](capabilities_matrix.md)** - Requirements vs SDK features
3. **[adapter_contracts.md](adapter_contracts.md)** - Exact interfaces to implement
4. **[event_mapping.md](event_mapping.md)** - SDK events → internal events
5. **[gaps_and_build_plan.md](gaps_and_build_plan.md)** - What to build + how
6. **[risks_open_questions.md](risks_open_questions.md)** - Risks and mitigations
7. **[contracts/sdk_contract.json](../contracts/sdk_contract.json)** - Machine-readable contract

---

## Questions or Issues?

**For SDK Questions**:
- Consult project-x-py documentation: https://github.com/TexasCoding/project-x-py
- Check SDK examples: `../project-x-py/examples/`

**For Architecture Questions**:
- Review planner docs: `docs/architecture/*.md`
- Escalate to Product Owner if decision needed

**For Integration Issues**:
- Check [risks_open_questions.md](risks_open_questions.md) first
- Document new issues in `docs/integration/issues.md` (create if needed)

---

## Final Checklist

Before starting implementation:

- [ ] Developer has read all integration docs
- [ ] Test-Orchestrator has read all integration docs
- [ ] SDK installed and test connection successful
- [ ] Test environment confirmed (sandbox or paper account)
- [ ] Product Owner has approved integration approach
- [ ] Product Owner has answered open questions (Q11-Q15 in [risks_open_questions.md](risks_open_questions.md))
- [ ] Development timeline agreed (4-6 days)
- [ ] Git repository and branches set up
- [ ] CI/CD pipeline configured

---

**Good luck! The SDK integration is well-documented and straightforward. Reach out if you hit any blockers.**

---

**Document Status**: ✅ Complete
**Last Updated**: 2025-10-15
**Author**: RM-SDK-Analyst
**Approved By**: [Pending Product Owner Review]
