# CLI Interfaces Implementation (Admin + Trader)

## Overview

This document provides detailed implementation specifications for the two command-line interfaces: the **Admin CLI** (full control with password protection for system configuration) and the **Trader CLI** (read-only monitoring interface for daily trading operations).

**Implementation Status**: NOT IMPLEMENTED (P0 Priority)
**Dependencies**: IPC API Layer (23), Service Wrapper (17), Logging Framework (20)
**Estimated Effort**: 3-4 days

## CLI Roles and Distinctions

### Admin CLI (Password-Protected Configuration Interface)
- **Purpose**: Configure and control the Risk Manager Daemon
- **Access**: Password-protected (HMAC challenge-response authentication)
- **Capabilities**:
  - Start/stop/restart daemon service
  - Configure risk rules and parameters
  - Setup SDK API keys and credentials
  - Add/edit/disable trading accounts
  - Reload configuration (hot-reload)
  - View system status and health metrics
- **Restrictions**:
  - **NO logs displayed in CLI** (logs are file-based only, not shown in terminal)
  - Admin configures the system, then daemon runs autonomously

### Trader CLI (Daily Monitoring Interface)
- **Purpose**: Real-time monitoring tool for active traders to use during trading hours
- **Access**: No password required (read-only access)
- **Capabilities**:
  - View current risk rules (read-only)
  - View enforcement log with **BREACHES IN RED TEXT**
  - **Clock in/out feature** (track trading session hours)
  - **Risk limit time tracker** (shows how long to wait after rule breach)
  - View current positions and PnL
  - **Current time and date display**
  - Monitor connection status
  - Switch to Admin mode (with password)
- **Restrictions**:
  - Cannot modify risk rules
  - Cannot start/stop daemon
  - Cannot change configuration
  - Cannot manage accounts
  - Read-only monitoring ONLY

### Daemon (Background Service)
- **Purpose**: Runs 24/7 monitoring and enforcing risk rules
- **Protection**: Cannot be task-killed or stopped without Administrator privileges
- **Operation**: Autonomous execution after Admin configures it

## Core Implementation Requirements

1. **Library**: `rich` for terminal UI (colors, tables, live updates)
2. **IPC Client**: Use `DaemonAPIClient` from doc 23 for daemon communication
3. **Authentication**: HMAC challenge-response for admin mode
4. **Entry Points**: Two separate commands (`risk-manager` for Trader, `risk-manager admin` for Admin)
5. **Live Updates**: Auto-refresh dashboard every 5 seconds
6. **Cross-Platform**: Support Windows Terminal, WSL, PowerShell

---

## Architecture Design

### CLI Communication Model

```
Admin CLI                    Trader CLI
    ↓                            ↓
DaemonAPIClient         DaemonAPIClient
    ↓                            ↓
HTTP REST API (127.0.0.1:5555)
    ↓
Risk Manager Daemon
```

**Key Design Decisions**:
- **Shared Client Library**: Both CLIs use `DaemonAPIClient` from doc 23
- **Rich Terminal UI**: Professional colors, tables, progress bars
- **Interactive Menus**: Numbered options, not command-line flags
- **Seamless Transition**: Trader CLI can switch to Admin mode with password
- **Error Handling**: Graceful fallback if daemon not running

---

## Python Implementation

### Shared Base Classes (src/cli/base.py)

