"""Configuration management for Risk Manager Daemon.

Provides centralized configuration loading, validation, hot-reload,
and query interfaces according to architecture/16-configuration-implementation.md.

Features:
- Atomic file writes (temp file + rename)
- Timestamped backups (keep last 10)
- Environment variable substitution for credentials
- Cross-reference validation (accounts → profiles)
- Hot-reload with file watching and debouncing
"""

import json
import logging
import os
import shutil
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from pydantic import ValidationError
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .models import (
    Account,
    AccountsConfig,
    NotificationsConfig,
    RiskRulesConfig,
    RuleConfig,
    SystemConfig,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Custom Exceptions
# ============================================================================


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


# ============================================================================
# File Watcher for Hot-Reload
# ============================================================================


class ConfigFileHandler(FileSystemEventHandler):
    """Watch for config file changes and trigger reloads."""

    def __init__(self, config_manager: "ConfigManager"):
        self.config_manager = config_manager
        self.debounce_timer: Optional[threading.Timer] = None

    def on_modified(self, event: Any) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return

        if event.src_path.endswith(".json"):
            # Debounce rapid changes (editors may write multiple times)
            if self.debounce_timer:
                self.debounce_timer.cancel()

            filename = Path(event.src_path).name
            self.debounce_timer = threading.Timer(
                0.15, self._handle_change, [filename]
            )
            self.debounce_timer.start()

    def _handle_change(self, filename: str) -> None:
        """Handle config file change after debounce."""
        try:
            self.config_manager.reload_config(filename)
        except Exception as e:
            logger.error(f"Failed to reload config {filename}: {e}")


# ============================================================================
# ConfigManager Class
# ============================================================================


class ConfigManager:
    """Central configuration management for Risk Manager Daemon.

    Manages loading, validation, hot-reload, and querying of all
    configuration files (system, accounts, risk_rules, notifications).
    """

    def __init__(self, config_dir: str = "~/.risk_manager/config"):
        """Initialize ConfigManager.

        Args:
            config_dir: Directory containing configuration files
        """
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
        self.observer: Optional[Any] = None  # Observer type from watchdog
        self.reload_callbacks: List[Callable[[str, Any], None]] = []

    # ========================================================================
    # Loading Methods
    # ========================================================================

    def load_all(self) -> bool:
        """Load all configuration files on daemon startup.

        Returns:
            True if all required configs loaded successfully

        Raises:
            ConfigurationError: If required config files are missing or invalid
        """
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
        """Load and validate system.json.

        Returns:
            Validated SystemConfig object

        Raises:
            ConfigurationError: If file missing, malformed, or invalid
        """
        path = self.config_dir / "system.json"

        if not path.exists():
            raise ConfigurationError(f"System config not found: {path}")

        try:
            with open(path, "r") as f:
                data = json.load(f)

            # Validate with Pydantic
            config = SystemConfig(**data)
            return config

        except ValidationError as e:
            raise ConfigurationError(f"Invalid system.json: {e}")
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Malformed JSON in system.json: {e}")

    def _load_accounts_config(self) -> AccountsConfig:
        """Load and validate accounts.json.

        Returns:
            AccountsConfig object (may be empty if file doesn't exist)

        Raises:
            ConfigurationError: If file malformed or invalid
        """
        path = self.config_dir / "accounts.json"

        if not path.exists():
            # No accounts configured yet - return empty
            return AccountsConfig(accounts=[])

        try:
            with open(path, "r") as f:
                data = json.load(f)

            config = AccountsConfig(**data)

            # Resolve environment variables in credentials
            for account in config.accounts:
                account.credentials.resolve_env_vars()

            return config

        except ValidationError as e:
            raise ConfigurationError(f"Invalid accounts.json: {e}")
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Malformed JSON in accounts.json: {e}")

    def _load_risk_rules_config(self) -> RiskRulesConfig:
        """Load and validate risk_rules.json.

        Returns:
            RiskRulesConfig object

        Raises:
            ConfigurationError: If file missing, malformed, or invalid
        """
        path = self.config_dir / "risk_rules.json"

        if not path.exists():
            # Return empty config if file doesn't exist
            return RiskRulesConfig(profiles={}, account_overrides={})

        try:
            with open(path, "r") as f:
                data = json.load(f)

            config = RiskRulesConfig(**data)
            return config

        except ValidationError as e:
            raise ConfigurationError(f"Invalid risk_rules.json: {e}")
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Malformed JSON in risk_rules.json: {e}")

    def _load_notifications_config(self) -> Optional[NotificationsConfig]:
        """Load and validate notifications.json.

        Returns:
            NotificationsConfig object or None if file doesn't exist

        Raises:
            ConfigurationError: If file malformed or invalid
        """
        path = self.config_dir / "notifications.json"

        if not path.exists():
            return None

        try:
            with open(path, "r") as f:
                data = json.load(f)

            config = NotificationsConfig(**data)
            return config

        except ValidationError as e:
            raise ConfigurationError(f"Invalid notifications.json: {e}")
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Malformed JSON in notifications.json: {e}")

    def _validate_cross_references(self) -> None:
        """Validate that accounts reference valid risk profiles.

        Raises:
            ConfigurationError: If account references non-existent profile
        """
        if not self.accounts or not self.risk_rules:
            return

        available_profiles = set(self.risk_rules.profiles.keys())

        for account in self.accounts.accounts:
            if account.risk_profile not in available_profiles:
                raise ConfigurationError(
                    f"Account {account.account_id} references unknown risk profile: {account.risk_profile}"
                )

    # ========================================================================
    # Query Interface
    # ========================================================================

    def get_system_config(self) -> SystemConfig:
        """Get current system configuration.

        Returns:
            SystemConfig object

        Raises:
            ConfigurationError: If system config not loaded
        """
        if self.system is None:
            raise ConfigurationError("System config not loaded")
        return self.system

    def get_enabled_accounts(self) -> List[Account]:
        """Get list of enabled accounts.

        Returns:
            List of Account objects where enabled=True
        """
        if self.accounts is None:
            return []
        return [acc for acc in self.accounts.accounts if acc.enabled]

    def get_account_config(self, account_id: str) -> Optional[Account]:
        """Get configuration for specific account.

        Args:
            account_id: Account ID to look up

        Returns:
            Account object or None if not found
        """
        if self.accounts is None:
            return None

        for account in self.accounts.accounts:
            if account.account_id == account_id:
                return account

        return None

    def get_rules_for_account(self, account_id: str) -> List[RuleConfig]:
        """Get all enabled risk rules for an account.

        Merges profile rules with account overrides.

        Args:
            account_id: Account ID to get rules for

        Returns:
            List of enabled RuleConfig objects
        """
        account = self.get_account_config(account_id)
        if not account or not self.risk_rules:
            return []

        profile = self.risk_rules.profiles.get(account.risk_profile)
        if not profile:
            return []

        # Make a copy of profile rules
        rules = [rule.model_copy(deep=True) for rule in profile.rules]

        # Apply account overrides
        if account_id in self.risk_rules.account_overrides:
            overrides = self.risk_rules.account_overrides[account_id].rule_overrides
            for override in overrides:
                # Find matching rule and update params
                for rule in rules:
                    if rule.rule == override.rule:
                        rule.params.update(override.params)

        # Return only enabled rules
        return [rule for rule in rules if rule.enabled]

    # ========================================================================
    # Atomic Writes and Backups
    # ========================================================================

    def _atomic_write(self, path: Path, data: Dict[str, Any]) -> None:
        """Write configuration file atomically to prevent corruption.

        Uses temp file + rename pattern for atomicity.

        Args:
            path: Target file path
            data: Dictionary to write as JSON

        Raises:
            ConfigurationError: If write fails
        """
        try:
            # Write to temp file first
            temp_fd, temp_path = tempfile.mkstemp(
                dir=path.parent, suffix=".json", text=True
            )

            try:
                with os.fdopen(temp_fd, "w") as f:
                    json.dump(data, f, indent=2)

                # Atomic rename
                shutil.move(temp_path, path)

            except Exception as e:
                # Clean up temp file on error
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise e

        except Exception as e:
            raise ConfigurationError(f"Failed to write config: {e}")

    def _backup_config(self, config_name: str) -> None:
        """Create timestamped backup before modification.

        Args:
            config_name: Name of config file (without .json extension)
        """
        source = self.config_dir / f"{config_name}.json"
        if not source.exists():
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]  # Include microseconds
        backup_path = self.backup_dir / f"{config_name}_{timestamp}.json"

        shutil.copy2(source, backup_path)

        # Cleanup old backups (keep last 10)
        backups = sorted(self.backup_dir.glob(f"{config_name}_*.json"))
        if len(backups) > 10:
            for old_backup in backups[:-10]:
                old_backup.unlink()

    # ========================================================================
    # Hot-Reload
    # ========================================================================

    def enable_hot_reload(self) -> None:
        """Enable file watching for hot-reload."""
        self.observer = Observer()
        handler = ConfigFileHandler(self)
        self.observer.schedule(handler, str(self.config_dir), recursive=False)
        self.observer.start()

    def reload_config(self, filename: str) -> bool:
        """Reload a specific config file safely.

        Args:
            filename: Name of config file (e.g., "system.json")

        Returns:
            True if reload successful, False if restart required
        """
        try:
            # Determine which config changed
            if filename == "system.json":
                new_system_config = self._load_system_config()

                # Check if restart required
                if self.system and new_system_config.daemon.timezone != self.system.daemon.timezone:
                    logger.warning("Timezone changed - daemon restart required")
                    return False

                self.system = new_system_config
                logger.info("System config reloaded")

            elif filename == "risk_rules.json":
                new_risk_config = self._load_risk_rules_config()
                self.risk_rules = new_risk_config
                logger.info("Risk rules config reloaded")

                # Notify subscribers
                for callback in self.reload_callbacks:
                    callback("risk_rules", new_risk_config)

            elif filename == "accounts.json":
                new_accounts_config = self._load_accounts_config()
                self.accounts = new_accounts_config
                logger.info("Accounts config reloaded")

                # Notify subscribers
                for callback in self.reload_callbacks:
                    callback("accounts", new_accounts_config)

            return True

        except Exception as e:
            logger.error(f"Failed to reload {filename}: {e}")
            # Keep old config on error
            return True  # Don't indicate restart needed, just log error
