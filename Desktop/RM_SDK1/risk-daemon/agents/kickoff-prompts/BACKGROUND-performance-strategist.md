# BACKGROUND RESEARCH: Performance Strategist Kickoff

**Agent**: performance-strategist
**Model**: opus
**Priority**: Background (PARALLEL with Phase 1)
**Estimated Time**: 1-2 hours
**Status**: Ready to run

---

## 📖 FIRST: Read Your Agent Definition

**CRITICAL**: Before starting, read your complete agent definition:
```
agents/background-research/performance-strategist.md
```

This file contains your full mission, constraints, and quality standards. The kickoff below is a quick-start summary.

---

## 🎯 Your Mission

You are the **performance-strategist** agent. Design comprehensive performance testing strategy and define acceptable performance benchmarks for production readiness.

## 📚 Required Reading

1. **src/** (Current implementation)
   - Understand async architecture
   - Identify potential bottlenecks (event processing, rule evaluation, state updates)

2. **docs/architecture/** (Design constraints)
   - Event-driven architecture
   - Risk rule evaluation pipeline
   - Enforcement engine operations

3. **Industry Benchmarks**
   - Research: Acceptable latency for risk management systems
   - Trading systems typically require <100ms for critical operations

## 📝 Your Deliverables

### 1. docs/research/performance_benchmarks.md

**Performance Targets** for each operation:

- **Event Processing Latency**
  - P50 (median): <50ms
  - P95: <100ms
  - P99: <200ms
  - P99.9: <500ms

- **Rule Evaluation Latency**
  - Single rule: <10ms
  - All 12 rules: <50ms
  - Worst-case cascade: <100ms

- **Enforcement Action Latency**
  - Close position: <200ms
  - Flatten account: <500ms
  - Set lockout: <50ms

- **Throughput Targets**
  - Events/second (sustained): 100+
  - Peak burst: 500 events/second
  - Daily event volume: 1M+ events

- **Resource Usage**
  - Memory: <500MB steady state
  - CPU: <50% average utilization
  - Disk I/O: <10MB/s

- **Reliability**
  - Uptime: 99.9% (max 8.76 hours downtime/year)
  - No memory leaks over 24h operation
  - Graceful degradation under load

### 2. docs/research/performance_test_plan.md

**Test Scenarios**:

#### Load Tests (Sustained Traffic)
- **Scenario 1**: 10 events/second for 10 minutes
  - Measure: Average latency, max latency, memory usage
  - Success: All events processed <100ms P95

- **Scenario 2**: 100 events/second for 10 minutes
  - Measure: Event queue depth, processing lag, CPU usage
  - Success: No queue buildup, <200ms P99

- **Scenario 3**: 500 events/second for 1 minute (burst)
  - Measure: System behavior under spike
  - Success: Recovers after burst, no crashes

#### Stress Tests (Breaking Point)
- **Scenario 4**: Ramp from 10 → 1000 events/second
  - Find: At what point does system fail?
  - Success: Graceful degradation (no crashes)

#### Endurance Tests (Memory Leaks)
- **Scenario 5**: 10 events/second for 24 hours
  - Measure: Memory growth over time
  - Success: <10% memory growth, no crashes

#### Chaos Tests (Reliability)
- **Scenario 6**: Random SDK disconnects during processing
  - Measure: Recovery time, lost events
  - Success: Reconnects <5s, no lost enforcement actions

### 3. docs/research/optimization_opportunities.md

**Potential Bottlenecks Identified**:

- **Event Processing**
  - Current: Serial event processing
  - Opportunity: Batch processing for non-critical events
  - Estimated Gain: 2-3x throughput

- **Rule Evaluation**
  - Current: All 12 rules evaluated for every event
  - Opportunity: Early exit on inapplicable rules
  - Estimated Gain: 30-40% faster

- **State Updates**
  - Current: Synchronous database writes
  - Opportunity: Async write buffering
  - Estimated Gain: 50% faster enforcement

- **Caching Strategies**
  - InstrumentCache: Already implemented
  - PriceCache: Already implemented
  - Opportunity: Add ConfigCache for rule parameters
  - Estimated Gain: Eliminate config file reads

- **Database Optimization**
  - Opportunity: Index on frequently queried columns
  - Opportunity: Connection pooling
  - Opportunity: Batch writes for audit logs

## ✅ Success Criteria

You succeed when:
- [ ] Concrete performance targets defined (latency, throughput, resources)
- [ ] Comprehensive test plan with specific scenarios
- [ ] Optimization opportunities identified and prioritized
- [ ] Benchmarks are measurable and testable
- [ ] Phase 2 team can validate performance from your plan

## 📊 Output Summary Template

```
✅ Performance Strategy Complete

Created 3 Research Documents:
- performance_benchmarks.md (latency, throughput, resource targets)
- performance_test_plan.md (6 test scenarios defined)
- optimization_opportunities.md (5 bottlenecks identified)

Key Performance Targets:
- Event Processing: <100ms P95
- Rule Evaluation: <50ms for all 12 rules
- Throughput: 100+ events/second sustained
- Memory: <500MB steady state
- Uptime: 99.9%

Test Scenarios Ready:
- Load tests: 3 scenarios
- Stress tests: 1 scenario
- Endurance tests: 1 scenario (24h)
- Chaos tests: 1 scenario

Optimization Opportunities:
1. [Most impactful optimization]
2. [Second most impactful]
3. [Third most impactful]

Ready for Performance Validation: ✅
```

---

## 🚀 Ready to Start?

Define the performance bar. Phase 2 production deployment depends on meeting these benchmarks.

**BEGIN PERFORMANCE PLANNING NOW.**