```python
"""
Base classes for CLI interfaces.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from typing import Optional, Dict, Any, List
import time
import sys

from api.client import DaemonAPIClient


class BaseCLI:
    """Base class for both Admin and Trader CLIs."""

    def __init__(self):
        self.console = Console()
        self.client = DaemonAPIClient()
        self.running = True

    def clear_screen(self):
        """Clear terminal screen."""
        self.console.clear()

    def print_header(self, title: str, subtitle: Optional[str] = None):
        """Print formatted header."""
        self.console.print()
        self.console.print(f"[bold cyan]{title}[/bold cyan]")
        if subtitle:
            self.console.print(f"[dim]{subtitle}[/dim]")
        self.console.print()

    def print_error(self, message: str):
        """Print error message in red."""
        self.console.print(f"[bold red]ERROR:[/bold red] {message}")

    def print_success(self, message: str):
        """Print success message in green."""
        self.console.print(f"[bold green]✓[/bold green] {message}")

    def print_warning(self, message: str):
        """Print warning message in yellow."""
        self.console.print(f"[bold yellow]⚠[/bold yellow] {message}")

    def prompt_input(self, prompt: str, choices: Optional[List[str]] = None) -> str:
        """Get user input with optional validation."""
        while True:
            self.console.print(f"\n[bold]{prompt}[/bold]", end=" ")
            user_input = input().strip()

            if choices and user_input not in choices:
                self.print_error(f"Invalid choice. Must be one of: {', '.join(choices)}")
                continue

            return user_input

    def prompt_yes_no(self, question: str) -> bool:
        """Prompt for yes/no confirmation."""
        response = self.prompt_input(f"{question} [y/n]:", choices=['y', 'n', 'Y', 'N'])
        return response.lower() == 'y'

    def prompt_int(self, prompt: str, min_val: Optional[int] = None, max_val: Optional[int] = None) -> int:
        """Prompt for integer input with validation."""
        while True:
            try:
                value = int(self.prompt_input(prompt))

                if min_val is not None and value < min_val:
                    self.print_error(f"Value must be at least {min_val}")
                    continue

                if max_val is not None and value > max_val:
                    self.print_error(f"Value must be at most {max_val}")
                    continue

                return value

            except ValueError:
                self.print_error("Please enter a valid number")

    def prompt_float(self, prompt: str, min_val: Optional[float] = None, max_val: Optional[float] = None) -> float:
        """Prompt for float input with validation."""
        while True:
            try:
                value = float(self.prompt_input(prompt))

                if min_val is not None and value < min_val:
                    self.print_error(f"Value must be at least {min_val}")
                    continue

                if max_val is not None and value > max_val:
                    self.print_error(f"Value must be at most {max_val}")
                    continue

                return value

            except ValueError:
                self.print_error("Please enter a valid number")

    def check_daemon_connection(self) -> bool:
        """Check if daemon is running and accessible."""
        try:
            health = self.client.get_health()
            return health["status"] == "healthy"
        except Exception:
            return False

    def handle_daemon_not_running(self) -> bool:
        """Handle case where daemon is not running."""
        self.print_error("Cannot connect to Risk Manager Daemon")
        self.console.print("\nThe daemon is not running or is not accessible.")
        self.console.print("Please ensure the service is started:\n")
        self.console.print("  [cyan]sc start RiskManagerDaemon[/cyan]\n")
        return False

    def show_menu(self, title: str, options: List[str]) -> int:
        """Show numbered menu and get selection."""
        self.print_header(title)

        for i, option in enumerate(options):
            if i == len(options) - 1:  # Last option (usually Exit/Back)
                self.console.print(f"[dim]0. {option}[/dim]")
            else:
                self.console.print(f"{i+1}. {option}")

        choice = self.prompt_int("\nSelect option:", min_val=0, max_val=len(options)-1)
        return choice

    def pause(self):
        """Pause and wait for user to press Enter."""
        input("\nPress Enter to continue...")

    def cleanup(self):
        """Cleanup resources before exit."""
        self.client.close()
```

---

### Trader CLI Implementation (src/cli/trader.py)

