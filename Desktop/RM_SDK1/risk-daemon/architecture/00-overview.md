# Risk Manager Daemon - System Overview

## Purpose

The Risk Manager Daemon is a professional-grade risk management system designed to protect trading accounts from catastrophic losses by enforcing configurable risk rules in real-time. It operates as an always-on guardian that monitors trading activity and automatically enforces position limits, loss thresholds, and trading rules without trader intervention.

## Core Philosophy

**Protection Over Discretion**: The system is intentionally designed to prevent the trader from disabling or bypassing risk controls during trading hours. This "enforced discipline" model treats risk management as non-negotiable infrastructure, not optional tooling.

**Event-Driven, Not Polling**: The system reacts to broker events (fills, position updates, PnL changes) rather than polling state. This ensures low latency enforcement and efficient resource usage.

**Professional Separation of Concerns**: Clear separation between administrative control (configuration, system management) and trader interaction (monitoring, visibility) mirrors institutional risk management practices.

## System Goals

1. **Prevent Account Blow-Ups**: Automatically close positions and lock trading when risk limits are breached
2. **Enforce Discipline**: Remove emotional decision-making during trading by making rules unkillable
3. **Real-Time Monitoring**: React instantly to fills and position changes via event-driven architecture
4. **Transparent Operations**: Provide traders with clear visibility into why enforcement actions occurred
5. **Flexibility**: Support multiple accounts with different rule sets, configurable per trader needs
6. **Extensibility**: Allow easy addition of new risk rules and features over time

## High-Level Components

### 1. Risk Daemon (Core Service)
- Windows service running under administrative privileges
- Connects to TopstepX broker via project-x-py SDK
- Monitors trading activity in real-time via event handlers
- Evaluates all events against configured risk rules
- Executes enforcement actions (close positions, flatten account, lockout trading)
- Cannot be stopped by regular user, only by admin authentication

### 2. SDK Adapter Layer
- Abstracts broker-specific SDK (project-x-py)
- Normalizes events into internal format
- Provides clean interface for position management
- Handles authentication, connection management, order execution

### 3. Risk Engine
- Evaluates events against all active risk rules
- Tracks combined realized + unrealized PnL continuously
- Maintains state for timer-based rules (cooldowns, frequency limits)
- Determines enforcement actions based on rule violations
- Modular plugin-based rule system

### 4. Enforcement Engine
- Executes actions: close specific position, flatten all, lockout trading
- Handles retry logic and error scenarios
- Ensures idempotent operations
- Logs all enforcement actions with reasoning

### 5. State Manager
- Tracks current positions per account
- Maintains real-time PnL (realized + unrealized)
- Manages lockout status and timer states
- Handles daily reset logic (5pm Chicago Time)
- Persists state to survive daemon restarts

### 6. Configuration System
- Stores risk rules per account
- Supports universal rules across all accounts
- Per-instrument settings for certain rules
- Validates configuration integrity
- Provides hot-reload where safe

### 7. Admin CLI
- Full system control interface
- Start/stop/restart daemon
- Configure risk rules, accounts, API credentials
- Password-protected administrative access
- Verbose logging access

### 8. Trader CLI
- Read-only monitoring interface
- View active rules, positions, connection status
- Live enforcement logs (why positions were closed)
- Live timers for rule resets
- Clock in/out for personal analytics
- Configure notification preferences
- Cannot modify rules or stop daemon without admin password

### 9. Notification Service
- Sends alerts to Discord/Telegram
- Configurable per trader preference
- Alerts on rule breaches, enforcement actions, connection issues

## User Personas

### Administrator
- Sets up system initially
- Configures risk rules and accounts
- Has full control over daemon lifecycle
- Can modify rules at any time with authentication
- Typically same person as trader, but with elevated privileges

### Trader (Regular User)
- Uses system daily for trading
- Can see what rules are active but cannot change them
- Receives real-time feedback on enforcement
- Can configure personal settings (notifications, clock in/out)
- Cannot stop daemon or bypass rules
- Must authenticate as admin to make rule changes

## Technology Stack (Conceptual)

