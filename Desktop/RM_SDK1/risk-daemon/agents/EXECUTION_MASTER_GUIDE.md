# 🎯 Risk Daemon Agent Execution Master Guide

**Visual Guide for Operating All 33 Agents**

---

## 📋 Quick Reference: Current Status

```
✅ COMPLETED: gap-closer (Architecture designed)
🟢 RUNNING: rm-test-orchestrator (Creating tests)
⏸️  WAITING: rm-developer (After rm-test-orchestrator)
⏸️  WAITING: implementation-validator (After rm-developer)
⏸️  WAITING: Background research agents (Can run NOW in parallel)
```

---

## 🗺️ Complete Agent Map (All 33 Agents)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PHASE 1: MOCKED IMPLEMENTATION               │
│                         (Current: Week 1-3)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ✅ 01. gap-closer               [DONE: Architecture created]       │
│  🟢 02. rm-test-orchestrator     [RUNNING: Creating 48 tests]       │
│  ⏸️  03. rm-developer            [NEXT: Make tests GREEN]           │
│  ⏸️  04. implementation-validator [AFTER: Orchestrate until done]   │
│  ⏸️  05. test-coverage-enforcer   [PARALLEL: Fill 0% modules]       │
│                                                                       │
│  🔵 BACKGROUND (Run in parallel terminals NOW):                     │
│     06. sdk-deep-analyzer        [Terminal 2: SDK analysis]         │
│     07. performance-strategist   [Terminal 3: Performance plan]     │
│     08. security-hardener        [Terminal 4: Security audit]       │
│     09. documentation-writer     [Terminal 5: User docs]            │
│     10. deployment-planner       [Terminal 6: Deploy strategy]      │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    BRIDGE: Phase 1 → Phase 2 Transition              │
│                         (Future: After Phase 1)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ⏳ 11. phase1-completion-validator    [Gate 1: GO/NO-GO]          │
│  ⏳ 12. vision-alignment-interviewer   [Gate 2: User check-in]     │
│  ⏳ 13. phase1-to-phase2-bridger       [Plan: Phase 2 strategy]    │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    PHASE 2: LIVE SDK INTEGRATION                     │
│                         (Future: Week 4-6)                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ⏳ 14. mock-replacement-strategist    [Plan mock → live]          │
│  ⏳ 15. data-model-reconciler          [Design transformers]        │
│  ⏳ 16. test-gap-filler                [Create live tests]          │
│  ⏳ 17. live-integration-orchestrator  [Replace mocks]              │
│  ⏳ 18. production-health-monitor      [BACKGROUND: Monitor]        │
│  ⏳ 19. infrastructure-designer        [Production infra]           │
│  ⏳ 20. production-readiness-validator [Final audit]                │
│  ⏳ 21. end-to-end-validator           [Complete validation]        │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    WORKFLOW AGENTS (Use Anytime)                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  🔧 test-failure-debugger      [When tests fail]                    │
│  🔧 code-reviewer              [After feature complete]              │
│  🔧 refactoring-assistant      [When code needs cleanup]             │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘

