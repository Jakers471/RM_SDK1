# BACKGROUND RESEARCH: SDK Deep Analyzer Kickoff

**Agent**: sdk-deep-analyzer
**Model**: opus
**Priority**: Background (PARALLEL with Phase 1)
**Estimated Time**: 2-3 hours
**Status**: Ready to run

---

## 📖 FIRST: Read Your Agent Definition

**CRITICAL**: Before starting, read your complete agent definition:
```
agents/background-research/sdk-deep-analyzer.md
```

This file contains your full mission, constraints, and quality standards. The kickoff below is a quick-start summary.

---

## 🎯 Your Mission

You are the **sdk-deep-analyzer** agent. Deep dive into the project-x-py SDK to prepare detailed integration documentation for Phase 2 (live SDK connections). Work in PARALLEL with Phase 1 implementation.

## 📚 Required Reading

1. **../project-x-py/src/project_x_py/** (SDK source code)
   - trading_suite.py - Main entry point
   - position_manager/core.py - Position management
   - order_manager/core.py - Order management
   - event_bus.py - Event system
   - models.py - Data structures
   - All other SDK modules

2. **../project-x-py/docs/api/** (SDK documentation)
   - trading-suite.md
   - position-manager.md
   - order-manager.md
   - All API documentation

3. **docs/audits/04_SDK_Integration_Analysis.md**
   - Previous SDK analysis findings
   - Known mismatches and issues

4. **docs/integration/** (Current integration docs)
   - Understand current assumptions
   - Identify gaps

## 📝 Your Deliverables

### 1. docs/research/sdk_capability_deep_dive.md

**Comprehensive SDK Reference** containing:

- **Authentication Flow**
  - Step-by-step with code examples
  - Error handling (what exceptions to expect)
  - Token refresh/expiration handling

- **Event System Deep Dive**
  - Every event type with EXACT string names
  - Event data structures with EXACT field names
  - Event timing (real-time, batched, polled)
  - Subscription patterns (callbacks, async/await)
  - Event ordering guarantees

- **Position Management**
  - Exact field names (size vs quantity, averagePrice vs entry_price)
  - How to query positions (method signatures)
  - Position update mechanisms (push vs pull)
  - Unrealized P&L: Does SDK provide it? How to calculate?

- **Order Management**
  - Place order method signatures
  - Cancel/modify order methods
  - Order status lifecycle
  - Order acknowledgment latency

- **Realized P&L Tracking**
  - CRITICAL: Does SDK track cumulative realized P&L?
  - If not, how to calculate from trade fills?
  - What data is available?

- **Reconnection Behavior**
  - What happens on disconnect?
  - Must we resubscribe to events?
  - Is state lost?
  - Event replay capabilities?

- **Rate Limits and Throttling**
  - Exact rate limits (requests/second, requests/minute)
  - Does SDK handle backoff automatically?
  - What errors indicate rate limiting?

- **Performance Characteristics**
  - WebSocket vs REST endpoints
  - Typical latencies
  - Throughput limits

### 2. docs/research/sdk_integration_challenges.md

**Known Issues and Workarounds**:

- SDK bugs or quirks discovered
- Limitations and constraints
- Workarounds for missing features
- Breaking changes between SDK versions
- Edge cases to watch for

### 3. docs/research/live_testing_requirements.md

**Test Environment Setup**:

- What test account credentials are needed?
- How to obtain test broker account?
- Environment variable configuration
- Test data requirements
- Cleanup procedures (how to reset test account)
- Rate limit considerations for testing

## 🔍 Key Focus Areas (CRITICAL)

1. **Event Type Strings**
   - Verify exact strings: "ORDER_FILLED" vs "order.filled"?
   - Daemon expects uppercase, does SDK match?

2. **Position Data Model**
   - SDK uses: `size`, `averagePrice`, `type`
   - Daemon expects: `quantity`, `entry_price`, `side`, `unrealized_pnl`
   - Document EVERY field mismatch

3. **Realized P&L**
   - MUST determine: Does SDK track this?
   - If not, design calculation from fill events

4. **Authentication**
   - Document EXACT initialization sequence
   - Environment variables required
   - Error handling patterns

5. **Reconnection**
   - Test what happens on disconnect
   - Document state recovery requirements

## ✅ Success Criteria

You succeed when:
- [ ] Every SDK method documented with exact signature
- [ ] Every event type with exact field structure
- [ ] Authentication flow clearly documented
- [ ] Data model mismatches ALL identified
- [ ] Reconnection behavior understood
- [ ] Test environment requirements specified
- [ ] Phase 2 team can implement live connection from your docs alone

## 📊 Output Summary Template

```
✅ SDK Deep Analysis Complete

Created 3 Research Documents:
- sdk_capability_deep_dive.md (150+ SDK methods documented)
- sdk_integration_challenges.md (12 known issues identified)
- live_testing_requirements.md (test environment setup guide)

Key Findings:
- Event Types: [list critical findings]
- Position Model: [field mismatches]
- P&L Tracking: [SDK capabilities]
- Authentication: [flow documented]

Critical Issues for Phase 2:
1. [Most important finding]
2. [Second most important]
3. [Third most important]

Ready for Phase 2 Implementation: ✅
```

---

## 🚀 Ready to Start?

Dive deep into the SDK. Document EVERYTHING. Phase 2 depends on your thoroughness.

**BEGIN SDK DEEP ANALYSIS NOW.**
