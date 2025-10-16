# Handoff to SDK Analyst

## Purpose

This document hands off the Risk Manager Daemon architecture to the **SDK Analyst** agent, whose job is to analyze the `project-x-py` SDK and determine how to integrate it with our architecture. The SDK Analyst will **read-only** analyze the SDK (no code changes) and produce comprehensive integration documentation.

---

## What We've Built So Far

The **Planner** (me) has created a complete architecture for a professional-grade risk management daemon:

### Architecture Documents Created

1. **[00-overview.md](00-overview.md)** - System goals, components, philosophy
2. **[01-event-driven-core.md](01-event-driven-core.md)** - Event bus, SDK adapter design
3. **[02-risk-engine.md](02-risk-engine.md)** - 12 risk rules, combined PnL monitoring
4. **[03-enforcement-actions.md](03-enforcement-actions.md)** - 5 enforcement action types
5. **[04-state-management.md](04-state-management.md)** - Position tracking, PnL, timers
6. **[05-configuration-system.md](05-configuration-system.md)** - Config schema, validation
7. **[06-cli-interfaces.md](06-cli-interfaces.md)** - Admin and Trader CLI designs
8. **[07-notifications-logging.md](07-notifications-logging.md)** - Alerts and logging
9. **[08-daemon-service.md](08-daemon-service.md)** - Windows service, unkillable design
10. **[09-extensibility.md](09-extensibility.md)** - Plugin system for future features
11. **[10-data-flow-diagrams.md](10-data-flow-diagrams.md)** - Visual flows and decision trees
12. **[11-architecture-tree-and-ownership.md](11-architecture-tree-and-ownership.md)** - Repo layout, ownership
13. **[12-core-interfaces-and-events.md](12-core-interfaces-and-events.md)** - Core data types, events
14. **[13-non-functionals-and-ops.md](13-non-functionals-and-ops.md)** - Performance, reliability
15. **[14-backlog-and-open-questions.md](14-backlog-and-open-questions.md)** - First TDD tickets, decisions

**Status**: Architecture approved by Product Owner (ready for SDK integration analysis).

---

## Your Mission: SDK Integration Analysis

You are the **SDK Analyst**. Your job is to:

1. **Analyze `project-x-py` SDK** (read-only, no code changes)
2. **Map our architecture to SDK capabilities**
3. **Identify what SDK provides vs. what we must build**
4. **Define adapter contracts** (how to wire our architecture to SDK)
5. **Document integration flows** (event mapping, order execution)
6. **Identify gaps and risks**
7. **Create handoff documentation** for Developer and Test-Orchestrator

---

## Capabilities We Need from SDK

Below are the **SDK-agnostic capabilities** our architecture requires. Your job is to find how `project-x-py` provides these (if it does).

### 1. Authentication and Connection

**What we need**:
- Authenticate with TopstepX broker using API credentials
- Establish persistent connection (WebSocket, HTTP polling, etc.)
- Detect connection loss and reconnection
- Graceful disconnect on shutdown

**Questions for you**:
- How does SDK authenticate? (API keys, JWT, OAuth?)
- Does SDK auto-reconnect on disconnect?
- How do we detect connection status changes?
- What's the connection initialization sequence?

---

### 2. Event Subscriptions (Real-Time Updates)

**What we need**:
- Subscribe to fill events (new positions opened)
- Subscribe to position updates (price changes, PnL updates)
- Subscribe to order updates (order status, stop loss attached)
- Receive events via push (not polling if possible)

**Questions for you**:
- Does SDK provide event listeners/callbacks?
- What events are available? (fill, position_update, order_update, etc.)
- Are events push-based or do we poll?
- How do we register event handlers?
- What data is included in each event?

---

### 3. Position and Account Queries

**What we need**:
- Query current open positions for an account
- Get position details: symbol, side, quantity, entry price, current price
- Get account PnL (realized and unrealized, if SDK provides)

**Questions for you**:
- How to query current positions? (method/endpoint)
- What position data is returned?
- Does SDK provide unrealized PnL, or must we calculate?
- Does SDK provide realized PnL for the day?

---

### 4. Order Execution (Close Positions)

**What we need**:
- Close specific position (full or partial quantity)
- Flatten entire account (close all positions)
- Send market orders (for instant execution)
- Receive order confirmation (filled, price, quantity)

