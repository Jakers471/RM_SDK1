# Product Owner Decisions - APPROVED

## Decision Log

**Date**: 2025-10-15
**Product Owner**: Jake
**Status**: ✅ APPROVED - Ready for Development

---

## Critical Decisions

### Q11: Enforcement Latency Target ✅ APPROVED

**Question**: What is acceptable enforcement latency?

**Decision**: **500ms or less is fantastic** (approved)

**Implementation**:
- Target: 95th percentile < 500ms
- Maximum: <1000ms
- Monitoring: Log all enforcement actions with timestamps
- Alert if >500ms occurs more than 5% of the time

---

### Q12: Per-Trade Loss Limit Buffer ✅ APPROVED

**Question**: Should per-trade loss limits include latency buffer?

**Decision**: **No buffer for now** - keep limits as configured

**Rationale**:
- Can readjust in the future if needed
- Start with actual limits, monitor real-world performance
- If violations consistently exceed limits during enforcement window, revisit

**Implementation**:
- Rule threshold = configured limit (no adjustment)
- Example: $400 loss limit → trigger at exactly -$400.00

---

### Q13: Enforcement Failure Policy ✅ APPROVED

**Question**: How to handle enforcement failures?

**Decision**: **Option B - Continue trading + log failure**

**Implementation**:
```python
async def handle_enforcement_failure(order_result: OrderResult, violation: RuleViolation):
    # Log the failure
    logger.critical(
        f"ENFORCEMENT FAILED: {violation.rule_name} - {order_result.error_message}"
    )

    # Continue trading (do NOT lockout)
    # Alert admin for manual intervention
    await notification_service.alert_critical(
        f"Enforcement failed for {violation.account_id}: {order_result.error_message}"
    )

    # Record in enforcement history for audit
    enforcement_tracker.record_failure(violation, order_result)
```

**Rationale**: Less disruptive than lockout, allows trader to continue while admin investigates

---

### Q14: NoStopLossGrace Rule - Mandatory or Optional ✅ APPROVED

**Question**: Should NoStopLossGrace rule be mandatory?

**Decision**: **Mandatory**

**Implementation**:
- NoStopLossGrace rule ALWAYS enabled
- Cannot be disabled via config
- Grace period configurable (default: 2 minutes)

**Config Example**:
```json
{
  "rules": {
    "NoStopLossGrace": {
      "enabled": true,  // Cannot be set to false
      "grace_period_seconds": 120,
      "action": "close_position"
    }
  }
}
```

---

### Q15: Multi-Broker Support ✅ APPROVED (Future)

**Question**: Should we support multiple broker platforms in the future?

**Decision**: **Yes, but not any time soon** - TopstepX only for now

**Roadmap**:
- **Phase 1** (Now): TopstepX only
- **Phase 2** (Future - TBD): Consider TradeStation, NinjaTrader, etc.
- **Design**: Keep SDK adapter abstracted to allow easy broker switching later

**Implementation Note**:
- SDKAdapter interface is broker-agnostic
- Adding new broker = implement new adapter with same interface
- No refactoring of core daemon needed

---

## Technical Decisions

### Q16: Event Queue Size Limit ✅ APPROVED

**Question**: Event queue size limit?

**Decision**: **10,000 events is plenty**

**Implementation**:
```python
EVENT_QUEUE_MAX_SIZE = 10_000

class EventBus:
    def __init__(self):
        self._queue = asyncio.Queue(maxsize=EVENT_QUEUE_MAX_SIZE)

    async def publish(self, event: Event):
        if self._queue.full():
            logger.critical(f"Event queue full ({EVENT_QUEUE_MAX_SIZE} events)!")
            await notification_service.alert_critical("Event queue overflow - daemon degraded")

        await self._queue.put(event)
```

---

### Q17: State Persistence Format ✅ APPROVED

**Question**: State persistence format - SQLite, JSON, or PostgreSQL?

**Decision**: **SQLite** (Product Owner approved based on recommendation)

**Rationale**:
- Embedded database (no separate server)
- ACID transactions (data integrity)
- Good performance for our use case
- Easy backup (single file)
- Supports complex queries if needed later

**Implementation**:
```python
# Database: ~/.risk_manager/state.db

# Tables:
# - account_state (account_id, realized_pnl, unrealized_pnl, last_reset, ...)
# - positions (position_id, account_id, symbol, side, quantity, entry_price, ...)
# - enforcement_history (timestamp, account_id, rule_name, action, reason, ...)
```

**File Location**: `~/.risk_manager/state.db`

**Backup Strategy**: Daily snapshot before 5pm reset

---

### Q18: Mock SDK for Testing ✅ APPROVED

**Question**: Create mock SDK for testing?

**Decision**: **Yes**

**Implementation**: Test-Orchestrator will create `tests/mocks/mock_sdk.py`

**Requirements**:
- Mock TradingSuite with minimal interface
- Mock EventBus for event testing
- Mock Position/Order objects
- Allow injecting test data (positions, events)

---

### Q19: Integration Test Environment ✅ APPROVED

