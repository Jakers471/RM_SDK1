# Architecture Tree and Ownership

## Overview

This document defines the planned repository structure for the Risk Manager Daemon project and assigns clear ownership boundaries for each agent/role in the development process. This is a **planning document** - no folders are created yet.

---

## Repository Layout (Planned)

```
risk-daemon/
│
├── docs/
│   ├── architecture/           # System design (Planner owns)
│   │   ├── 00-overview.md
│   │   ├── 01-event-driven-core.md
│   │   ├── 02-risk-engine.md
│   │   ├── 03-enforcement-actions.md
│   │   ├── 04-state-management.md
│   │   ├── 05-configuration-system.md
│   │   ├── 06-cli-interfaces.md
│   │   ├── 07-notifications-logging.md
│   │   ├── 08-daemon-service.md
│   │   ├── 09-extensibility.md
│   │   ├── 10-data-flow-diagrams.md
│   │   ├── 11-architecture-tree-and-ownership.md (this file)
│   │   ├── 12-core-interfaces-and-events.md
│   │   ├── 13-non-functionals-and-ops.md
│   │   ├── 14-backlog-and-open-questions.md
│   │   └── 99-handoff-to-sdk-analyst.md
│   │
│   └── integration/             # SDK analysis (SDK Analyst owns)
│       ├── sdk_survey.md
│       ├── capabilities_matrix.md
│       ├── adapter_contracts.md
│       ├── event_mapping.md
│       ├── integration_flows.md
│       ├── gaps_and_build_plan.md
│       ├── risks_open_questions.md
│       └── handoff_to_dev_and_test.md
│
├── contracts/                   # Machine-readable contracts (SDK Analyst owns)
│   └── sdk_contract.json
│
├── src/                         # Application source code (Developer owns)
│   ├── daemon/
│   │   ├── __init__.py
│   │   ├── main.py              # Daemon entry point
│   │   ├── event_bus.py         # Event bus implementation
│   │   └── service_wrapper.py   # NSSM/Windows service integration
│   │
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── sdk_adapter.py       # Broker SDK abstraction layer
│   │   └── event_normalizer.py  # SDK events → internal Event objects
│   │
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── risk_engine.py       # Rule evaluation orchestrator
│   │   └── enforcement_engine.py # Action executor
│   │
│   ├── rules/                   # Risk rule plugins
│   │   ├── __init__.py
│   │   ├── base.py              # RiskRulePlugin interface
│   │   ├── max_contracts.py
│   │   ├── max_contracts_per_instrument.py
│   │   ├── daily_realized_loss.py
│   │   ├── daily_realized_profit.py
│   │   ├── unrealized_loss.py
│   │   ├── unrealized_profit.py
│   │   ├── trade_frequency_limit.py
│   │   ├── cooldown_after_loss.py
│   │   ├── no_stop_loss_grace.py
│   │   ├── session_block_outside.py
│   │   ├── symbol_block.py
│   │   └── auth_loss_guard.py
│   │
│   ├── state/
│   │   ├── __init__.py
│   │   ├── state_manager.py     # State tracking and persistence
│   │   └── models.py            # AccountState, Position data models
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── config_manager.py    # Configuration loading and validation
│   │   └── schemas.py           # Config validation schemas
│   │
│   ├── notifications/
│   │   ├── __init__.py
│   │   ├── notification_service.py
│   │   ├── discord_notifier.py
│   │   └── telegram_notifier.py
│   │
│   ├── logging/
│   │   ├── __init__.py
│   │   └── logger.py            # Structured logging setup
│   │
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── admin_cli.py         # Admin CLI (Typer + Rich)
│   │   ├── trader_cli.py        # Trader CLI (Typer + Rich)
│   │   └── ipc_client.py        # HTTP API client for daemon communication
│   │
│   └── api/
│       ├── __init__.py
│       └── daemon_api.py        # HTTP API server (127.0.0.1)
│
├── tests/                       # All tests (Test-Orchestrator owns)
│   ├── unit/
│   │   ├── test_rules/
│   │   │   ├── test_max_contracts.py
│   │   │   ├── test_daily_realized_loss.py
│   │   │   └── ...
│   │   ├── test_enforcement_engine.py
│   │   ├── test_state_manager.py
│   │   └── test_notification_service.py
│   │
│   ├── integration/
│   │   ├── test_event_flow.py
│   │   ├── test_combined_pnl_monitoring.py
│   │   ├── test_enforcement_idempotency.py
│   │   ├── test_session_block_outside.py
│   │   └── test_daily_reset.py
│   │
│   ├── e2e/
│   │   └── test_full_trading_scenario.py
│   │
│   ├── fixtures/
│   │   ├── mock_sdk.py
│   │   ├── test_events.py
│   │   └── test_configs.py
│   │
│   └── conftest.py              # Pytest configuration
│
├── config/                      # Runtime configuration files
│   ├── system.json
│   ├── accounts.json
│   ├── risk_rules.json
│   └── notifications.json
│
├── scripts/                     # Installation and utility scripts
│   ├── install_daemon.py        # NSSM service registration
│   ├── uninstall_daemon.py
│   └── setup_dev_env.py
│
├── .env.example                 # Environment variable template
├── requirements.txt             # Python dependencies
├── requirements-dev.txt         # Dev/test dependencies
├── pyproject.toml               # Project metadata (Poetry or setuptools)
├── README.md
└── LICENSE
```