**Questions for you**:
- How to send close/flatten orders? (method/endpoint)
- Does SDK support "flatten all" natively?
- What order types are supported? (market, limit, stop)
- How do we get order confirmation? (event, callback, blocking call?)
- What's the typical order execution latency?

---

### 5. Stop Loss Detection

**What we need**:
- Detect if a position has a stop loss attached
- Get stop loss price (if available)

**Questions for you**:
- Does SDK expose stop loss info for positions?
- Is stop loss part of position data or separate order?
- How to detect if bracket/OCO orders exist?

---

### 6. Pre-Trade Rejection (Nice-to-Have)

**What we need (ideal)**:
- Block order from being placed (before fill)

**Questions for you**:
- Does SDK allow pre-trade validation/rejection?
- If not, what's the fastest way to close a just-filled position?

---

### 7. Price Data and Tick Values

**What we need**:
- Current mark/last price for calculating unrealized PnL
- Tick value per instrument (e.g., $5 per point for MNQ)

**Questions for you**:
- Does SDK provide current prices in position updates?
- Where do we get tick values? (SDK constant, config, API?)
- Is unrealized PnL calculated by SDK or must we compute?

---

### 8. Rate Limits and Backoff

**What we need**:
- Understand API rate limits (calls per second/minute)
- Recommended backoff/retry strategy

**Questions for you**:
- What are SDK rate limits?
- Does SDK handle rate limiting internally?
- Recommended retry strategy for failed calls?

---

## Adapters We Intend to Build

Based on our architecture, we will build the following **adapter modules** (you define the contracts):

### 1. SDK Adapter (`src/adapters/sdk_adapter.py`)

**Purpose**: Abstraction layer over `project-x-py` SDK

**Responsibilities**:
- Initialize SDK connection
- Handle authentication
- Provide clean interface for queries (get positions, get PnL)
- Provide clean interface for orders (close position, flatten account)
- Manage connection lifecycle

**Interface (SDK-agnostic, you fill in implementation details)**:
```python
class SDKAdapter:
    def connect(account_id: str, credentials: dict) -> None
    def disconnect() -> None
    def is_connected() -> bool

    def get_current_positions(account_id: str) -> list[Position]
    def get_account_pnl(account_id: str) -> dict  # {realized: Decimal, unrealized: Decimal}

    def close_position(account_id: str, position_id: str, quantity: int) -> OrderResult
    def flatten_account(account_id: str) -> list[OrderResult]
```

**Your job**: Define how each method maps to SDK calls.

---

### 2. Event Normalizer (`src/adapters/event_normalizer.py`)

**Purpose**: Convert SDK events to our internal `Event` type (defined in `12-core-interfaces-and-events.md`)

**Responsibilities**:
- Listen to SDK event callbacks
- Extract data from SDK event format
- Create our `Event` objects
- Publish to Event Bus

**Your job**: Document SDK event types and how to map them to our `EventType` enum.

---

## Blank Capability Matrix (You Fill This)

Complete this matrix to show what SDK provides vs. what we must build.

| Capability | SDK Provides? | SDK Method/Event | Notes | We Must Build? |
|------------|---------------|------------------|-------|----------------|
| **Authentication** | | | | |
| API key authentication | | | | |
| JWT/OAuth authentication | | | | |
| Auto-reconnect on disconnect | | | | |
| **Event Subscriptions** | | | | |
| Fill events (push) | | | | |
| Position update events (push) | | | | |
| Order update events (push) | | | | |
| Connection status events | | | | |
| **Position Queries** | | | | |
| Get current positions | | | | |
| Position details (symbol, qty, price) | | | | |
| Unrealized PnL (per position) | | | | |
| Realized PnL (daily) | | | | |
| **Order Execution** | | | | |
| Close position (market order) | | | | |
| Close position (partial qty) | | | | |
| Flatten account (all positions) | | | | |
| Order confirmation callback | | | | |
| **Stop Loss Detection** | | | | |
| Detect SL attached to position | | | | |
| Get SL price | | | | |
| Bracket/OCO order support | | | | |
| **Price Data** | | | | |
| Current mark/last price | | | | |
| Tick value per instrument | | | | |
| Historical price data | | | | |
| **Pre-Trade Rejection** | | | | |
| Block order before execution | | | | |
| **Rate Limits** | | | | |
| API calls per second limit | | | | |
| SDK enforces rate limits | | | | |