Total: 33 agents across 4 categories
```

---

## 🎬 Current Execution Plan (RIGHT NOW)

### Terminal Setup (5 Terminals Recommended)

```
┌────────────────────────────────────────────────────────────────┐
│ Terminal 1 (MAIN)        │ Terminal 2 (BACKGROUND)             │
│                          │                                     │
│ 🟢 rm-test-orchestrator  │ 🔵 sdk-deep-analyzer                │
│    (RUNNING NOW)         │    (START NOW)                      │
│                          │                                     │
│ ⏸️  rm-developer         │                                     │
│    (AFTER #1)            │                                     │
├──────────────────────────┼─────────────────────────────────────┤
│ Terminal 3 (BACKGROUND)  │ Terminal 4 (BACKGROUND)             │
│                          │                                     │
│ 🔵 performance-strategist│ 🔵 security-hardener                │
│    (START NOW)           │    (START NOW)                      │
│                          │                                     │
├──────────────────────────┼─────────────────────────────────────┤
│ Terminal 5 (BACKGROUND)  │ Terminal 6 (BACKGROUND)             │
│                          │                                     │
│ 🔵 documentation-writer  │ 🔵 deployment-planner               │
│    (START NOW)           │    (START NOW)                      │
│                          │                                     │
└──────────────────────────┴─────────────────────────────────────┘
```

### Commands to Run NOW

**Terminal 1 (Main - Already Running):**
```bash
# 🟢 RUNNING: rm-test-orchestrator
cat agents/kickoff-prompts/WORKFLOW-rm-test-orchestrator.md
# Wait for completion (48 tests created, all RED)
```

**Terminal 2 (Background Research):**
```bash
# Start SDK deep analysis
cat agents/background-research/sdk-deep-analyzer.md
# Let it run in background (30-60 mins)
```

**Terminal 3 (Background Research):**
```bash
# Start performance strategy
cat agents/background-research/performance-strategist.md
# Let it run in background (30-60 mins)
```

**Terminal 4 (Background Research):**
```bash
# Start security hardening
cat agents/background-research/security-hardener.md
# Let it run in background (45-90 mins)
```

**Terminal 5 (Background Research):**
```bash
# Start documentation writing
cat agents/background-research/documentation-writer.md
# Let it run in background (60-90 mins)
```

**Terminal 6 (Background Research):**
```bash
# Start deployment planning
cat agents/background-research/deployment-planner.md
# Let it run in background (45-60 mins)
```

---

## ✅ Phase 1 Execution Checklist

### Week 1: Configuration System (Days 1-4)

**Current Status:**
- [x] Day 1: gap-closer creates architecture ✅ DONE
- [🟢] Day 2: rm-test-orchestrator creates tests (IN PROGRESS)
- [ ] Day 2-3: rm-developer implements code
- [ ] Day 4: implementation-validator verifies completion

#### Day 2 (TODAY) - Testing Phase

```
┌─────────────────────────────────────────────────────────────┐
│ MORNING (9am-12pm)                                          │
├─────────────────────────────────────────────────────────────┤
│ Terminal 1: rm-test-orchestrator RUNNING                   │
│ Terminal 2-6: Background agents RUNNING                    │
│                                                              │
│ ⏰ Check every 30 mins:                                     │
│    - Terminal 1: Has rm-test-orchestrator finished?        │
│    - Terminals 2-6: Any completions or errors?             │
│                                                              │
│ ☕ Take breaks - agents work autonomously                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ AFTERNOON (1pm-5pm) - WHEN rm-test-orchestrator COMPLETES  │
├─────────────────────────────────────────────────────────────┤
│ 1. Verify rm-test-orchestrator output:                     │
│    [ ] 48 tests created in tests/unit/config/              │
│    [ ] tests/integration/config/                            │
│    [ ] TEST_NOTES.md updated                                │
│    [ ] All tests RED (0/48 passing)                        │
│                                                              │
│ 2. Run verification:                                        │
│    uv run pytest tests/unit/config/ -v                      │
│    # Should show: 0/X passing (all RED) ✅                 │
│                                                              │
│ 3. Launch rm-developer in Terminal 1:                      │
│    cat agents/kickoff-prompts/WORKFLOW-rm-developer.md      │
│                                                              │
│ 4. Let rm-developer work (2-3 hours)                       │
│    ⏰ Check progress every 30 mins                         │
└─────────────────────────────────────────────────────────────┘
```

#### Day 3 - Implementation Phase

```
┌─────────────────────────────────────────────────────────────┐
│ MORNING (9am-12pm) - rm-developer continues                │
├─────────────────────────────────────────────────────────────┤
│ Watch for progress:                                         │
│    uv run pytest tests/unit/config/ --tb=short             │
│    # Should see: X/48 passing (increasing)                  │
│                                                              │
│ When rm-developer reports COMPLETE:                        │
│    [ ] 48/48 tests passing                                  │
│    [ ] Coverage ≥85%                                        │
│    [ ] Linting passes (ruff check)                         │
│    [ ] Type checking passes (mypy)                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ AFTERNOON (1pm-5pm) - Validation                           │
├─────────────────────────────────────────────────────────────┤
│ 1. Manual verification:                                     │
│    uv run pytest tests/unit/config/ tests/integration/config/ -v │
│    # Should see: 48/48 PASSED ✅                           │
│                                                              │
│    uv run pytest --cov=src/config --cov-report=term        │
│    # Should see: ≥85% coverage ✅                          │
│                                                              │
│ 2. Decision point:                                          │
│    ✅ All green? → Commit and move to Phase 2 (CLI System) │
│    ❌ Issues? → Run test-failure-debugger                  │
└─────────────────────────────────────────────────────────────┘
```

#### Day 4 - Next Phase or Fix Issues

```
Option A: Everything Green ✅
┌─────────────────────────────────────────────────────────────┐
│ Commit Phase 1 Complete:                                    │
│    git add .                                                 │
│    git commit -m "Phase 1.1: Configuration System complete" │
│                                                              │
│ Move to Phase 1.2: CLI System                               │
│    # gap-closer already created architecture/17-*.md        │
│    # Run rm-test-orchestrator for CLI tests                │
└─────────────────────────────────────────────────────────────┘

Option B: Issues Found ❌
┌─────────────────────────────────────────────────────────────┐
│ Debug cycle:                                                 │
│    cat agents/utilities/test-failure-debugger.md            │
│    # Identifies root cause                                   │
│                                                              │
│    cat agents/existing-workflow/rm-developer.md             │
│    # Fix implementation                                      │
│                                                              │
│ Repeat until green                                          │
└─────────────────────────────────────────────────────────────┘
```

---

### Week 2-3: Remaining Phase 1 Components (Days 5-20)

**Repeat the pattern for each component:**

```
┌──────────────────┬──────────────┬───────────────────────────────┐
│ Component        │ Days         │ Agent Sequence                │
├──────────────────┼──────────────┼───────────────────────────────┤
│ Configuration    │ 1-4 (DONE)   │ gap-closer → orchestrator     │
│                  │              │ → developer → validator       │
├──────────────────┼──────────────┼───────────────────────────────┤
│ CLI System       │ 5-8          │ Same sequence                 │
│ (17-*)           │              │ (architecture exists)         │
├──────────────────┼──────────────┼───────────────────────────────┤
│ Service Wrapper  │ 9-12         │ Same sequence                 │
│ (NSSM)           │              │ (architecture exists)         │
├──────────────────┼──────────────┼───────────────────────────────┤
│ Monitoring       │ 13-16        │ Same sequence                 │
│ (Prometheus)     │              │ (needs architecture)          │
├──────────────────┼──────────────┼───────────────────────────────┤
│ State            │ 17-20        │ Same sequence                 │
│ Persistence      │              │ (needs architecture)          │
└──────────────────┴──────────────┴───────────────────────────────┘
```

**For each component:**
1. Check if architecture exists (gap-closer may have created it)
2. If not, run gap-closer for that component
3. Run rm-test-orchestrator (create tests)
4. Run rm-developer (implement code)
5. Verify green
6. Commit
7. Move to next component

---

## 🌉 Bridge Phase Execution (After Phase 1 Complete)

### Gate 1: Completion Validation (1-2 hours)

```
┌─────────────────────────────────────────────────────────────┐
│ WHEN: All Phase 1 components complete                      │
├─────────────────────────────────────────────────────────────┤
│ Terminal 1:                                                  │
│    cat agents/phase1-to-phase2-bridge/                      │
│        10-phase1-completion-validator.md                    │
│                                                              │
│ Agent runs comprehensive checks:                            │
│    [ ] pytest (100% pass)                                   │
│    [ ] Coverage (≥85%)                                      │
│    [ ] Linting (ruff check)                                 │
│    [ ] Type checking (mypy)                                 │
│    [ ] Security scan (bandit)                               │
│    [ ] Architecture review                                  │
│    [ ] Documentation complete                               │
│    [ ] Performance baselines                                │
│                                                              │
│ OUTPUT: docs/validation/phase1_completion_report.md        │
│                                                              │
│ Decision:                                                    │
│    ✅ GO → Proceed to Gate 2                               │
│    ❌ NO-GO → Fix blockers, re-run                         │
└─────────────────────────────────────────────────────────────┘
```

### Gate 2: Vision Alignment (1 hour)

```
┌─────────────────────────────────────────────────────────────┐
│ WHEN: Gate 1 passed (GO decision)                          │
├─────────────────────────────────────────────────────────────┤
│ Terminal 1:                                                  │
│    cat agents/phase1-to-phase2-bridge/                      │
│        11-vision-alignment-interviewer.md                   │
│                                                              │
│ ⚠️  INTERACTIVE SESSION - User required!                   │
│                                                              │
│ Agent asks you questions:                                   │
│    "Does this match what you envisioned?"                   │
│    "What are you nervous about?"                            │
│    "What would you change?"                                 │
│    "Are you ready for Phase 2?"                             │
│                                                              │
│ You provide honest answers                                  │
│                                                              │
│ OUTPUT: docs/validation/vision_alignment_report.md         │
│                                                              │
│ Decision:                                                    │
│    ✅ APPROVED → Proceed to Gate 3                         │
│    ❌ CHANGES NEEDED → Document, implement, re-run Gate 1  │
└─────────────────────────────────────────────────────────────┘
```

### Gate 3: Phase 2 Planning (2-3 hours)

```
┌─────────────────────────────────────────────────────────────┐
│ WHEN: Gate 2 approved (User confident)                     │
├─────────────────────────────────────────────────────────────┤
│ Terminal 1:                                                  │
│    cat agents/phase1-to-phase2-bridge/                      │
│        12-phase1-to-phase2-bridger.md                       │
│                                                              │
│ Agent synthesizes:                                          │
│    [ ] All 18 background research docs                      │
│    [ ] Phase 1 completion report                            │
│    [ ] Vision alignment insights                            │
│    [ ] SDK analysis findings                                │
│    [ ] Security audit results                               │
│    [ ] Performance benchmarks                               │
│                                                              │
│ Creates comprehensive Phase 2 plan:                         │
│    - Agent sequencing (5 stages)                            │
│    - Risk assessment & mitigation                           │
│    - Validation gates                                       │
│    - Monitoring strategy                                    │
│    - Timeline (10-21 days)                                  │
│                                                              │
│ OUTPUT: docs/phase2/execution_master_plan.md               │
│                                                              │
│ Decision:                                                    │
│    ✅ APPROVED → Begin Phase 2                             │
│    ❌ REVISE → Adjust plan, re-run                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Phase 2 Execution (Future)

### Stage 1: Planning (Days 1-3)

```
Terminal 1:                      Terminal 2:
┌─────────────────────────────┐  ┌──────────────────────────────┐
│ mock-replacement-strategist │  │ data-model-reconciler        │
│ (Run in parallel)           │  │ (Run in parallel)            │
└─────────────────────────────┘  └──────────────────────────────┘

Both agents run simultaneously (no dependencies)
Wait for both to complete before Stage 2
```

### Stage 2: Test Infrastructure (Days 4-6)

```
Terminal 1:
┌─────────────────────────────────────────────────────────────┐
│ test-gap-filler                                              │
│ Creates: tests/integration/live/** (live SDK tests)        │
│                                                              │
│ Tests will be RED (expected - no live SDK yet)              │
└─────────────────────────────────────────────────────────────┘
```

### Stage 3: Implementation (Days 7-11)

```
Terminal 1 (Main):               Terminal 2 (Monitoring):
┌─────────────────────────────┐  ┌──────────────────────────────┐
│ live-integration-orchestrator│  │ production-health-monitor    │
│                              │  │ (Runs continuously)          │
│ Replaces mocks one-by-one   │  │                              │
│ Validates after each         │  │ Watches for:                 │
│                              │  │ - Performance degradation    │
│ Orchestrates:                │  │ - Memory leaks               │
│ - rm-developer               │  │ - Error spikes               │
│ - test-failure-debugger      │  │ - Connection issues          │
└─────────────────────────────┘  └──────────────────────────────┘

⚠️  IMPORTANT: Keep Terminal 2 running throughout Stage 3!
   It provides real-time monitoring as mocks are replaced.
```

### Stage 4: Hardening (Days 12-14)

```
Terminal 1:
┌─────────────────────────────────────────────────────────────┐
│ infrastructure-designer                                      │
│ Deploys: Monitoring, logging, alerts, dashboards           │
│                                                              │
│ Implements security hardening from security-hardener        │
└─────────────────────────────────────────────────────────────┘
```

### Stage 5: Final Validation (Days 15-16)

```
Terminal 1:                      Terminal 2:
┌─────────────────────────────┐  ┌──────────────────────────────┐
│ production-readiness-       │  │ end-to-end-validator         │
│ validator                   │  │                              │
│                             │  │ Tests:                       │
│ Final audit:                │  │ - 10 user scenarios          │
│ - All checks pass           │  │ - 3 disaster scenarios       │
│ - Security hardened         │  │ - 2 load tests               │
│ - Docs complete             │  │ - Security scan              │
└─────────────────────────────┘  └──────────────────────────────┘

Both agents must approve before production deployment
```

---

## 📊 Progress Tracking Dashboard

### Phase 1: Mocked Implementation

| Component         | Architecture | Tests | Implementation | Coverage | Status |
|-------------------|--------------|-------|----------------|----------|--------|
| Configuration     | ✅ Done      | 🟢 In Progress | ⏸️  Waiting | - | IN PROGRESS |
| CLI System        | ✅ Done      | ⏸️  Waiting | ⏸️  Waiting | - | READY |
| Service Wrapper   | ✅ Done      | ⏸️  Waiting | ⏸️  Waiting | - | READY |
| Monitoring        | ⏳ Todo      | ⏳ Todo | ⏳ Todo | - | NOT STARTED |
| State Persistence | ⏳ Todo      | ⏳ Todo | ⏳ Todo | - | NOT STARTED |

### Background Research

| Agent                  | Status      | ETA       | Output |
|------------------------|-------------|-----------|--------|
| sdk-deep-analyzer      | 🔵 Running  | 60 mins   | docs/research/sdk_capability_deep_dive.md |
| performance-strategist | 🔵 Running  | 60 mins   | docs/research/performance_benchmarks.md |
| security-hardener      | 🔵 Running  | 90 mins   | docs/research/security_audit.md |
| documentation-writer   | 🔵 Running  | 90 mins   | docs/user-guides/*.md |
| deployment-planner     | 🔵 Running  | 60 mins   | docs/deployment/deployment_strategy.md |

### Bridge Agents

| Gate | Agent                         | Status      | Blocker |
|------|-------------------------------|-------------|---------|
| 1    | phase1-completion-validator   | ⏳ Waiting  | Phase 1 incomplete |
| 2    | vision-alignment-interviewer  | ⏳ Waiting  | Gate 1 not passed |
| 3    | phase1-to-phase2-bridger      | ⏳ Waiting  | Gate 2 not approved |

---

## 🎯 Decision Trees

### "What Should I Run Next?"

```
START
  ↓
Is Phase 1 complete? (All components implemented & tested)
  ├─ NO → Are background agents running?
  │        ├─ NO → Start background agents NOW (5 terminals)
  │        └─ YES → Continue current Phase 1 component
  │                  ↓
  │                  Is rm-test-orchestrator running?
  │                  ├─ NO → Start rm-test-orchestrator
  │                  └─ YES → Wait for completion, then rm-developer
  │
  └─ YES → Run Gate 1: phase1-completion-validator
             ↓
             Passed?
             ├─ NO → Fix blockers, re-run
             └─ YES → Run Gate 2: vision-alignment-interviewer
                        ↓
                        Approved?
                        ├─ NO → Make changes, re-run Gate 1
                        └─ YES → Run Gate 3: phase1-to-phase2-bridger
                                   ↓
                                   Approved?
                                   ├─ NO → Revise plan
                                   └─ YES → START PHASE 2
```

### "Tests Are Failing - What Do I Do?"

```
Tests failing?
  ↓
How many tests failing?
  ├─ FEW (1-5) → Run: rm-developer (fix specific issues)
  ├─ MANY (6-20) → Run: test-failure-debugger (analyze patterns)
  └─ ALL → Check: Did implementation start?
             ├─ NO → This is expected (RED phase)
             └─ YES → Run: test-failure-debugger (systematic issue)
```

### "Background Agent Completed - What Next?"

```
Background agent completed
  ↓
Which agent?
  ├─ sdk-deep-analyzer → Review: docs/research/sdk_capability_deep_dive.md
  │                       Note: Will be used in Phase 2 planning
  │
  ├─ performance-strategist → Review: docs/research/performance_benchmarks.md
  │                             Note: Baselines for monitoring
  │
  ├─ security-hardener → Review: docs/research/security_audit.md
  │                       ⚠️  IMPORTANT: Check for HIGH severity issues
  │                       If found: Create issue tickets, address in Phase 1
  │
  ├─ documentation-writer → Review: docs/user-guides/*.md
  │                          Test: Follow installation guide on clean system
  │
  └─ deployment-planner → Review: docs/deployment/deployment_strategy.md
                          Note: Will guide Phase 2 → Production transition
```

---

## 🔥 Emergency Procedures

### "Everything Is Broken" Protocol

```
1. STOP all running agents (Ctrl+C in all terminals)

2. Check current state:
   uv run pytest -v
   # How many tests passing?

3. If >80% passing:
   → Minor issue, run test-failure-debugger

4. If 20-80% passing:
   → Review recent changes
   → git log --oneline -5
   → Consider: git revert HEAD
   → Run test-failure-debugger

5. If <20% passing:
   → Major issue, rollback
   → git revert HEAD
   → Re-run last working agent

6. If 0% passing:
   → Likely infrastructure issue
   → Check: uv run python --version
   → Check: uv sync
   → Check: pytest.ini exists
```

### "Agent Won't Complete" Protocol

```
Agent running >2x expected time?
  ↓
1. Check agent output:
   - Is it waiting for user input?
   - Is it stuck in a loop?
   - Is it showing errors?

2. Check system resources:
   - Memory usage (should be <2GB)
   - CPU usage (should be <80%)
   - Disk space (should have >5GB free)

3. Decision:
   ├─ Waiting for input → Provide input
   ├─ Stuck in loop → Ctrl+C, review agent MD, restart
   ├─ Showing errors → Copy errors, search docs, ask for help
   └─ No output → Ctrl+C, check logs, restart agent
```

---

## 📅 Weekly Cadence

### Week 1 (Days 1-7)

**Monday-Wednesday:**
- Launch background agents (5 terminals)
- Complete Configuration System (Terminal 1)
- Monitor background progress

**Thursday-Friday:**
- Complete CLI System
- Begin Service Wrapper

**Weekend:**
- Background agents complete
- Review all background research outputs

### Week 2 (Days 8-14)

**Monday-Wednesday:**
- Complete Service Wrapper
- Complete Monitoring System

**Thursday-Friday:**
- Complete State Persistence
- Final Phase 1 cleanup

### Week 3 (Days 15-21)

**Monday:**
- Run Gate 1: phase1-completion-validator
- Fix any blockers

**Tuesday:**
- Run Gate 2: vision-alignment-interviewer
- Address any concerns

**Wednesday-Thursday:**
- Run Gate 3: phase1-to-phase2-bridger
- Review Phase 2 plan

**Friday:**
- Approve Phase 2 plan
- Begin Phase 2 Stage 1

---

## 🎓 Agent Interaction Patterns

### Sequential (Wait for Completion)

```
Agent A → Agent B → Agent C
   ↓         ↓         ↓
 Output   Input    Output

Example:
gap-closer → rm-test-orchestrator → rm-developer
```

### Parallel (Run Simultaneously)

```
        ┌─ Agent A ─┐
Start ──┼─ Agent B ─┼── Collect Results
        └─ Agent C ─┘

Example:
Start ─┬─ sdk-deep-analyzer ──────┬─ Gate 3
       ├─ performance-strategist ──┤
       ├─ security-hardener ───────┤
       ├─ documentation-writer ────┤
       └─ deployment-planner ──────┘
```

### Orchestrator (Calls Multiple Agents)

```
                ┌─ Agent A ─┐
Orchestrator ───┼─ Agent B ─┼─ Verify
                └─ Agent C ─┘

Example:
implementation-validator ─┬─ rm-developer ──────┬─ Check
                          └─ test-debugger ─────┘
```

---

## 💡 Pro Tips

### Terminal Management

```bash
# Use tmux or screen for persistent sessions
tmux new-session -s risk-daemon

# Create 6 panes
Ctrl+b %    # Split vertically
Ctrl+b "    # Split horizontally
# Repeat to create 6 panes

# Navigate panes
Ctrl+b ←↑→↓  # Arrow keys

# Name panes (in .tmux.conf)
# Pane 1: MAIN
# Pane 2: SDK Analysis
# Pane 3: Performance
# Pane 4: Security
# Pane 5: Docs
# Pane 6: Deployment
```

### Progress Logging

```bash
# Create a progress log
touch progress.log

# After each agent completes, log it
echo "$(date): rm-test-orchestrator COMPLETE - 48 tests created" >> progress.log

# View progress
tail -20 progress.log
```

### Time Management

```
⏰ Time Check:
- Background agents: 30-90 mins (run once at start)
- rm-test-orchestrator: 30-60 mins per component
- rm-developer: 2-4 hours per component
- Validation agents: 15-30 mins each

📅 Total Phase 1: 15-20 days
📅 Bridge Phase: 1-2 days
📅 Total Phase 2: 10-15 days
📅 TOTAL PROJECT: 26-37 days
```

---

## 🎯 Success Metrics

Track these throughout:

```
Phase 1 Metrics:
[ ] Components designed: 5/5
[ ] Tests created: X/X
[ ] Tests passing: X/X (should be 100%)
[ ] Coverage: X% (should be ≥85%)
[ ] Linting: PASS/FAIL
[ ] Type checking: PASS/FAIL
[ ] Background research: 5/5 complete

Bridge Metrics:
[ ] Gate 1: GO/NO-GO
[ ] Gate 2: APPROVED/CHANGES
[ ] Gate 3: APPROVED/REVISE

Phase 2 Metrics:
[ ] Mocks replaced: X/Y
[ ] Live tests passing: X/X
[ ] Performance: Within 20% baseline
[ ] Security: No HIGH vulnerabilities
[ ] Production ready: YES/NO
```

---

**Next Action:** Check your 6 terminals and ensure background agents are running!
