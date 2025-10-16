# Risks and Open Questions

## Overview

This document identifies integration risks, unresolved questions, and recommended mitigation strategies for the Risk Manager Daemon integration with project-x-py SDK.

---

## CRITICAL RISKS

### RISK-1: Post-Fill Enforcement Latency

**Severity**: 🔴 CRITICAL
**Probability**: CERTAIN (architectural constraint)

**Description**:
Cannot block orders pre-trade. Enforcement happens **after** fill, introducing 120-500ms latency between rule violation and position close.

**Impact**:
- Per-trade loss limits may be exceeded by ~$10-50 during enforcement window
- Combined daily limits accurate (realized + unrealized checked in real-time)

**Mitigation**:
1. ✅ Set per-trade limits conservatively (e.g., $400 limit → close at $350 to account for latency)
2. ✅ Use market orders for instant execution (not limit orders)
3. ✅ Monitor enforcement latency metrics; alert if >500ms

**Acceptance Criteria**:
- 95% of enforcements complete within 500ms
- Max observed enforcement latency <1000ms

**Open Questions**:
- **Q1**: Should we add buffer to per-trade loss limits? (e.g., -$400 limit → enforce at -$350)
  - **Recommendation**: YES. Configure rule threshold = limit - (estimated_latency_loss).

---

### RISK-2: Race Condition During Account Flatten

**Severity**: 🟡 MEDIUM
**Probability**: LOW (requires precise timing)

**Description**:
When flattening account, new position might open between querying positions and closing them.

**Scenario**:
1. Query positions → [Position A, Position B]
2. Close Position A (OK)
3. **Trader opens Position C** (via web UI)
4. Close Position B (OK)
5. **Position C remains open** (not in original query)

**Impact**:
- Account not fully flattened
- Enforcement action incomplete

**Mitigation**:
1. ✅ After flatten, query positions again
2. ✅ If new positions found → close them (repeat until no positions)
3. ✅ Max 3 iterations to prevent infinite loop
4. ✅ Log all new positions discovered during flatten

**Implementation**:
```python
async def flatten_account_robust(account_id: str, max_iterations: int = 3):
    for iteration in range(max_iterations):
        positions = await client.search_open_positions(account_id)
        if not positions:
            break  # All closed

        for pos in positions:
            await close_position(pos.contractId)

        if iteration > 0:
            logger.warning(f"Flatten iteration {iteration}: found {len(positions)} new positions")

    # Final check
    final_positions = await client.search_open_positions(account_id)
    if final_positions:
        logger.critical(f"FLATTEN FAILED: {len(final_positions)} positions remain after {max_iterations} iterations")
```

**Open Questions**:
- **Q2**: Should we lock trading during flatten? (prevent new positions)
  - **Answer**: NO - cannot control TopstepX web UI. Log and alert instead.

---

### RISK-3: Missed Events During Disconnect

**Severity**: 🟡 MEDIUM
**Probability**: MEDIUM (network instability)

**Description**:
When WebSocket disconnects, events (fills, position updates) are **not replayed** upon reconnection.

