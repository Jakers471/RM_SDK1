# Configuration System Architecture

## Overview

The Configuration System manages all settings for the Risk Manager Daemon: accounts, risk rules, credentials, notification preferences, and system settings. Configuration must be flexible (per-account or universal rules), secure (protect API keys), validated (prevent invalid settings), and support hot-reload where safe.

## Core Responsibilities

1. **Store Configuration**: Accounts, risk rules, system settings
2. **Validate Configuration**: Ensure all settings are valid before applying
3. **Provide Access**: Clean interface for components to query config
4. **Security**: Protect sensitive data (API keys, passwords)
5. **Hot-Reload**: Apply config changes without daemon restart (where safe)
6. **Versioning**: Support config schema evolution

## Configuration Structure

Configuration is organized into **4 main sections**:

### 1. System Configuration
Global daemon settings

### 2. Account Configuration
Per-account settings (credentials, enabled accounts)

### 3. Risk Rule Configuration
Per-account or universal risk rules

### 4. Notification Configuration
Alert channels and preferences

---

## 1. System Configuration

**File**: `system.json`

**Contents**:
```json
{
  "version": "1.0",
  "daemon": {
    "auto_start": true,
    "log_level": "info",
    "state_persistence_path": "~/.risk_manager/state/",
    "daily_reset_time": "17:00",
    "timezone": "America/Chicago"
  },
  "admin": {
    "password_hash": "<bcrypt_hash>",
    "require_auth": true
  },
  "sdk": {
    "connection_timeout": 30,
    "reconnect_attempts": 5,
    "reconnect_delay": 10
  }
}
```

### Fields

**daemon**:
- `auto_start`: Start daemon on system boot (boolean)
- `log_level`: Logging verbosity ("debug", "info", "warning", "error")
- `state_persistence_path`: Where to save state files (string)
- `daily_reset_time`: Time for daily PnL reset (HH:MM format)
- `timezone`: Timezone for daily reset (string)

**admin**:
- `password_hash`: Hashed admin password (bcrypt)
- `require_auth`: Enforce admin auth for CLI (boolean)

**sdk**:
- `connection_timeout`: SDK connection timeout in seconds
- `reconnect_attempts`: How many times to retry on disconnect
- `reconnect_delay`: Delay between reconnect attempts

---

## 2. Account Configuration

**File**: `accounts.json`

**Contents**:
```json
{
  "accounts": [
    {
      "account_id": "ABC123",
      "account_name": "TopstepX Main",
      "enabled": true,
      "broker": "topstepx",
      "credentials": {
        "api_key": "<encrypted_or_env_var>",
        "api_secret": "<encrypted_or_env_var>",
        "account_number": "ABC123"
      },
      "risk_profile": "conservative"
    },
    {
      "account_id": "XYZ789",
      "account_name": "TopstepX Secondary",
      "enabled": false,
      "broker": "topstepx",
      "credentials": {
        "api_key": "<encrypted_or_env_var>",
        "api_secret": "<encrypted_or_env_var>",
        "account_number": "XYZ789"
      },
      "risk_profile": "aggressive"
    }
  ]
}
```

### Fields

**Per Account**:
- `account_id`: Unique identifier (string)
- `account_name`: Human-readable name (string)
- `enabled`: Monitor this account? (boolean)
- `broker`: Broker type (currently only "topstepx")
- `credentials`: Broker API credentials (object)
- `risk_profile`: References which risk rule set to use (string)

### Credential Security

**Options**:
1. **Environment Variables**: `api_key: "${TOPSTEP_API_KEY}"`
2. **Encrypted File**: Store encrypted, decrypt on load with master password
3. **External Secret Manager**: Integrate with vault service

Implementation agent decides best approach for Windows environment.

---

## 3. Risk Rule Configuration

**File**: `risk_rules.json`

