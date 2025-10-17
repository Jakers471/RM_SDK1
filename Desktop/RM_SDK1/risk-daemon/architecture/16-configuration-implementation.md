# Configuration System Implementation

## Overview

This document provides detailed implementation specifications for the Configuration System described in `05-configuration-system.md`. While the high-level architecture defines WHAT the configuration system does, this document specifies HOW to implement it with specific file formats, validation schemas, Python libraries, and error handling patterns.

**Implementation Status**: NOT IMPLEMENTED (P0 Priority)
**Dependencies**: None (foundational component)
**Estimated Effort**: 3-5 days

## Core Implementation Requirements

1. **File Format**: JSON with schema validation (JSON Schema Draft 7)
2. **Library**: Use Python's `jsonschema` for validation, `pydantic` for data models
3. **File I/O**: Atomic writes (write to temp, then rename) to prevent corruption
4. **Hot-Reload**: File watcher using `watchdog` library for safe changes
5. **Credential Security**: Use environment variable substitution + optional encryption
6. **Backup Management**: Timestamped backups before any modification

---

## Configuration File Schemas

### 1. System Configuration Schema

**File**: `config/system.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "System Configuration",
  "type": "object",
  "required": ["version", "daemon", "admin", "sdk"],
  "properties": {
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+$",
      "description": "Config schema version (e.g., '1.0')"
    },
    "daemon": {
      "type": "object",
      "required": ["auto_start", "log_level", "state_persistence_path", "daily_reset_time", "timezone"],
      "properties": {
        "auto_start": {"type": "boolean"},
        "log_level": {"enum": ["debug", "info", "warning", "error"]},
        "state_persistence_path": {"type": "string"},
        "daily_reset_time": {
          "type": "string",
          "pattern": "^([01]\\d|2[0-3]):([0-5]\\d)$"
        },
        "timezone": {
          "type": "string",
          "enum": ["America/Chicago", "America/New_York", "America/Los_Angeles", "UTC"]
        }
      }
    },
    "admin": {
      "type": "object",
      "required": ["password_hash", "require_auth"],
      "properties": {
        "password_hash": {
          "type": "string",
          "pattern": "^\\$2[aby]\\$\\d+\\$.{53}$"
        },
        "require_auth": {"type": "boolean"}
      }
    },
    "sdk": {
      "type": "object",
      "required": ["connection_timeout", "reconnect_attempts", "reconnect_delay"],
      "properties": {
        "connection_timeout": {
          "type": "integer",
          "minimum": 5,
          "maximum": 300
        },
        "reconnect_attempts": {
          "type": "integer",
          "minimum": 1,
          "maximum": 20
        },
        "reconnect_delay": {
          "type": "integer",
          "minimum": 1,
          "maximum": 60
        }
      }
    }
  }
}
```

### 2. Accounts Configuration Schema

**File**: `config/accounts.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Accounts Configuration",
  "type": "object",
  "required": ["accounts"],
  "properties": {
    "accounts": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["account_id", "account_name", "enabled", "broker", "credentials", "risk_profile"],
        "properties": {
          "account_id": {"type": "string", "minLength": 1},
          "account_name": {"type": "string", "minLength": 1},
          "enabled": {"type": "boolean"},
          "broker": {"enum": ["topstepx"]},
          "credentials": {
            "type": "object",
            "required": ["api_key", "api_secret", "account_number"],
            "properties": {
              "api_key": {"type": "string"},
              "api_secret": {"type": "string"},
              "account_number": {"type": "string"}
            }
          },
          "risk_profile": {"type": "string", "minLength": 1}
        }
      },
      "uniqueItems": true
    }
  }
}
```

### 3. Risk Rules Configuration Schema

**File**: `config/risk_rules.json`

(Schema omitted for brevity - see `05-configuration-system.md` for structure. Schema validates: profiles exist, rule names valid, params match rule requirements)

---

## Python Data Models (Pydantic)

### SystemConfig Model