```python
"""
Trader CLI - Read-only monitoring interface.
"""

from cli.base import BaseCLI
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from datetime import datetime, timezone
import time


class TraderCLI(BaseCLI):
    """Trader command-line interface for risk monitoring."""

    def __init__(self, account_id: Optional[str] = None):
        super().__init__()
        self.account_id = account_id
        self.auto_refresh = False

    def run(self):
        """Main entry point for Trader CLI."""
        self.clear_screen()
        self.print_header("Risk Manager - Trader Interface", "Read-only monitoring for active traders")

        # Check daemon connection
        if not self.check_daemon_connection():
            self.handle_daemon_not_running()
            return

        # Get account ID if not provided
        if not self.account_id:
            self.account_id = self.select_account()

        # Main menu loop
        while self.running:
            self.show_trader_menu()

    def select_account(self) -> str:
        """Select account to monitor."""
        try:
            health = self.client.get_health()
            accounts = health.get("accounts", {})

            if not accounts:
                self.print_error("No accounts configured")
                sys.exit(1)

            if len(accounts) == 1:
                return list(accounts.keys())[0]

            # Multiple accounts - let user choose
            self.print_header("Select Account")
            account_list = list(accounts.keys())

            for i, account_id in enumerate(account_list):
                acc_info = accounts[account_id]
                connected = "✓" if acc_info["connected"] else "✗"
                self.console.print(f"{i+1}. {account_id} [{connected}]")

            choice = self.prompt_int("Select account:", min_val=1, max_val=len(account_list))
            return account_list[choice - 1]

        except Exception as e:
            self.print_error(f"Failed to get accounts: {e}")
            sys.exit(1)

    def show_trader_menu(self):
        """Show main trader menu."""
        self.clear_screen()

        choice = self.show_menu(
            "TRADER MENU",
            [
                "Dashboard",
                "View Positions",
                "View Risk Rules",
                "Enforcement Log",
                "Notification Settings",
                "Clock In/Out",
                "Connection Status",
                "Admin Mode (requires password)",
                "Exit"
            ]
        )

        if choice == 1:
            self.show_dashboard()
        elif choice == 2:
            self.show_positions()
        elif choice == 3:
            self.show_risk_rules()
        elif choice == 4:
            self.show_enforcement_log()
        elif choice == 5:
            self.configure_notifications()
        elif choice == 6:
            self.clock_in_out()
        elif choice == 7:
            self.show_connection_status()
        elif choice == 8:
            self.switch_to_admin_mode()
        elif choice == 0:
            self.running = False

    def show_dashboard(self):
        """Show live dashboard with positions, PnL, limits."""
        self.clear_screen()
        self.print_header("Dashboard", f"Account: {self.account_id}")

        # Ask if user wants live updates
        live_mode = self.prompt_yes_no("Enable auto-refresh (updates every 5 seconds)?")

        if live_mode:
            self.show_live_dashboard()
        else:
            self.show_static_dashboard()
            self.pause()

    def show_live_dashboard(self):
        """Show dashboard with live updates."""
        with Live(self.render_dashboard(), refresh_per_second=0.2, screen=False) as live:
            while True:
                live.update(self.render_dashboard())
                time.sleep(5)  # Refresh every 5 seconds

                # Check for user interrupt (Ctrl+C)
                try:
                    pass
                except KeyboardInterrupt:
                    break

    def show_static_dashboard(self):
        """Show dashboard snapshot."""
        self.console.print(self.render_dashboard())

    def render_dashboard(self) -> Panel:
        """Render dashboard panel."""
        try:
            # Fetch data
            positions = self.client.get_positions(self.account_id)
            pnl = self.client.get_pnl(self.account_id)
            health = self.client.get_health()

            # Build dashboard layout
            layout = Layout()
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="positions", size=10),
                Layout(name="pnl", size=8),
                Layout(name="limits", size=6),
                Layout(name="status", size=4)
            )

            # Header
            account_info = health["accounts"][self.account_id]
            connected = "✓ Connected" if account_info["connected"] else "✗ Disconnected"
            layout["header"].update(
                Panel(f"[bold]Account:[/bold] {self.account_id} | [bold]Status:[/bold] {connected}")
            )

            # Positions table
            positions_table = Table(title="Open Positions")
            positions_table.add_column("Symbol", style="cyan")
            positions_table.add_column("Side", style="magenta")
            positions_table.add_column("Qty", justify="right")
            positions_table.add_column("Entry", justify="right")
            positions_table.add_column("Current", justify="right")
            positions_table.add_column("Unrealized PnL", justify="right")

            for pos in positions["positions"]:
                pnl_color = "green" if pos["unrealized_pnl"] >= 0 else "red"
                pnl_str = f"[{pnl_color}]${pos['unrealized_pnl']:.2f}[/{pnl_color}]"

                positions_table.add_row(
                    pos["symbol"],
                    pos["side"].capitalize(),
                    str(pos["quantity"]),
                    f"${pos['entry_price']:.2f}",
                    f"${pos['current_price']:.2f}",
                    pnl_str
                )

            layout["positions"].update(positions_table)

            # PnL Summary
            realized_color = "green" if pnl["realized_pnl_today"] >= 0 else "red"
            unrealized_color = "green" if pnl["unrealized_pnl"] >= 0 else "red"
            combined_color = "green" if pnl["combined_pnl"] >= 0 else "red"

            pnl_text = Text()
            pnl_text.append("PnL Today:\n", style="bold")
            pnl_text.append(f"  Realized:   ", style="dim")
            pnl_text.append(f"${pnl['realized_pnl_today']:.2f}\n", style=realized_color)
            pnl_text.append(f"  Unrealized: ", style="dim")
            pnl_text.append(f"${pnl['unrealized_pnl']:.2f}\n", style=unrealized_color)
            pnl_text.append(f"  Combined:   ", style="bold")
            pnl_text.append(f"${pnl['combined_pnl']:.2f}", style=f"bold {combined_color}")

            layout["pnl"].update(Panel(pnl_text, title="Performance"))

            # Risk Limits
            loss_pct = (pnl["realized_pnl_today"] / pnl["daily_loss_limit"]) * 100 if pnl["daily_loss_limit"] < 0 else 0
            profit_pct = (pnl["realized_pnl_today"] / pnl["daily_profit_target"]) * 100 if pnl["daily_profit_target"] > 0 else 0

            limits_text = Text()
            limits_text.append("Risk Limits:\n", style="bold")
            limits_text.append(f"  Daily Loss:   ${pnl['realized_pnl_today']:.2f} / ${pnl['daily_loss_limit']:.2f} ({loss_pct:.1f}%)\n")
            limits_text.append(f"  Daily Profit: ${pnl['realized_pnl_today']:.2f} / ${pnl['daily_profit_target']:.2f} ({profit_pct:.1f}%)\n")

            if pnl["lockout"]:
                limits_text.append("\n⚠️  ACCOUNT LOCKED OUT", style="bold red")

            layout["limits"].update(Panel(limits_text, title="Limits"))

            # Status
            status_text = f"Last updated: {datetime.now().strftime('%H:%M:%S')}"
            layout["status"].update(Panel(status_text, style="dim"))

            return Panel(layout, title="[bold cyan]Dashboard[/bold cyan]", border_style="cyan")

        except Exception as e:
            return Panel(f"[red]Error loading dashboard: {e}[/red]", title="Dashboard", border_style="red")

    def show_positions(self):
        """Show open positions table."""
        self.clear_screen()
        self.print_header("Open Positions", f"Account: {self.account_id}")

        try:
            positions = self.client.get_positions(self.account_id)

            if not positions["positions"]:
                self.console.print("[yellow]No open positions[/yellow]")
                self.pause()
                return

            # Create positions table
            table = Table(title=f"Open Positions for {self.account_id}")
            table.add_column("Symbol", style="cyan", no_wrap=True)
            table.add_column("Side", style="magenta")
            table.add_column("Quantity", justify="right")
            table.add_column("Entry Price", justify="right")
            table.add_column("Current Price", justify="right")
            table.add_column("Unrealized PnL", justify="right")

            for pos in positions["positions"]:
                pnl_color = "green" if pos["unrealized_pnl"] >= 0 else "red"
                pnl_str = f"[{pnl_color}]${pos['unrealized_pnl']:.2f}[/{pnl_color}]"

                table.add_row(
                    pos["symbol"],
                    pos["side"].capitalize(),
                    str(pos["quantity"]),
                    f"${pos['entry_price']:.2f}",
                    f"${pos['current_price']:.2f}",
                    pnl_str
                )

            self.console.print(table)
            self.console.print(f"\n[bold]Total Unrealized PnL:[/bold] ${positions['total_unrealized_pnl']:.2f}")

        except Exception as e:
            self.print_error(f"Failed to load positions: {e}")

        self.pause()

    def show_risk_rules(self):
        """Show active risk rules (read-only)."""
        self.clear_screen()
        self.print_header("Active Risk Rules", f"Account: {self.account_id} (Read-Only)")

        self.console.print("[yellow]Note:[/yellow] Risk rules can only be modified in Admin Mode\n")

        # TODO: Get rules from daemon
        self.console.print("[dim]Risk rules display not yet implemented[/dim]")

        self.pause()

    def show_enforcement_log(self):
        """Show recent enforcement actions."""
        self.clear_screen()
        self.print_header("Enforcement Log", f"Account: {self.account_id}")

        try:
            log = self.client.get_enforcement_log(self.account_id, limit=20)

            if not log["enforcement_actions"]:
                self.console.print("[green]No enforcement actions yet today[/green]")
                self.pause()
                return

            for action in log["enforcement_actions"]:
                timestamp = action["timestamp"]
                rule = action["rule"]
                action_type = action["action"]
                result = action["result"]

                # Format enforcement message
                self.console.print(f"\n[bold][{timestamp}][/bold]")
                self.console.print(f"  [yellow]Rule:[/yellow] {rule}")
                self.console.print(f"  [yellow]Action:[/yellow] {action_type}")

                # Show position details
                pos = action.get("position", {})
                if pos:
                    for key, value in pos.items():
                        self.console.print(f"  [dim]{key}:[/dim] {value}")

                self.console.print(f"  [yellow]Result:[/yellow] {result}")

        except Exception as e:
            self.print_error(f"Failed to load enforcement log: {e}")

        self.pause()

    def configure_notifications(self):
        """Configure notification settings."""
        self.clear_screen()
        self.print_header("Notification Settings", "Configure Discord/Telegram alerts")

        self.console.print("[yellow]Note:[/yellow] Notification configuration coming soon\n")
        self.pause()

    def clock_in_out(self):
        """Clock in/out for session tracking."""
        self.clear_screen()
        self.print_header("Clock In/Out", "Track your trading hours")

        self.console.print("[yellow]Note:[/yellow] Time tracking feature coming soon\n")
        self.pause()

    def show_connection_status(self):
        """Show daemon and broker connection status."""
        self.clear_screen()
        self.print_header("Connection Status")

        try:
            health = self.client.get_health()

            # Daemon status
            self.console.print("[bold]Daemon Status:[/bold]")
            self.console.print(f"  Status: [green]Running ✓[/green]")
            self.console.print(f"  Uptime: {health['uptime_seconds'] // 3600} hours")
            self.console.print(f"  Memory: {health['memory_usage_mb']:.1f} MB")
            self.console.print(f"  CPU: {health['cpu_usage_percent']:.1f}%")

            # Account status
            account_info = health["accounts"].get(self.account_id)
            if account_info:
                self.console.print(f"\n[bold]Account {self.account_id}:[/bold]")

                if account_info["connected"]:
                    self.console.print(f"  Connection: [green]Connected ✓[/green]")
                else:
                    self.console.print(f"  Connection: [red]Disconnected ✗[/red]")

                self.console.print(f"  Open Positions: {account_info['positions_count']}")
                self.console.print(f"  Last Event: {account_info['last_event_seconds_ago']}s ago")

                if account_info["lockout"]:
                    self.console.print(f"  [bold red]⚠️  ACCOUNT LOCKED OUT[/bold red]")

        except Exception as e:
            self.print_error(f"Failed to get connection status: {e}")

        self.pause()

    def switch_to_admin_mode(self):
        """Switch to Admin CLI with password authentication."""
        self.clear_screen()
        self.print_header("Switch to Admin Mode", "Authentication required")

        password = self.prompt_input("Enter admin password:")

        try:
            authenticated = self.client.authenticate_admin(password)

            if authenticated:
                self.print_success("Authentication successful")
                time.sleep(1)

                # Launch Admin CLI
                from cli.admin import AdminCLI
                admin_cli = AdminCLI(authenticated_client=self.client)
                admin_cli.run()

                # Return to trader mode when admin exits
                self.clear_screen()
                self.print_header("Returned to Trader Mode")
                time.sleep(1)

            else:
                self.print_error("Authentication failed")
                self.pause()

        except Exception as e:
            self.print_error(f"Authentication error: {e}")
            self.pause()
```

