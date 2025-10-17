# Risk Daemon Agent Orchestration System

**Last Updated**: 2025-10-17
**Status**: Phase 1 Active, Phase 2 Queued

---

## 📋 Quick Navigation

- **[Phase 1: Current Implementation](#phase-1-current-implementation)** ← **START HERE**
- **[Phase 2: Live Deployment](#phase-2-live-deployment)** (Run AFTER Phase 1 complete)
- **[Existing Workflow](#existing-workflow-agents)** (Your beloved TDD agents)
- **[Utilities](#utility-agents)** (Supporting agents)
- **[Background Research](#background-research-agents)** (Parallel work during Phase 1)

---

## 🎯 System Overview

This agent system orchestrates **autonomous development** from **incomplete implementation** → **all tests green** → **live SDK deployment** → **production-ready**.

### Current State
- ✅ 70% of architecture implemented
- ✅ All 12 risk rules working (with mocks)
- ❌ Missing: Configuration, CLI, Service Wrapper, Notifications
- ❌ 0% coverage on 3 critical modules
- ❌ Never connected to real SDK (all mocks)

### Goal
**Phase 1**: Complete implementation, all tests green, 85%+ coverage (MOCKED)
**Phase 2**: Replace mocks with live SDK, production deployment

---

## 🚀 Phase 1: Current Implementation

**Objective**: Fill implementation gaps, achieve 100% tests passing + 85% coverage (mocked)

### Agents

#### 1. **gap-closer** (Architecture Designer)
**File**: `1-current-implementation/gap-closer.md`
**Color**: Purple
**When to Use**: Need architecture for missing components (config system, CLI, etc.)

**Inputs**:
- docs/audits/01_Architecture_Audit.md (missing components)
- docs/audits/02_Testing_Coverage_Audit.md (test gaps)
- docs/architecture/** (existing designs for pattern matching)

**Outputs**:
- docs/architecture/16-configuration-system.md
- docs/architecture/17-windows-service-wrapper.md
- docs/architecture/18-admin-cli.md
- docs/architecture/19-notification-service.md
- docs/architecture/20-structured-logging.md
- docs/plans/gap_closure_roadmap.md

**Invocation**:
```bash
# Example usage
claude-code --agent gap-closer
```

**Next Step**: Hands off to rm-test-orchestrator to create tests

---

#### 2. **test-coverage-enforcer** (Coverage Guardian)
**File**: `1-current-implementation/test-coverage-enforcer.md`
**Color**: Red
**When to Use**: Modules have 0% coverage or <85% coverage

**Inputs**:
- docs/audits/02_Testing_Coverage_Audit.md (coverage gaps)
- reports/coverage.json (exact uncovered lines)
- src/** (code to test)

**Outputs**:
- tests/unit/adapters/test_connection_manager.py (0% → 85%+)
- tests/unit/state/test_persistence.py (0% → 85%+)
- tests/integration/test_main.py (0% → 85%+)
- Extended tests for <85% modules

**Invocation**:
```bash
claude-code --agent test-coverage-enforcer
```

**Next Step**: Hands off to rm-developer for implementation

---

#### 3. **implementation-validator** (Quality Gate Enforcer)
**File**: `1-current-implementation/implementation-validator.md`
**Color**: Cyan
**When to Use**: Orchestrate implementation until all tests green + coverage >85%

**Inputs**:
- reports/junit.xml (test results)
- reports/coverage.json (coverage data)
- docs/plans/gap_closure_roadmap.md (implementation sequence)

**Outputs**:
- docs/status/implementation_status.md (real-time progress)
- docs/status/blocking_failures.md (current blockers)
- docs/status/current_cycle.md (active work)

**Orchestrates**:
- rm-developer (for implementation)
- test-failure-debugger (for triage)
- test-coverage-enforcer (if coverage drops)

**Invocation**:
```bash
claude-code --agent implementation-validator
```

**Loop Until**: 100% tests pass + 85% coverage achieved

---

### Phase 1 Workflow

```
gap-closer (designs missing components)
    ↓
Architecture docs created
    ↓
rm-test-orchestrator (creates failing tests from architecture)
    ↓
test-coverage-enforcer (adds coverage tests for 0% modules)
    ↓
implementation-validator LOOP:
    │
    ├─→ rm-developer (implements code)
    │       ↓
    ├─→ Run tests (pytest)
    │       ↓
    ├─→ test-failure-debugger (if failures)
    │       ↓
    └─→ Repeat until ALL GREEN + 85% coverage
    ↓
All tests GREEN ✅
    ↓
auto-commit (create PR: "Phase 1 complete")
    ↓
READY FOR PHASE 2
```

---

## 🌐 Phase 2: Live Deployment

**Objective**: Replace mocks with real SDK, deploy to production

**⚠️ DO NOT START PHASE 2 UNTIL PHASE 1 COMPLETE**

### Agents

#### 05. **mock-replacement-strategist**
**File**: `2-live-deployment/05-mock-replacement-strategist.md`
**Purpose**: Plan how to replace each mock with real SDK connection
**Output**: Mock replacement strategy with dependency graph

#### 06. **data-model-reconciler**
**File**: `2-live-deployment/06-data-model-reconciler.md`
**Purpose**: Design transformation layer for SDK ↔ Daemon data model mismatches
**Output**: Model transformer specifications

#### 07. **test-gap-filler**
**File**: `2-live-deployment/07-test-gap-filler.md`
**Purpose**: Create live SDK integration tests (with ENABLE_INTEGRATION=1)
**Output**: tests/integration/live/** with real SDK connection tests

#### 08. **infrastructure-designer**
**File**: `2-live-deployment/08-infrastructure-designer.md`
**Purpose**: Design production monitoring, logging, deployment infrastructure
**Output**: Production infrastructure plan

#### 09. **production-readiness-validator**
**File**: `2-live-deployment/09-production-readiness-validator.md`
**Purpose**: Final pre-production audit, GO/NO-GO decision
**Output**: Production readiness report

---

## 🛠️ Existing Workflow Agents

**Your beloved TDD workflow** (created "with a lot of love") - **PRESERVED**

### rm-planner
**File**: `existing-workflow/rm-planner.md`
**Purpose**: Feature-first architecture from USER conversation
**Use When**: Designing NEW features (not gap-filling)

### rm-coordinator
**File**: `existing-workflow/rm-coordinator.md`
**Purpose**: Sprint board management, work sequencing
**Use When**: Need workflow coordination

### rm-test-orchestrator
**File**: `existing-workflow/rm-test-orchestrator.md`
**Purpose**: Create failing tests from architecture docs (TDD RED phase)
**Use When**: Have architecture, need tests

**⭐ THIS IS YOUR CROWN JEWEL** - Preserves TDD principles

### rm-developer
**File**: `existing-workflow/rm-developer.md`
**Purpose**: Implement code to make tests pass (TDD GREEN phase)
**Use When**: Have failing tests, need implementation

**⭐ YOUR OTHER CROWN JEWEL** - Clean architecture enforcer

### rm-sdk-analyst
**File**: `existing-workflow/rm-sdk-analyst.md`
**Purpose**: Analyze SDK, create integration documentation
**Use When**: Need SDK capability mapping

---

## 🔧 Utility Agents

**Supporting agents** for debugging, review, commit automation

### test-failure-debugger
**File**: `utilities/test-failure-debugger.md`
**Purpose**: Triage test failures, create fix specifications
**Invoked By**: implementation-validator

### doc-reviewer
**File**: `utilities/doc-reviewer.md`
**Purpose**: Review documentation for accuracy and completeness

### integration-validator
**File**: `utilities/integration-validator.md`
**Purpose**: Validate integration between components

### auto-commit
**File**: `utilities/auto-commit.md`
**Purpose**: Create git commits, branches, PRs when work complete

### coverage-hardening-agent
**File**: `utilities/coverage-hardening-agent.md`
**Purpose**: Improve test coverage incrementally

### pre-deployment-audit
**File**: `utilities/pre-deployment-audit.md`
**Purpose**: Pre-deployment checklist validation

---

## 🔬 Background Research Agents

**Run in PARALLEL during Phase 1** (non-blocking, preparatory work)

### sdk-deep-analyzer
**File**: `background-research/sdk-deep-analyzer.md`
**Purpose**: Deep SDK analysis for Phase 2 preparation
**Output**: Comprehensive SDK integration guide
**Run When**: Phase 1 in progress, prepare for Phase 2

### performance-strategist
**File**: `background-research/performance-strategist.md`
**Purpose**: Design performance testing and benchmarks
**Output**: Performance test plan, optimization opportunities

### security-hardener
**File**: `background-research/security-hardener.md`
**Purpose**: Security audit and hardening recommendations
**Output**: Security hardening plan, vulnerability assessment

### documentation-writer
**File**: `background-research/documentation-writer.md`
**Purpose**: Create user-facing documentation (trader/admin guides)
**Output**: Installation guide, user manual, troubleshooting guide, FAQ

### deployment-planner
**File**: `background-research/deployment-planner.md`
**Purpose**: Design production deployment strategy
**Output**: Deployment runbook, rollback procedures, disaster recovery

---

## 📊 Agent Invocation Strategy

### Phase 1 Execution (Current)

**Sequential (blocking)**:
1. `gap-closer` → creates architecture
2. `rm-test-orchestrator` → creates tests from architecture
3. `test-coverage-enforcer` → adds coverage tests
4. `implementation-validator` → orchestrates until green
   - Invokes: `rm-developer`, `test-failure-debugger` in loop

**Parallel (non-blocking)** while Phase 1 runs:
- `sdk-deep-analyzer` (prepare for Phase 2)
- `performance-strategist` (create benchmarks)
- `security-hardener` (audit security)
- `documentation-writer` (user guides)
- `deployment-planner` (deployment strategy)

### Phase 2 Execution (After Phase 1 complete)

**Sequential**:
1. `mock-replacement-strategist` → plan mock → real SDK migration
2. `data-model-reconciler` → design transformation layer
3. `test-gap-filler` → create live SDK tests
4. `implementation-validator` → implement until all tests (mocked + live) pass
5. `infrastructure-designer` → production infrastructure
6. `production-readiness-validator` → final GO/NO-GO

---

## 🎮 Quick Start Guide

### Starting Phase 1 (NOW)

```bash
# Step 1: Design missing components
claude-code --agent gap-closer

# Step 2: Create coverage tests
claude-code --agent test-coverage-enforcer

# Step 3: Implement until all green (autonomous loop)
claude-code --agent implementation-validator

# Step 4 (parallel): Background research
claude-code --agent sdk-deep-analyzer &
claude-code --agent performance-strategist &
claude-code --agent security-hardener &
claude-code --agent documentation-writer &
claude-code --agent deployment-planner &
```

### Checking Phase 1 Progress

```bash
# View current status
cat docs/status/implementation_status.md

# View blocking failures
cat docs/status/blocking_failures.md

# Check test results
cat reports/junit.xml

# Check coverage
cat reports/coverage.json
```

### Phase 1 Completion Criteria

- [ ] All tests passing (100%)
- [ ] Coverage ≥ 85%
- [ ] All missing components implemented (config, CLI, service wrapper, etc.)
- [ ] 0% coverage modules now ≥85%
- [ ] Background research complete

**When complete**: Move to Phase 2

---

## 🔥 Agent Dependencies

```
gap-closer (no dependencies)
    ↓
rm-test-orchestrator (needs: architecture docs)
    ↓
test-coverage-enforcer (needs: coverage audit, source code)
    ↓
implementation-validator (needs: tests, roadmap)
    ├─→ rm-developer (needs: tests, architecture)
    ├─→ test-failure-debugger (needs: test failures)
    └─→ test-coverage-enforcer (if coverage drops)
```

**Background agents**: No dependencies, run anytime

---

## 📚 Agent Audit Reports

All agents can read these comprehensive audits:

1. **docs/audits/01_Architecture_Audit.md**
   - Missing components
   - Implementation gaps
   - Recommendations

2. **docs/audits/02_Testing_Coverage_Audit.md**
   - Coverage gaps
   - Untested modules
   - Test quality assessment

3. **docs/audits/03_Deployment_Roadmap.md**
   - Mock inventory
   - Deployment sequence
   - Dependencies

4. **docs/audits/04_SDK_Integration_Analysis.md**
   - SDK data model mismatches
   - Critical integration issues
   - Production readiness checklist

---

## 🎯 Success Criteria

### Phase 1 Success
✅ All tests passing (100%)
✅ Coverage ≥ 85%
✅ Missing components implemented
✅ Background research complete

### Phase 2 Success
✅ All mocked tests still passing
✅ Live SDK integration tests passing
✅ Data model transformations working
✅ Production infrastructure in place
✅ GO decision from production-readiness-validator

---

## 🚨 Troubleshooting

### "Agent is stuck in a loop"
- Check `docs/status/implementation_status.md` for cycle count
- If >50 cycles, escalate to human
- Review `docs/status/blocking_failures.md` for root cause

### "Coverage not improving"
- Invoke `test-coverage-enforcer` for specific modules
- Check if tests are comprehensive (not just dummy tests)

### "Tests failing for unknown reason"
- Invoke `test-failure-debugger` for triage
- Review `reports/pytest_last.txt` for detailed output

### "Need to add new component not in original plan"
- Use `rm-planner` (requires user conversation)
- Then feed into existing workflow

---

## 📞 Contact & Support

- **Project Owner**: User
- **Agent System**: Claude Code
- **Documentation**: This README + individual agent files
- **Status**: docs/status/**

---

**Remember**: The TDD workflow (rm-test-orchestrator + rm-developer) is the heart of this system. All new agents INTEGRATE with it, never replace it.

**Made with ❤️ following TDD principles you created "with a lot of love"**
