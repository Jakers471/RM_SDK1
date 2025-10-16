# Daemon Service Architecture

## Overview

The Risk Manager Daemon must run as a **Windows service** with **administrative privileges** to ensure it cannot be killed by the regular trader user. This "unkillable" design is critical to the system's philosophy: risk rules cannot be bypassed by the trader during trading hours.

## Core Requirements

1. **Run as Windows Service**: Background process, not tied to user session
2. **Administrative Privileges**: Run under admin account, not trader account
3. **Auto-Start on Boot**: Daemon starts when computer boots, before user login
4. **Unkillable by Regular User**: Trader cannot stop daemon from Task Manager
5. **Graceful Shutdown**: Admin can stop daemon cleanly (persist state)
6. **Crash Recovery**: Restart automatically if daemon crashes
7. **Process Isolation**: Daemon runs independently of CLI interfaces

## Windows Service Design

### Service Architecture

**Windows Service Wrapper**:
- Service registered with Windows Service Manager
- Runs under SYSTEM or dedicated admin account
- Starts/stops the actual daemon process

**Daemon Process**:
- Main Python application (event loop, risk engine, etc.)
- Spawned and managed by service wrapper
- Communicates with CLI via IPC

```
Windows Service Manager
    ↓
Risk Manager Service (wrapper)
    ↓
Daemon Process (Python application)
    ↓ ↓ ↓
Event Bus, Risk Engine, Enforcement Engine, etc.
```

### Service Properties

**Service Name**: `RiskManagerDaemon`

**Display Name**: Risk Manager Daemon

**Description**: Professional risk management service for trading accounts. Enforces position limits and loss thresholds in real-time.

**Start Type**: Automatic (delayed start)
- Delayed start ensures network and system services are ready

**Run As**:
- **Option 1**: Local System account (highest privileges)
- **Option 2**: Dedicated admin account (better security)

**Dependencies**: Network service (requires network for broker connection)

### Installation and Registration

Admin installs daemon:

```
admin> install daemon

Installing Risk Manager Daemon as Windows service...

Service will run as: Administrator
Auto-start on boot: Yes
Recovery on failure: Restart

Installation steps:
1. Creating service configuration
2. Registering with Windows Service Manager
3. Setting permissions (regular user cannot stop)
4. Testing service start

Installation complete!

Start daemon now? [y/n]: y
Starting service...
Service started successfully (PID: 12345)
```

Implementation agent will use Python library like `pywin32` or `nssm` (Non-Sucking Service Manager) to create Windows service.

---

## Process Protection (Unkillable Design)

### How to Make Daemon Unkillable

**1. Service-Level Protection**:
- Service runs under SYSTEM or admin account
- Regular user account cannot stop services they don't own
- Task Manager won't show daemon to regular user (running under different account)

**2. Process Permissions**:
- Daemon process ACL restricts termination to admin only
- Regular user cannot kill process even if they find PID

**3. Service Recovery**:
- Windows Service Manager configured to restart on failure
- If daemon crashes, service manager restarts it automatically
- Regular user cannot change recovery settings

### Testing Unkillable Behavior

**As Regular User**:
```
trader> tasklist | findstr "risk"
(No results - process owned by different account)

trader> taskkill /F /IM risk-manager.exe
ERROR: Access is denied.
```

**As Admin**:
```
admin> sc stop RiskManagerDaemon
Stopping service...
Service stopped successfully.

admin> sc start RiskManagerDaemon
Starting service...
Service started successfully.
```

This ensures trader cannot bypass enforcement, but admin has full control.

---

## Daemon Lifecycle

### Startup Sequence

1. **Service Manager starts service wrapper**
2. **Service wrapper initializes**:
   - Load configuration
   - Validate config
   - Initialize logging
3. **Spawn daemon process**:
   - Start Python application
   - Initialize components (SDK adapter, risk engine, state manager, etc.)
4. **Daemon initialization**:
   - Connect to broker via SDK
   - Load persisted state
   - Reconcile state with broker
   - Register event handlers
   - Start event loop
5. **Signal ready**:
   - Write PID file
   - Log "Daemon started"
   - Mark service as running

**Startup time**: Target <30 seconds from service start to fully operational.

### Shutdown Sequence

**Graceful Shutdown** (admin-initiated):

1. **Admin sends stop command** (via Admin CLI or service manager)
2. **Service wrapper receives stop signal**
3. **Daemon shutdown initiated**:
   - Stop accepting new events from SDK
   - Finish processing queued events
   - Close all open resources (SDK connection, logs, etc.)
   - **Persist state to disk** (critical!)
   - Log "Daemon stopping"
4. **Daemon process exits**
5. **Service wrapper cleans up**
6. **Service marked as stopped**

