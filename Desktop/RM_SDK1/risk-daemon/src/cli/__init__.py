"""
CLI interfaces for Risk Manager Daemon.

Provides two interfaces:
- Admin CLI: Password-protected full control interface
- Trader CLI: Read-only monitoring interface for daily trading
"""

__all__ = ["AdminCLI", "TraderCLI", "BaseCLI"]
