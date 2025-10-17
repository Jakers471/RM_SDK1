"""
Unit tests for Configuration Pydantic Models.

Tests the data validation layer defined in src/config/models.py according to
architecture/16-configuration-implementation.md specifications.

Coverage Target: >95%
Priority: P0 (foundational)
"""

import pytest
from pydantic import ValidationError
from datetime import datetime


# ============================================================================
# SystemConfig Model Tests
# ============================================================================


class TestSystemConfigValidation:
    """Test SystemConfig model validation according to JSON schema specs."""

    def test_valid_system_config_parses_successfully(self):
        """
        GIVEN a valid system configuration dictionary
        WHEN SystemConfig model is instantiated
        THEN it should parse without errors and all fields accessible
        """
        # Import the model that doesn't exist yet
        from src.config.models import SystemConfig

        valid_config = {
            "version": "1.0",
            "daemon": {
                "auto_start": True,
                "log_level": "info",
                "state_persistence_path": "~/.risk_manager/state",
                "daily_reset_time": "17:00",
                "timezone": "America/Chicago"
            },
            "admin": {
                "password_hash": "$2b$12$" + "a" * 53,  # Valid bcrypt hash format
                "require_auth": True
            },
            "sdk": {
                "connection_timeout": 30,
                "reconnect_attempts": 5,
                "reconnect_delay": 10
            }
        }

        config = SystemConfig(**valid_config)

        assert config.version == "1.0"
        assert config.daemon.auto_start is True
        assert config.daemon.log_level == "info"
        assert config.admin.require_auth is True
        assert config.sdk.connection_timeout == 30

    def test_invalid_version_format_raises_validation_error(self):
        """
        GIVEN a system config with invalid version format (not X.Y)
        WHEN SystemConfig model is instantiated
        THEN it should raise ValidationError

        Business Rule: Version must match regex ^\d+\.\d+$
        """
        from src.config.models import SystemConfig

        invalid_config = {
            "version": "1",  # Missing minor version
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

        with pytest.raises(ValidationError) as exc_info:
            SystemConfig(**invalid_config)

        assert "version" in str(exc_info.value).lower()

    def test_unsupported_version_raises_validation_error(self):
        """
        GIVEN a system config with version != "1.0"
        WHEN SystemConfig model is instantiated
        THEN it should raise ValidationError with clear message

        Business Rule: Only version "1.0" is currently supported
        """
        from src.config.models import SystemConfig

        invalid_config = {
            "version": "2.0",  # Not supported yet
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

        with pytest.raises(ValidationError) as exc_info:
            SystemConfig(**invalid_config)

        assert "unsupported" in str(exc_info.value).lower()

    def test_invalid_log_level_raises_validation_error(self):
        """
        GIVEN a system config with invalid log_level (not in enum)
        WHEN SystemConfig model is instantiated
        THEN it should raise ValidationError

        Business Rule: log_level must be one of: debug, info, warning, error
        """
        from src.config.models import SystemConfig

        invalid_config = {
            "version": "1.0",
            "daemon": {
                "auto_start": True,
                "log_level": "verbose",  # Not in enum
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

        with pytest.raises(ValidationError) as exc_info:
            SystemConfig(**invalid_config)

        assert "log_level" in str(exc_info.value).lower()

    def test_invalid_reset_time_format_raises_validation_error(self):
        """
        GIVEN a system config with malformed daily_reset_time (not HH:MM)
        WHEN SystemConfig model is instantiated
        THEN it should raise ValidationError

        Business Rule: daily_reset_time must match regex ^([01]\d|2[0-3]):([0-5]\d)$
        """
        from src.config.models import SystemConfig

        test_cases = [
            "25:00",  # Invalid hour
            "17:60",  # Invalid minute
            "5pm",    # Wrong format
            "17-00",  # Wrong separator
        ]

        for invalid_time in test_cases:
            invalid_config = {
                "version": "1.0",
                "daemon": {
                    "auto_start": True,
                    "log_level": "info",
                    "state_persistence_path": "~/.risk_manager/state",
                    "daily_reset_time": invalid_time,
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

            with pytest.raises(ValidationError) as exc_info:
                SystemConfig(**invalid_config)

            assert "daily_reset_time" in str(exc_info.value).lower(), f"Failed for: {invalid_time}"

    def test_invalid_timezone_raises_validation_error(self):
        """
        GIVEN a system config with unsupported timezone
        WHEN SystemConfig model is instantiated
        THEN it should raise ValidationError

        Business Rule: Only specific timezones allowed (Chicago, New_York, LA, UTC)
        """
        from src.config.models import SystemConfig

        invalid_config = {
            "version": "1.0",
            "daemon": {
                "auto_start": True,
                "log_level": "info",
                "state_persistence_path": "~/.risk_manager/state",
                "daily_reset_time": "17:00",
                "timezone": "America/Denver"  # Not in allowed list
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

        with pytest.raises(ValidationError) as exc_info:
            SystemConfig(**invalid_config)

        assert "timezone" in str(exc_info.value).lower()

    def test_invalid_bcrypt_hash_format_raises_validation_error(self):
        """
        GIVEN a system config with malformed password_hash (not bcrypt format)
        WHEN SystemConfig model is instantiated
        THEN it should raise ValidationError

        Business Rule: password_hash must match regex ^\$2[aby]\$\d+\$.{53}$
        """
        from src.config.models import SystemConfig

        test_cases = [
            "plain_password",  # Not hashed
            "$2x$12$" + "a" * 53,  # Wrong bcrypt version
            "$2b$12$" + "a" * 50,  # Too short
            "$2b$12$",  # Missing hash
        ]

        for invalid_hash in test_cases:
            invalid_config = {
                "version": "1.0",
                "daemon": {
                    "auto_start": True,
                    "log_level": "info",
                    "state_persistence_path": "~/.risk_manager/state",
                    "daily_reset_time": "17:00",
                    "timezone": "America/Chicago"
                },
                "admin": {
                    "password_hash": invalid_hash,
                    "require_auth": True
                },
                "sdk": {
                    "connection_timeout": 30,
                    "reconnect_attempts": 5,
                    "reconnect_delay": 10
                }
            }

            with pytest.raises(ValidationError) as exc_info:
                SystemConfig(**invalid_config)

            assert "password_hash" in str(exc_info.value).lower(), f"Failed for: {invalid_hash}"

    def test_sdk_timeout_below_minimum_raises_validation_error(self):
        """
        GIVEN a system config with connection_timeout < 5
        WHEN SystemConfig model is instantiated
        THEN it should raise ValidationError

        Business Rule: connection_timeout must be >= 5 and <= 300
        """
        from src.config.models import SystemConfig

        invalid_config = {
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
                "connection_timeout": 2,  # Below minimum
                "reconnect_attempts": 5,
                "reconnect_delay": 10
            }
        }

        with pytest.raises(ValidationError) as exc_info:
            SystemConfig(**invalid_config)

        assert "connection_timeout" in str(exc_info.value).lower()

    def test_sdk_timeout_above_maximum_raises_validation_error(self):
        """
        GIVEN a system config with connection_timeout > 300
        WHEN SystemConfig model is instantiated
        THEN it should raise ValidationError
        """
        from src.config.models import SystemConfig

        invalid_config = {
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
                "connection_timeout": 600,  # Above maximum
                "reconnect_attempts": 5,
                "reconnect_delay": 10
            }
        }

        with pytest.raises(ValidationError) as exc_info:
            SystemConfig(**invalid_config)

        assert "connection_timeout" in str(exc_info.value).lower()

    def test_missing_required_field_raises_validation_error(self):
        """
        GIVEN a system config missing required field
        WHEN SystemConfig model is instantiated
        THEN it should raise ValidationError listing missing field
        """
        from src.config.models import SystemConfig

        incomplete_config = {
            "version": "1.0",
            "daemon": {
                "auto_start": True,
                "log_level": "info",
                # Missing: state_persistence_path, daily_reset_time, timezone
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

        with pytest.raises(ValidationError) as exc_info:
            SystemConfig(**incomplete_config)

        error_msg = str(exc_info.value).lower()
        assert "state_persistence_path" in error_msg or "daily_reset_time" in error_msg


# ============================================================================
# AccountConfig Model Tests
# ============================================================================


class TestAccountConfigValidation:
    """Test AccountsConfig and Account model validation."""

    def test_valid_account_config_parses_successfully(self):
        """
        GIVEN a valid accounts configuration
        WHEN AccountsConfig model is instantiated
        THEN it should parse without errors
        """
        from src.config.models import AccountsConfig

        valid_config = {
            "accounts": [
                {
                    "account_id": "ACC001",
                    "account_name": "TopStep Combine",
                    "enabled": True,
                    "broker": "topstepx",
                    "credentials": {
                        "api_key": "${TOPSTEP_API_KEY}",
                        "api_secret": "${TOPSTEP_API_SECRET}",
                        "account_number": "TS123456"
                    },
                    "risk_profile": "conservative"
                }
            ]
        }

        config = AccountsConfig(**valid_config)

        assert len(config.accounts) == 1
        assert config.accounts[0].account_id == "ACC001"
        assert config.accounts[0].broker == "topstepx"
        assert config.accounts[0].enabled is True

    def test_duplicate_account_ids_raises_validation_error(self):
        """
        GIVEN accounts config with duplicate account_id values
        WHEN AccountsConfig model is instantiated
        THEN it should raise ValidationError

        Business Rule: account_id must be unique across all accounts
        """
        from src.config.models import AccountsConfig

        invalid_config = {
            "accounts": [
                {
                    "account_id": "ACC001",  # Duplicate
                    "account_name": "Account 1",
                    "enabled": True,
                    "broker": "topstepx",
                    "credentials": {
                        "api_key": "key1",
                        "api_secret": "secret1",
                        "account_number": "TS123456"
                    },
                    "risk_profile": "conservative"
                },
                {
                    "account_id": "ACC001",  # Duplicate
                    "account_name": "Account 2",
                    "enabled": True,
                    "broker": "topstepx",
                    "credentials": {
                        "api_key": "key2",
                        "api_secret": "secret2",
                        "account_number": "TS789012"
                    },
                    "risk_profile": "aggressive"
                }
            ]
        }

        with pytest.raises(ValidationError) as exc_info:
            AccountsConfig(**invalid_config)

        assert "duplicate" in str(exc_info.value).lower()

    def test_invalid_broker_raises_validation_error(self):
        """
        GIVEN account config with unsupported broker
        WHEN AccountsConfig model is instantiated
        THEN it should raise ValidationError

        Business Rule: Only "topstepx" broker is currently supported
        """
        from src.config.models import AccountsConfig

        invalid_config = {
            "accounts": [
                {
                    "account_id": "ACC001",
                    "account_name": "Test Account",
                    "enabled": True,
                    "broker": "interactive_brokers",  # Not supported
                    "credentials": {
                        "api_key": "key",
                        "api_secret": "secret",
                        "account_number": "123456"
                    },
                    "risk_profile": "conservative"
                }
            ]
        }

        with pytest.raises(ValidationError) as exc_info:
            AccountsConfig(**invalid_config)

        assert "broker" in str(exc_info.value).lower()

    def test_empty_account_id_raises_validation_error(self):
        """
        GIVEN account config with empty account_id
        WHEN AccountsConfig model is instantiated
        THEN it should raise ValidationError

        Business Rule: account_id must have minLength: 1
        """
        from src.config.models import AccountsConfig

        invalid_config = {
            "accounts": [
                {
                    "account_id": "",  # Empty string
                    "account_name": "Test Account",
                    "enabled": True,
                    "broker": "topstepx",
                    "credentials": {
                        "api_key": "key",
                        "api_secret": "secret",
                        "account_number": "123456"
                    },
                    "risk_profile": "conservative"
                }
            ]
        }

        with pytest.raises(ValidationError) as exc_info:
            AccountsConfig(**invalid_config)

        assert "account_id" in str(exc_info.value).lower()

    def test_missing_credentials_fields_raises_validation_error(self):
        """
        GIVEN account config with incomplete credentials
        WHEN AccountsConfig model is instantiated
        THEN it should raise ValidationError

        Business Rule: All credential fields (api_key, api_secret, account_number) are required
        """
        from src.config.models import AccountsConfig

        invalid_config = {
            "accounts": [
                {
                    "account_id": "ACC001",
                    "account_name": "Test Account",
                    "enabled": True,
                    "broker": "topstepx",
                    "credentials": {
                        "api_key": "key",
                        # Missing: api_secret, account_number
                    },
                    "risk_profile": "conservative"
                }
            ]
        }

        with pytest.raises(ValidationError) as exc_info:
            AccountsConfig(**invalid_config)

        error_msg = str(exc_info.value).lower()
        assert "api_secret" in error_msg or "account_number" in error_msg


# ============================================================================
# Credentials Model Tests (Environment Variable Substitution)
# ============================================================================


class TestCredentialsModel:
    """Test Credentials model and environment variable resolution."""

    def test_credentials_with_env_var_placeholders_parse_successfully(self):
        """
        GIVEN credentials with ${ENV_VAR} placeholders
        WHEN Credentials model is instantiated
        THEN it should parse and preserve placeholder strings

        Note: Actual resolution happens in resolve_env_vars() method
        """
        from src.config.models import Credentials

        creds = Credentials(
            api_key="${TOPSTEP_API_KEY}",
            api_secret="${TOPSTEP_API_SECRET}",
            account_number="TS123456"
        )

        assert creds.api_key == "${TOPSTEP_API_KEY}"
        assert creds.api_secret == "${TOPSTEP_API_SECRET}"
        assert creds.account_number == "TS123456"

    def test_resolve_env_vars_substitutes_environment_variables(self, monkeypatch):
        """
        GIVEN credentials with ${ENV_VAR} placeholders
        AND environment variables are set
        WHEN resolve_env_vars() is called
        THEN placeholders should be replaced with actual values

        Business Rule: Pattern ${VAR_NAME} replaced with os.getenv("VAR_NAME")
        """
        from src.config.models import Credentials

        # Set environment variables
        monkeypatch.setenv("TEST_API_KEY", "actual_key_12345")
        monkeypatch.setenv("TEST_API_SECRET", "actual_secret_67890")

        creds = Credentials(
            api_key="${TEST_API_KEY}",
            api_secret="${TEST_API_SECRET}",
            account_number="ACC123"
        )

        creds.resolve_env_vars()

        assert creds.api_key == "actual_key_12345"
        assert creds.api_secret == "actual_secret_67890"
        assert creds.account_number == "ACC123"  # Unchanged

    def test_resolve_env_vars_raises_error_when_variable_not_set(self):
        """
        GIVEN credentials with ${MISSING_VAR} placeholder
        AND environment variable MISSING_VAR is not set
        WHEN resolve_env_vars() is called
        THEN it should raise ValueError with clear message

        Business Rule: Fail fast if referenced env var doesn't exist
        """
        from src.config.models import Credentials

        creds = Credentials(
            api_key="${MISSING_VARIABLE}",
            api_secret="direct_secret",
            account_number="ACC123"
        )

        with pytest.raises(ValueError) as exc_info:
            creds.resolve_env_vars()

        error_msg = str(exc_info.value)
        assert "MISSING_VARIABLE" in error_msg
        assert "not set" in error_msg.lower()

    def test_resolve_env_vars_leaves_non_placeholder_values_unchanged(self, monkeypatch):
        """
        GIVEN credentials with mix of placeholders and direct values
        WHEN resolve_env_vars() is called
        THEN only placeholders should be substituted
        """
        from src.config.models import Credentials

        monkeypatch.setenv("TEST_KEY", "resolved_value")

        creds = Credentials(
            api_key="${TEST_KEY}",
            api_secret="hardcoded_secret",  # No placeholder
            account_number="ACC123"
        )

        creds.resolve_env_vars()

        assert creds.api_key == "resolved_value"
        assert creds.api_secret == "hardcoded_secret"  # Unchanged


# ============================================================================
# RiskRulesConfig Model Tests
# ============================================================================


class TestRiskRulesConfigValidation:
    """Test RiskRulesConfig model validation."""

    def test_valid_risk_rules_config_parses_successfully(self):
        """
        GIVEN a valid risk rules configuration
        WHEN RiskRulesConfig model is instantiated
        THEN it should parse without errors
        """
        from src.config.models import RiskRulesConfig

        valid_config = {
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
                            "enabled": True,
                            "params": {"limit": -500.00}
                        }
                    ]
                }
            },
            "account_overrides": {}
        }

        config = RiskRulesConfig(**valid_config)

        assert "conservative" in config.profiles
        assert len(config.profiles["conservative"].rules) == 2
        assert config.profiles["conservative"].rules[0].rule == "MaxContracts"
        assert config.profiles["conservative"].rules[0].enabled is True

    def test_empty_profile_name_raises_validation_error(self):
        """
        GIVEN risk rules config with empty profile name
        WHEN RiskRulesConfig model is instantiated
        THEN it should raise ValidationError

        Business Rule: Profile names must be non-empty strings
        """
        from src.config.models import RiskRulesConfig

        invalid_config = {
            "profiles": {
                "": {  # Empty profile name
                    "rules": []
                }
            },
            "account_overrides": {}
        }

        with pytest.raises(ValidationError) as exc_info:
            RiskRulesConfig(**invalid_config)

        # Pydantic may reject empty dict keys or fail validation
        assert exc_info.value is not None


# ============================================================================
# NotificationsConfig Model Tests
# ============================================================================


class TestNotificationsConfigValidation:
    """Test NotificationsConfig model validation."""

    def test_valid_notifications_config_parses_successfully(self):
        """
        GIVEN a valid notifications configuration
        WHEN NotificationsConfig model is instantiated
        THEN it should parse without errors
        """
        from src.config.models import NotificationsConfig

        valid_config = {
            "discord": {
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123456/token"
            },
            "telegram": {
                "enabled": False,
                "bot_token": "",
                "chat_id": ""
            }
        }

        config = NotificationsConfig(**valid_config)

        assert config.discord.enabled is True
        assert "discord.com" in config.discord.webhook_url
        assert config.telegram.enabled is False

    def test_invalid_discord_webhook_url_raises_validation_error(self):
        """
        GIVEN notifications config with malformed Discord webhook URL
        WHEN NotificationsConfig model is instantiated
        THEN it should raise ValidationError

        Business Rule: Discord webhook_url must be valid HTTPS URL
        """
        from src.config.models import NotificationsConfig

        invalid_config = {
            "discord": {
                "enabled": True,
                "webhook_url": "not_a_url"  # Invalid URL format
            },
            "telegram": {
                "enabled": False,
                "bot_token": "",
                "chat_id": ""
            }
        }

        with pytest.raises(ValidationError) as exc_info:
            NotificationsConfig(**invalid_config)

        assert "webhook_url" in str(exc_info.value).lower()