**Question**: Integration test environment?

**Decision**: **Paper trading account** (practice account)

**Details**:
- Use existing practice account
- Same authentication as live (API key + username)
- Just switch account name in config
- Can test real orders without risk

**Setup**:
```python
# Test config
TEST_CONFIG = {
    "api_key": os.getenv("PROJECT_X_API_KEY"),  # Same as production
    "username": os.getenv("PROJECT_X_USERNAME"), # Same as production
    "account_name": "Practice Account"  # Different account name
}
```

---

### Q20: Performance Benchmarks ✅ APPROVED

**Question**: What performance metrics to track?

**Decision**: **YES - Track all recommended metrics** (Product Owner approved)

**3 Critical Metrics** (MUST track):

1. **Enforcement Latency** (CRITICAL)
   - Measure: Time from FILL event received → close order placed
   - Target: <500ms (95th percentile)
   - Alert: If >500ms occurs >5% of the time

2. **Event Processing Time** (IMPORTANT)
   - Measure: Time to process single event (rule evaluation)
   - Target: <10ms per event
   - Alert: If >50ms (indicates performance issue)

3. **Memory Usage** (IMPORTANT)
   - Measure: RSS memory over 24-hour period
   - Target: <100MB steady state
   - Alert: If >200MB or growing trend

**Additional Metrics** (ALSO track - approved):
4. **State Reconciliation Time** (after disconnect)
   - Measure: Time to query REST API and reconcile state
   - Target: <5 seconds
   - Alert: If >10 seconds

5. **Queue Depth** (event backlog)
   - Measure: Number of events pending in queue
   - Target: <100 events normally
   - Alert: If >1000 events (approaching limit)

6. **Rule Evaluation Time** (per rule performance)
   - Measure: Time to evaluate each rule type
   - Target: <5ms per rule
   - Alert: If any rule >20ms (optimization needed)

**Implementation**:
```python
class PerformanceTracker:
    def record_enforcement_latency(self, latency_ms: float):
        self.enforcement_latencies.append(latency_ms)

        # Check P95
        if len(self.enforcement_latencies) >= 100:
            p95 = np.percentile(self.enforcement_latencies, 95)
            if p95 > 500:
                logger.warning(f"Enforcement latency P95: {p95:.1f}ms (target: <500ms)")
```

---

## Async Testing Requirements ✅ NOTED

**Requirement**: All tests MUST follow async patterns from `project-x-py/.cursor/rules/async_testing.md`

**Critical Rules**:
1. ✅ Always use `@pytest.mark.asyncio` for async tests
2. ✅ Use `AsyncMock` for async methods
3. ✅ Use `aioresponses` for HTTP mocking
4. ✅ Properly test async context managers
5. ✅ Never use `asyncio.run()` in test methods
6. ✅ Always cleanup async resources

**Test Execution**:
```bash
# Correct way to run tests
./test.sh tests/test_async_client.py
uv run pytest --asyncio-mode=auto tests/
```

**Required Dependencies**:
```toml
[project.optional-dependencies]
dev = [
    "pytest-asyncio>=0.21.0",
    "aioresponses>=0.7.4",
    "pytest>=7.0.0",
]
```

---

## Summary: All Questions Resolved ✅

| Question | Decision | Status |
|----------|----------|--------|
| Q11: Enforcement latency | 500ms approved | ✅ |
| Q12: Loss limit buffer | No buffer | ✅ |
| Q13: Enforcement failure | Continue trading + log | ✅ |
| Q14: NoStopLossGrace | Mandatory | ✅ |
| Q15: Multi-broker | Future (not now) | ✅ |
| Q16: Queue size | 10,000 events | ✅ |
| Q17: Persistence | SQLite | ✅ |
| Q18: Mock SDK | Yes | ✅ |
| Q19: Test environment | Paper trading account | ✅ |
| Q20: Performance metrics | 3 critical metrics | ✅ |

---

## Next Steps

**For Developer**:
1. ✅ All decisions made - no blockers
2. ✅ Begin implementation per [handoff_to_dev_and_test.md](handoff_to_dev_and_test.md)
3. ✅ Use SQLite for state persistence
4. ✅ Implement enforcement failure logging (no lockout)
5. ✅ Make NoStopLossGrace mandatory
6. ✅ Follow async testing rules strictly

**For Test-Orchestrator**:
1. ✅ Create mock SDK for unit tests
2. ✅ Setup paper trading account for integration tests
3. ✅ Implement 3 performance metrics tracking
4. ✅ Follow async testing patterns from project-x-py

**For Product Owner (Jake)**:
- ✅ All approvals documented
- ✅ Ready to proceed with development
- ✅ Can track progress via enforcement latency metrics

---

## Integration Approval

**Status**: ✅ **APPROVED FOR DEVELOPMENT**

**Approved By**: Jake (Product Owner)
**Date**: 2025-10-15
**Next Gate**: Developer code review after implementation

---

**Document Status**: ✅ Complete
**Last Updated**: 2025-10-15
**Author**: RM-SDK-Analyst
