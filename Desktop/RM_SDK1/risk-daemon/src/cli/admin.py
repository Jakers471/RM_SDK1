"""
Admin CLI for Risk Manager Daemon management.

Provides password-protected administrative interface for daemon control,
configuration management, and system monitoring.

Architecture: architecture/18-cli-interfaces-implementation.md
"""

import subprocess
import time
from typing import Optional
from unittest.mock import Mock

from src.cli.base import BaseCLI


class AdminCLI(BaseCLI):
    """
    Administrative command-line interface (password-protected).

    Features:
    - HMAC challenge-response authentication
    - Daemon control (start/stop/restart)
    - Configuration management (view/edit/reload/backup/restore)
    - Account management (list/add/edit/toggle)
    - Risk rules editing
    - System status display
    - NO logs displayed in CLI (file-based only)
    """

    def __init__(self, authenticated_client: Optional[Mock] = None):
        """
        Initialize Admin CLI.

        Args:
            authenticated_client: Pre-authenticated DaemonAPIClient (for Trader→Admin transition)
        """
        super().__init__()

        if authenticated_client:
            # Pre-authenticated from Trader CLI
            self.client = authenticated_client
            self.authenticated = True
        else:
            # Create new client, needs authentication
            self.client = None  # Will be initialized when needed
            self.authenticated = False

        self.running = True

    def authenticate(self) -> bool:
        """
        Authenticate with daemon using HMAC challenge-response.

        Maximum 3 attempts allowed.

        Returns:
            bool: True if authenticated, False otherwise
        """
        max_attempts = 3

        for attempt in range(max_attempts):
            try:
                password = input(f"Admin password (attempt {attempt + 1}/{max_attempts}): ")

                if self.client.authenticate_admin(password):
                    self.authenticated = True
                    return True

            except (ConnectionError, TimeoutError) as e:
                print(f"Connection error: {e}")
                self.authenticated = False
                return False

        # Failed all attempts
        self.authenticated = False
        return False

    def start_daemon(self):
        """Start daemon via Windows service control."""
        confirm = input("Start Risk Manager Daemon? (y/n): ")
        if confirm.lower() != 'y':
            return

        result = subprocess.run(
            ["sc", "start", "RiskManagerDaemon"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("✓ Daemon started successfully")
        else:
            print(f"✗ Failed to start daemon: {result.stderr}")

    def stop_daemon(self):
        """Stop daemon via IPC (requires confirmation)."""
        confirm = input("WARNING: Stopping daemon will close all positions. Continue? (y/n): ")
        if confirm.lower() != 'y':
            return

        response = self.client.stop_daemon(reason="Manual shutdown by admin")
        print(f"✓ Daemon shutting down (ETA: {response['shutdown_eta_seconds']}s)")

    def restart_daemon(self):
        """Restart daemon (stop via IPC, then start via sc)."""
        confirm = input("Restart Risk Manager Daemon? (y/n): ")
        if confirm.lower() != 'y':
            return

        # Stop daemon
        response = self.client.stop_daemon(reason="Manual restart by admin")
        wait_time = response['shutdown_eta_seconds']
        print(f"Stopping daemon (waiting {wait_time}s)...")
        time.sleep(wait_time)

        # Start daemon
        result = subprocess.run(
            ["sc", "start", "RiskManagerDaemon"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("✓ Daemon restarted successfully")
        else:
            print(f"✗ Failed to restart daemon: {result.stderr}")

    def offer_to_start_daemon(self) -> bool:
        """
        Offer to start daemon if not running.

        Returns:
            bool: True if daemon started, False otherwise
        """
        offer = input("Daemon is not running. Start it now? (y/n): ")
        if offer.lower() != 'y':
            return False

        result = subprocess.run(
            ["sc", "start", "RiskManagerDaemon"],
            capture_output=True,
            text=True
        )

        return result.returncode == 0

    def view_system_config(self):
        """View current system configuration from daemon."""
        config = self.client.get_config()
        print("\n=== System Configuration ===")
        for section, values in config.items():
            print(f"\n[{section}]")
            for key, value in values.items():
                print(f"  {key} = {value}")
        print()

    def reload_config(self):
        """Hot-reload configuration without daemon restart."""
        print("\nSelect configuration type to reload:")
        print("1. System")
        print("2. Accounts")
        print("3. Risk Rules")
        print("4. Notifications")

        choice = input("Choice: ")
        config_types = {
            "1": "system",
            "2": "accounts",
            "3": "risk_rules",
            "4": "notifications"
        }

        config_type = config_types.get(choice)
        if not config_type:
            print("Invalid choice")
            return

        confirm = input(f"Reload {config_type} configuration? (y/n): ")
        if confirm.lower() != 'y':
            return

        response = self.client.reload_config(config_type)
        print(f"✓ {response['message']}")

    def backup_config(self):
        """Create timestamped configuration backup."""
        # To be implemented
        pass

    def restore_config(self):
        """Restore configuration from backup."""
        # To be implemented
        pass

    def edit_system_config(self):
        """Interactive configuration editor with validation."""
        # To be implemented
        pass

    def list_accounts(self):
        """List all configured accounts with status."""
        health = self.client.get_health()

        print("\n=== Configured Accounts ===")
        for account_id, status in health['accounts'].items():
            conn_status = "✓" if status['connected'] else "✗"
            lockout_status = "LOCKED" if status['lockout'] else "Active"
            print(f"{account_id}: {conn_status} {lockout_status} ({status['positions_count']} positions)")
        print()

        input("Press Enter to continue...")

    def add_account(self):
        """Add new account interactively."""
        # To be implemented
        pass

    def edit_account(self):
        """Edit existing account credentials."""
        # To be implemented
        pass

    def toggle_account(self):
        """Toggle account enabled/disabled status."""
        # To be implemented
        pass

    def test_account_connection(self):
        """Test account SDK connection."""
        # To be implemented
        pass

    def show_system_status(self):
        """Display daemon health and system metrics."""
        try:
            health = self.client.get_health()

            print("\n=== Risk Manager Daemon Status ===")
            print(f"Status: {health['status']}")

            uptime_seconds = health['uptime_seconds']
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            print(f"Uptime: {hours}h {minutes}m")

            print(f"Version: {health['version']}")
            print(f"Memory: {health['memory_usage_mb']:.1f} MB")
            print(f"CPU: {health['cpu_usage_percent']:.1f}%")

            print("\nAccounts:")
            for account_id, status in health['accounts'].items():
                print(f"  {account_id}: {'✓' if status['connected'] else '✗'} ({status['positions_count']} positions)")
            print()

        except ConnectionError:
            print("✗ Daemon not accessible")

        input("Press Enter to continue...")

    def view_logs_menu(self):
        """View log files (NOT live streaming to CLI)."""
        # Admin can view log FILES, not live streaming
        # Architecture requirement: NO logs in CLI terminal
        pass

    def tail_daemon_logs(self):
        """Tail daemon log file (file-based, not stdout)."""
        # Should tail daemon.log FILE, not daemon stdout
        input("Press Enter to continue...")

    def risk_rules_menu(self):
        """Risk rules management menu."""
        input("Press Enter to continue...")

    def check_daemon_connection(self) -> bool:
        """
        Check if daemon is accessible.

        Returns:
            bool: True if daemon responds, False otherwise
        """
        try:
            self.client.get_health()
            return True
        except (ConnectionError, TimeoutError):
            return False

    def show_admin_menu(self):
        """Display main admin menu."""
        choice = self.show_menu("Admin Menu", [
            "System Status",
            "Manage Accounts",
            "Risk Rules",
            "Configuration",
            "Daemon Control",
            "Exit"
        ])

        if choice == 0:  # Exit
            self.running = False

    def cleanup(self):
        """Clean up resources and close connections."""
        if self.client:
            self.client.close()