---

### Admin CLI Implementation (src/cli/admin.py)

```python
"""
Admin CLI - Full control interface with authentication.
"""

from cli.base import BaseCLI
from typing import Optional
import time


class AdminCLI(BaseCLI):
    """Admin command-line interface for full system control."""

    def __init__(self, authenticated_client: Optional[DaemonAPIClient] = None):
        super().__init__()

        if authenticated_client:
            self.client = authenticated_client
            self.authenticated = True
        else:
            self.authenticated = False

    def run(self):
        """Main entry point for Admin CLI."""
        self.clear_screen()
        self.print_header("Risk Manager - Admin Interface", "Full system control")

        # Authenticate if not already authenticated
        if not self.authenticated:
            if not self.authenticate():
                return

        # Check daemon connection
        if not self.check_daemon_connection():
            if not self.offer_to_start_daemon():
                return

        # Main menu loop
        while self.running:
            self.show_admin_menu()

    def authenticate(self) -> bool:
        """Authenticate admin user."""
        self.console.print("\n[bold]Admin Authentication Required[/bold]\n")

        for attempt in range(3):
            password = self.prompt_input("Enter admin password:")

            try:
                authenticated = self.client.authenticate_admin(password)

                if authenticated:
                    self.print_success("Authentication successful")
                    self.authenticated = True
                    time.sleep(1)
                    return True
                else:
                    self.print_error(f"Authentication failed (attempt {attempt + 1}/3)")

            except Exception as e:
                self.print_error(f"Authentication error: {e}")

        self.print_error("Maximum authentication attempts exceeded")
        return False

    def offer_to_start_daemon(self) -> bool:
        """Offer to start daemon if not running."""
        if self.prompt_yes_no("Daemon is not running. Would you like to start it now?"):
            try:
                import subprocess
                result = subprocess.run(
                    ["sc", "start", "RiskManagerDaemon"],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    self.print_success("Daemon started successfully")
                    time.sleep(2)
                    return True
                else:
                    self.print_error(f"Failed to start daemon: {result.stderr}")
                    return False

            except Exception as e:
                self.print_error(f"Failed to start daemon: {e}")
                return False

        return False

    def show_admin_menu(self):
        """Show main admin menu."""
        self.clear_screen()

        choice = self.show_menu(
            "ADMIN MENU",
            [
                "Daemon Control",
                "Configuration",
                "Accounts",
                "Risk Rules",
                "View Logs",
                "System Status",
                "Exit"
            ]
        )

        if choice == 1:
            self.daemon_control_menu()
        elif choice == 2:
            self.configuration_menu()
        elif choice == 3:
            self.accounts_menu()
        elif choice == 4:
            self.risk_rules_menu()
        elif choice == 5:
            self.view_logs_menu()
        elif choice == 6:
            self.show_system_status()
        elif choice == 0:
            self.running = False

    def daemon_control_menu(self):
        """Daemon control submenu."""
        self.clear_screen()

        # Get current daemon status
        try:
            health = self.client.get_health()
            status = "Running"
            uptime = f"{health['uptime_seconds'] // 3600} hours, {(health['uptime_seconds'] % 3600) // 60} minutes"
        except:
            status = "Stopped"
            uptime = "N/A"

        self.print_header("Daemon Control")
        self.console.print(f"[bold]Current Status:[/bold] {status}")
        self.console.print(f"[bold]Uptime:[/bold] {uptime}\n")

        choice = self.show_menu(
            "DAEMON CONTROL",
            [
                "Start Daemon",
                "Stop Daemon",
                "Restart Daemon",
                "View Daemon Logs (live)",
                "Back"
            ]
        )

        if choice == 1:
            self.start_daemon()
        elif choice == 2:
            self.stop_daemon()
        elif choice == 3:
            self.restart_daemon()
        elif choice == 4:
            self.tail_daemon_logs()

    def start_daemon(self):
        """Start daemon service."""
        if not self.prompt_yes_no("Start Risk Manager Daemon?"):
            return

        try:
            import subprocess
            result = subprocess.run(
                ["sc", "start", "RiskManagerDaemon"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                self.print_success("Daemon started successfully")
            else:
                self.print_error(f"Failed to start daemon: {result.stderr}")

        except Exception as e:
            self.print_error(f"Failed to start daemon: {e}")

        self.pause()

    def stop_daemon(self):
        """Stop daemon service gracefully."""
        if not self.prompt_yes_no("⚠️  Stop Risk Manager Daemon? This will close all positions."):
            return

        try:
            result = self.client.stop_daemon(reason="Manual shutdown by admin")
            self.print_success(f"Daemon shutdown initiated (ETA: {result['shutdown_eta_seconds']}s)")

        except Exception as e:
            self.print_error(f"Failed to stop daemon: {e}")

        self.pause()

    def restart_daemon(self):
        """Restart daemon service."""
        if not self.prompt_yes_no("Restart Risk Manager Daemon?"):
            return

        try:
            # Stop daemon
            self.client.stop_daemon(reason="Restart requested by admin")
            self.console.print("Stopping daemon...")
            time.sleep(5)

            # Start daemon
            import subprocess
            subprocess.run(["sc", "start", "RiskManagerDaemon"])
            self.print_success("Daemon restarted successfully")

        except Exception as e:
            self.print_error(f"Failed to restart daemon: {e}")

        self.pause()

    def tail_daemon_logs(self):
        """Tail daemon log file in real-time."""
        self.clear_screen()
        self.print_header("Daemon Logs (Live)", "Press Ctrl+C to stop")

        # TODO: Implement log tailing
        self.console.print("[yellow]Live log tailing not yet implemented[/yellow]")
        self.pause()

    def configuration_menu(self):
        """Configuration management submenu."""
        self.clear_screen()

        choice = self.show_menu(
            "CONFIGURATION",
            [
                "View System Config",
                "Edit System Config",
                "Reload Config (hot-reload)",
                "Backup Config",
                "Restore Config",
                "Back"
            ]
        )

        if choice == 1:
            self.view_system_config()
        elif choice == 2:
            self.edit_system_config()
        elif choice == 3:
            self.reload_config()
        elif choice == 4:
            self.backup_config()
        elif choice == 5:
            self.restore_config()

    def view_system_config(self):
        """View current system configuration."""
        self.clear_screen()
        self.print_header("System Configuration")

        # TODO: Get config from daemon
        self.console.print("[yellow]Config viewing not yet implemented[/yellow]")
        self.pause()

    def edit_system_config(self):
        """Edit system configuration interactively."""
        self.clear_screen()
        self.print_header("Edit System Configuration")

        self.console.print("[yellow]Config editing not yet implemented[/yellow]")
        self.pause()

    def reload_config(self):
        """Hot-reload configuration without restarting daemon."""
        self.clear_screen()
        self.print_header("Reload Configuration")

        config_types = ["system", "accounts", "risk_rules", "notifications"]

        self.console.print("[bold]Which configuration to reload?[/bold]\n")
        for i, config_type in enumerate(config_types):
            self.console.print(f"{i+1}. {config_type}.json")
        self.console.print("0. Cancel")

        choice = self.prompt_int("\nSelect option:", min_val=0, max_val=len(config_types))

        if choice == 0:
            return

        config_type = config_types[choice - 1]

        if not self.prompt_yes_no(f"Reload {config_type} configuration?"):
            return

        try:
            result = self.client.reload_config(config_type)
            self.print_success(result["message"])

        except Exception as e:
            self.print_error(f"Failed to reload config: {e}")

        self.pause()

    def backup_config(self):
        """Create configuration backup."""
        self.clear_screen()
        self.print_header("Backup Configuration")

        self.console.print("[yellow]Config backup not yet implemented[/yellow]")
        self.pause()

    def restore_config(self):
        """Restore configuration from backup."""
        self.clear_screen()
        self.print_header("Restore Configuration")

        self.console.print("[yellow]Config restore not yet implemented[/yellow]")
        self.pause()

    def accounts_menu(self):
        """Accounts management submenu."""
        self.clear_screen()

        choice = self.show_menu(
            "ACCOUNTS",
            [
                "List Accounts",
                "Add Account",
                "Edit Account",
                "Enable/Disable Account",
                "Test Connection",
                "Back"
            ]
        )

        if choice == 1:
            self.list_accounts()
        elif choice == 2:
            self.add_account()
        elif choice == 3:
            self.edit_account()
        elif choice == 4:
            self.toggle_account()
        elif choice == 5:
            self.test_account_connection()

    def list_accounts(self):
        """List all configured accounts."""
        self.clear_screen()
        self.print_header("Accounts List")

        try:
            health = self.client.get_health()
            accounts = health.get("accounts", {})

            if not accounts:
                self.console.print("[yellow]No accounts configured[/yellow]")
                self.pause()
                return

            from rich.table import Table
            table = Table(title="Configured Accounts")
            table.add_column("ID", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Connected", justify="center")
            table.add_column("Positions", justify="right")
            table.add_column("Lockout", justify="center")

            for account_id, info in accounts.items():
                connected = "✓" if info["connected"] else "✗"
                lockout = "⚠️" if info["lockout"] else ""

                table.add_row(
                    account_id,
                    "Enabled",  # TODO: Get from config
                    connected,
                    str(info["positions_count"]),
                    lockout
                )

            self.console.print(table)

        except Exception as e:
            self.print_error(f"Failed to list accounts: {e}")

        self.pause()

    def add_account(self):
        """Add new account interactively."""
        self.clear_screen()
        self.print_header("Add Account")

        self.console.print("[yellow]Account management not yet implemented[/yellow]")
        self.pause()

    def edit_account(self):
        """Edit existing account."""
        self.clear_screen()
        self.print_header("Edit Account")

        self.console.print("[yellow]Account editing not yet implemented[/yellow]")
        self.pause()

    def toggle_account(self):
        """Enable/disable account."""
        self.clear_screen()
        self.print_header("Enable/Disable Account")

        self.console.print("[yellow]Account toggle not yet implemented[/yellow]")
        self.pause()

    def test_account_connection(self):
        """Test SDK connection for account."""
        self.clear_screen()
        self.print_header("Test Account Connection")

        self.console.print("[yellow]Connection testing not yet implemented[/yellow]")
        self.pause()

    def risk_rules_menu(self):
        """Risk rules management submenu."""
        self.clear_screen()
        self.print_header("Risk Rules Management")

        self.console.print("[yellow]Risk rules editing not yet implemented[/yellow]")
        self.pause()

    def view_logs_menu(self):
        """Logs viewing submenu."""
        self.clear_screen()

        choice = self.show_menu(
            "VIEW LOGS",
            [
                "Live Daemon Logs (tail -f)",
                "Enforcement Log (recent)",
                "Error Log",
                "Search Logs",
                "Back"
            ]
        )

        if choice == 1:
            self.tail_daemon_logs()
        elif choice == 2:
            self.view_enforcement_log()
        elif choice == 3:
            self.view_error_log()
        elif choice == 4:
            self.search_logs()

    def view_enforcement_log(self):
        """View recent enforcement actions."""
        self.clear_screen()
        self.print_header("Recent Enforcement Actions")

        # TODO: Get enforcement log from daemon
        self.console.print("[yellow]Enforcement log viewing not yet implemented[/yellow]")
        self.pause()

    def view_error_log(self):
        """View error log."""
        self.clear_screen()
        self.print_header("Error Log")

        self.console.print("[yellow]Error log viewing not yet implemented[/yellow]")
        self.pause()

    def search_logs(self):
        """Search logs by keyword."""
        self.clear_screen()
        self.print_header("Search Logs")

        self.console.print("[yellow]Log search not yet implemented[/yellow]")
        self.pause()

    def show_system_status(self):
        """Show comprehensive system status."""
        self.clear_screen()
        self.print_header("System Status")

        try:
            health = self.client.get_health()

            # Daemon status
            self.console.print("[bold cyan]Daemon[/bold cyan]")
            self.console.print(f"  Status: [green]Running[/green]")
            self.console.print(f"  Uptime: {health['uptime_seconds'] // 3600}h {(health['uptime_seconds'] % 3600) // 60}m")
            self.console.print(f"  Version: {health['version']}")
            self.console.print(f"  Memory: {health['memory_usage_mb']:.1f} MB")
            self.console.print(f"  CPU: {health['cpu_usage_percent']:.1f}%")

            # Accounts status
            self.console.print("\n[bold cyan]Accounts[/bold cyan]")
            for account_id, info in health["accounts"].items():
                connected_str = "[green]Connected[/green]" if info["connected"] else "[red]Disconnected[/red]"
                self.console.print(f"  {account_id}: {connected_str}, {info['positions_count']} positions")

        except Exception as e:
            self.print_error(f"Failed to get system status: {e}")

        self.pause()
```