---

## Ownership Table

Clear boundaries for who writes where. **Single-writer rule**: only one role owns each path.

| Path Pattern | Owner | Responsibilities | Notes |
|--------------|-------|------------------|-------|
| `docs/architecture/**` | **Planner** | System design, architecture decisions, flow diagrams | Read-only for all other roles |
| `docs/integration/**` | **SDK Analyst** | SDK capabilities, adapter contracts, integration plan | Created after architecture approval |
| `contracts/**` | **SDK Analyst** | Machine-readable SDK contracts (JSON) | Used by Developer and Test-Orchestrator |
| `src/**` | **Developer** | All application code (daemon, rules, CLIs, adapters) | Implements architecture + adapter contracts |
| `tests/**` | **Test-Orchestrator** | All tests (unit, integration, e2e), fixtures, mocks | References contracts and architecture |
| `config/**` | **Product Owner** | Default runtime configs (reviewed by Developer) | Templates for actual deployment configs |
| `scripts/**` | **Developer** | Installation scripts, dev tooling | Owned by Developer, reviewed by Product Owner |
| `README.md`, `LICENSE` | **Product Owner** | Project documentation and licensing | High-level user-facing docs |
| `.env.example`, `requirements.txt`, `pyproject.toml` | **Developer** | Dependency management and environment setup | Infrastructure files |

---

## Role Definitions

### Planner (Current Agent)
- **Input**: User requirements, clarifying questions
- **Output**: Complete architecture documentation (`docs/architecture/**`)
- **Approval gate**: Product Owner reviews and approves all architecture docs before handoff
- **Handoff to**: SDK Analyst (via `99-handoff-to-sdk-analyst.md`)

### SDK Analyst (Next Agent)
- **Input**: Architecture docs + access to `project-x-py` SDK (read-only analysis)
- **Output**: Integration documentation (`docs/integration/**`) + SDK contract (`contracts/sdk_contract.json`)
- **Responsibilities**:
  - Analyze SDK capabilities
  - Map architecture requirements to SDK features
  - Identify gaps and propose solutions
  - Define adapter contracts
  - Create integration flows
- **Approval gate**: Product Owner reviews integration docs
- **Handoff to**: Developer and Test-Orchestrator (via `handoff_to_dev_and_test.md`)

