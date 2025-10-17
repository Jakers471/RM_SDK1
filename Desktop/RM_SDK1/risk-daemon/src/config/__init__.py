"""Configuration management module for Risk Manager Daemon.

Public API exports for configuration loading, validation, and hot-reload.
"""

from .config_manager import (
    ConfigManager,
    ConfigurationError,
    ConfigValidationError,
    ConfigNotFoundError,
    ConfigCorruptedError,
)
from .models import (
    # System Configuration
    LogLevel,
    DaemonConfig,
    AdminConfig,
    SdkConfig,
    SystemConfig,
    # Account Configuration
    Credentials,
    Account,
    AccountsConfig,
    # Risk Rules Configuration
    RuleConfig,
    RuleOverride,
    RiskProfile,
    AccountOverride,
    RiskRulesConfig,
    # Notifications Configuration
    DiscordConfig,
    TelegramConfig,
    NotificationsConfig,
)

__all__ = [
    # ConfigManager and Exceptions
    "ConfigManager",
    "ConfigurationError",
    "ConfigValidationError",
    "ConfigNotFoundError",
    "ConfigCorruptedError",
    # System Configuration Models
    "LogLevel",
    "DaemonConfig",
    "AdminConfig",
    "SdkConfig",
    "SystemConfig",
    # Account Configuration Models
    "Credentials",
    "Account",
    "AccountsConfig",
    # Risk Rules Configuration Models
    "RuleConfig",
    "RuleOverride",
    "RiskProfile",
    "AccountOverride",
    "RiskRulesConfig",
    # Notifications Configuration Models
    "DiscordConfig",
    "TelegramConfig",
    "NotificationsConfig",
]