---

### CLI Entry Points (scripts/risk-manager)

```bash
#!/usr/bin/env python3
"""
Risk Manager CLI entry point.

Usage:
    risk-manager                # Launch Trader CLI
    risk-manager admin          # Launch Admin CLI
    risk-manager --account ABC  # Trader CLI for specific account
"""

import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Risk Manager CLI")
    parser.add_argument("mode", nargs="?", default="trader", choices=["trader", "admin"],
                       help="CLI mode: trader (default) or admin")
    parser.add_argument("--account", type=str, help="Account ID to monitor")

    args = parser.parse_args()

    if args.mode == "admin":
        from cli.admin import AdminCLI
        cli = AdminCLI()
        cli.run()
    else:
        from cli.trader import TraderCLI
        cli = TraderCLI(account_id=args.account)
        cli.run()

if __name__ == "__main__":
    main()
```

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/cli/test_base_cli.py
import pytest
from unittest.mock import Mock, patch
from cli.base import BaseCLI


class TestBaseCLI:

    def test_prompt_yes_no_accepts_y(self):
        """Test yes/no prompt accepts 'y'."""
        cli = BaseCLI()

        with patch('builtins.input', return_value='y'):
            result = cli.prompt_yes_no("Continue?")
            assert result is True

    def test_prompt_yes_no_accepts_n(self):
        """Test yes/no prompt accepts 'n'."""
        cli = BaseCLI()

        with patch('builtins.input', return_value='n'):
            result = cli.prompt_yes_no("Continue?")
            assert result is False

    def test_prompt_int_validates_range(self):
        """Test integer prompt validates min/max."""
        cli = BaseCLI()

        with patch('builtins.input', side_effect=['0', '10', '5']):
            result = cli.prompt_int("Enter value:", min_val=1, max_val=10)
            assert result == 5

    def test_check_daemon_connection_returns_true_when_healthy(self):
        """Test daemon connection check when healthy."""
        cli = BaseCLI()
        cli.client = Mock()
        cli.client.get_health.return_value = {"status": "healthy"}

        assert cli.check_daemon_connection() is True

    def test_check_daemon_connection_returns_false_on_error(self):
        """Test daemon connection check when daemon down."""
        cli = BaseCLI()
        cli.client = Mock()
        cli.client.get_health.side_effect = ConnectionError()

        assert cli.check_daemon_connection() is False