---

## Open Questions for SDK Analyst

Please answer these questions in your documentation:

### 1. Push vs. Pull for Position Updates?
- Does SDK push position updates automatically (WebSocket, callbacks)?
- Or must we poll (query positions periodically)?
- If polling, recommended frequency?

### 2. Unrealized PnL: Provided or Compute?
- Does SDK calculate unrealized PnL for us?
- If not, what price source should we use? (last price, mark price, bid/ask?)
- Where do we get tick/point value per symbol?

### 3. Authentication Details
- What credentials are required? (API key, secret, account number?)
- How are credentials passed to SDK? (constructor, method call, config file?)
- Does SDK handle token refresh (if JWT)?

### 4. Order Execution Acknowledgment and Latency
- How do we know when an order is filled? (callback, event, blocking call?)
- What's typical latency for market order execution?
- What error surfaces exist? (rejected, timeout, network error?)

### 5. Connection Recovery Semantics
- If connection drops, does SDK auto-reconnect?
- Do we need to re-subscribe to events after reconnect?
- Are missed events replayed, or must we query state?

### 6. Rate Limits and Recommended Backoff
- What are the actual rate limits? (X calls per Y seconds?)
- Does SDK queue requests internally to respect limits?
- Recommended retry/backoff strategy for failed requests?

### 7. Detecting Attached Stop Loss
- How do we know if a position has a stop loss? (order query, position metadata, separate subscription?)
- Are bracket orders (entry + SL + TP) supported?

### 8. Pre-Trade Reject Support?
- Can we reject an order before it's sent to exchange?
- If not, what's the fastest post-fill close path? (cancel-replace, market close?)

---

## Expected Deliverables from SDK Analyst

Create the following documents in `docs/integration/` (you own this directory):

### 1. `sdk_survey.md`
- Overview of `project-x-py` SDK
- Architecture (WebSocket, REST, hybrid?)
- Core classes and modules
- Event model (push/pull, callbacks, listeners)
- Authentication flow
- Order lifecycle
- Limitations and quirks

### 2. `capabilities_matrix.md`
- Completed version of the blank capability matrix above
- For each capability: SDK provides? How? Method/event name?
- What we must build custom

### 3. `adapter_contracts.md`
- Detailed specification for `SDKAdapter` class
- Each method: parameters, return type, SDK mapping, error handling
- Detailed specification for `EventNormalizer` class
- Event mappings: SDK event → our `Event` type

### 4. `event_mapping.md`
- Table of SDK events → our `EventType`
- Data extraction: SDK event payload → our `event.data` dict
- Example code snippets for each event type

### 5. `integration_flows.md`
- Sequence diagrams:
  - Connection and authentication
  - Fill event flow (broker → SDK → our Event Bus)
  - Position update flow
  - Order execution flow (our enforcement → SDK → broker)
  - Crash recovery and state reconciliation