### Developer (Implementation Agent)
- **Input**: Architecture docs + integration docs + SDK contracts
- **Output**: Working code in `src/**` + installation scripts
- **Responsibilities**:
  - Implement all components (daemon, rules, CLIs, adapters)
  - Follow architecture specifications exactly
  - Implement adapter contracts defined by SDK Analyst
  - Write inline code documentation
  - Create installation scripts for Windows service
- **Works with**: Test-Orchestrator (for test feedback)
- **Does NOT**: Write tests (Test-Orchestrator owns), modify architecture

### Test-Orchestrator (Testing Agent)
- **Input**: Architecture docs + integration docs + SDK contracts + Developer's code
- **Output**: Comprehensive test suite in `tests/**`
- **Responsibilities**:
  - Write unit tests for all rules and components
  - Write integration tests for event flows and enforcement
  - Write e2e tests for full scenarios
  - Create test fixtures and mocks (including mock SDK)
  - Maintain pytest configuration
  - Report bugs to Developer
- **Does NOT**: Modify `src/**` code (except via bug reports to Developer)

### Product Owner (You)
- **Input**: Business requirements, trading experience
- **Output**: Approval decisions, requirement clarifications
- **Responsibilities**:
  - Review and approve all architecture docs
  - Review and approve integration plans
  - Make final decisions on open questions
  - Define acceptance criteria
  - Approve default configurations
- **Gates all handoffs**: No agent proceeds without Product Owner approval

---

## Workflow: Handoff Chain

```
Product Owner
    │
    │ (provides requirements)
    ▼
Planner
    │
    │ (creates docs/architecture/**)
    ▼
Product Owner Review & Approval
    │
    │ (approves architecture)
    ▼
SDK Analyst
    │
    │ (creates docs/integration/** + contracts/**)
    ▼
Product Owner Review & Approval
    │
    │ (approves integration plan)
    ▼
┌───────────────┴───────────────┐
│                               │
▼                               ▼
Developer                   Test-Orchestrator
│                               │
│ (implements src/**)           │ (writes tests/**)
│                               │
└───────────────┬───────────────┘
                │
                │ (iterative: tests → bugs → fixes)
                ▼
Product Owner Review & Acceptance
    │
    │ (accepts final product)
    ▼
Deployment
```

---

## Conflict Resolution

If ownership boundaries are unclear:

1. **Architecture questions** → Planner (via Product Owner)
2. **SDK capability questions** → SDK Analyst
3. **Implementation questions** → Developer (but must align with architecture)
4. **Test coverage questions** → Test-Orchestrator
5. **Final decisions** → Product Owner

---

## File Naming Conventions

### Documentation
- Architecture docs: `NN-topic-name.md` (numbered for reading order)
- Integration docs: `descriptive_name.md` (no numbers, alphabetical ok)

### Source Code
- Python files: `snake_case.py`
- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`

### Tests
- Test files: `test_component_name.py`
- Test functions: `test_specific_behavior()`

### Configuration
- Config files: `lowercase.json` (avoid underscores for user-facing files)

---

## Version Control (Future)

When project moves to Git:

- **Protected branches**:
  - `main`: Production-ready code (Product Owner approval required)
  - `develop`: Integration branch (Developer + Test-Orchestrator)

- **Branch naming**:
  - `docs/architecture-updates` (Planner)
  - `docs/sdk-analysis` (SDK Analyst)
  - `feature/rule-name` (Developer)
  - `test/component-name` (Test-Orchestrator)

---

## Summary

This ownership model ensures:

✅ **Single-writer rule**: No merge conflicts, clear responsibility
✅ **Clear handoffs**: Each agent knows what they receive and produce
✅ **Product Owner gates**: No work proceeds without approval
✅ **Separation of concerns**: Architecture, implementation, and testing are independent
✅ **Traceability**: Every file has a clear owner

**Next Steps**:
1. Product Owner approves this ownership model
2. Planner completes remaining architecture docs (12, 13, 14, 99)
3. Product Owner reviews full architecture package
4. Handoff to SDK Analyst via `99-handoff-to-sdk-analyst.md`
