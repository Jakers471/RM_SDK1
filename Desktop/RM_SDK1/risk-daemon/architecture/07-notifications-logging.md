# Notifications and Logging Architecture

## Overview

The Notification and Logging System provides visibility into daemon operations, enforcement actions, and system health. Notifications alert the trader in real-time via external channels (Discord, Telegram), while logging creates a permanent audit trail for review and debugging.

## Core Responsibilities

### Notification Service
1. **Real-Time Alerts**: Send notifications to Discord/Telegram on key events
2. **Channel Management**: Support multiple notification channels
3. **Severity Levels**: Different alert levels (info, warning, critical)
4. **Per-Account Config**: Traders configure their own notification preferences
5. **Rate Limiting**: Prevent notification spam during rapid events

### Logging System
1. **Audit Trail**: Record all enforcement actions with full context
2. **System Logs**: Daemon operations, errors, debug info
3. **Multiple Log Levels**: debug, info, warning, error, critical
4. **Structured Logging**: Parseable format for analysis
5. **Log Rotation**: Manage log file sizes
6. **CLI Integration**: Display logs in Trader/Admin CLI

---

## Notification Service Design

### Supported Channels

**Discord** (via Webhooks):
- Easy setup (just webhook URL)
- Rich embeds with colors and formatting
- No rate limits for reasonable usage

**Telegram** (via Bot API):
- Requires bot token and chat ID
- Supports Markdown formatting
- Good mobile notifications

**Future Channels**:
- Email (SMTP)
- SMS (Twilio)
- Slack
- Custom webhooks

### Notification Types

**Enforcement Actions**:
- Position closed (per-trade limit)
- Account flattened (daily limit)
- Account locked out
- Cooldown started

**System Events**:
- Daemon started/stopped
- Connection loss
- Connection restored
- Configuration reloaded

**Errors**:
- Enforcement action failed
- SDK error
- Configuration error

### Severity Levels

**Info**: Normal operations
- Position closed (per-trade limit)
- Cooldown expired
- Daily reset occurred

**Warning**: Attention needed but not critical
- Approaching daily limits (e.g., 80% of loss limit)
- Cooldown started
- Frequent enforcement actions

**Critical**: Immediate attention required
- Account locked out
- Daily limit hit
- Connection loss
- Enforcement action failed
- System error

### Notification Message Format

**Discord Embed Example**:
```
Title: 🚨 Position Closed - Unrealized Loss Limit
Color: Red (#FF0000)

Fields:
  Account: ABC123 (TopstepX Main)
  Position: MNQ 2 contracts @ 5042.50
  Unrealized PnL: -$210.00
  Limit: -$200.00
  Action: Position closed automatically
  Time: 2025-10-15 10:23:45 CT

Footer: Risk Manager Daemon
```

**Telegram Message Example**:
```
🚨 *Position Closed - Unrealized Loss Limit*

Account: ABC123 (TopstepX Main)
Position: MNQ 2 contracts @ 5042.50
Unrealized PnL: -$210.00
Limit: -$200.00
Action: Position closed automatically

Time: 2025-10-15 10:23:45 CT
```

### Notification Service Interface

```
NotificationService:
    send_enforcement_alert(account_id, rule_name, details, severity)
    send_system_alert(message, severity)
    send_error_alert(error_message, context)
    test_channel(channel_name, account_id)
```

### Implementation Design