### 6. `gaps_and_build_plan.md`
- Capabilities SDK doesn't provide (gaps)
- What we must build ourselves:
  - Timer events (TIME_TICK, SESSION_TICK)
  - Daily reset logic (5pm CT)
  - Unrealized PnL calculation (if SDK doesn't provide)
  - Idempotency tracking
  - Notification service
  - etc.
- Recommended build approach for each gap

### 7. `risks_open_questions.md`
- Integration risks (latency, reliability, data accuracy)
- Unresolved questions after SDK analysis
- Recommendations for Product Owner decisions
- Workarounds for SDK limitations

### 8. `handoff_to_dev_and_test.md`
- Summary for Developer: what to implement
- Summary for Test-Orchestrator: what to test and mock
- SDK setup instructions (installation, API credentials)
- Sandbox/test environment availability

### 9. `contracts/sdk_contract.json`
- Machine-readable contract (JSON schema)
- Event types, data structures, method signatures
- For Developer and Test-Orchestrator to reference

---

## Contract Format Example (sdk_contract.json)

```json
{
  "version": "1.0",
  "sdk_name": "project-x-py",
  "sdk_version": "X.Y.Z",
  "events": {
    "fill": {
      "sdk_event_name": "...",
      "our_event_type": "FILL",
      "priority": 2,
      "data_mapping": {
        "symbol": "event.instrument_symbol",
        "side": "event.order_side",
        "quantity": "event.filled_quantity",
        "fill_price": "event.execution_price",
        "order_id": "event.order_id"
      }
    }
  },
  "methods": {
    "get_current_positions": {
      "sdk_method": "...",
      "parameters": ["account_id"],
      "returns": "list[Position]",
      "example": "..."
    }
  },
  "tick_values": {
    "MNQ": 5.00,
    "ES": 50.00,
    "NQ": 20.00
  }
}
```

---

## What NOT to Do

**DO NOT**:
- Modify `project-x-py` SDK code (read-only analysis)
- Write any application code (Developer's job)
- Write tests (Test-Orchestrator's job)
- Make architecture decisions (Planner's job, already done)
- Modify files in `docs/architecture/` (read-only for you)

**DO**:
- Analyze SDK thoroughly
- Document SDK capabilities honestly (including limitations)
- Provide clear adapter contracts
- Ask questions if SDK behavior is unclear
- Recommend solutions for gaps

---

## Success Criteria

Your deliverables are successful if:

✅ **Developer** can implement adapters from your contracts (no guesswork)
✅ **Test-Orchestrator** can create mocks from your contracts
✅ **Product Owner** understands gaps and can make decisions
✅ **All questions answered** (or documented as unresolved with recommendations)
✅ **Integration risks identified** with mitigation strategies
✅ **Capability matrix complete** (no blank cells)

---

## Timeline and Approval Gate

1. **SDK Analyst** completes analysis and documentation
2. **Product Owner** reviews `docs/integration/` and `contracts/sdk_contract.json`
3. **Product Owner** approves or requests revisions
4. **Handoff** to Developer and Test-Orchestrator via `handoff_to_dev_and_test.md`

**Estimated effort**: 8-16 hours of SDK analysis and documentation (depending on SDK complexity).

---

## Resources Available to You

### Architecture Documents (Read-Only)
- All 15 architecture docs in `docs/architecture/`
- Focus on:
  - `01-event-driven-core.md` (SDK adapter design)
  - `12-core-interfaces-and-events.md` (Event types and data structures)
  - `13-non-functionals-and-ops.md` (Performance requirements)

### SDK Access
- `project-x-py` SDK (assumed available in Python environment)
- SDK documentation (if exists)
- SDK source code (read-only analysis)
- TopstepX API documentation (if publicly available)

### Questions and Support
- If SDK behavior is unclear, document as "Open Question" in `risks_open_questions.md`
- If critical capability is missing, escalate to Product Owner for decision
- If multiple implementation approaches exist, document pros/cons and recommend one

---

## Communication

**Your outputs** (in `docs/integration/` and `contracts/`) will be read by:
- Product Owner (approval)
- Developer (implementation)
- Test-Orchestrator (testing and mocking)

**Write for your audience**:
- Be precise and technical (developers need specifics)
- Be honest about limitations (don't over-promise)
- Be actionable (clear next steps for Developer)

---

## Final Checklist

Before marking your work complete, ensure:

- [ ] All 8 integration docs created in `docs/integration/`
- [ ] `contracts/sdk_contract.json` created and validated
- [ ] Capability matrix fully filled (no blanks)
- [ ] All 8 open questions answered (or documented as unresolved)
- [ ] Integration flows documented with sequence diagrams
- [ ] Gaps identified with build recommendations
- [ ] Risks documented with mitigation strategies
- [ ] Handoff doc explains clearly what Developer and Test-Orchestrator must do
- [ ] You are confident Developer can implement adapters from your contracts

---

## Good Luck!

You are a critical link in the chain. The architecture is complete, but it's just theory until you map it to the real SDK. Your analysis will determine:

- How feasible our architecture is
- What gaps we must fill
- How complex the integration will be
- Whether we can meet our <1s enforcement latency requirement

**Be thorough. Be honest. Be precise.**

The Product Owner, Developer, and Test-Orchestrator are counting on you to provide a rock-solid integration plan.

---

**Next Agent After You**: Developer (implements adapters) and Test-Orchestrator (writes tests)

**Handoff Document**: `docs/integration/handoff_to_dev_and_test.md`

**Questions?** Document them in `risks_open_questions.md` and recommend a path forward.
