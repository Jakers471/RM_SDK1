# Risk Manager Daemon - SDK Integration Documentation

## 📋 Overview

This directory contains complete integration documentation for integrating the **project-x-py SDK** (v3.5.9) with the Risk Manager Daemon.

**Status**: ✅ **APPROVED - Ready for Development**
**Product Owner Approval**: Jake - 2025-10-15
**SDK**: project-x-py v3.5.9 (TopstepX broker)
**Integration Complexity**: 🟡 Medium (4-6 days development)

---

## 📚 Documentation Index

### Core Analysis Documents

1. **[sdk_survey.md](sdk_survey.md)** - START HERE
   - Complete SDK overview and capabilities
   - Authentication, events, queries, order execution
   - Architecture: async-first, event-driven, WebSocket push
   - Assessment: ⭐⭐⭐⭐⭐ Production-ready

2. **[capabilities_matrix.md](capabilities_matrix.md)**
   - 60+ capabilities mapped (SDK vs requirements)
   - ✅ SDK provides: 75% of features
   - ❌ Must build: 25% of features
   - Critical finding: Pre-trade rejection impossible

3. **[event_mapping.md](event_mapping.md)**
   - SDK events → Internal events (9 mappings)
   - Complete EventNormalizer implementation
   - Data field extraction with code examples
   - Price cache and PnL calculation logic

### Implementation Contracts

4. **[adapter_contracts.md](adapter_contracts.md)** - CRITICAL FOR DEVELOPER
   - Exact SDKAdapter interface (10 methods)
   - EventNormalizer specification
   - InstrumentCache and PriceCache contracts
   - Error handling and testing guidelines

5. **[integration_flows.md](integration_flows.md)**
   - 5 detailed sequence diagrams
   - Fill → Enforcement flow (120-500ms)
   - State reconciliation after disconnect
   - Daily reset at 5pm CT

6. **[gaps_and_build_plan.md](gaps_and_build_plan.md)** - BUILD PLAN
   - 9 gaps with implementation plans
   - Code examples for each component
   - Effort estimates: 40+ hours total
   - Recommended build order (6-day plan)

### Risk Management

7. **[risks_open_questions.md](risks_open_questions.md)**
   - 9 risks catalogued and mitigated
   - Overall risk: 🟡 MEDIUM (acceptable)
   - All questions answered (see product_owner_decisions.md)

8. **[product_owner_decisions.md](product_owner_decisions.md)** - ✅ APPROVED
   - All 20 questions answered
   - Enforcement latency: 500ms approved
   - No loss limit buffer
   - Enforcement failures: log + continue (no lockout)
   - NoStopLossGrace: mandatory
   - State persistence: SQLite

### Handoff Documents

9. **[handoff_to_dev_and_test.md](handoff_to_dev_and_test.md)** - START IMPLEMENTATION HERE
   - Complete 6-day implementation roadmap
   - Testing strategy (unit, integration, performance)
   - SDK setup instructions
   - Success criteria checklist

10. **[../contracts/sdk_contract.json](../contracts/sdk_contract.json)** - MACHINE-READABLE
    - Event mappings, method signatures
    - Tick values, rate limits, gaps
    - Performance targets
    - For Developer/Test-Orchestrator consumption

---

## 🎯 Quick Start

### For Developer

**Day 1-2**: Core Integration
1. Read [handoff_to_dev_and_test.md](handoff_to_dev_and_test.md)
2. Review [adapter_contracts.md](adapter_contracts.md)
3. Install SDK: `uv add project-x-py`
4. Implement `SDKAdapter` + `EventNormalizer`

**Day 3-4**: Custom Components
1. Implement PnL tracking + daily reset
2. Implement price cache + PnL calculation
3. Create session timer (5pm CT reset)

**Day 5-6**: Reliability + Testing
1. Implement state reconciliation
2. Implement stop loss detection
3. Unit tests + integration tests
4. Code review + bug fixes

### For Test-Orchestrator

**Day 1**: Setup
1. Read [handoff_to_dev_and_test.md](handoff_to_dev_and_test.md)
2. Create mock SDK (`tests/mocks/mock_sdk.py`)
3. Setup paper trading account credentials

**Day 2**: Unit Tests
1. Test SDKAdapter methods (10 tests)
2. Test EventNormalizer (5 tests)
3. Test PnL calculations (3 tests)

**Day 3**: Integration + Performance
1. End-to-end enforcement flow test
2. State reconciliation test
3. Performance benchmarks (3 metrics)

### For Product Owner

**Review Completed** ✅
- All integration docs reviewed
- All questions answered ([product_owner_decisions.md](product_owner_decisions.md))
- Approved for development

**Track Progress**:
- Monitor enforcement latency (<500ms target)
- Review weekly status updates from Developer
- User acceptance testing (UAT) after Day 6

---

## 🔑 Key Findings Summary

### What SDK Provides ✅