**Impact**:
- Daemon state diverges from broker state
- Rules evaluated on stale data
- False positives (think position closed when it's open) or false negatives (miss violation)

**Mitigation**:
1. ✅ On reconnect → query REST API for positions, orders
2. ✅ Compare with cached state → log discrepancies
3. ✅ Re-evaluate all rules with reconciled state
4. ✅ Alert if significant discrepancies found

**Implementation**: See `Gap 8: State Reconciliation` in [gaps_and_build_plan.md](gaps_and_build_plan.md)

**Open Questions**:
- **Q3**: How to handle positions opened during disconnect?
  - **Answer**: Add to state, re-evaluate rules. If violates rule, close immediately.
- **Q4**: Should we lockout trading after disconnect until state reconciled?
  - **Recommendation**: NO - but flag account as "reconciling" and log all actions during this period.

---

### RISK-4: Stop Loss Detection Unreliable

**Severity**: 🟡 MEDIUM
**Probability**: MEDIUM (for manually-placed stops)

**Description**:
- SDK Position doesn't include stop loss metadata
- Must query all orders and match by contractId
- Cannot detect manually-placed stops instantly (polling lag)

**Impact**:
- NoStopLossGrace rule may trigger false positives (stop exists but not detected)
- Grace period might close position even if stop attached

**Mitigation**:
1. ✅ Track SDK-placed brackets internally (100% accuracy)
2. ✅ Poll orders every 30 seconds for manually-placed stops
3. ✅ Grace period = 2 minutes (allows time for detection)
4. ✅ Log all detected stops for audit

**Open Questions**:
- **Q5**: Should NoStopLossGrace rule be optional?
  - **Recommendation**: YES - make configurable. Some traders prefer manual stop management.

---

## MEDIUM RISKS

### RISK-5: Tick Value Hardcoded vs Dynamic

**Severity**: 🟡 MEDIUM
**Probability**: LOW (tick values rarely change)

**Description**:
Tick values (e.g., MNQ = $2/point) are queried from SDK but could change (contract rollover, exchange changes).

**Impact**:
- PnL calculations incorrect if tick value stale
- Rule thresholds based on wrong dollar amounts

**Mitigation**:
1. ✅ Query tick value from SDK (not hardcoded)
2. ✅ Cache per instrument, refresh daily
3. ✅ Log tick value changes for audit

**Open Questions**:
- **Q6**: How often to refresh tick values?
  - **Recommendation**: Daily at 5pm CT (with PnL reset).

---

### RISK-6: Price Cache Stale During Low Volume

**Severity**: 🟡 MEDIUM
**Probability**: LOW (futures are liquid)

**Description**:
If no quotes received for extended period (e.g., after-hours), price cache becomes stale.

**Impact**:
- Unrealized PnL calculations inaccurate
- DailyRealizedLoss rule may not trigger when it should

**Mitigation**:
1. ✅ Timestamp price cache entries
2. ✅ If price >60 seconds old → query REST API for latest price
3. ✅ Log stale price warnings

**Open Questions**:
- **Q7**: Should we disable PnL monitoring during low-volume hours?
  - **Recommendation**: NO - but increase refresh frequency via REST API queries.

---

### RISK-7: Timezone and DST Handling

**Severity**: 🟡 MEDIUM
**Probability**: MEDIUM (twice per year)

**Description**:
5pm CT daily reset must handle Daylight Saving Time transitions correctly.

**Impact**:
- Reset occurs at wrong time (4pm or 6pm) on DST switch days
- Realized PnL not reset properly

**Mitigation**:
1. ✅ Use `pytz` library (handles DST automatically)
2. ✅ Test explicitly for DST transition dates
3. ✅ Log reset time with timezone info

**Testing**:
- March 2nd Sunday (spring forward) → verify reset at 5pm CST → 5pm CDT
- November 1st Sunday (fall back) → verify reset at 5pm CDT → 5pm CST

**Open Questions**:
- **Q8**: Should we use CT (central) or always CST (standard)?
  - **Answer**: CT (America/Chicago) - pytz handles DST automatically.

---

## LOW RISKS

### RISK-8: Rate Limit Hit During Enforcement

**Severity**: 🟢 LOW
**Probability**: LOW (SDK has built-in throttling)

**Description**:
Rapid rule violations → many close orders → hit rate limit (60 req/min).

**Impact**:
- Order placement delayed
- Enforcement latency increased

**Mitigation**:
1. ✅ SDK RateLimiter queues requests automatically
2. ✅ Configure burst_limit=10 for enforcement bursts
3. ✅ Monitor rate limit warnings

**Open Questions**:
- **Q9**: Should we increase rate limit for enforcement actions?
  - **Recommendation**: NO - SDK default (60/min) sufficient for retail trader.

---

### RISK-9: Order Rejection During Enforcement

**Severity**: 🟢 LOW
**Probability**: LOW (market orders rarely rejected)

**Description**:
Enforcement close order rejected by broker (insufficient margin, invalid price, etc.).

**Impact**:
- Position remains open despite rule violation
- Critical enforcement failure

**Mitigation**:
1. ✅ Retry close order up to 3 times
2. ✅ If all fail → CRITICAL alert to admin
3. ✅ Log rejection reason for debugging
4. ✅ Fallback: lockout trading for account

**Open Questions**:
- **Q10**: Should we lockout trading after failed enforcement?
  - **Recommendation**: YES - safer to halt trading than allow violations.

---

## OPEN QUESTIONS

### Product Owner Decisions Needed

**Q11**: What is acceptable enforcement latency?
- **Current Target**: 95% < 500ms
- **Product Owner**: Approve or adjust?

**Q12**: Should per-trade loss limits include latency buffer?
- **Example**: -$400 limit → enforce at -$350 to account for lag
- **Product Owner**: Decide buffering strategy

**Q13**: How to handle enforcement failures?
- **Option A**: Lockout trading + admin alert
- **Option B**: Continue trading + log failure
- **Product Owner**: Choose policy

**Q14**: Should NoStopLossGrace rule be mandatory or optional?
- **Trade-off**: Safety (mandatory) vs. Flexibility (optional)
- **Product Owner**: Decide

**Q15**: Should we support multiple broker platforms in future?
- **Current**: TopstepX only
- **Future**: Add TradeStation, NinjaTrader, etc.?
- **Product Owner**: Roadmap decision

### Technical Decisions Needed (Developer/Test-Orchestrator)

**Q16**: Event queue size limit?
- **Recommendation**: 10,000 events (prevent memory overflow)
- **Developer**: Confirm or adjust

**Q17**: State persistence format?
- **Options**: SQLite, JSON file, PostgreSQL
- **Developer**: Choose based on performance needs

**Q18**: Mock SDK for testing?
- **Recommendation**: Create MockTradingSuite for unit tests
- **Test-Orchestrator**: Design mock interface

**Q19**: Integration test environment?
- **Options**: TopstepX sandbox, paper trading account
- **Test-Orchestrator**: Verify sandbox availability

**Q20**: Performance benchmarks?
- **Metrics**: Event processing time, enforcement latency, memory usage
- **Developer + Test-Orchestrator**: Define test suite

---

## Risk Mitigation Summary

| Risk ID | Severity | Mitigation Status | Owner |
|---------|----------|-------------------|-------|
| RISK-1 | CRITICAL | ✅ Documented + Metrics | Developer |
| RISK-2 | MEDIUM | ✅ Robust Algorithm Designed | Developer |
| RISK-3 | MEDIUM | ✅ Reconciliation Planned | Developer |
| RISK-4 | MEDIUM | ✅ Dual Detection Strategy | Developer |
| RISK-5 | MEDIUM | ✅ Dynamic Query Planned | Developer |
| RISK-6 | MEDIUM | ✅ Stale Price Detection | Developer |
| RISK-7 | MEDIUM | ✅ Pytz + DST Tests | Developer + Test-Orchestrator |
| RISK-8 | LOW | ✅ SDK Handles | N/A |
| RISK-9 | LOW | ✅ Retry + Lockout | Developer |

**Overall Risk Level**: 🟡 MEDIUM (acceptable with mitigations)

---

## Recommendation to Product Owner

**Proceed with Integration**: ✅ YES

**Rationale**:
1. ✅ All critical risks have documented mitigations
2. ✅ Post-fill enforcement latency is acceptable for use case (not HFT)
3. ✅ SDK is production-ready and well-maintained
4. ✅ Build effort is reasonable (4-6 days for Developer)

**Conditions**:
1. Product Owner must approve enforcement latency targets (Q11, Q12)
2. Product Owner must decide enforcement failure policy (Q13)
3. Developer must implement all mitigations in [gaps_and_build_plan.md](gaps_and_build_plan.md)
4. Test-Orchestrator must verify all mitigations via integration tests

---

**Document Status**: ✅ Complete
**Last Updated**: 2025-10-15
**Author**: RM-SDK-Analyst
**Approved By**: [Pending Product Owner Review]