```python
from pydantic import BaseModel, Field, validator
from enum import Enum
from typing import Literal

class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class DaemonConfig(BaseModel):
    auto_start: bool
    log_level: LogLevel
    state_persistence_path: str
    daily_reset_time: str = Field(..., regex=r"^([01]\d|2[0-3]):([0-5]\d)$")
    timezone: Literal["America/Chicago", "America/New_York", "America/Los_Angeles", "UTC"]

class AdminConfig(BaseModel):
    password_hash: str = Field(..., regex=r"^\$2[aby]\$\d+\$.{53}$")
    require_auth: bool

class SdkConfig(BaseModel):
    connection_timeout: int = Field(..., ge=5, le=300)
    reconnect_attempts: int = Field(..., ge=1, le=20)
    reconnect_delay: int = Field(..., ge=1, le=60)

class SystemConfig(BaseModel):
    version: str = Field(..., regex=r"^\d+\.\d+$")
    daemon: DaemonConfig
    admin: AdminConfig
    sdk: SdkConfig

    @validator("version")
    def validate_version(cls, v):
        if v != "1.0":
            raise ValueError(f"Unsupported config version: {v}")
        return v
```

### AccountConfig Model

```python
from typing import Dict

class Credentials(BaseModel):
    api_key: str
    api_secret: str
    account_number: str

    def resolve_env_vars(self):
        """Replace ${VAR} patterns with environment variables."""
        import os
        import re

        for field in ["api_key", "api_secret"]:
            value = getattr(self, field)
            if value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                resolved = os.getenv(env_var)
                if resolved is None:
                    raise ValueError(f"Environment variable {env_var} not set")
                setattr(self, field, resolved)

class Account(BaseModel):
    account_id: str
    account_name: str
    enabled: bool
    broker: Literal["topstepx"]
    credentials: Credentials
    risk_profile: str

class AccountsConfig(BaseModel):
    accounts: List[Account]

    @validator("accounts")
    def validate_unique_ids(cls, v):
        ids = [acc.account_id for acc in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate account_id found")
        return v
```

---

## ConfigManager Implementation

### Class Structure

```python
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import ValidationError
import bcrypt
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ConfigManager:
    """Central configuration management for Risk Manager Daemon."""

    def __init__(self, config_dir: str = "~/.risk_manager/config"):
        self.config_dir = Path(config_dir).expanduser()
        self.backup_dir = self.config_dir / "backups"

        # Ensure directories exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)

        # Loaded configurations
        self.system: Optional[SystemConfig] = None
        self.accounts: Optional[AccountsConfig] = None
        self.risk_rules: Optional[RiskRulesConfig] = None
        self.notifications: Optional[NotificationsConfig] = None

        # File watcher for hot-reload
        self.observer: Optional[Observer] = None
        self.reload_callbacks = []

    def load_all(self):
        """Load all configuration files on daemon startup."""
        try:
            self.system = self._load_system_config()
            self.accounts = self._load_accounts_config()
            self.risk_rules = self._load_risk_rules_config()
            self.notifications = self._load_notifications_config()

            # Validate cross-references
            self._validate_cross_references()

            return True
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")

    def _load_system_config(self) -> SystemConfig:
        """Load and validate system.json."""
        path = self.config_dir / "system.json"

        if not path.exists():
            raise ConfigurationError(f"System config not found: {path}")

        try:
            with open(path, 'r') as f:
                data = json.load(f)

            # Validate with Pydantic
            config = SystemConfig(**data)
            return config

        except ValidationError as e:
            raise ConfigurationError(f"Invalid system.json: {e}")
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Malformed JSON in system.json: {e}")

    def _load_accounts_config(self) -> AccountsConfig:
        """Load and validate accounts.json."""
        path = self.config_dir / "accounts.json"

        if not path.exists():
            # No accounts configured yet - return empty
            return AccountsConfig(accounts=[])

        try:
            with open(path, 'r') as f:
                data = json.load(f)

            config = AccountsConfig(**data)

            # Resolve environment variables in credentials
            for account in config.accounts:
                account.credentials.resolve_env_vars()

            return config

        except ValidationError as e:
            raise ConfigurationError(f"Invalid accounts.json: {e}")

    def _validate_cross_references(self):
        """Validate that accounts reference valid risk profiles."""
        if not self.accounts or not self.risk_rules:
            return

        available_profiles = set(self.risk_rules.profiles.keys())

        for account in self.accounts.accounts:
            if account.risk_profile not in available_profiles:
                raise ConfigurationError(
                    f"Account {account.account_id} references unknown risk profile: {account.risk_profile}"
                )
```

### Atomic File Writes