**Contents**:
```json
{
  "profiles": {
    "conservative": {
      "rules": [
        {
          "rule": "MaxContracts",
          "enabled": true,
          "params": {
            "max_contracts": 2
          }
        },
        {
          "rule": "MaxContractsPerInstrument",
          "enabled": true,
          "params": {
            "limits": {
              "MNQ": 2,
              "ES": 1,
              "NQ": 1
            }
          }
        },
        {
          "rule": "DailyRealizedLoss",
          "enabled": true,
          "params": {
            "limit": -500.00
          }
        },
        {
          "rule": "DailyRealizedProfit",
          "enabled": true,
          "params": {
            "limit": 1000.00
          }
        },
        {
          "rule": "UnrealizedLoss",
          "enabled": true,
          "params": {
            "limit": -100.00
          }
        },
        {
          "rule": "UnrealizedProfit",
          "enabled": true,
          "params": {
            "limit": 300.00
          }
        },
        {
          "rule": "TradeFrequencyLimit",
          "enabled": true,
          "params": {
            "max_trades": 5,
            "window": "daily"
          }
        },
        {
          "rule": "CooldownAfterLoss",
          "enabled": true,
          "params": {
            "loss_threshold": -50.00,
            "cooldown_duration": 600
          }
        },
        {
          "rule": "NoStopLossGrace",
          "enabled": true,
          "params": {
            "grace_period": 5
          }
        },
        {
          "rule": "SessionBlockOutside",
          "enabled": true,
          "params": {
            "allowed_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "allowed_times": [
              {"start": "08:30", "end": "15:00"}
            ]
          }
        },
        {
          "rule": "SymbolBlock",
          "enabled": true,
          "params": {
            "blocked_symbols": ["GC", "CL"]
          }
        },
        {
          "rule": "AuthLossGuard",
          "enabled": true,
          "params": {
            "alert_only": true
          }
        }
      ]
    },
    "aggressive": {
      "rules": [
        {
          "rule": "MaxContracts",
          "enabled": true,
          "params": {
            "max_contracts": 4
          }
        },
        {
          "rule": "DailyRealizedLoss",
          "enabled": true,
          "params": {
            "limit": -1000.00
          }
        },
        {
          "rule": "UnrealizedLoss",
          "enabled": true,
          "params": {
            "limit": -200.00
          }
        }
      ]
    },
    "universal": {
      "rules": [
        {
          "rule": "AuthLossGuard",
          "enabled": true,
          "params": {
            "alert_only": true
          }
        }
      ]
    }
  },
  "account_overrides": {
    "ABC123": {
      "profile": "conservative",
      "rule_overrides": [
        {
          "rule": "MaxContracts",
          "params": {
            "max_contracts": 3
          }
        }
      ]
    }
  }
}
```

### Configuration Concepts

**Profiles**: Named rule sets (conservative, aggressive, etc.)
- Accounts reference a profile via `risk_profile` field
- Profiles can be reused across multiple accounts

**Universal Rules**: Applied to all accounts regardless of profile
- Defined in `universal` profile

**Account Overrides**: Per-account customization
- Override specific rule params without changing profile
- Merge with profile rules

### Rule Parameter Schemas

Each rule type has specific parameters:

**MaxContracts**:
- `max_contracts`: integer

**MaxContractsPerInstrument**:
- `limits`: dict {symbol: max_count}

**DailyRealizedLoss / DailyRealizedProfit**:
- `limit`: float (negative for loss, positive for profit)

**UnrealizedLoss / UnrealizedProfit**:
- `limit`: float (per-trade)

**TradeFrequencyLimit**:
- `max_trades`: integer
- `window`: "daily" | "per_hour" | "per_15min" | custom duration

**CooldownAfterLoss**:
- `loss_threshold`: float
- `cooldown_duration`: seconds

**NoStopLossGrace**:
- `grace_period`: seconds

**SessionBlockOutside**:
- `allowed_days`: list of day names
- `allowed_times`: list of time ranges {start: HH:MM, end: HH:MM}

**SymbolBlock**:
- `blocked_symbols`: list of symbol strings

**AuthLossGuard**:
- `alert_only`: boolean

---

## 4. Notification Configuration

**File**: `notifications.json`

**Contents**:
```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "webhook_url": "https://discord.com/api/webhooks/...",
      "username": "Risk Manager",
      "alert_levels": ["warning", "critical"]
    },
    "telegram": {
      "enabled": false,
      "bot_token": "<token>",
      "chat_id": "<chat_id>",
      "alert_levels": ["critical"]
    }
  },
  "per_account": {
    "ABC123": {
      "channels": ["discord"],
      "notify_on": {
        "enforcement_action": true,
        "lockout": true,
        "cooldown": true,
        "connection_loss": true
      }
    }
  }
}
```

### Fields

**channels**: Global notification channel configs
- `discord`: Discord webhook settings
- `telegram`: Telegram bot settings

**per_account**: Account-specific notification preferences
- Which channels to use
- Which events to notify on

Trader can modify their own notification settings via Trader CLI.

---

## Configuration Loading and Validation

### Loading Sequence

On daemon startup:

1. **Load system.json** → validate schema → apply system settings
2. **Load accounts.json** → validate → decrypt credentials
3. **Load risk_rules.json** → validate → build rule sets per account
4. **Load notifications.json** → validate → configure notification service

### Validation Rules

**System Config**:
- `timezone` must be valid IANA timezone
- `daily_reset_time` must be HH:MM format
- `log_level` must be valid level

**Account Config**:
- `account_id` must be unique
- `risk_profile` must exist in risk_rules.json
- `credentials` must have required fields for broker type

**Risk Rule Config**:
- All rule names must be valid (match implemented rules)
- All params must match rule's schema
- Numeric limits must be sane (e.g., max_contracts > 0)
- Time windows must be positive

**Notification Config**:
- Webhook URLs must be valid URLs
- Alert levels must be valid

### Validation Errors