- ✅ Async-first architecture with EventBus
- ✅ Real-time WebSocket push events (no polling)
- ✅ Position queries with full details
- ✅ Order execution (market, limit, stop, bracket)
- ✅ Auto-reconnect with circuit breaker
- ✅ Rate limiting and retry logic
- ✅ Comprehensive error handling
- ✅ Production-ready (v3.5.9, actively maintained)

### What We Must Build ❌

- ❌ Realized PnL tracking (daily 5pm CT reset)
- ❌ Unrealized PnL calculation (from price cache)
- ❌ Daily reset timer (5pm CT)
- ❌ TIME_TICK events (1-second interval)
- ❌ Stop loss detection (query orders separately)
- ❌ State reconciliation (after disconnect)
- ❌ Flatten all positions (loop through positions)
- ❌ Discord/Telegram notifications
- ❌ Pre-trade rejection (IMPOSSIBLE - client-side limitation)

### Critical Constraint 🔴

**Pre-Trade Rejection: IMPOSSIBLE**
- Cannot block orders before they reach broker
- **Mitigation**: Post-fill enforcement (120-500ms latency)
- **Approved**: 500ms target is acceptable

---

## 📊 Integration Metrics

### Effort Estimates

| Phase | Effort | Owner |
|-------|--------|-------|
| Core SDK Integration | 1.5 days | Developer |
| PnL Tracking + Reset | 1 day | Developer |
| Timers + Reconciliation | 1 day | Developer |
| Stop Loss Detection | 1 day | Developer |
| Unit Tests | 1 day | Test-Orchestrator |
| Integration Tests | 2 days | Test-Orchestrator |
| **Total** | **4-6 days** | Both |

### Performance Targets

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Enforcement Latency (P95) | <500ms | FILL event → close order placed |
| Event Processing | <10ms | Rule evaluation time per event |
| Memory Usage | <100MB | RSS over 24 hours |
| State Reconciliation | <5s | Time to reconcile after reconnect |

### Success Criteria

✅ All adapter methods implemented per contracts
✅ All custom components built per gaps plan
✅ Unit test coverage >80%
✅ Integration tests passing with paper account
✅ Enforcement latency <500ms (95th percentile)
✅ No known bugs or regressions
✅ Code reviewed and approved

---

## 🚨 Critical Async Testing Requirements

**MANDATORY**: All tests MUST follow async patterns

**Rules** (from `project-x-py/.cursor/rules/async_testing.md`):
1. ✅ Always use `@pytest.mark.asyncio` for async tests
2. ✅ Use `AsyncMock` for async methods
3. ✅ Use `aioresponses` for HTTP mocking
4. ✅ Never use `asyncio.run()` in test methods
5. ✅ Always cleanup async resources

**Test Execution**:
```bash
# Correct
./test.sh tests/test_async_client.py
uv run pytest --asyncio-mode=auto tests/

# Wrong
pytest tests/  # Missing asyncio mode
```

**Dependencies**:
```toml
[project.optional-dependencies]
dev = [
    "pytest-asyncio>=0.21.0",
    "aioresponses>=0.7.4",
    "pytest>=7.0.0",
]
```

---

## 🔐 SDK Setup

### Installation

```bash
cd risk-daemon
uv add project-x-py==3.5.9
```

### Configuration

**Environment Variables** (`.env`):
```bash
PROJECT_X_API_KEY=your_topstepx_api_key
PROJECT_X_USERNAME=your_username
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

### Test Connection

```python
import asyncio
from project_x_py import TradingSuite

async def test():
    suite = await TradingSuite.create("MNQ")
    print(f"Connected: {suite.client.account_info.name}")
    await suite.disconnect()

asyncio.run(test())
```

---

## 📝 Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-10-15 | RM-SDK-Analyst | Initial analysis and integration docs |
| 1.1.0 | 2025-10-15 | RM-SDK-Analyst | Product Owner approvals added |

---

## 🆘 Support and Questions

### SDK Questions
- Project-x-py docs: https://github.com/TexasCoding/project-x-py
- Examples: `../project-x-py/examples/`

### Architecture Questions
- Review planner docs: `../architecture/*.md`
- Escalate to Product Owner (Jake)

### Integration Issues
- Check [risks_open_questions.md](risks_open_questions.md) first
- Document new issues in this directory

---

## ✅ Final Approval Status

**Integration Approach**: ✅ APPROVED
**SDK Suitability**: ✅ APPROVED
**Development Timeline**: ✅ APPROVED (4-6 days)
**Performance Targets**: ✅ APPROVED (500ms enforcement)
**Risk Level**: 🟡 MEDIUM (acceptable with mitigations)

**Ready for Development**: ✅ **YES**

**Approved By**: Jake (Product Owner)
**Date**: 2025-10-15

---

**Next Step**: Developer begins implementation per [handoff_to_dev_and_test.md](handoff_to_dev_and_test.md)

**Good luck! The integration is well-documented and ready to build.** 🚀