```python
def _atomic_write(self, path: Path, data: dict):
    """Write configuration file atomically to prevent corruption."""
    import tempfile
    import shutil

    # Write to temp file first
    temp_fd, temp_path = tempfile.mkstemp(dir=path.parent, text=True)

    try:
        with os.fdopen(temp_fd, 'w') as f:
            json.dump(data, f, indent=2)

        # Atomic rename
        shutil.move(temp_path, path)

    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise ConfigurationError(f"Failed to write config: {e}")
```

### Backup Management

```python
def _backup_config(self, config_name: str):
    """Create timestamped backup before modification."""
    from datetime import datetime

    source = self.config_dir / f"{config_name}.json"
    if not source.exists():
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = self.backup_dir / f"{config_name}_{timestamp}.json"

    shutil.copy2(source, backup_path)

    # Cleanup old backups (keep last 10)
    backups = sorted(self.backup_dir.glob(f"{config_name}_*.json"))
    if len(backups) > 10:
        for old_backup in backups[:-10]:
            old_backup.unlink()
```

---

## Hot-Reload Implementation

### File Watcher Setup

```python
class ConfigFileHandler(FileSystemEventHandler):
    """Watch for config file changes."""

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.debounce_timer = None

    def on_modified(self, event):
        if event.is_directory:
            return

        if event.src_path.endswith(".json"):
            # Debounce rapid changes (editors may write multiple times)
            if self.debounce_timer:
                self.debounce_timer.cancel()

            self.debounce_timer = threading.Timer(1.0, self._handle_change, [event.src_path])
            self.debounce_timer.start()

    def _handle_change(self, path: str):
        """Handle config file change after debounce."""
        try:
            self.config_manager.reload_config(Path(path).name)
        except Exception as e:
            logger.error(f"Failed to reload config {path}: {e}")

def enable_hot_reload(self):
    """Enable file watching for hot-reload."""
    self.observer = Observer()
    handler = ConfigFileHandler(self)
    self.observer.schedule(handler, str(self.config_dir), recursive=False)
    self.observer.start()

def reload_config(self, filename: str):
    """Reload a specific config file safely."""
    # Determine which config changed
    if filename == "system.json":
        new_config = self._load_system_config()

        # Check if restart required
        if new_config.daemon.timezone != self.system.daemon.timezone:
            logger.warning("Timezone changed - daemon restart required")
            return False

        self.system = new_config
        logger.info("System config reloaded")

    elif filename == "risk_rules.json":
        new_config = self._load_risk_rules_config()
        self.risk_rules = new_config
        logger.info("Risk rules config reloaded")

        # Notify subscribers
        for callback in self.reload_callbacks:
            callback("risk_rules", new_config)

    return True
```

---

## Credential Security

### Environment Variable Substitution

```python
def resolve_credentials(credentials: Credentials) -> Credentials:
    """
    Replace ${ENV_VAR} patterns in credentials with actual values.

    Example:
        Input: {"api_key": "${TOPSTEP_API_KEY}"}
        Output: {"api_key": "actual_key_from_environment"}
    """
    import os
    import re

    env_var_pattern = r'\$\{([^}]+)\}'

    resolved = credentials.copy()

    for field in ["api_key", "api_secret"]:
        value = getattr(resolved, field)

        # Check for environment variable pattern
        matches = re.findall(env_var_pattern, value)
        if matches:
            for var_name in matches:
                env_value = os.getenv(var_name)
                if env_value is None:
                    raise ConfigurationError(f"Environment variable not set: {var_name}")
                value = value.replace(f"${{{var_name}}}", env_value)

            setattr(resolved, field, value)

    return resolved
```

### Optional Encryption (Future Enhancement)

```python
def encrypt_config_file(self, filename: str, master_password: str):
    """
    Encrypt configuration file with master password.
    Uses AES-256-GCM encryption via cryptography library.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
    import secrets

    # Derive key from password
    salt = secrets.token_bytes(16)
    kdf = PBKDF2(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = kdf.derive(master_password.encode())

    # Read plaintext config
    path = self.config_dir / filename
    with open(path, 'rb') as f:
        plaintext = f.read()

    # Encrypt
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    # Write encrypted file (salt + nonce + ciphertext)
    encrypted_path = path.with_suffix('.json.enc')
    with open(encrypted_path, 'wb') as f:
        f.write(salt + nonce + ciphertext)
```

---

