"""
Base CLI - Shared utilities for Admin and Trader CLIs.

Provides common functionality:
- Menu navigation
- Input validation
- Rich console formatting
- Error handling

Architecture Reference: architecture/18-cli-interfaces-implementation.md
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from typing import List, Optional


class BaseCLI:
    """
    Base class for CLI interfaces.

    Provides shared utilities for menu navigation, input validation,
    and rich terminal formatting.
    """

    def __init__(self):
        """Initialize base CLI with Rich console."""
        self.console = Console()
        self.running = False

    def show_menu(self, title: str, options: List[str]) -> int:
        """
        Display numbered menu and get user choice.

        Args:
            title: Menu title
            options: List of menu options (last option is exit)

        Returns:
            Selected option index (0 for exit/back)
        """
        while True:
            self.console.print(f"\n[bold cyan]{title}[/bold cyan]")
            self.console.print()

            # Show numbered options (1-based)
            for i, option in enumerate(options[:-1], start=1):
                self.console.print(f"  {i}. {option}")

            # Show exit option (0) last, dimmed
            self.console.print(f"  [dim]0. {options[-1]}[/dim]")
            self.console.print()

            # Get user input
            try:
                choice = input("Select option: ").strip()
                choice_int = int(choice)

                # Validate range (0 to len(options)-1)
                if 0 <= choice_int < len(options):
                    return choice_int
                else:
                    self.console.print("[red]Invalid option. Please try again.[/red]")
            except ValueError:
                self.console.print("[red]Invalid input. Please enter a number.[/red]")
            except (EOFError, KeyboardInterrupt):
                return 0  # Exit on Ctrl+C or Ctrl+D

    def clear_screen(self):
        """Clear the console screen."""
        self.console.clear()

    def print_error(self, message: str):
        """Print error message in red."""
        self.console.print(f"[red]✗ {message}[/red]")

    def print_success(self, message: str):
        """Print success message in green."""
        self.console.print(f"[green]✓ {message}[/green]")

    def print_warning(self, message: str):
        """Print warning message in yellow."""
        self.console.print(f"[yellow]⚠ {message}[/yellow]")

    def print_info(self, message: str):
        """Print info message in blue."""
        self.console.print(f"[blue]ℹ {message}[/blue]")

    def confirm(self, message: str) -> bool:
        """
        Ask for user confirmation.

        Args:
            message: Confirmation prompt

        Returns:
            True if user confirms, False otherwise
        """
        try:
            response = input(f"{message} (y/n): ").strip().lower()
            return response == 'y'
        except (EOFError, KeyboardInterrupt):
            return False

    def pause(self, message: str = "Press Enter to continue..."):
        """Pause and wait for user to press Enter."""
        try:
            input(message)
        except (EOFError, KeyboardInterrupt):
            pass

    def format_uptime(self, seconds: float) -> str:
        """
        Format uptime seconds as human-readable string.

        Args:
            seconds: Uptime in seconds

        Returns:
            Formatted string like "2h 15m" or "45s"
        """
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    def format_currency(self, amount: float) -> str:
        """
        Format currency with color coding.

        Args:
            amount: Dollar amount

        Returns:
            Formatted string with Rich color tags
        """
        if amount > 0:
            return f"[green]+${amount:,.2f}[/green]"
        elif amount < 0:
            return f"[red]${amount:,.2f}[/red]"
        else:
            return f"${amount:,.2f}"
