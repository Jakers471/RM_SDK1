"""
Trader CLI for Risk Manager Daemon monitoring.

Provides read-only monitoring interface for traders to view:
- Live dashboard with positions and PnL
- Enforcement log with BREACHES IN RED TEXT
- Clock in/out for session tracking
- Risk limit time tracker
- Current time and date display
- Switch to Admin mode (with password)

Architecture: architecture/18-cli-interfaces-implementation.md
"""

import sys
import time
from datetime import datetime
from typing import Optional
from unittest.mock import Mock

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.cli.base import BaseCLI


class TraderCLI(BaseCLI):
    """
    Trader command-line interface (read-only monitoring).

    Features:
    - Live dashboard with auto-refresh
    - Position and PnL display
    - Enforcement log with RED text for breaches
    - Clock in/out tracking
    - Risk limit time tracker
    - Current time/date display
    - Switch to Admin mode (password-protected)
    - READ-ONLY: Cannot modify rules or control daemon
    """

    def __init__(self, account_id: Optional[str] = None):
        """
        Initialize Trader CLI.

        Args:
            account_id: Trading account ID to monitor
        """
        super().__init__()
        self.account_id = account_id
        self.client = None  # Will be initialized when needed
        self.session_start = None  # For clock in/out

    def render_dashboard(self) -> Panel:
        """
        Render live dashboard with positions, PnL, and status.

        Returns:
            Panel: Rich panel with dashboard content
        """
        try:
            # Fetch data from daemon
            positions_data = self.client.get_positions(self.account_id)
            pnl_data = self.client.get_pnl(self.account_id)
            health_data = self.client.get_health()

            # Get current time/date
            now = datetime.now()
            time_str = now.strftime("%H:%M:%S")
            date_str = now.strftime("%Y-%m-%d")

            # Build dashboard content
            content = []

            # Header with time/date
            content.append(f"[bold]{date_str} {time_str}[/bold]")
            content.append("")

            # Connection status
            account_status = health_data['accounts'].get(self.account_id, {})
            if account_status.get('connected'):
                content.append("[green]Connected ✓[/green]")
            else:
                content.append("[red]Disconnected ✗[/red]")
            content.append("")

            # Lockout warning
            if pnl_data.get('lockout'):
                content.append("[bold red]⚠ ACCOUNT LOCKED OUT ⚠[/bold red]")
                content.append("")

            # P&L Summary
            realized = pnl_data.get('realized_pnl_today', 0.0)
            unrealized = pnl_data.get('unrealized_pnl', 0.0)
            combined = pnl_data.get('combined_pnl', 0.0)

            content.append("[bold]P&L Summary[/bold]")
            content.append(f"Realized: {self.format_currency(realized)}")
            content.append(f"Unrealized: {self.format_currency(unrealized)}")
            content.append(f"Combined: {self.format_currency(combined)}")
            content.append("")

            # Risk Limits
            loss_limit = pnl_data.get('daily_loss_limit', -500.0)
            profit_target = pnl_data.get('daily_profit_target', 1000.0)

            loss_pct = (combined / loss_limit * 100) if loss_limit else 0
            profit_pct = (combined / profit_target * 100) if profit_target else 0

            content.append("[bold]Risk Limits[/bold]")
            content.append(f"Loss Limit: ${loss_limit:.2f} ({loss_pct:.1f}% used)")
            content.append(f"Profit Target: ${profit_target:.2f} ({profit_pct:.1f}% reached)")
            content.append("")

            # Positions Table
            if positions_data.get('positions'):
                content.append("[bold]Open Positions[/bold]")
                for pos in positions_data['positions']:
                    pnl_str = self.format_currency(pos['unrealized_pnl'])
                    content.append(
                        f"{pos['symbol']} {pos['side']} {pos['quantity']} @ "
                        f"${pos['entry_price']:.2f} (now ${pos['current_price']:.2f}) {pnl_str}"
                    )
            else:
                content.append("[yellow]No open positions[/yellow]")

            return Panel(
                "\n".join(content),
                title=f"[bold cyan]Risk Manager Dashboard - {self.account_id}[/bold cyan]",
                border_style="cyan"
            )

        except Exception as e:
            # Error panel
            return Panel(
                f"[red]Error fetching dashboard data: {e}[/red]",
                title="[bold red]Dashboard Error[/bold red]",
                border_style="red"
            )

    def show_live_dashboard(self):
        """Show live dashboard with 5-second auto-refresh."""
        try:
            while True:
                self.clear_screen()
                dashboard = self.render_dashboard()
                self.console.print(dashboard)
                time.sleep(5)  # 5 second refresh
        except KeyboardInterrupt:
            pass

    def show_static_dashboard(self):
        """Show static dashboard snapshot."""
        dashboard = self.render_dashboard()
        self.console.print(dashboard)
        input("Press Enter to continue...")

    def show_enforcement_log(self):
        """
        Display enforcement log with BREACHES IN RED TEXT.

        Architecture requirement:
        - Breaches MUST be displayed in RED text
        """
        log_data = self.client.get_enforcement_log(self.account_id, limit=20)

        if not log_data.get('enforcement_actions'):
            self.console.print("[green]✓ No enforcement actions yet today[/green]")
            input("Press Enter to continue...")
            return

        self.console.print("\n[bold]Enforcement Log[/bold]")
        self.console.print()

        for action in log_data['enforcement_actions']:
            timestamp = action.get('timestamp', '')
            rule = action.get('rule', '')
            action_type = action.get('action', '')
            result = action.get('result', '')
            breach = action.get('breach', False)

            # CRITICAL: Display breaches in RED text
            if breach:
                self.console.print(f"[bold red]⚠ BREACH - {timestamp}[/bold red]")
                self.console.print(f"[bold red]  Rule: {rule}[/bold red]")
                self.console.print(f"[bold red]  Action: {action_type}[/bold red]")
                self.console.print(f"[bold red]  Result: {result}[/bold red]")
            else:
                self.console.print(f"{timestamp}")
                self.console.print(f"  Rule: {rule}")
                self.console.print(f"  Action: {action_type}")
                self.console.print(f"  Result: {result}")

            if 'position' in action:
                pos = action['position']
                symbol = pos.get('symbol', '')
                quantity = pos.get('quantity', 0)
                self.console.print(f"  Position: {symbol} x{quantity}")

            self.console.print()

        input("Press Enter to continue...")

    def clock_in_out(self):
        """Clock in/out feature for session tracking."""
        # To be implemented
        input("Press Enter to continue...")

    def show_risk_rules(self):
        """Display risk rules (read-only)."""
        self.console.print("\n[yellow]Risk rules are read-only in Trader mode.[/yellow]")
        self.console.print("[yellow]Switch to Admin mode to modify rules.[/yellow]")
        input("Press Enter to continue...")

    def show_positions(self):
        """Display positions table."""
        positions_data = self.client.get_positions(self.account_id)

        if not positions_data.get('positions'):
            self.console.print("[yellow]No open positions[/yellow]")
            input("Press Enter to continue...")
            return

        # Create positions table
        table = Table(title=f"Open Positions - {self.account_id}")
        table.add_column("Symbol", style="cyan")
        table.add_column("Side", style="white")
        table.add_column("Qty", justify="right")
        table.add_column("Entry", justify="right")
        table.add_column("Current", justify="right")
        table.add_column("P&L", justify="right")

        total_pnl = 0.0
        for pos in positions_data['positions']:
            pnl = pos['unrealized_pnl']
            total_pnl += pnl

            pnl_style = "green" if pnl >= 0 else "red"

            table.add_row(
                pos['symbol'],
                pos['side'],
                str(pos['quantity']),
                f"${pos['entry_price']:.2f}",
                f"${pos['current_price']:.2f}",
                f"[{pnl_style}]${pnl:.2f}[/{pnl_style}]"
            )

        self.console.print(table)

        pnl_style = "green" if total_pnl >= 0 else "red"
        self.console.print(f"\nTotal Unrealized P&L: [{pnl_style}]${total_pnl:.2f}[/{pnl_style}]")

        input("\nPress Enter to continue...")

    def show_connection_status(self):
        """Display connection status and daemon health."""
        health = self.client.get_health()

        self.console.print("\n[bold]Daemon Status[/bold]")
        self.console.print(f"Status: {health['status']}")
        self.console.print(f"Uptime: {self.format_uptime(health['uptime_seconds'])}")
        self.console.print(f"Memory: {health['memory_usage_mb']:.1f} MB")
        self.console.print(f"CPU: {health['cpu_usage_percent']:.1f}%")

        account_status = health['accounts'].get(self.account_id, {})
        self.console.print(f"\nAccount: {self.account_id}")

        if account_status.get('connected'):
            self.console.print("[green]Connected ✓[/green]")
        else:
            self.console.print("[red]Disconnected ✗[/red]")

        self.console.print(f"Positions: {account_status.get('positions_count', 0)}")
        self.console.print(f"Last Event: {account_status.get('last_event_seconds_ago', 'N/A')}s ago")

        if account_status.get('lockout'):
            self.console.print("[bold red]⚠ ACCOUNT LOCKED OUT ⚠[/bold red]")

        input("\nPress Enter to continue...")

    def select_account(self) -> str:
        """
        Select trading account to monitor.

        Returns:
            str: Selected account ID
        """
        health = self.client.get_health()
        accounts = health.get('accounts', {})

        if not accounts:
            self.console.print("[red]No accounts configured. Please contact admin.[/red]")
            sys.exit(1)
            return ""  # Never reached, but satisfies type checker

        if len(accounts) == 1:
            # Auto-select single account
            return list(accounts.keys())[0]

        # Show account selection menu
        self.console.print("\n[bold]Select Account[/bold]")
        account_list = list(accounts.keys())

        for i, account_id in enumerate(account_list, start=1):
            status = accounts[account_id]
            conn = "✓" if status['connected'] else "✗"
            self.console.print(f"{i}. {account_id} {conn} ({status['positions_count']} positions)")

        while True:
            try:
                choice = int(input("\nSelect account: "))
                if 1 <= choice <= len(account_list):
                    return account_list[choice - 1]
                else:
                    self.console.print("[red]Invalid choice[/red]")
            except ValueError:
                self.console.print("[red]Please enter a number[/red]")
            except (EOFError, KeyboardInterrupt):
                sys.exit(0)

    def switch_to_admin_mode(self):
        """Switch to Admin mode (requires password authentication)."""
        from src.cli.admin import AdminCLI

        password = input("Admin password: ")

        if self.client.authenticate_admin(password):
            self.console.print("[green]✓ Authentication successful[/green]")

            # Launch Admin CLI with authenticated client
            admin_cli = AdminCLI(authenticated_client=self.client)
            admin_cli.run()

            # Return to Trader mode
            self.console.print("[cyan]Returned to Trader Mode[/cyan]")
        else:
            self.console.print("[red]✗ Authentication failed[/red]")

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

    def cleanup(self):
        """Clean up resources and close connections."""
        if self.client:
            self.client.close()