## Password Hashing (Admin Auth)

### Bcrypt Implementation

```python
def hash_admin_password(password: str) -> str:
    """
    Hash admin password using bcrypt (cost factor 12).

    Returns:
        Bcrypt hash string (e.g., "$2b$12$...")
    """
    import bcrypt

    if len(password) < 8:
        raise ValueError("Admin password must be at least 8 characters")

    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)

    return hashed.decode('utf-8')

def verify_admin_password(password: str, password_hash: str) -> bool:
    """Verify admin password against stored hash."""
    import bcrypt

    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False
```

---

## Configuration Query Interface

### API for Other Components

```python
class ConfigManager:
    # ... (previous methods)

    def get_system_config(self) -> SystemConfig:
        """Get current system configuration."""
        if self.system is None:
            raise ConfigurationError("System config not loaded")
        return self.system

    def get_enabled_accounts(self) -> List[Account]:
        """Get list of enabled accounts."""
        if self.accounts is None:
            return []
        return [acc for acc in self.accounts.accounts if acc.enabled]

    def get_account_config(self, account_id: str) -> Optional[Account]:
        """Get configuration for specific account."""
        if self.accounts is None:
            return None

        for account in self.accounts.accounts:
            if account.account_id == account_id:
                return account

        return None

    def get_rules_for_account(self, account_id: str) -> List[RuleConfig]:
        """
        Get all enabled risk rules for an account.
        Merges profile rules with account overrides.
        """
        account = self.get_account_config(account_id)
        if not account or not self.risk_rules:
            return []

        profile = self.risk_rules.profiles.get(account.risk_profile)
        if not profile:
            return []

        rules = profile.rules.copy()

        # Apply account overrides
        if account_id in self.risk_rules.account_overrides:
            overrides = self.risk_rules.account_overrides[account_id].rule_overrides
            for override in overrides:
                # Find matching rule and update params
                for rule in rules:
                    if rule.rule == override.rule:
                        rule.params.update(override.params)

        return [rule for rule in rules if rule.enabled]
```

---

## Error Handling

### Custom Exceptions

```python
class ConfigurationError(Exception):
    """Base exception for configuration errors."""
    pass

class ConfigValidationError(ConfigurationError):
    """Configuration validation failed."""
    pass

class ConfigNotFoundError(ConfigurationError):
    """Configuration file not found."""
    pass

class ConfigCorruptedError(ConfigurationError):
    """Configuration file corrupted or unreadable."""
    pass
```

### Graceful Degradation

```python
def load_all_with_fallback(self):
    """
    Load all configs, continuing on non-critical errors.

    Returns:
        (success: bool, errors: List[str])
    """
    errors = []

    # System config is required
    try:
        self.system = self._load_system_config()
    except Exception as e:
        raise ConfigurationError(f"Cannot start without system config: {e}")

    # Accounts config is optional initially
    try:
        self.accounts = self._load_accounts_config()
    except Exception as e:
        errors.append(f"Accounts config error: {e}")
        self.accounts = AccountsConfig(accounts=[])

    # Risk rules required if accounts exist
    try:
        self.risk_rules = self._load_risk_rules_config()
    except Exception as e:
        if self.accounts and len(self.accounts.accounts) > 0:
            raise ConfigurationError(f"Risk rules required when accounts configured: {e}")
        errors.append(f"Risk rules config error: {e}")

    return len(errors) == 0, errors
```

---

## Testing Strategy

### Unit Tests

```python
def test_system_config_validation():
    """Test that invalid system config is rejected."""
    invalid_config = {
        "version": "1.0",
        "daemon": {
            "auto_start": "yes",  # Should be boolean
            "log_level": "verbose",  # Invalid enum value
            "daily_reset_time": "25:00",  # Invalid time
        }
    }

    with pytest.raises(ValidationError):
        SystemConfig(**invalid_config)

def test_environment_variable_substitution():
    """Test credential environment variable resolution."""
    os.environ["TEST_API_KEY"] = "actual_key_123"

    creds = Credentials(
        api_key="${TEST_API_KEY}",
        api_secret="direct_secret",
        account_number="ACC123"
    )

    creds.resolve_env_vars()

    assert creds.api_key == "actual_key_123"
    assert creds.api_secret == "direct_secret"

def test_atomic_write():
    """Test atomic file write prevents corruption."""
    manager = ConfigManager()
    test_path = manager.config_dir / "test.json"

    # Simulate write failure midway
    with patch('shutil.move', side_effect=OSError("Disk full")):
        with pytest.raises(ConfigurationError):
            manager._atomic_write(test_path, {"test": "data"})

    # Original file should not be corrupted
    assert not test_path.exists() or test_path.read_text() != ""
```