**Async Delivery**:
- Notifications sent asynchronously (don't block daemon)
- Queued and delivered in background thread
- Retry failed deliveries (with backoff)

**Error Handling**:
- If notification fails (network error, invalid webhook):
  - Log error
  - Retry up to 3 times
  - If still fails, log and continue (don't crash daemon)

**Rate Limiting**:
- Prevent spam during rapid enforcement (e.g., 10 positions closed in 5 seconds)
- Aggregate multiple similar events into single notification:
  ```
  🚨 Multiple Enforcement Actions (5 positions closed)

  Account: ABC123
  Reason: Daily loss limit exceeded
  Actions: Flattened all positions, account locked out
  Positions closed: MNQ, ES, NQ, GC, CL
  ```

---

## Logging System Design

### Log Levels

**DEBUG**: Very detailed info for troubleshooting
- Event processing details
- State updates
- SDK communication

**INFO**: Normal operations
- Daemon started/stopped
- Enforcement actions
- Daily resets
- Configuration changes

**WARNING**: Unusual but not error
- Approaching limits
- Retrying failed action
- State reconciliation needed

**ERROR**: Something failed but system continues
- Enforcement action failed
- SDK error
- Invalid event data

**CRITICAL**: Severe error, system may halt
- Cannot load configuration
- State corruption
- Cannot connect to broker

### Log Categories

**System Log** (`system.log`):
- Daemon lifecycle (start, stop, restart)
- Configuration loading/reloading
- SDK connection status
- Performance metrics

**Enforcement Log** (`enforcement.log`):
- All enforcement actions
- Rule violations
- Actions taken (close, flatten, lockout)
- Results (success/failure)

**Error Log** (`error.log`):
- All errors and exceptions
- Stack traces
- Context for debugging

**Audit Log** (`audit.log`):
- All state changes
- Configuration modifications (who, what, when)
- Admin CLI actions
- Critical events

### Log Format

**Structured Logging** (JSON format for parsing):

```json
{
  "timestamp": "2025-10-15T10:23:45.123Z",
  "level": "INFO",
  "category": "enforcement",
  "account_id": "ABC123",
  "rule": "UnrealizedLoss",
  "event": "position_closed",
  "details": {
    "position": {
      "symbol": "MNQ",
      "quantity": 2,
      "entry_price": 5042.50,
      "current_price": 5000.00
    },
    "unrealized_pnl": -210.00,
    "limit": -200.00,
    "action": "close_position",
    "result": "success"
  },
  "message": "Position closed due to unrealized loss limit exceeded"
}
```

**Human-Readable Format** (for CLI display):

```
[2025-10-15 10:23:45] INFO | enforcement | ABC123 | UnrealizedLoss
Position closed: MNQ 2 contracts @ 5042.50
Unrealized PnL: -$210.00 (limit: -$200.00)
Action: Close position
Result: Success
```

### Log Storage

**Location**:
- System log: `~/.risk_manager/logs/system.log`
- Enforcement log: `~/.risk_manager/logs/enforcement.log`
- Error log: `~/.risk_manager/logs/error.log`
- Audit log: `~/.risk_manager/logs/audit.log`

**Rotation**:
- Max file size: 50 MB
- Keep last 10 rotated files
- Compress old logs (gzip)
- Delete logs older than 90 days

### Logging Interface

```
Logger:
    debug(message, context)
    info(message, context)
    warning(message, context)
    error(message, context, exception)
    critical(message, context, exception)

    log_enforcement(account_id, rule, action, details)
    log_system_event(event_type, details)
    log_audit(action, actor, details)
```

---

## CLI Integration

### Trader CLI Enforcement Log

**Display Format** (user-friendly, non-verbose):

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

[09:45:12] ⚠️ ACCOUNT LOCKED OUT ⚠️
  Reason: Daily realized loss limit exceeded
  Details: Realized loss -$550 (limit: -$500)
  Action: All positions closed, trading locked until 5:00 PM CT
```

**Features**:
- Recent actions only (last 20)
- Red text for enforcement
- Clear, simple language (no technical jargon)
- Highlights lockouts and critical events

### Admin CLI Logs

**Verbose Log View**:

```
=== DAEMON LOGS (LIVE) ===

[10:23:45.123] DEBUG | event_bus | Received position_update event for ABC123 MNQ
[10:23:45.124] DEBUG | risk_engine | Evaluating UnrealizedLoss rule
[10:23:45.125] INFO  | risk_engine | UnrealizedLoss violated: -210 > -200
[10:23:45.126] INFO  | enforcement | Executing close_position for MNQ
[10:23:45.127] DEBUG | sdk_adapter | Sending close order to broker
[10:23:45.340] INFO  | sdk_adapter | Close order filled @ 5000.00
[10:23:45.341] INFO  | state_manager | Position MNQ closed, realized -$210
[10:23:45.342] INFO  | enforcement | Enforcement action completed successfully

Press Ctrl+C to stop...
```

**Features**:
- All log levels visible
- Technical details for debugging
- Live tail (updates in real-time)
- Searchable and filterable

---

## Enforcement Logging Details

Every enforcement action logs:

1. **Timestamp**: Exact time of action
2. **Account**: Which account
3. **Rule**: Which rule violated
4. **Violation Details**:
   - Current value vs limit
   - Position details (symbol, quantity, price)
   - PnL amounts
5. **Action Taken**:
   - What was done (close, flatten, lockout)
   - How many positions affected
6. **Result**:
   - Success or failure
   - If failed, error details
7. **State After**:
   - New realized PnL
   - Remaining positions
   - Lockout status

### Example Enforcement Log Entry

```json
{
  "timestamp": "2025-10-15T10:23:45.342Z",
  "level": "INFO",
  "category": "enforcement",
  "account_id": "ABC123",
  "account_name": "TopstepX Main",
  "rule": "UnrealizedLoss",
  "violation": {
    "current_value": -210.00,
    "limit": -200.00,
    "threshold_exceeded_by": -10.00
  },
  "position": {
    "symbol": "MNQ",
    "side": "long",
    "quantity": 2,
    "entry_price": 5042.50,
    "exit_price": 5000.00,
    "unrealized_pnl": -210.00
  },
  "action": {
    "type": "close_position",
    "positions_closed": 1,
    "contracts_closed": 2
  },
  "result": {
    "status": "success",
    "order_id": "1234567890",
    "fill_price": 5000.00,
    "realized_pnl": -210.00
  },
  "state_after": {
    "realized_pnl_today": -360.00,
    "open_positions": 1,
    "lockout": false
  }
}
```

This provides complete audit trail for every enforcement.

---

## Performance Considerations

### Async Logging

- Log writes happen asynchronously (don't block event processing)
- Use buffered writes (flush every 1 second or on critical events)

### Log Volume

Expected log volume per day:
- **Low trading**: ~1000 log entries (5 MB)
- **High trading**: ~10000 log entries (50 MB)

With rotation at 50 MB, should handle easily.

### Notification Rate Limiting

Prevent spam:
- Max 10 notifications per minute per channel
- If exceeded, aggregate into summary notification

---

## Testing Strategy

### Notification Tests

```
Test: Discord notification sent on enforcement
Given: Enforcement action occurs
When: send_enforcement_alert called
Then: Discord webhook receives message
And: Message format matches expected
```

```
Test: Failed notification retried
Given: Discord webhook returns 500 error
When: send_enforcement_alert called
Then: Retry attempted 3 times
And: Error logged after exhaustion
```

### Logging Tests

```
Test: Enforcement log entry created
Given: Position closed by rule
When: log_enforcement called
Then: Entry written to enforcement.log
And: Entry contains all required fields
```

```
Test: Log rotation works
Given: Log file reaches 50 MB
When: New log entry written
Then: File rotated to .1 suffix
And: New file created
```

---

## Configuration

### Notification Config (per trader)

```json
{
  "account_id": "ABC123",
  "channels": {
    "discord": {
      "enabled": true,
      "webhook_url": "https://discord.com/api/webhooks/...",
      "severity_levels": ["warning", "critical"]
    },
    "telegram": {
      "enabled": false
    }
  },
  "notify_on": {
    "enforcement_action": true,
    "lockout": true,
    "cooldown": true,
    "connection_loss": true,
    "daily_reset": false
  },
  "rate_limit": {
    "max_per_minute": 10,
    "aggregate_similar": true
  }
}
```

### Logging Config (system-wide)

```json
{
  "log_level": "info",
  "log_path": "~/.risk_manager/logs/",
  "rotation": {
    "max_size_mb": 50,
    "max_files": 10,
    "compress": true
  },
  "retention_days": 90,
  "structured_format": true
}
```

---

## Monitoring and Alerting

### Health Checks

Daemon periodically checks:
- Notification channels reachable (test ping)
- Log files writable
- Disk space available for logs

If issues detected, alert admin.

### Metrics

Track:
- Notifications sent per channel
- Notification failures
- Log entries per level
- Log file sizes

Display in Admin CLI system status.

---

## Privacy and Security

### Sensitive Data

Never log:
- API keys or secrets
- Passwords
- Full account credentials

Mask in logs:
```
API Key: ******1234 (last 4 digits only)
```

### Log Access

- Log files readable by daemon user and admin only
- File permissions: 600 (user read/write only)

---

## Summary for Implementation Agent

**To implement Notifications and Logging, you need to:**

1. **Build NotificationService** with Discord and Telegram support
2. **Implement structured logging** (JSON format)
3. **Create log rotation** mechanism (50 MB limit)
4. **Integrate with CLI** (live log viewing, enforcement log)
5. **Implement rate limiting** for notifications
6. **Add retry logic** for failed notifications
7. **Create log categories** (system, enforcement, error, audit)
8. **Build aggregation** for similar rapid events
9. **Implement health checks** for notification channels
10. **Secure log files** (permissions, no secrets logged)

Notifications and logging provide **visibility and accountability**. Traders need real-time alerts (notifications) and historical records (logs) to trust the system and understand its actions. Good logging also makes debugging and auditing possible.