**Shutdown timeout**: 30 seconds (if daemon doesn't stop gracefully, force kill)

### Crash Recovery

**If Daemon Crashes**:

1. **Service manager detects process exit** (non-zero exit code or unexpected termination)
2. **Service recovery action triggered**:
   - Wait 10 seconds (backoff)
   - Restart daemon process
3. **Daemon restarts**:
   - Load persisted state from disk
   - Reconcile with broker
   - Resume normal operation
4. **Alert admin** (log critical error, send notification)

**Recovery Settings**:
- First failure: Restart after 10 seconds
- Second failure: Restart after 30 seconds
- Subsequent failures: Restart after 60 seconds
- Reset failure count after 1 hour of successful operation

### Forced Shutdown

**If Daemon Hangs** (doesn't respond to graceful shutdown):

1. Graceful shutdown initiated
2. Wait for shutdown timeout (30 seconds)
3. If still running, force kill process
4. Log error: "Daemon did not shutdown gracefully, forced termination"
5. **Risk**: State may not be persisted if force killed

To minimize risk, daemon periodically saves state (every 30 seconds) in addition to event-driven saves.

---

## Service Communication

### Inter-Process Communication (IPC)

CLI interfaces (Admin, Trader) need to communicate with daemon service:

**Options**:

1. **Named Pipes** (Windows native):
   - Fast, efficient
   - Good for same-machine IPC
   - Requires admin permissions for pipe creation

2. **TCP Sockets** (localhost):
   - Daemon listens on `127.0.0.1:5555`
   - CLI connects to send commands and receive status
   - Firewall rules needed

3. **HTTP API** (REST):
   - Daemon runs simple HTTP server
   - CLI makes HTTP requests
   - Easy to test and debug

**Recommendation**: Named Pipes for Windows (native, secure) or HTTP API for simplicity.

### IPC Protocol

**CLI → Daemon Commands**:
- `get_status()` - Get daemon health and account status
- `get_positions(account_id)` - Get open positions
- `get_pnl(account_id)` - Get realized/unrealized PnL
- `get_enforcement_log(account_id, limit)` - Get recent enforcement actions
- `reload_config()` - Hot-reload configuration (admin only)
- `stop_daemon()` - Graceful shutdown (admin only, requires auth)

**Daemon → CLI Responses**:
- JSON format with status and data

**Example**:
```
CLI sends: {"command": "get_positions", "account_id": "ABC123"}

Daemon responds:
{
  "status": "success",
  "data": {
    "positions": [
      {"symbol": "MNQ", "side": "long", "quantity": 2, "unrealized_pnl": 85.00},
      {"symbol": "ES", "side": "long", "quantity": 1, "unrealized_pnl": -25.00}
    ]
  }
}
```

### Authentication for Admin Commands

Admin commands (reload_config, stop_daemon) require authentication:

**Challenge-Response**:
1. CLI sends admin command
2. Daemon challenges with nonce
3. CLI hashes nonce + password
4. Daemon verifies hash
5. If valid, execute command

This prevents regular user from sending admin commands even if they figure out IPC.

---

## Auto-Start on Boot

### Windows Service Auto-Start

Setting service start type to **Automatic** ensures it starts on boot.

**Service Start Order**:
1. Windows boots
2. Network services start
3. Risk Manager Daemon starts (delayed start)
4. Daemon connects to broker
5. Ready before user logs in

**User Login**:
- Trader logs into their regular user account
- Daemon already running in background (under admin account)
- Trader can open Trader CLI and see daemon status

### Pre-Login Operation

Daemon can operate **before any user logs in**:
- Useful if markets open early (e.g., futures at 6pm ET Sunday)
- Daemon monitors positions even if trader isn't logged in
- Enforcement happens automatically

---

## Service Monitoring and Health Checks

### Watchdog Process

**Optional**: Separate watchdog process monitors daemon health:

```
Watchdog (lightweight process)
    ↓ (checks every 60 seconds)
Daemon (sends heartbeat)
```

If daemon stops responding:
- Watchdog alerts admin
- Watchdog attempts to restart daemon (if service manager didn't)

### Daemon Health Status

Daemon exposes health status via IPC:

```
{
  "status": "healthy",
  "uptime": 172800,  // seconds
  "accounts": {
    "ABC123": {
      "connected": true,
      "last_event": "2 seconds ago",
      "positions": 2,
      "lockout": false
    }
  },
  "memory_usage_mb": 245,
  "cpu_usage_percent": 1.2
}
```

CLI can query this to display in System Status menu.

---

## Logging and Debugging

### Service-Level Logging

Service wrapper logs:
- Service start/stop events
- Daemon process spawn
- Crashes and restarts
- Recovery actions

**Windows Event Log**:
- Critical events logged to Windows Event Log
- Admin can view via Event Viewer
- Useful for diagnosing service issues

**Service Log File**:
- `~/.risk_manager/logs/service.log`
- Detailed service wrapper operations

### Daemon Logging

Daemon logs to its own log files (see 07-notifications-logging.md):
- System log
- Enforcement log
- Error log

---

## Security Considerations

### Running as SYSTEM vs Admin Account

**Local System Account**:
- Highest privileges
- No network credentials (can't access network shares)
- Isolated from user accounts

**Dedicated Admin Account**:
- Lower privilege than SYSTEM (better security)
- Can be audited separately
- Requires password management

**Recommendation**: Local System account for simplicity, unless specific security requirements dictate otherwise.

### Service Hardening

**Best Practices**:
- Service runs with minimal required privileges
- Service cannot be stopped by regular users
- IPC communication authenticated (admin commands)
- Config files readable only by service account
- No sensitive data in service description or display name

---

## Installation and Uninstallation

### Installation Process

Admin runs installer:

```
admin> install-daemon

Risk Manager Daemon Installer

This will:
- Register Windows service
- Configure auto-start on boot
- Set permissions (unkillable by regular users)
- Create default configuration files

Proceed? [y/n]: y

Installing...
✓ Service registered
✓ Auto-start configured
✓ Permissions set
✓ Configuration created

Installation complete!

Next steps:
1. Configure accounts (risk-manager admin)
2. Configure risk rules
3. Start daemon (admin> start daemon)

Press Enter to continue...
```

### Uninstallation Process

Admin uninstalls:

```
admin> uninstall-daemon

This will:
- Stop daemon
- Unregister Windows service
- Optionally delete configuration and state files

Proceed? [y/n]: y

Stopping daemon...
Unregistering service...

Delete configuration files? [y/n]: n
Delete state files? [y/n]: n

Service uninstalled. Configuration preserved.
```

---

## Multi-User Environment

### Scenario: Same Computer, Different User Accounts

**Setup**:
- Admin account: Sets up daemon, configures rules
- Trader account: Logs in daily to trade

**Workflow**:
1. Admin logs in, installs daemon, configures
2. Admin logs out
3. Trader logs in to their account
4. Daemon already running (under admin account)
5. Trader opens Trader CLI, sees daemon status
6. Trader trades, daemon enforces
7. Trader logs out, daemon keeps running

**Why This Works**:
- Daemon runs as service (not tied to user session)
- Trader cannot kill service (different account)
- CLIs communicate with daemon via IPC (works across user accounts)

---

## Performance and Resource Usage

### Resource Monitoring

Daemon should be lightweight:
- **Memory**: <500 MB (even with multiple accounts)
- **CPU**: <2% (idle), <10% (active trading)
- **Network**: Minimal (SDK events only)
- **Disk I/O**: Low (periodic state saves, log writes)

### Optimization

- Use async I/O (don't block on network or disk)
- Lazy-load configuration (don't re-parse on every event)
- Cache frequently accessed data (current positions, PnL)
- Efficient data structures (dicts for fast lookups)

---

## Testing Strategy

### Service Installation Tests

```
Test: Service registers successfully
Given: Admin runs installer
When: Install command executed
Then: Service registered in Windows Service Manager
And: Service set to auto-start
```

### Unkillable Tests

```
Test: Regular user cannot stop service
Given: Daemon running as service
When: Regular user attempts to stop via Task Manager
Then: Access denied error
And: Service still running
```

### Auto-Start Tests

```
Test: Daemon starts on boot
Given: Service installed with auto-start
When: Computer rebooted
Then: Daemon running before user login
```

### Crash Recovery Tests

```
Test: Daemon restarts after crash
Given: Daemon running
When: Daemon process killed forcefully
Then: Service manager restarts daemon
And: State loaded from disk
And: Operations resume
```

---

## Platform Considerations

### Windows Versions

Target:
- Windows 10 and later
- Windows Server 2016 and later

Service creation may differ slightly between versions, but core functionality same.

### WSL Integration

Trader may use WSL for CLI:
- Daemon runs as Windows service (not in WSL)
- CLI in WSL can communicate with Windows daemon via TCP or named pipes (accessible from WSL)

Implementation agent must test IPC from WSL to Windows service.

---

## Summary for Implementation Agent

**To implement Daemon Service, you need to:**

1. **Create Windows service wrapper** (use `pywin32`, `nssm`, or similar)
2. **Register service** with Windows Service Manager
3. **Configure auto-start** and recovery settings
4. **Set service permissions** (admin only control)
5. **Implement graceful shutdown** (persist state before exit)
6. **Build IPC mechanism** (named pipes or HTTP API)
7. **Add authentication** for admin commands
8. **Create installer/uninstaller** scripts
9. **Implement crash recovery** (restart on failure)
10. **Test unkillable behavior** (regular user cannot stop)
11. **Handle state persistence** on shutdown and crash
12. **Test cross-user communication** (admin service, trader CLI)

The daemon service is the **foundation** of the unkillable design. It must be **reliable** (survive crashes), **secure** (admin-only control), and **transparent** (CLI can monitor it). This architecture ensures the trader cannot bypass risk enforcement, which is the core value proposition of the system.
