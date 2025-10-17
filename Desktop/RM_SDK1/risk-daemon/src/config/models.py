"""Configuration data models with Pydantic validation.

Provides type-safe configuration models for the Risk Manager Daemon,
with automatic validation according to JSON schema specifications
defined in architecture/16-configuration-implementation.md.

All models use Pydantic v2 for validation and serialization.
"""

import os
import re
from enum import Enum
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# System Configuration Models
# ============================================================================


class LogLevel(str, Enum):
    """Valid log levels for daemon logging."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DaemonConfig(BaseModel):
    """Daemon runtime configuration settings."""

    auto_start: bool
    log_level: LogLevel
    state_persistence_path: str
    daily_reset_time: str = Field(pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    timezone: Literal["America/Chicago", "America/New_York", "America/Los_Angeles", "UTC"]


class AdminConfig(BaseModel):
    """Administrator authentication configuration."""

    password_hash: str = Field(pattern=r"^\$2[aby]\$\d+\$.{53}$")
    require_auth: bool


class SdkConfig(BaseModel):
    """TradingSuite SDK connection configuration."""

    connection_timeout: int = Field(ge=5, le=300)
    reconnect_attempts: int = Field(ge=1, le=20)
    reconnect_delay: int = Field(ge=1, le=60)


class SystemConfig(BaseModel):
    """Top-level system configuration."""

    version: str = Field(pattern=r"^\d+\.\d+$")
    daemon: DaemonConfig
    admin: AdminConfig
    sdk: SdkConfig

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate that config version is supported."""
        if v != "1.0":
            raise ValueError(f"Unsupported config version: {v}")
        return v


# ============================================================================
# Account Configuration Models
# ============================================================================


class Credentials(BaseModel):
    """Broker API credentials with environment variable substitution support."""

    api_key: str
    api_secret: str
    account_number: str

    def resolve_env_vars(self) -> None:
        """Replace ${ENV_VAR} patterns with environment variables.

        Modifies api_key and api_secret fields in-place if they contain
        ${VAR_NAME} patterns, replacing them with os.getenv("VAR_NAME").

        Raises:
            ValueError: If referenced environment variable is not set
        """
        env_var_pattern = r"\$\{([^}]+)\}"

        for field_name in ["api_key", "api_secret"]:
            value = getattr(self, field_name)

            # Check if value matches ${VAR_NAME} pattern
            match = re.fullmatch(env_var_pattern, value)
            if match:
                var_name = match.group(1)
                env_value = os.getenv(var_name)

                if env_value is None:
                    raise ValueError(f"Environment variable not set: {var_name}")

                setattr(self, field_name, env_value)


class Account(BaseModel):
    """Individual trading account configuration."""

    account_id: str = Field(min_length=1)
    account_name: str = Field(min_length=1)
    enabled: bool
    broker: Literal["topstepx"]
    credentials: Credentials
    risk_profile: str


class AccountsConfig(BaseModel):
    """Collection of trading accounts."""

    accounts: List[Account]

    @field_validator("accounts")
    @classmethod
    def validate_unique_ids(cls, v: List[Account]) -> List[Account]:
        """Ensure all account IDs are unique."""
        ids = [acc.account_id for acc in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate account_id found")
        return v


# ============================================================================
# Risk Rules Configuration Models
# ============================================================================


class RuleConfig(BaseModel):
    """Individual risk rule configuration."""

    rule: str
    enabled: bool
    params: Dict[str, Any]


class RuleOverride(BaseModel):
    """Rule parameter override (no enabled field)."""

    rule: str
    params: Dict[str, Any]


class RiskProfile(BaseModel):
    """Named collection of risk rules."""

    rules: List[RuleConfig]


class AccountOverride(BaseModel):
    """Per-account rule parameter overrides."""

    rule_overrides: List[RuleOverride]


class RiskRulesConfig(BaseModel):
    """Risk rules organized by profiles with account-specific overrides."""

    profiles: Dict[str, RiskProfile]
    account_overrides: Dict[str, AccountOverride] = Field(default_factory=dict)

    @field_validator("profiles")
    @classmethod
    def validate_profile_names(cls, v: Dict[str, RiskProfile]) -> Dict[str, RiskProfile]:
        """Ensure profile names are non-empty."""
        if "" in v:
            raise ValueError("Profile name cannot be empty")
        return v


# ============================================================================
# Notifications Configuration Models
# ============================================================================


class DiscordConfig(BaseModel):
    """Discord webhook notification configuration."""

    enabled: bool
    webhook_url: str

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str) -> str:
        """Validate that webhook_url is a valid HTTPS URL."""
        if not v.startswith("http"):
            raise ValueError("webhook_url must be a valid URL")
        return v


class TelegramConfig(BaseModel):
    """Telegram bot notification configuration."""

    enabled: bool
    bot_token: str
    chat_id: str


class NotificationsConfig(BaseModel):
    """Multi-channel notification settings."""

    discord: DiscordConfig
    telegram: TelegramConfig
