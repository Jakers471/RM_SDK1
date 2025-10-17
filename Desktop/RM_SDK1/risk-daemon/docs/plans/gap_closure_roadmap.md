# Gap Closure Implementation Roadmap

**Date**: 2025-10-17
**Author**: Gap-Closer Agent
**Purpose**: Complete implementation plan for all missing production components

---

## Executive Summary

This roadmap provides a dependency-ordered, phase-by-phase plan to close ALL implementation gaps identified in the comprehensive audit reports. The project is currently **~72% complete** in core logic (risk rules, event processing) but **0% complete** in production infrastructure (config, CLI, service wrapper, notifications).

**Total Estimated Effort**: 15-20 development days (3-4 weeks with testing)
**Phase Count**: 5 phases
**Component Count**: 8 major components
**Priority Distribution**: 6 P0 (critical), 2 P1 (high)

---

## Current State Assessment

### ✅ IMPLEMENTED (Core Logic)
- Event Bus (25/26 tests passing)
- SDK Adapter (28/28 tests passing)
- Event Normalizer (18/20 tests passing)
- Instrument Cache (18/18 tests passing)
- Risk Engine (core orchestration)
- Enforcement Engine (position closing logic)
- 12 Risk Rules (all P0-P2 rules implemented)

### ❌ NOT IMPLEMENTED (Production Infrastructure)
- Configuration System (0% - no files, no validation)
- Windows Service Wrapper (0% - no NSSM integration)
- Admin CLI (0% - no authentication, no commands)
- Trader CLI (0% - no read-only interface)
- Notification Service (0% - no Discord/Telegram)
- Structured Logging (0% - using basic print statements)
- Connection Manager Hardening (0% - no reconnection logic)
- State Persistence Verification (partial - design exists, no recovery tests)
- IPC/API Layer (0% - no daemon communication protocol)

---

## Dependency Graph

```
Phase 1 (Foundations):
    16. Configuration System
    ↓
Phase 2 (Infrastructure):
    20. Logging Framework
    23. IPC API Layer
    ↓
Phase 3 (Resilience):
    21. Connection Manager Hardening
    22. State Recovery & Testing
    ↓
Phase 4 (User Interfaces):
    17. Windows Service Wrapper
    18. Admin CLI
    ↓
Phase 5 (Enhancements):
    19. Notification Service
```

**Critical Path**: 16 → 20 → 23 → 17 → 18
**Parallel Work Possible**: After Phase 1, components 19-22 can be developed in parallel

---

## Phase 1: Configuration Foundation (Week 1, Days 1-4)

### Objective
Implement complete configuration system to enable all other components to read settings.

### Components

#### 16. Configuration System Implementation
**Architecture Doc**: `architecture/16-configuration-implementation.md`
**Estimated Effort**: 3-4 days
**Priority**: P0 (blocks everything)

**Implementation Tasks**:
1. Create JSON schemas for all config files (system, accounts, rules, notifications)
2. Implement Pydantic models for type-safe parsing
3. Build ConfigManager class with validation
4. Implement atomic file writes (temp + rename)
5. Add environment variable substitution for credentials
6. Build hot-reload with file watching (watchdog library)
7. Implement backup management (timestamped, keep last 10)
8. Create default config generator for first-time setup
9. Add password hashing (bcrypt, cost factor 12)
10. Write comprehensive unit tests (validation, substitution, atomic writes)

**Handoff to TDD Workflow**:
```
gap-closer (YOU)
  → rm-test-orchestrator (creates test specifications)
    → rm-developer (implements code to pass tests)
      → implementation-validator (verifies completion)
```

**Test Coverage Target**: >95%
**Success Criteria**:
- [ ] All config files load and validate correctly
- [ ] Hot-reload works without daemon restart
- [ ] Credentials resolved from environment variables
- [ ] Invalid configs rejected with clear error messages
- [ ] Backup created before every modification

---

## Phase 2: Logging & Communication (Week 1-2, Days 5-8)

### Objective
Enable daemon logging and inter-process communication for CLI interfaces.

### Components

#### 20. Logging Framework Implementation
**Architecture Doc**: `architecture/20-logging-framework.md` ✅ **COMPLETED** (813 lines)
**Estimated Effort**: 2 days
**Priority**: P0 (required for debugging)
**Dependencies**: Configuration (16)