### Integration Tests

```python
def test_config_hot_reload():
    """Test hot-reload when config file changes."""
    manager = ConfigManager()
    manager.load_all()
    manager.enable_hot_reload()

    # Register reload callback
    reload_called = []
    manager.reload_callbacks.append(lambda name, config: reload_called.append(name))

    # Modify risk rules file
    rules_path = manager.config_dir / "risk_rules.json"
    config = json.loads(rules_path.read_text())
    config["profiles"]["conservative"]["rules"][0]["params"]["max_contracts"] = 5

    with open(rules_path, 'w') as f:
        json.dump(config, f)

    # Wait for file watcher
    time.sleep(2)

    # Verify reload occurred
    assert "risk_rules" in reload_called
    assert manager.risk_rules.profiles["conservative"].rules[0].params["max_contracts"] == 5
```

---

## Default Configuration Generation

### First-Time Setup

```python
def create_default_configs(config_dir: Path):
    """Create default configuration files for first-time setup."""
    config_dir = Path(config_dir).expanduser()
    config_dir.mkdir(parents=True, exist_ok=True)

    # Default system.json
    default_system = {
        "version": "1.0",
        "daemon": {
            "auto_start": True,
            "log_level": "info",
            "state_persistence_path": "~/.risk_manager/state",
            "daily_reset_time": "17:00",
            "timezone": "America/Chicago"
        },
        "admin": {
            "password_hash": hash_admin_password("admin"),  # Default password
            "require_auth": True
        },
        "sdk": {
            "connection_timeout": 30,
            "reconnect_attempts": 5,
            "reconnect_delay": 10
        }
    }

    with open(config_dir / "system.json", 'w') as f:
        json.dump(default_system, f, indent=2)

    # Empty accounts.json
    with open(config_dir / "accounts.json", 'w') as f:
        json.dump({"accounts": []}, f, indent=2)

    # Conservative risk profile
    default_rules = {
        "profiles": {
            "conservative": {
                "rules": [
                    {"rule": "MaxContracts", "enabled": True, "params": {"max_contracts": 2}},
                    {"rule": "DailyRealizedLoss", "enabled": True, "params": {"limit": -500.00}},
                    # ... (other rules with safe defaults)
                ]
            }
        },
        "account_overrides": {}
    }

    with open(config_dir / "risk_rules.json", 'w') as f:
        json.dump(default_rules, f, indent=2)

    print(f"Default configuration created at {config_dir}")
    print("WARNING: Default admin password is 'admin' - change immediately!")
```

---

## Summary for Implementation Agent

**To implement Configuration System, you must:**

1. **Install dependencies**:
   ```
   pydantic>=2.0  # Data validation
   jsonschema>=4.0  # JSON schema validation
   watchdog>=3.0  # File watching for hot-reload
   bcrypt>=4.0  # Password hashing
   ```

2. **Create JSON schemas** for all config files (system, accounts, rules, notifications)

3. **Implement Pydantic models** for type-safe configuration access

4. **Build ConfigManager class** with:
   - Atomic file writes (temp file + rename pattern)
   - Backup management (timestamped, keep last 10)
   - Environment variable substitution for credentials
   - Cross-reference validation (accounts → profiles)
   - Hot-reload with file watching + debouncing

5. **Implement password hashing** with bcrypt (cost factor 12)

6. **Create default config generator** for first-time setup

7. **Add comprehensive error handling** with custom exception types

8. **Write unit tests** for validation, substitution, atomic writes

9. **Write integration tests** for hot-reload and cross-validation

10. **Document all config file formats** in user-facing docs

**Critical Implementation Notes:**
- NEVER log credentials or password hashes
- Use atomic writes to prevent corruption on crash
- Validate EVERYTHING before applying changes
- Backup before any modification
- Support graceful degradation (daemon starts even if some configs missing)

**Dependencies**: None (this is a foundational component)
**Blocks**: All other components (they all need configuration)
**Priority**: P0 (implement first)
