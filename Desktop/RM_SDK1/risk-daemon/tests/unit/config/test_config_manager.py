"""
Unit tests for ConfigManager class.

Tests the configuration loading, validation, and management functionality
defined in src/config/config_manager.py according to architecture/16-configuration-implementation.md.

Coverage Target: >95%
Priority: P0 (foundational)
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from pydantic import ValidationError


# ============================================================================
# ConfigManager Initialization Tests
# ============================================================================


class TestConfigManagerInitialization:
    """Test ConfigManager initialization and directory setup."""

    def test_config_manager_creates_config_directory_if_missing(self, tmp_path):
        """
        GIVEN a config directory path that doesn't exist
        WHEN ConfigManager is instantiated
        THEN it should create the config directory
        """
        from src.config.config_manager import ConfigManager

        config_dir = tmp_path / "new_config_dir"
        assert not config_dir.exists()

        manager = ConfigManager(config_dir=str(config_dir))

        assert config_dir.exists()
        assert config_dir.is_dir()

    def test_config_manager_creates_backup_directory(self, tmp_path):
        """
        GIVEN a config directory path
        WHEN ConfigManager is instantiated
        THEN it should create a backups subdirectory
        """
        from src.config.config_manager import ConfigManager

        config_dir = tmp_path / "config"
        manager = ConfigManager(config_dir=str(config_dir))

        backup_dir = config_dir / "backups"
        assert backup_dir.exists()
        assert backup_dir.is_dir()

    def test_config_manager_expands_tilde_in_path(self):
        """
        GIVEN a config directory path with ~ (home dir)
        WHEN ConfigManager is instantiated
        THEN it should expand ~ to absolute path
        """
        from src.config.config_manager import ConfigManager

        manager = ConfigManager(config_dir="~/.risk_manager_test/config")

        assert not str(manager.config_dir).startswith("~")
        assert manager.config_dir.is_absolute()


# ============================================================================
# Configuration Loading Tests
# ============================================================================


class TestConfigManagerLoading:
    """Test configuration file loading and validation."""

    def test_load_system_config_from_valid_file_succeeds(self, tmp_path):
        """
        GIVEN a valid system.json file exists
        WHEN load_all() is called
        THEN system config should be loaded and accessible
        """
        from src.config.config_manager import ConfigManager

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create valid system.json
        system_config = {
            "version": "1.0",
            "daemon": {
                "auto_start": True,
                "log_level": "info",
                "state_persistence_path": "~/.risk_manager/state",
                "daily_reset_time": "17:00",
                "timezone": "America/Chicago"
            },
            "admin": {
                "password_hash": "$2b$12$" + "a" * 53,
                "require_auth": True
            },
            "sdk": {
                "connection_timeout": 30,
                "reconnect_attempts": 5,
                "reconnect_delay": 10
            }
        }

        with open(config_dir / "system.json", "w") as f:
            json.dump(system_config, f)

        # Also create minimal other config files to avoid missing file errors
        with open(config_dir / "accounts.json", "w") as f:
            json.dump({"accounts": []}, f)

        with open(config_dir / "risk_rules.json", "w") as f:
            json.dump({"profiles": {}, "account_overrides": {}}, f)

        manager = ConfigManager(config_dir=str(config_dir))
        result = manager.load_all()

        assert result is True
        assert manager.system is not None
        assert manager.system.version == "1.0"
        assert manager.system.daemon.log_level == "info"

    def test_load_system_config_raises_error_when_file_missing(self, tmp_path):
        """
        GIVEN system.json file does NOT exist
        WHEN load_all() is called
        THEN it should raise ConfigurationError

        Business Rule: System config is required for daemon startup
        """
        from src.config.config_manager import ConfigManager, ConfigurationError

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        manager = ConfigManager(config_dir=str(config_dir))

        with pytest.raises(ConfigurationError) as exc_info:
            manager.load_all()

        assert "system config not found" in str(exc_info.value).lower()

    def test_load_system_config_raises_error_on_malformed_json(self, tmp_path):
        """
        GIVEN system.json with invalid JSON syntax
        WHEN load_all() is called
        THEN it should raise ConfigurationError with clear message
        """
        from src.config.config_manager import ConfigManager, ConfigurationError

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Write malformed JSON
        with open(config_dir / "system.json", "w") as f:
            f.write('{"version": "1.0", invalid json')

        manager = ConfigManager(config_dir=str(config_dir))

        with pytest.raises(ConfigurationError) as exc_info:
            manager.load_all()

        error_msg = str(exc_info.value).lower()
        assert "malformed json" in error_msg or "json" in error_msg

    def test_load_system_config_raises_error_on_validation_failure(self, tmp_path):
        """
        GIVEN system.json with valid JSON but invalid schema
        WHEN load_all() is called
        THEN it should raise ConfigurationError from ValidationError
        """
        from src.config.config_manager import ConfigManager, ConfigurationError

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Valid JSON, invalid schema (missing required fields)
        invalid_config = {
            "version": "1.0",
            "daemon": {
                "auto_start": "yes"  # Should be boolean
            }
        }

        with open(config_dir / "system.json", "w") as f:
            json.dump(invalid_config, f)

        manager = ConfigManager(config_dir=str(config_dir))

        with pytest.raises(ConfigurationError) as exc_info:
            manager.load_all()

        assert "invalid" in str(exc_info.value).lower()

    def test_load_accounts_config_returns_empty_when_file_missing(self, tmp_path):
        """
        GIVEN accounts.json file does NOT exist
        WHEN load_all() is called
        THEN it should return empty accounts list (not fail)

        Business Rule: accounts.json is optional initially
        """
        from src.config.config_manager import ConfigManager

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create only system.json
        system_config = {
            "version": "1.0",
            "daemon": {
                "auto_start": True,
                "log_level": "info",
                "state_persistence_path": "~/.risk_manager/state",
                "daily_reset_time": "17:00",
                "timezone": "America/Chicago"
            },
            "admin": {
                "password_hash": "$2b$12$" + "a" * 53,
                "require_auth": True
            },
            "sdk": {
                "connection_timeout": 30,
                "reconnect_attempts": 5,
                "reconnect_delay": 10
            }
        }

        with open(config_dir / "system.json", "w") as f:
            json.dump(system_config, f)

        # Create empty risk_rules to pass cross-validation
        with open(config_dir / "risk_rules.json", "w") as f:
            json.dump({"profiles": {}, "account_overrides": {}}, f)

        manager = ConfigManager(config_dir=str(config_dir))
        result = manager.load_all()

        assert result is True
        assert manager.accounts is not None
        assert len(manager.accounts.accounts) == 0

    def test_load_accounts_config_resolves_environment_variables(self, tmp_path, monkeypatch):
        """
        GIVEN accounts.json with ${ENV_VAR} placeholders in credentials
        AND environment variables are set
        WHEN load_all() is called
        THEN credentials should have resolved values

        Business Rule: Credential environment variables resolved at load time
        """
        from src.config.config_manager import ConfigManager

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Set environment variables
        monkeypatch.setenv("TEST_API_KEY", "resolved_key_123")
        monkeypatch.setenv("TEST_API_SECRET", "resolved_secret_456")

        # Create system.json
        system_config = {
            "version": "1.0",
            "daemon": {
                "auto_start": True,
                "log_level": "info",
                "state_persistence_path": "~/.risk_manager/state",
                "daily_reset_time": "17:00",
                "timezone": "America/Chicago"
            },
            "admin": {
                "password_hash": "$2b$12$" + "a" * 53,
                "require_auth": True
            },
            "sdk": {
                "connection_timeout": 30,
                "reconnect_attempts": 5,
                "reconnect_delay": 10
            }
        }

        # Create accounts.json with env var placeholders
        accounts_config = {
            "accounts": [
                {
                    "account_id": "ACC001",
                    "account_name": "Test Account",
                    "enabled": True,
                    "broker": "topstepx",
                    "credentials": {
                        "api_key": "${TEST_API_KEY}",
                        "api_secret": "${TEST_API_SECRET}",
                        "account_number": "TS123456"
                    },
                    "risk_profile": "conservative"
                }
            ]
        }

        # Create risk_rules.json with matching profile
        risk_rules_config = {
            "profiles": {
                "conservative": {
                    "rules": []
                }
            },
            "account_overrides": {}
        }

        with open(config_dir / "system.json", "w") as f:
            json.dump(system_config, f)
        with open(config_dir / "accounts.json", "w") as f:
            json.dump(accounts_config, f)
        with open(config_dir / "risk_rules.json", "w") as f:
            json.dump(risk_rules_config, f)

        manager = ConfigManager(config_dir=str(config_dir))
        manager.load_all()

        assert manager.accounts.accounts[0].credentials.api_key == "resolved_key_123"
        assert manager.accounts.accounts[0].credentials.api_secret == "resolved_secret_456"


# ============================================================================
# Cross-Reference Validation Tests
# ============================================================================


class TestConfigManagerCrossValidation:
    """Test cross-reference validation between config files."""

    def test_load_all_validates_account_risk_profile_exists(self, tmp_path):
        """
        GIVEN accounts.json references a risk_profile "aggressive"
        AND risk_rules.json does NOT have "aggressive" profile
        WHEN load_all() is called
        THEN it should raise ConfigurationError

        Business Rule: Every account's risk_profile must exist in risk_rules.json profiles
        """
        from src.config.config_manager import ConfigManager, ConfigurationError

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create system.json
        system_config = {
            "version": "1.0",
            "daemon": {
                "auto_start": True,
                "log_level": "info",
                "state_persistence_path": "~/.risk_manager/state",
                "daily_reset_time": "17:00",
                "timezone": "America/Chicago"
            },
            "admin": {
                "password_hash": "$2b$12$" + "a" * 53,
                "require_auth": True
            },
            "sdk": {
                "connection_timeout": 30,
                "reconnect_attempts": 5,
                "reconnect_delay": 10
            }
        }

        # Create accounts.json referencing "aggressive" profile
        accounts_config = {
            "accounts": [
                {
                    "account_id": "ACC001",
                    "account_name": "Test Account",
                    "enabled": True,
                    "broker": "topstepx",
                    "credentials": {
                        "api_key": "key",
                        "api_secret": "secret",
                        "account_number": "TS123456"
                    },
                    "risk_profile": "aggressive"  # References non-existent profile
                }
            ]
        }

        # Create risk_rules.json WITHOUT "aggressive" profile
        risk_rules_config = {
            "profiles": {
                "conservative": {
                    "rules": []
                }
            },
            "account_overrides": {}
        }

        with open(config_dir / "system.json", "w") as f:
            json.dump(system_config, f)
        with open(config_dir / "accounts.json", "w") as f:
            json.dump(accounts_config, f)
        with open(config_dir / "risk_rules.json", "w") as f:
            json.dump(risk_rules_config, f)

        manager = ConfigManager(config_dir=str(config_dir))

        with pytest.raises(ConfigurationError) as exc_info:
            manager.load_all()

        error_msg = str(exc_info.value).lower()
        assert "aggressive" in error_msg
        assert "unknown" in error_msg or "not found" in error_msg

    def test_load_all_succeeds_when_all_profiles_exist(self, tmp_path):
        """
        GIVEN accounts.json references risk_profile "conservative"
        AND risk_rules.json HAS "conservative" profile
        WHEN load_all() is called
        THEN it should succeed without errors
        """
        from src.config.config_manager import ConfigManager

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create system.json
        system_config = {
            "version": "1.0",
            "daemon": {
                "auto_start": True,
                "log_level": "info",
                "state_persistence_path": "~/.risk_manager/state",
                "daily_reset_time": "17:00",
                "timezone": "America/Chicago"
            },
            "admin": {
                "password_hash": "$2b$12$" + "a" * 53,
                "require_auth": True
            },
            "sdk": {
                "connection_timeout": 30,
                "reconnect_attempts": 5,
                "reconnect_delay": 10
            }
        }

        # Create accounts.json
        accounts_config = {
            "accounts": [
                {
                    "account_id": "ACC001",
                    "account_name": "Test Account",
                    "enabled": True,
                    "broker": "topstepx",
                    "credentials": {
                        "api_key": "key",
                        "api_secret": "secret",
                        "account_number": "TS123456"
                    },
                    "risk_profile": "conservative"
                }
            ]
        }

        # Create risk_rules.json with matching profile
        risk_rules_config = {
            "profiles": {
                "conservative": {
                    "rules": [
                        {
                            "rule": "MaxContracts",
                            "enabled": True,
                            "params": {"max_contracts": 2}
                        }
                    ]
                }
            },
            "account_overrides": {}
        }

        with open(config_dir / "system.json", "w") as f:
            json.dump(system_config, f)
        with open(config_dir / "accounts.json", "w") as f:
            json.dump(accounts_config, f)
        with open(config_dir / "risk_rules.json", "w") as f:
            json.dump(risk_rules_config, f)

        manager = ConfigManager(config_dir=str(config_dir))
        result = manager.load_all()

        assert result is True


# ============================================================================
# Configuration Query Interface Tests
# ============================================================================


class TestConfigManagerQueryInterface:
    """Test ConfigManager query methods for other components."""

    def test_get_enabled_accounts_returns_only_enabled_accounts(self, tmp_path):
        """
        GIVEN accounts.json with mix of enabled and disabled accounts
        WHEN get_enabled_accounts() is called
        THEN it should return only accounts where enabled=True
        """
        from src.config.config_manager import ConfigManager

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Setup complete config
        system_config = {
            "version": "1.0",
            "daemon": {
                "auto_start": True,
                "log_level": "info",
                "state_persistence_path": "~/.risk_manager/state",
                "daily_reset_time": "17:00",
                "timezone": "America/Chicago"
            },
            "admin": {
                "password_hash": "$2b$12$" + "a" * 53,
                "require_auth": True
            },
            "sdk": {
                "connection_timeout": 30,
                "reconnect_attempts": 5,
                "reconnect_delay": 10
            }
        }

        accounts_config = {
            "accounts": [
                {
                    "account_id": "ACC001",
                    "account_name": "Enabled Account",
                    "enabled": True,
                    "broker": "topstepx",
                    "credentials": {
                        "api_key": "key1",
                        "api_secret": "secret1",
                        "account_number": "TS123"
                    },
                    "risk_profile": "conservative"
                },
                {
                    "account_id": "ACC002",
                    "account_name": "Disabled Account",
                    "enabled": False,
                    "broker": "topstepx",
                    "credentials": {
                        "api_key": "key2",
                        "api_secret": "secret2",
                        "account_number": "TS456"
                    },
                    "risk_profile": "conservative"
                }
            ]
        }

        risk_rules_config = {
            "profiles": {
                "conservative": {
                    "rules": []
                }
            },
            "account_overrides": {}
        }

        with open(config_dir / "system.json", "w") as f:
            json.dump(system_config, f)
        with open(config_dir / "accounts.json", "w") as f:
            json.dump(accounts_config, f)
        with open(config_dir / "risk_rules.json", "w") as f:
            json.dump(risk_rules_config, f)

        manager = ConfigManager(config_dir=str(config_dir))
        manager.load_all()

        enabled_accounts = manager.get_enabled_accounts()

        assert len(enabled_accounts) == 1
        assert enabled_accounts[0].account_id == "ACC001"

    def test_get_account_config_returns_specific_account(self, tmp_path):
        """
        GIVEN multiple accounts configured
        WHEN get_account_config(account_id) is called
        THEN it should return the matching account or None
        """
        from src.config.config_manager import ConfigManager

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Setup complete config
        system_config = {
            "version": "1.0",
            "daemon": {
                "auto_start": True,
                "log_level": "info",
                "state_persistence_path": "~/.risk_manager/state",
                "daily_reset_time": "17:00",
                "timezone": "America/Chicago"
            },
            "admin": {
                "password_hash": "$2b$12$" + "a" * 53,
                "require_auth": True
            },
            "sdk": {
                "connection_timeout": 30,
                "reconnect_attempts": 5,
                "reconnect_delay": 10
            }
        }

        accounts_config = {
            "accounts": [
                {
                    "account_id": "ACC001",
                    "account_name": "Account 1",
                    "enabled": True,
                    "broker": "topstepx",
                    "credentials": {
                        "api_key": "key1",
                        "api_secret": "secret1",
                        "account_number": "TS123"
                    },
                    "risk_profile": "conservative"
                },
                {
                    "account_id": "ACC002",
                    "account_name": "Account 2",
                    "enabled": True,
                    "broker": "topstepx",
                    "credentials": {
                        "api_key": "key2",
                        "api_secret": "secret2",
                        "account_number": "TS456"
                    },
                    "risk_profile": "conservative"
                }
            ]
        }

        risk_rules_config = {
            "profiles": {
                "conservative": {
                    "rules": []
                }
            },
            "account_overrides": {}
        }

        with open(config_dir / "system.json", "w") as f:
            json.dump(system_config, f)
        with open(config_dir / "accounts.json", "w") as f:
            json.dump(accounts_config, f)
        with open(config_dir / "risk_rules.json", "w") as f:
            json.dump(risk_rules_config, f)

        manager = ConfigManager(config_dir=str(config_dir))
        manager.load_all()

        # Test finding existing account
        account = manager.get_account_config("ACC002")
        assert account is not None
        assert account.account_id == "ACC002"
        assert account.account_name == "Account 2"

        # Test finding non-existent account
        missing = manager.get_account_config("ACC999")
        assert missing is None

    def test_get_rules_for_account_returns_enabled_rules(self, tmp_path):
        """
        GIVEN risk_rules.json with profile containing enabled and disabled rules
        WHEN get_rules_for_account(account_id) is called
        THEN it should return only enabled rules for that account's profile
        """
        from src.config.config_manager import ConfigManager

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Setup complete config
        system_config = {
            "version": "1.0",
            "daemon": {
                "auto_start": True,
                "log_level": "info",
                "state_persistence_path": "~/.risk_manager/state",
                "daily_reset_time": "17:00",
                "timezone": "America/Chicago"
            },
            "admin": {
                "password_hash": "$2b$12$" + "a" * 53,
                "require_auth": True
            },
            "sdk": {
                "connection_timeout": 30,
                "reconnect_attempts": 5,
                "reconnect_delay": 10
            }
        }

        accounts_config = {
            "accounts": [
                {
                    "account_id": "ACC001",
                    "account_name": "Test Account",
                    "enabled": True,
                    "broker": "topstepx",
                    "credentials": {
                        "api_key": "key",
                        "api_secret": "secret",
                        "account_number": "TS123"
                    },
                    "risk_profile": "conservative"
                }
            ]
        }

        risk_rules_config = {
            "profiles": {
                "conservative": {
                    "rules": [
                        {
                            "rule": "MaxContracts",
                            "enabled": True,
                            "params": {"max_contracts": 2}
                        },
                        {
                            "rule": "DailyRealizedLoss",
                            "enabled": False,  # Disabled
                            "params": {"limit": -500.00}
                        },
                        {
                            "rule": "UnrealizedLoss",
                            "enabled": True,
                            "params": {"limit": -200.00}
                        }
                    ]
                }
            },
            "account_overrides": {}
        }

        with open(config_dir / "system.json", "w") as f:
            json.dump(system_config, f)
        with open(config_dir / "accounts.json", "w") as f:
            json.dump(accounts_config, f)
        with open(config_dir / "risk_rules.json", "w") as f:
            json.dump(risk_rules_config, f)

        manager = ConfigManager(config_dir=str(config_dir))
        manager.load_all()

        rules = manager.get_rules_for_account("ACC001")

        assert len(rules) == 2  # Only enabled rules
        rule_names = [r.rule for r in rules]
        assert "MaxContracts" in rule_names
        assert "UnrealizedLoss" in rule_names
        assert "DailyRealizedLoss" not in rule_names  # Disabled, excluded


# ============================================================================
# Atomic Write Tests
# ============================================================================


class TestConfigManagerAtomicWrites:
    """Test atomic file write behavior to prevent corruption."""

    def test_atomic_write_creates_file_successfully(self, tmp_path):
        """
        GIVEN a config manager and valid data
        WHEN _atomic_write() is called
        THEN file should be created with correct content
        """
        from src.config.config_manager import ConfigManager

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        manager = ConfigManager(config_dir=str(config_dir))

        test_data = {"version": "1.0", "test": "data"}
        test_path = config_dir / "test.json"

        manager._atomic_write(test_path, test_data)

        assert test_path.exists()
        with open(test_path, "r") as f:
            loaded = json.load(f)
        assert loaded == test_data

    @pytest.mark.skip(reason="Requires mocking shutil.move failure - implement in rm-developer phase")
    def test_atomic_write_prevents_corruption_on_failure(self, tmp_path):
        """
        GIVEN an existing config file
        WHEN _atomic_write() fails midway (disk full, permission error)
        THEN original file should remain unchanged

        Business Rule: Use temp file + rename pattern to ensure atomicity
        """
        # This test will be fully implemented by rm-developer
        # with proper mocking of shutil.move() failure
        pass


# ============================================================================
# Backup Management Tests
# ============================================================================


class TestConfigManagerBackupManagement:
    """Test backup creation and cleanup."""

    def test_backup_config_creates_timestamped_backup(self, tmp_path):
        """
        GIVEN an existing config file
        WHEN _backup_config(config_name) is called
        THEN a timestamped backup should be created in backups/ directory
        """
        from src.config.config_manager import ConfigManager

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create original config file
        original_data = {"version": "1.0"}
        with open(config_dir / "test.json", "w") as f:
            json.dump(original_data, f)

        manager = ConfigManager(config_dir=str(config_dir))
        manager._backup_config("test")

        backup_dir = config_dir / "backups"
        backups = list(backup_dir.glob("test_*.json"))

        assert len(backups) == 1
        # Verify backup contains original data
        with open(backups[0], "r") as f:
            backup_data = json.load(f)
        assert backup_data == original_data

    def test_backup_config_keeps_only_last_10_backups(self, tmp_path):
        """
        GIVEN 12 existing backups for a config file
        WHEN _backup_config() is called
        THEN only the 10 most recent backups should remain

        Business Rule: Keep last 10 backups to prevent disk bloat
        """
        from src.config.config_manager import ConfigManager

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        backup_dir = config_dir / "backups"
        backup_dir.mkdir()

        # Create 12 old backup files
        for i in range(12):
            timestamp = f"202501{i:02d}_120000"
            backup_file = backup_dir / f"test_{timestamp}.json"
            with open(backup_file, "w") as f:
                json.dump({"backup": i}, f)

        # Create current config
        with open(config_dir / "test.json", "w") as f:
            json.dump({"version": "1.0"}, f)

        manager = ConfigManager(config_dir=str(config_dir))
        manager._backup_config("test")  # Creates 13th backup

        # Verify only 10 backups remain
        backups = list(backup_dir.glob("test_*.json"))
        assert len(backups) == 10

    def test_backup_config_does_nothing_if_file_not_exists(self, tmp_path):
        """
        GIVEN a config file that doesn't exist yet
        WHEN _backup_config() is called
        THEN it should not raise an error (no backup to create)
        """
        from src.config.config_manager import ConfigManager

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        manager = ConfigManager(config_dir=str(config_dir))

        # Should not raise
        manager._backup_config("nonexistent")

        backup_dir = config_dir / "backups"
        backups = list(backup_dir.glob("nonexistent_*.json"))
        assert len(backups) == 0
