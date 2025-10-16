# CLI Interfaces Architecture

## Overview

The Risk Manager Daemon provides **two distinct command-line interfaces** (CLIs): the Admin CLI for full system control, and the Trader CLI for daily monitoring. These interfaces are the primary way users interact with the system. They must be intuitive, responsive, and clearly separated by privilege level.

## Design Philosophy

### Admin CLI
- **Full Control**: Configure, start, stop, manage everything
- **Password Protected**: Requires admin authentication
- **Configuration Focus**: Primary use case is setup and management
- **Verbose Logging**: Access to detailed system logs

### Trader CLI
- **Read-Only**: View state, cannot modify rules or daemon
- **Real-Time Monitoring**: Live updates on positions, enforcement, timers
- **Limited Configuration**: Only personal settings (notifications, clock in/out)
- **User-Friendly**: Clear, non-technical language for enforcement logs

### Shared Characteristics
- **Terminal-Based**: Run in WSL or Windows Terminal
- **Interactive Menus**: Numbered options, not command-line arguments
- **Responsive**: Live updates (positions, timers, connection status)
- **Clear Feedback**: Confirm all actions, show success/error messages

---

## Admin CLI

### Entry Point

```
$ risk-manager admin

Risk Manager - Admin Interface
Please enter admin password: ********

Authentication successful.

=== ADMIN MENU ===
1. Daemon Control
2. Configuration
3. Accounts
4. Risk Rules
5. View Logs
6. System Status
0. Exit

Select option:
```

### 1. Daemon Control

```
=== DAEMON CONTROL ===
Current Status: Running (PID: 12345)
Uptime: 2 days, 5 hours, 23 minutes

1. Start Daemon
2. Stop Daemon
3. Restart Daemon
4. View Daemon Logs (live)
0. Back

Select option: 2

Are you sure you want to stop the daemon? [y/n]: y
Stopping daemon...
Daemon stopped successfully.
```

**Actions**:
- **Start**: Launch daemon process (if not running)
- **Stop**: Gracefully shutdown daemon (persists state)
- **Restart**: Stop then start (useful after config changes)
- **View Logs**: Tail daemon log file in real-time

### 2. Configuration

```
=== CONFIGURATION ===
1. View System Config
2. Edit System Config
3. Reload Config (hot-reload)
4. Backup Config
5. Restore Config
0. Back

Select option: 2

=== EDIT SYSTEM CONFIG ===
Current Settings:
  Log Level: info
  Daily Reset Time: 17:00 CT
  Timezone: America/Chicago
  Auto Start: true

Which setting to edit?
1. Log Level
2. Daily Reset Time
3. Timezone
4. Auto Start
0. Cancel

Select option: 1

Current log level: info
Available: debug, info, warning, error
New log level: debug

Log level updated to debug.
Reload config to apply? [y/n]: y
Config reloaded. Daemon now logging at debug level.
```

**Features**:
- View all config files
- Edit settings interactively
- Validate changes before saving
- Hot-reload where safe (warn if restart needed)
- Backup before changes
- Restore from backup

### 3. Accounts

```
=== ACCOUNTS ===
1. List Accounts
2. Add Account
3. Edit Account
4. Enable/Disable Account
5. Test Connection
0. Back

Select option: 1

=== ACCOUNTS LIST ===
ID         Name              Status      Connected   Risk Profile
ABC123     TopstepX Main     Enabled     Yes         conservative
XYZ789     TopstepX Backup   Disabled    No          aggressive

Select option: 2

=== ADD ACCOUNT ===
Account ID: NEW123
Account Name: New Test Account
Broker (topstepx): topstepx
API Key: ***************
API Secret: ***************
Account Number: NEW123
Risk Profile [conservative/aggressive/custom]: conservative
Enable account? [y/n]: y

Account added successfully.
Restart daemon to connect? [y/n]: y
Restarting daemon...
```

**Features**:
- List all configured accounts with status
- Add new accounts (with credential input)
- Edit account settings
- Enable/disable without deleting
- Test SDK connection for account

### 4. Risk Rules