If validation fails:
- **Log error with details**
- **Halt daemon startup** (don't run with invalid config)
- **Alert admin** via system notification

Admin must fix config and restart daemon.

---

## Configuration Access Interface

Components query configuration via clean interface:

```
ConfigManager:
    get_system_config() -> SystemConfig
    get_account_config(account_id) -> AccountConfig
    get_enabled_accounts() -> List[AccountConfig]
    get_rules_for_account(account_id) -> List[RuleConfig]
    get_notification_config(account_id) -> NotificationConfig
    reload_config() -> Result
```

**Example Usage**:
```python
risk_engine.py:

config_manager = ConfigManager()
account_config = config_manager.get_account_config("ABC123")
rules = config_manager.get_rules_for_account("ABC123")

for rule in rules:
    if rule.enabled:
        # Instantiate rule with params
        rule_instance = create_rule(rule.name, rule.params)
```

---

## Hot-Reload Support

### What Can Be Hot-Reloaded

**Safe to reload without restart**:
- Notification settings (channels, preferences)
- Log level changes
- Rule param adjustments (with caution)

**Requires daemon restart**:
- Account credentials (need SDK reconnect)
- Adding/removing accounts
- System-level settings (timezone, reset time)

### Hot-Reload Process

Admin triggers reload via Admin CLI:

```
admin> reload config
Reloading configuration...
- System config: No changes
- Accounts: No changes
- Risk rules: Updated MaxContracts limit for ABC123 (2 -> 3)
- Notifications: Updated Discord webhook URL
Config reloaded successfully.
```

Daemon:
1. Re-parse config files
2. Validate new config
3. Compare with current config
4. Apply safe changes
5. Log all changes
6. If unsafe changes detected, warn admin to restart

---

## Configuration Versioning

### Schema Evolution

As system evolves, config schema may change (new rules, new params):

**Version Field**: Each config file has `version` field

**Migration**: When daemon loads old version config:
- Detect version mismatch
- Run migration script to convert to new schema
- Save migrated config
- Log migration

**Example Migration**:
```
Detected risk_rules.json version 1.0 (current: 1.1)
Running migration 1.0 -> 1.1...
- Adding default params for new rule "AutoBreakeven"
Migration complete. Saving updated config.
```

---

## Security Considerations

### Credential Protection

**API Keys and Secrets**:
- Never log credentials
- Store encrypted or in environment variables
- Restrict file permissions (600 for config files)

**Admin Password**:
- Stored as bcrypt hash (never plaintext)
- Require strong password (8+ chars, mixed case, numbers)

### File Permissions

Config files should be:
- **Readable by daemon user only**
- **Writable by admin only**

On Windows, set ACLs appropriately.

---

## Default Configuration

On first install, daemon creates default configs:

**system.json**: Safe defaults (info logging, auth required)

**accounts.json**: Empty accounts list (admin must add)

**risk_rules.json**: Conservative profile with all rules enabled at safe limits

**notifications.json**: All channels disabled (admin must configure)

Admin guided through setup wizard on first run (via Admin CLI).

---

## Configuration Backup

Before modifying config:
- **Create backup** of current config files
- Store in `~/.risk_manager/config_backups/` with timestamp
- Allow admin to rollback via CLI

**Example**:
```
admin> rollback config
Available backups:
1. 2025-10-15_10:30:00
2. 2025-10-14_09:15:00
Select backup to restore: 1
Restoring config from 2025-10-15_10:30:00...
Config restored. Restart daemon to apply.
```

---

## Testing Strategy

### Validation Tests

Test config validation catches errors:

```
Test: Invalid timezone rejected
Given: system.json with timezone "Invalid/Timezone"
When: Load config
Then: Validation error raised
And: Daemon does not start
```

### Hot-Reload Tests

Test safe config changes applied without restart:

```
Test: Notification webhook updated
Given: Daemon running with discord webhook A
When: Update webhook to B and hot-reload
Then: Notifications sent to webhook B
And: Daemon still running
```

### Migration Tests

Test schema version migrations:

```
Test: Migrate v1.0 to v1.1
Given: Config files at version 1.0
When: Daemon starts with v1.1 code
Then: Migration applied
And: Config saved as v1.1
```

---

## Configuration UI (Admin CLI)

Admin CLI provides interactive config editing:

```
admin> config
Configuration Menu:
1. View system config
2. Edit system config
3. List accounts
4. Add account
5. Edit account
6. View risk rules for account
7. Edit risk rules
8. View notifications
9. Edit notifications
0. Back

Select option: 4

Add Account:
Account ID: TEST123
Account Name: Test Account
Broker: topstepx
API Key: ****************
API Secret: ****************
Risk Profile [conservative/aggressive]: conservative
Enable account? [y/n]: y

Account added successfully.
Restart daemon to connect to new account.
```

Implementation agent will design detailed CLI menus (see 06-cli-interfaces.md).

---

## Summary for Implementation Agent

**To implement Configuration System, you need to:**

1. **Define config file schemas** (JSON structure)
2. **Create config loading logic** (parse, decrypt credentials)
3. **Build validation framework** (check all config constraints)
4. **Implement ConfigManager interface** (query methods)
5. **Create hot-reload mechanism** (detect changes, apply safely)
6. **Build versioning and migration** (handle schema evolution)
7. **Secure credential storage** (encryption or env vars)
8. **Create default configs** (for first install)
9. **Implement config backup/restore** (before modifications)
10. **Design Admin CLI config editor** (interactive menus)

Configuration is the **control panel** of the system. It must be **flexible** (support many scenarios), **safe** (validate everything), and **secure** (protect secrets). Good configuration design makes the system usable and maintainable.