- **Language**: Python (matches project-x-py SDK)
- **Broker SDK**: project-x-py (TopstepX integration)
- **Service Architecture**: Windows service (admin-level privileges)
- **Configuration**: JSON-based config files
- **Notifications**: Webhook-based (Discord, Telegram)
- **CLI Framework**: Terminal-based interactive menus
- **Event Model**: Asynchronous event-driven architecture

## Key Design Principles

### 1. Single Source of Truth
- One state manager for positions and PnL
- One enforcement engine for all actions
- Centralized configuration

### 2. Modularity
- Each risk rule is independent plugin
- Components communicate via well-defined interfaces
- Easy to test and develop in isolation

### 3. Fail-Safe Design
- On ambiguous state → take conservative action (close positions)
- On configuration error → halt trading, alert admin
- On SDK disconnect → alert only (no auto-flatten per user preference)

### 4. Transparency
- All enforcement actions logged with clear reasoning
- Trader always knows why something was closed
- Audit trail for review

### 5. Extensibility
- Plugin interface for new risk rules
- Config schema versioning
- Easy to add features without touching core

## High-Level Data Flow

```
Broker (TopstepX)
    ↓
SDK Events (fills, position updates, PnL changes)
    ↓
SDK Adapter (normalize to internal format)
    ↓
Event Bus (route to handlers)
    ↓
Risk Engine (evaluate against rules)
    ↓
State Manager (update positions, PnL, timers)
    ↓
Enforcement Decision (close, flatten, lockout, or allow)
    ↓
Enforcement Engine (execute action)
    ↓
SDK Adapter (send close/flatten orders)
    ↓
Broker (position closed)
    ↓
Notification Service + Logging (alert trader, log action)
```

## Scope Boundaries

### In Scope
- Real-time risk rule enforcement
- Position and PnL monitoring
- Automated position closing and account flattening
- Trading lockouts (timer-based and daily)
- Multiple account support
- Per-account and universal rule configuration
- Admin and trader CLI interfaces
- Discord/Telegram notifications
- Daily reset logic (5pm CT)
- Daemon lifecycle management (start/stop/restart)
- Process protection (unkillable by regular user)

### Out of Scope (For Initial Version)
- Advanced features like auto-breakeven (future extension)
- Multi-broker support (TopstepX only initially)
- Web-based dashboard (CLI only)
- Historical analytics and reporting
- Backtesting risk rules
- Machine learning / adaptive rules

### Future Extensions (Noted for Extensibility Design)
- Auto-breakeven for winning trades
- Trailing stop automation
- Position scaling rules
- Advanced analytics dashboard
- Multi-broker support
- Cloud deployment options

## Success Criteria

The system successfully achieves its goals when:

1. **Trader cannot bypass rules** during trading hours without admin authentication
2. **All enforcement actions happen within <1 second** of rule breach
3. **No position ever exceeds configured limits** (contract size, loss, etc.)
4. **Daily limits never exceeded** due to combined realized + unrealized monitoring
5. **Daemon survives** computer reboots and restarts automatically
6. **Trader has full visibility** into why any position was closed
7. **System is extensible** - new rules can be added without refactoring core
8. **Zero data loss** on daemon restart (state persists)

## Next Steps for Implementation Agent

The implementation/mapping agent should:

1. **Analyze project-x-py SDK** to understand:
   - Event types available (onFill, onPositionUpdate, etc.)
   - Authentication mechanisms (JWT, API keys, etc.)
   - Order execution methods (close position, flatten account)
   - Connection management and reconnection logic
   - Data formats for positions, fills, PnL

2. **Map our design to SDK capabilities**:
   - Which events can trigger which rules?
   - How to calculate unrealized PnL from SDK data?
   - How to execute enforcement actions via SDK?
   - What SDK provides vs what we build custom?

3. **Identify gaps and solutions**:
   - If SDK doesn't provide X, how do we implement it?
   - Custom timers, state management, etc.

4. **Create implementation plan**:
   - File structure and module organization
   - Dependencies and libraries needed
   - Development phases and milestones

This overview provides the strategic vision. The following architecture documents provide detailed design for each component.