```
=== RISK RULES ===
Select account: ABC123

=== RISK RULES FOR ABC123 ===
Using profile: conservative

Rule                        Status      Limit/Config
MaxContracts                Enabled     2 contracts
MaxContractsPerInstrument   Enabled     MNQ: 2, ES: 1
DailyRealizedLoss           Enabled     -$500.00
DailyRealizedProfit         Enabled     +$1000.00
UnrealizedLoss              Enabled     -$100.00 per trade
UnrealizedProfit            Enabled     +$300.00 per trade
TradeFrequencyLimit         Enabled     5 trades per day
CooldownAfterLoss           Enabled     -$50 → 600s cooldown
NoStopLossGrace             Enabled     5 seconds
SessionBlockOutside         Enabled     Mon-Fri 08:30-15:00 CT
SymbolBlock                 Enabled     Blocked: GC, CL
AuthLossGuard               Enabled     Alert only

1. Edit Rule
2. Enable/Disable Rule
3. Change Profile
4. Create Custom Profile
0. Back

Select option: 1

Which rule to edit? (1-12): 1

=== EDIT MaxContracts ===
Current limit: 2 contracts
New limit: 3

MaxContracts limit updated to 3.
This change will be applied on next config reload.
Reload now? [y/n]: y
Config reloaded.
```

**Features**:
- View all rules for account
- Edit individual rule parameters
- Enable/disable rules
- Switch between profiles
- Create custom profiles
- Preview changes before applying

### 5. View Logs

```
=== VIEW LOGS ===
1. Live Daemon Logs (tail -f)
2. Enforcement Log (recent)
3. Error Log
4. Search Logs
0. Back

Select option: 2

=== RECENT ENFORCEMENT ACTIONS ===
[2025-10-15 10:23:45] ABC123 | UnrealizedLoss
  Position: MNQ 2 contracts @ 5042.50
  Unrealized: -$210 (limit: -$200)
  Action: Closed position
  Result: Success

[2025-10-15 10:15:30] ABC123 | MaxContracts
  Position: Added 2 ES, total would be 5 (limit: 4)
  Action: Closed 1 ES contract
  Result: Success

[2025-10-15 09:45:12] ABC123 | DailyRealizedLoss
  Realized PnL: -$550 (limit: -$500)
  Action: Flattened all positions, account locked out until 17:00
  Result: Success

Press Enter to continue...
```

**Features**:
- Real-time log tailing
- View enforcement history
- Filter by account, rule, time range
- Search logs by keyword
- Export logs to file

### 6. System Status

```
=== SYSTEM STATUS ===

Daemon: Running (PID: 12345)
Uptime: 2 days, 5 hours, 23 minutes
Version: 1.0.0

Accounts:
  ABC123: Connected, 2 open positions
  XYZ789: Disabled

SDK Connections:
  TopstepX: Connected (latency: 45ms)

State Persistence:
  Last save: 10 seconds ago
  Location: /home/user/.risk_manager/state/

Memory Usage: 245 MB
CPU Usage: 1.2%

Recent Activity:
  - 10:23:45: Enforcement action (ABC123)
  - 10:15:30: Enforcement action (ABC123)
  - 09:45:12: Account lockout (ABC123)

Press Enter to refresh...
```

**Features**:
- Daemon health and uptime
- Connection status per account
- Resource usage
- Recent activity summary
- Live refresh

---

## Trader CLI

### Entry Point

```
$ risk-manager

Risk Manager - Trader Interface

=== TRADER MENU ===
1. Dashboard
2. View Positions
3. View Risk Rules
4. Enforcement Log
5. Notifications Settings
6. Clock In/Out
7. Connection Status
8. Admin Mode (requires password)
0. Exit

Select option:
```

**Note**: No password required for trader mode.

### 1. Dashboard

```
=== DASHBOARD ===

Account: ABC123 (TopstepX Main)
Status: Active | Connected ✓

Current Positions:
  MNQ: 2 Long @ 5042.50 | Unrealized: +$85.00
  ES:  1 Long @ 4525.00 | Unrealized: -$25.00

PnL Today:
  Realized:   -$150.00
  Unrealized: +$60.00
  Combined:   -$90.00

Risk Limits:
  Daily Loss Limit: -$90.00 / -$500.00 (18% used)
  Daily Profit Limit: -$90.00 / +$1000.00

  Trades Today: 3 / 5

Lockout Status: None
Cooldown Status: None

Active Timers:
  (None)

Press 'r' to refresh | 'b' for back
```

**Features**:
- Overview of current state
- Open positions with live PnL
- Daily PnL vs limits (progress bars)
- Lockout/cooldown status
- Live timers for resets
- Auto-refresh every 5 seconds

### 2. View Positions

```
=== OPEN POSITIONS ===

Account: ABC123

Symbol  Side  Qty  Entry      Current    Unrealized  Stop Loss
MNQ     Long  2    5042.50    5063.25    +$415.00    5025.00 ✓
ES      Long  1    4525.00    4520.00    -$250.00    4510.00 ✓

Total Positions: 2
Total Unrealized: +$165.00

Press 'r' to refresh | 'b' for back
```