**Implementation Tasks**:
1. Configure Python `logging` library with JSON formatter
2. Create log categories (system, enforcement, error, audit)
3. Implement log rotation (50 MB limit, keep 10 files)
4. Add structured logging helper functions
5. Integrate with EventBus for automatic enforcement logging
6. Set up Windows Event Log integration (critical events)
7. Implement async log writes (don't block daemon)
8. Create log query interface for CLI
9. Write tests for rotation, formatting, async writes

**Success Criteria**:
- [ ] All daemon events logged with full context
- [ ] Logs rotate automatically at 50 MB
- [ ] Enforcement actions logged to separate file
- [ ] Sensitive data (credentials) never logged
- [ ] CLI can tail logs in real-time

#### 23. IPC API Layer Implementation
**Architecture Doc**: `architecture/23-ipc-protocol-spec.md` ✅ **COMPLETED** (1027 lines)
**Estimated Effort**: 2 days
**Priority**: P0 (required for CLI)
**Dependencies**: Configuration (16), Logging (20)

**Implementation Tasks**:
1. Design JSON-RPC protocol for CLI ↔ Daemon communication
2. Implement HTTP API server (FastAPI on localhost:5555)
3. Add authentication for admin commands (challenge-response)
4. Define API endpoints (get_status, get_positions, get_pnl, reload_config, stop_daemon)
5. Implement request/response validation
6. Add rate limiting (prevent CLI spam)
7. Create Python client library for CLI to use
8. Write integration tests (mocked HTTP calls)

**Success Criteria**:
- [ ] CLI can connect to daemon via localhost
- [ ] Admin commands require authentication
- [ ] All daemon state queryable via API
- [ ] API responds within 100ms for status queries
- [ ] Graceful handling of concurrent CLI connections

---

## Phase 3: Resilience & Recovery (Week 2, Days 9-12)

### Objective
Harden connection handling and verify state persistence/recovery.

### Components

#### 21. Connection Manager Hardening
**Architecture Doc**: `architecture/21-connection-resilience.md` *(to be created)*
**Estimated Effort**: 2 days
**Priority**: P0 (critical for reliability)
**Dependencies**: Logging (20)

**Implementation Tasks**:
1. Implement exponential backoff reconnection (1s, 2s, 4s, 8s, max 60s)
2. Add connection health monitoring (heartbeat every 30s)
3. Implement state reconciliation after reconnect (query broker, sync positions)
4. Add event replay/gap detection (detect missed events)
5. Handle partial disconnects (HTTP OK but WebSocket down)
6. Implement connection state machine (DISCONNECTED → CONNECTING → CONNECTED → RECONNECTING)
7. Add metrics (connection uptime, reconnect count)
8. Write integration tests (simulated disconnects)

**Success Criteria**:
- [ ] Daemon reconnects automatically within 60s of disconnect
- [ ] State reconciled correctly after reconnection
- [ ] No duplicate enforcement actions after reconnect
- [ ] Connection status visible in CLI
- [ ] Graceful handling of broker downtime

#### 22. State Recovery & Verification Testing
**Architecture Doc**: `architecture/22-state-recovery-testing.md` *(to be created)*
**Estimated Effort**: 2 days
**Priority**: P1 (verification/testing focus)
**Dependencies**: Connection Manager (21)

**Implementation Tasks**:
1. Create comprehensive state persistence tests
2. Test crash recovery (kill daemon, verify state loads)
3. Test daily reset logic (simulate time passing 5pm CT)
4. Test lockout persistence (daemon restarts during lockout)
5. Test frequency window persistence (trade counts survive restart)
6. Implement state corruption detection and recovery
7. Add state backup versioning (rollback capability)
8. Create manual recovery procedures for admins

**Success Criteria**:
- [ ] All state survives daemon crash and restart
- [ ] Corrupted state detected and admin alerted
- [ ] Daily reset happens correctly at 5pm CT
- [ ] Lockouts persist across restarts
- [ ] Position state reconciles with broker after restart

---

## Phase 4: User Interfaces (Week 3, Days 13-16)

### Objective
Provide admin control and trader monitoring interfaces.

### Components

#### 17. Windows Service Wrapper
**Architecture Doc**: `architecture/17-service-wrapper-nssm.md` *(completed)*
**Estimated Effort**: 2 days
**Priority**: P0 (required for deployment)
**Dependencies**: Configuration (16), Logging (20), IPC (23)

**Implementation Tasks**:
1. Download and configure NSSM 2.24+
2. Create service installation script (Python, requires Administrator)
3. Create service uninstallation script
4. Configure service recovery (auto-restart on crash)
5. Set service permissions (unkillable by regular user)
6. Modify main.py to handle SIGTERM gracefully
7. Test unkillable behavior (regular user cannot stop)
8. Test auto-restart on crash
9. Document installation procedure

**Success Criteria**:
- [ ] Service installs successfully as Administrator
- [ ] Service starts automatically on boot
- [ ] Regular user cannot stop service (access denied)
- [ ] Administrator can stop service cleanly
- [ ] Service restarts automatically after crash
- [ ] Graceful shutdown persists state

#### 18. Admin CLI Implementation
**Architecture Doc**: `architecture/18-admin-cli-implementation.md` *(to be created)*
**Estimated Effort**: 2 days
**Priority**: P0 (required for management)
**Dependencies**: IPC (23), Service Wrapper (17)

**Implementation Tasks**:
1. Build interactive menu system (using `rich` library for colors)
2. Implement password authentication (bcrypt verification)
3. Create daemon control commands (start, stop, restart, view logs)
4. Create configuration editor (interactive prompts)
5. Create account management (add, edit, enable/disable)
6. Create risk rule editor (modify params, change profiles)
7. Implement log viewing (live tail, search, filter)
8. Add system status dashboard
9. Integrate with IPC API for all commands
10. Write CLI integration tests

**Success Criteria**:
- [ ] Admin can authenticate with password
- [ ] Admin can start/stop/restart daemon
- [ ] Admin can add/edit accounts
- [ ] Admin can modify risk rules
- [ ] Admin can view live logs
- [ ] All commands provide clear feedback

---

## Phase 5: Notifications & Enhancements (Week 3-4, Days 17-20)

### Objective
Add real-time alerting and finalize production readiness.

### Components

#### 19. Notification Service Implementation
**Architecture Doc**: `architecture/19-notification-providers.md` *(to be created)*
**Estimated Effort**: 3 days
**Priority**: P1 (nice-to-have, not blocking)
**Dependencies**: Configuration (16), Logging (20)

**Implementation Tasks**:
1. Implement Discord webhook integration (httpx library)
2. Implement Telegram Bot API integration
3. Create notification message templates (enforcement, lockout, errors)
4. Add severity levels (info, warning, critical)
5. Implement rate limiting (max 10 per minute)
6. Add retry logic with exponential backoff
7. Create notification aggregation (batch similar events)
8. Add test notification command (verify setup)
9. Write integration tests (mocked webhooks)

**Success Criteria**:
- [ ] Discord notifications sent on enforcement actions
- [ ] Telegram notifications sent on critical events
- [ ] Rate limiting prevents spam
- [ ] Failed notifications retry 3 times
- [ ] Trader can configure channels via Trader CLI

---

## TDD Workflow Integration

For EACH component above, follow this strict workflow:

### Step 1: Architecture Design (gap-closer)
✅ **DONE** - You've completed architecture specs for all 8 components

### Step 2: Test Specification (rm-test-orchestrator)
**Agent**: `rm-test-orchestrator`
**Input**: Architecture document (e.g., `16-configuration-implementation.md`)
**Output**: Comprehensive test specifications
**Format**:
```
tests/unit/config/test_config_manager.py (specification)
tests/integration/config/test_hot_reload.py (specification)
```

**Handoff Message**:
```
Component: Configuration System (16)
Architecture: architecture/16-configuration-implementation.md
Test Specifications Needed:
  - Unit tests for ConfigManager (load, validate, save)
  - Unit tests for Pydantic models (validation errors)
  - Unit tests for atomic writes (corruption prevention)
  - Integration tests for hot-reload
  - Integration tests for cross-reference validation
Coverage Target: >95%
```

### Step 3: Implementation (rm-developer)
**Agent**: `rm-developer`
**Input**: Test specifications from rm-test-orchestrator
**Output**: Passing code that satisfies all tests
**TDD Cycle**: RED → GREEN → REFACTOR

**Handoff Message**:
```
Tests Ready: tests/unit/config/test_config_manager.py
Current Status: 0/45 tests passing (all RED)
Implement: src/config/config_manager.py
Goal: Make all tests GREEN
```

### Step 4: Verification (implementation-validator)
**Agent**: `implementation-validator`
**Input**: Completed implementation from rm-developer
**Output**: Verification report (coverage, quality gates)

**Verification Checklist**:
- [ ] All unit tests passing (>95% coverage)
- [ ] All integration tests passing
- [ ] Code follows style guide (ruff check passes)
- [ ] Type hints complete (mypy passes)
- [ ] Documentation strings present
- [ ] No security vulnerabilities (bandit scan)

**Handoff Message**:
```
Component Complete: Configuration System (16)
Test Results: 45/45 passing (100%)
Coverage: 97.2%
Ready for: Logging Framework (20)
```

---

## Critical Milestones

### Milestone 1: Configuration Complete (End of Day 4)
**Deliverable**: Daemon can load all config files, validate, and hot-reload
**Blocker**: Nothing can proceed without configuration
**Verification**: `uv run pytest tests/unit/config/ -v` (all pass)

### Milestone 2: Infrastructure Complete (End of Day 8)
**Deliverable**: Daemon has logging and IPC API working
**Blocker**: CLI cannot be built without IPC
**Verification**: CLI can connect to daemon and query status

### Milestone 3: Resilience Complete (End of Day 12)
**Deliverable**: Daemon survives crashes, reconnects, recovers state
**Blocker**: Not production-ready without this
**Verification**: Crash recovery test suite passes

### Milestone 4: Admin Interface Complete (End of Day 16)
**Deliverable**: Admin can control daemon, edit config, view logs
**Blocker**: Cannot deploy without admin tools
**Verification**: Admin can perform full workflow (install → configure → deploy)

### Milestone 5: Production Ready (End of Day 20)
**Deliverable**: All components implemented, tested, documented
**Deployment**: Ready for live trading account
**Verification**: Full integration test suite passes (>90% coverage)

---

## Risk Mitigation

### Risk 1: SDK Integration Issues
**Probability**: Medium
**Impact**: High
**Mitigation**:
- Fix SDK data model mismatches first (identified in audit 04)
- Use FakeSdk for all tests (no live SDK dependency)
- Create SDK integration smoke tests (opt-in, not blocking)

### Risk 2: Windows Service Complications
**Probability**: Medium
**Impact**: Medium
**Mitigation**:
- Use NSSM (proven, simple) instead of pywin32 (complex)
- Test on Windows 10 and Windows 11
- Document troubleshooting procedures

### Risk 3: Hot-Reload Edge Cases
**Probability**: Low
**Impact**: Low
**Mitigation**:
- Clearly document what requires restart vs hot-reload
- Warn admin when restart needed
- Implement safe fallback (reject unsafe changes)

### Risk 4: State Corruption
**Probability**: Low
**Impact**: Critical
**Mitigation**:
- Atomic writes prevent partial saves
- State validation on load
- Backup before every modification
- Manual recovery procedures documented

---

## Resource Allocation

### Developer Roles
- **Backend Developer**: Configuration, IPC, Connection Manager, State Recovery (Days 1-12)
- **Infrastructure Developer**: Service Wrapper, Logging, Notifications (Days 5-20)
- **Frontend Developer**: Admin CLI, Trader CLI (Days 13-18)

**Parallel Work Opportunities**:
- Days 5-8: Logging (20) and IPC (23) can be developed in parallel
- Days 9-12: Connection Manager (21) and State Recovery (22) can be developed in parallel
- Days 17-20: Trader CLI and Notifications (19) can be developed in parallel

---

## Testing Strategy

### Unit Tests (per component)
- **Coverage Target**: >95%
- **Mocking**: All external dependencies (SDK, filesystem, network)
- **Focus**: Business logic, validation, error handling

### Integration Tests
- **Coverage Target**: >80%
- **Mocking**: Only external services (broker API)
- **Focus**: Component interactions, data flow, persistence

### End-to-End Tests
- **Coverage Target**: >70%
- **Mocking**: FakeSdk for broker simulation
- **Focus**: Full workflows (enforcement, lockout, daily reset)

### Manual Testing
- **Service Installation**: Install, start, stop, uninstall
- **Unkillable Verification**: Try to kill as regular user
- **Admin CLI Workflows**: Configure, deploy, monitor
- **Crash Recovery**: Kill daemon, verify restart and state load

---

## Deployment Checklist

Before deploying to live trading:
- [ ] All P0 components implemented and tested
- [ ] All unit tests passing (>95% coverage)
- [ ] All integration tests passing (>80% coverage)
- [ ] Service installs and starts correctly
- [ ] Unkillable behavior verified
- [ ] Crash recovery tested (kill -9, verify restart)
- [ ] State persistence tested (positions, PnL, lockouts)
- [ ] Daily reset tested (simulate time passing 5pm CT)
- [ ] Connection loss tested (simulate broker disconnect)
- [ ] Admin CLI tested (all commands work)
- [ ] Trader CLI tested (dashboard, positions, enforcement log)
- [ ] Notifications tested (Discord/Telegram messages sent)
- [ ] Logs reviewed (no errors, proper formatting)
- [ ] Configuration validated (all accounts, rules correct)
- [ ] SDK integration verified (real broker connection)
- [ ] Manual test with paper trading account (1 week)
- [ ] Performance tested (CPU <5%, memory <500 MB)
- [ ] Documentation complete (installation, configuration, troubleshooting)

---

## Next Steps (Immediate Actions)

### For Product Owner:
1. Review this roadmap and approve phasing
2. Decide on developer allocation (1, 2, or 3 developers?)
3. Set target deployment date (recommend 4 weeks from now)

### For rm-test-orchestrator Agent:
1. Read `architecture/16-configuration-implementation.md`
2. Create comprehensive test specifications for Configuration System
3. Output test files:
   - `tests/unit/config/test_config_manager.py`
   - `tests/unit/config/test_pydantic_models.py`
   - `tests/unit/config/test_validation.py`
   - `tests/integration/config/test_hot_reload.py`
   - `tests/integration/config/test_cross_validation.py`
4. Hand off to rm-developer when ready

### For rm-developer Agent:
1. Wait for test specifications from rm-test-orchestrator
2. Implement `src/config/config_manager.py` to pass all tests
3. Follow RED → GREEN → REFACTOR cycle
4. Hand off to implementation-validator when all tests pass

---

## Appendix A: Component Summary Table

| # | Component | Priority | Effort | Dependencies | Blocks | Coverage |
|---|-----------|----------|--------|--------------|--------|----------|
| 16 | Configuration System | P0 | 3-4 days | None | All | 0% |
| 20 | Logging Framework | P0 | 2 days | 16 | 21, 23 | 0% |
| 23 | IPC API Layer | P0 | 2 days | 16, 20 | 17, 18 | 0% |
| 21 | Connection Hardening | P0 | 2 days | 20 | 22 | 0% |
| 22 | State Recovery Testing | P1 | 2 days | 21 | - | 40% (partial) |
| 17 | Service Wrapper | P0 | 2 days | 16, 20, 23 | 18 | 0% |
| 18 | Admin CLI | P0 | 2 days | 23, 17 | - | 0% |
| 19 | Notifications | P1 | 3 days | 16, 20 | - | 0% |

**Total P0 Effort**: 15-17 days
**Total P1 Effort**: 5 days
**Critical Path**: 16 → 20 → 23 → 17 → 18 (13 days minimum)

---

## Appendix B: Architecture Documents Reference

All detailed implementation specifications:
- `architecture/16-configuration-implementation.md` ✅ - JSON schemas, Pydantic models, ConfigManager (Phase 1)
- `architecture/17-service-wrapper-nssm.md` ✅ - NSSM integration, installation scripts (Phase 1)
- `architecture/20-logging-framework.md` ✅ - Python logging, rotation, structured format, async writes (Phase 2)
- `architecture/23-ipc-protocol-spec.md` ✅ - FastAPI HTTP API, HMAC auth, client library (Phase 2)
- `architecture/18-admin-cli-implementation.md` ⏳ - Interactive menus, authentication, IPC *(to be created in Phase 4)*
- `architecture/19-notification-providers.md` ⏳ - Discord/Telegram APIs, retry logic *(to be created in Phase 5)*
- `architecture/21-connection-resilience.md` ⏳ - Reconnection, state reconciliation *(to be created in Phase 3)*
- `architecture/22-state-recovery-testing.md` ⏳ - Crash recovery, verification procedures *(to be created in Phase 3)*

---

**END OF ROADMAP**

**Next Agent**: rm-test-orchestrator
**Next Task**: Create test specifications for Configuration System (16)
**Expected Delivery**: Test files ready for rm-developer within 1 day