```

### Integration Tests

```python
# tests/integration/cli/test_trader_cli_integration.py
import pytest
from cli.trader import TraderCLI
from unittest.mock import Mock, patch


@pytest.mark.integration
def test_trader_cli_shows_dashboard():
    """Test Trader CLI can display dashboard."""
    # Start daemon in background
    # ...

    cli = TraderCLI(account_id="TEST123")
    cli.client = Mock()
    cli.client.get_health.return_value = {
        "status": "healthy",
        "accounts": {"TEST123": {"connected": True, "positions_count": 2, "lockout": False}}
    }
    cli.client.get_positions.return_value = {
        "account_id": "TEST123",
        "positions": [
            {
                "symbol": "MNQ",
                "side": "long",
                "quantity": 2,
                "entry_price": 5042.50,
                "current_price": 5055.00,
                "unrealized_pnl": 62.50
            }
        ],
        "total_unrealized_pnl": 62.50
    }
    cli.client.get_pnl.return_value = {
        "account_id": "TEST123",
        "realized_pnl_today": -150.00,
        "unrealized_pnl": 62.50,
        "combined_pnl": -87.50,
        "daily_loss_limit": -500.00,
        "daily_profit_target": 1000.00,
        "lockout": False
    }

    # Render dashboard
    dashboard = cli.render_dashboard()

    # Verify dashboard rendered
    assert dashboard is not None