**Features**:
- List all open positions
- Live unrealized PnL per position
- Stop loss status (attached or missing)
- Auto-refresh

### 3. View Risk Rules

```
=== ACTIVE RISK RULES ===

Account: ABC123
Profile: Conservative

Contract Limits:
  Max Total Contracts: 2
  Per Instrument: MNQ=2, ES=1

Daily Limits:
  Max Realized Loss: -$500.00
  Max Realized Profit: +$1000.00

Per-Trade Limits:
  Max Unrealized Loss: -$100.00
  Max Unrealized Profit: +$300.00

Trading Rules:
  Max Trades per Day: 5
  Cooldown After Loss: -$50 → 600 seconds
  Stop Loss Required: 5 seconds grace
  Allowed Sessions: Mon-Fri 08:30-15:00 CT
  Blocked Symbols: GC, CL

Press Enter to continue...
```

**Features**:
- Read-only view of all active rules
- Formatted for easy reading (non-technical)
- Shows trader what limits are enforced
- Cannot modify (admin only)

### 4. Enforcement Log

```
=== ENFORCEMENT LOG ===

[10:23:45] Position Closed
  Reason: Unrealized loss limit exceeded
  Details: MNQ 2 contracts reached -$210 (limit: -$200)
  Action: Position closed automatically

[10:15:30] Position Reduced
  Reason: Max contracts exceeded
  Details: Attempted 5 total contracts (limit: 4)
  Action: Closed 1 ES contract

[09:45:12] ACCOUNT LOCKED OUT
  Reason: Daily realized loss limit exceeded
  Details: Realized loss -$550 (limit: -$500)
  Action: All positions closed, trading locked until 5:00 PM CT
  Time Remaining: 6 hours, 14 minutes

Press 'n' for next page | 'b' for back
```

**Features**:
- Recent enforcement actions (non-verbose, trader-friendly)
- **Red text** for enforcement messages
- Clear explanation of why action taken
- Countdown for lockout expiration
- Paginated (show 10 at a time)

### 5. Notification Settings

```
=== NOTIFICATION SETTINGS ===

Account: ABC123

Discord: Enabled
  Webhook: https://discord.com/api/webhooks/...
  Test Notification: Send Test

Telegram: Disabled
  Enable Telegram? [y/n]

Notify On:
  ✓ Enforcement Actions
  ✓ Account Lockout
  ✓ Cooldown Started
  ✓ Connection Loss

1. Enable/Disable Discord
2. Enable/Disable Telegram
3. Configure Discord Webhook
4. Configure Telegram Bot
5. Toggle Notification Types
0. Back

Select option: 3

Enter new Discord webhook URL: https://discord.com/api/webhooks/new_url
Webhook updated. Sending test notification...
Test notification sent successfully!
```

**Features**:
- Configure notification channels (trader can modify)
- Test notifications
- Choose which events to be notified about
- Enable/disable channels

### 6. Clock In/Out

```
=== CLOCK IN/OUT ===

Status: Not Clocked In

Total Hours Today: 0h 0m
Total Hours This Week: 5h 32m

1. Clock In
2. Clock Out
3. View History
0. Back

Select option: 1

Clocked in at 10:25:30 AM
Welcome to trading!

--- Later ---

Select option: 2

Clocked out at 3:00:15 PM
Session duration: 4h 34m 45s
Great trading today!
```

**Features**:
- Simple clock in/out tracking
- Session duration tracking
- Weekly/monthly stats
- Personal accountability tool (no enforcement tied to it)

### 7. Connection Status

```
=== CONNECTION STATUS ===

Daemon: Running ✓
Uptime: 2 days, 5 hours

Account: ABC123
  Broker: TopstepX
  Connection: Connected ✓
  Latency: 45ms
  Last Event: 2 seconds ago

SDK Status: Healthy
Last Heartbeat: 1 second ago

Press 'r' to refresh | 'b' for back
```

**Features**:
- Real-time connection health
- Latency monitoring
- Last event received timestamp
- Alerts if disconnected

### 8. Admin Mode

```
Select option: 8

Switching to Admin Mode...
Please enter admin password: ********

Authentication successful.

[Enters Admin CLI menu]
```

**Features**:
- Seamless transition from trader to admin
- Requires password authentication
- Returns to trader mode when admin exits

---

## Live Updates and Timers

### Trader CLI Live Features

**Auto-Refresh**:
- Dashboard auto-refreshes every 5 seconds
- Positions auto-refresh every 2 seconds
- Enforcement log updates in real-time

**Live Timers**:
When account locked out or in cooldown:

```
=== DASHBOARD ===

Lockout Status: ACTIVE
  Reason: Daily loss limit exceeded
  Locked until: 5:00 PM CT
  Time Remaining: 6h 14m 23s ⏳

Cooldown Status: None
```

Timer counts down in real-time (updates every second).

**Enforcement Alerts**:
When enforcement action occurs, CLI shows **flash message** in red:

```
⚠️  ENFORCEMENT ACTION ⚠️
Position MNQ closed: Unrealized loss limit exceeded
See Enforcement Log for details
```

---

## Terminal UI Framework

### Implementation Approach

**Option 1: Simple Print/Input**
- Use basic `print()` and `input()` for menus
- Clear screen with `os.system('clear')` or `cls`
- Simple but functional

**Option 2: Rich Terminal Library**
- Use library like `rich` (Python) for colors, tables, progress bars
- Prettier, more professional
- Live tables for positions

**Option 3: Full TUI Framework**
- Use `curses` or `textual` for full terminal UI
- Split panes, live updates without refresh
- More complex but best UX

**Recommendation**: Start with Option 2 (Rich library) for balance of UX and complexity.

### Colors and Formatting

**Admin CLI**:
- Headers: Cyan
- Success messages: Green
- Error messages: Red
- Warnings: Yellow

**Trader CLI**:
- Enforcement messages: Red (bold)
- Profit PnL: Green
- Loss PnL: Red
- Timers: Yellow
- Connection status: Green (connected) / Red (disconnected)

---

## CLI Session Management

### Persistent Sessions

Trader CLI can run as persistent session:

```
$ risk-manager --watch

Running in watch mode...
Dashboard will update automatically.
Press Ctrl+C to exit.

[Dashboard displayed and auto-refreshes]
```

Useful for leaving CLI open on second monitor during trading.

---

## Error Handling in CLI

### User Input Validation

Invalid selections:
```
Select option: 99
Invalid option. Please enter a number from 0-8.
```

Invalid values:
```
New limit: -5
Error: Limit must be positive. Please try again.
New limit: 3
```

### System Errors

If daemon not running (Trader CLI):
```
Error: Cannot connect to daemon.
The Risk Manager daemon is not running.

Please contact admin to start the daemon.
```

If daemon not running (Admin CLI):
```
Error: Daemon is not running.

Would you like to start it now? [y/n]: y
Starting daemon...
Daemon started successfully.
```

---

## Cross-Platform Considerations

### Windows vs Linux (WSL)

- **Path handling**: Use `pathlib` for cross-platform paths
- **Clear screen**: Detect OS and use `cls` (Windows) or `clear` (Linux)
- **Color support**: Check terminal capabilities before using colors

### Terminal Compatibility

- Test on Windows Terminal, WSL, PowerShell
- Fallback to plain text if colors not supported

---

## Testing Strategy

### Manual Testing

- Test all menu flows (every option)
- Test input validation (invalid inputs)
- Test authentication (wrong password, lockouts)
- Test live updates (watch mode)

### Automated Testing

- Mock daemon responses
- Test CLI commands programmatically
- Verify output formatting

---

## Accessibility

### User-Friendly Design

- **Clear labels**: "Max Contracts: 4" not "mc: 4"
- **Explain actions**: "This will stop the daemon and close all positions"
- **Confirm destructive actions**: "Are you sure? [y/n]"
- **Help text**: `?` shows help for current menu

### Navigation

- **Numbered menus**: Easy to select
- **Breadcrumbs**: Show current location (Main > Config > Edit)
- **Back option**: Always `0` to go back
- **Exit option**: Available at top level

---

## Summary for Implementation Agent

**To implement CLI interfaces, you need to:**

1. **Create Admin CLI** with all management menus
2. **Create Trader CLI** with read-only monitoring menus
3. **Implement authentication** (password for admin mode)
4. **Build live update mechanism** (auto-refresh, timers)
5. **Add color/formatting** for better UX (rich library)
6. **Handle user input validation** and errors gracefully
7. **Create watch mode** for persistent dashboard
8. **Integrate with daemon** via IPC or API
9. **Test on Windows Terminal and WSL**
10. **Document all menus** and options

The CLI is the **user's window** into the system. It must be **intuitive** (easy to navigate), **informative** (show all relevant data), and **responsive** (live updates). Good CLI design makes the difference between a tool users trust and a tool they avoid.