@pytest.mark.integration
def test_admin_cli_authenticates():
    """Test Admin CLI authentication flow."""
    cli = AdminCLI()
    cli.client = Mock()
    cli.client.authenticate_admin.return_value = True

    with patch('builtins.input', return_value='admin_password'):
        authenticated = cli.authenticate()

    assert authenticated is True
    assert cli.authenticated is True
```

---

## Installation and Usage

### Installation

```bash
# Install CLI dependencies
uv add rich httpx

# Make CLI executable
chmod +x scripts/risk-manager

# Add to PATH (optional)
ln -s $(pwd)/scripts/risk-manager /usr/local/bin/risk-manager
```

### Usage

```bash
# Launch Trader CLI (read-only)
risk-manager

# Launch Trader CLI for specific account
risk-manager --account ABC123

# Launch Admin CLI (password required)
risk-manager admin
```

---

## Summary for Implementation Agent

**To implement CLI Interfaces, you must:**

1. **Install dependencies**:
   ```
   rich>=13.0  # Terminal UI library
   httpx>=0.24  # HTTP client (already required by IPC client)
   ```

2. **Create base CLI class** (`src/cli/base.py`):
   - Common UI functions (menus, prompts, error handling)
   - Daemon connection checking
   - Input validation helpers

3. **Create Trader CLI** (`src/cli/trader.py`):
   - Dashboard with live updates
   - Positions view (table format)
   - Enforcement log (paginated)
   - Connection status
   - Switch to Admin mode

4. **Create Admin CLI** (`src/cli/admin.py`):
   - Authentication (HMAC challenge-response)
   - Daemon control (start/stop/restart)
   - Configuration management (view/edit/reload)
   - Accounts management (add/edit/list)
   - Risk rules editor
   - Logs viewer (tail, search)

5. **Create CLI entry point** (`scripts/risk-manager`):
   - Parse command-line arguments
   - Launch appropriate CLI mode

6. **Write unit tests** for CLI logic:
   - Input validation
   - Menu navigation
   - Authentication flow

7. **Write integration tests** for daemon communication:
   - Dashboard rendering with live data
   - Admin commands execution
   - Error handling when daemon down

8. **Test cross-platform compatibility**:
   - Windows Terminal
   - WSL
   - PowerShell

**Critical Implementation Notes:**
- Use `DaemonAPIClient` from doc 23 for all daemon communication
- Handle daemon not running gracefully (offer to start in Admin mode)
- Validate all user inputs before sending to daemon
- Use colors consistently (green for success, red for errors, yellow for warnings)
- Implement auto-refresh for dashboard (every 5 seconds)
- Show enforcement actions in red with clear explanations

**Dependencies**: IPC API Layer (23), Service Wrapper (17), Logging (20)
**Blocks**: None (user-facing interfaces)
**Priority**: P0 (required for system usability)
