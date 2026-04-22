"""
CLI error presenter utility.

This module provides a centralized way to present trxo_lib exceptions
to the user with a clean, professional UI using Rich, including
actionable hints to help solve the problem.
"""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from trxo_lib.exceptions import TrxoError

# Global console instance
_console = Console()


def present_error(exception: TrxoError) -> None:
    """
    Present a TrxoError to the user in a clean and beautiful format.

    Args:
        exception: The TrxoError instance to present.
    """
    # 1. Prepare Error Message
    error_text = Text()
    error_text.append("✖ ", style="bold red")
    error_text.append(str(exception), style="bold white")

    # 2. Add Hint if available
    hint_text = None
    if hasattr(exception, "hint") and exception.hint:
        hint_text = Text()
        hint_text.append("\n💡 ", style="bold yellow")
        hint_text.append("Hint: ", style="bold yellow")
        hint_text.append(exception.hint, style="italic cyan")

    # 3. Create the panel content
    content = error_text
    if hint_text:
        content.append(hint_text)

    # 4. Print the error block
    _console.print()
    _console.print(Panel(content, border_style="red", expand=False, padding=(1, 2)))
    _console.print()


def present_generic_error(exception: Exception, command_name: str = "") -> None:
    """
    Present a non-TrxoError exception to the user.

    Args:
        exception: The Exception instance to present.
        command_name: Optional command name where the error occurred.
    """
    title = f"Error in {command_name}" if command_name else "Unexpected Error"

    _console.print()
    _console.print(
        Panel(
            Text(str(exception), style="bold white"),
            title=f"[bold red]{title}[/bold red]",
            border_style="red",
            expand=False,
            padding=(1, 2),
        )
    )
    _console.print(
        "[dim]Use --log-level DEBUG to see the full traceback in the logs.[/dim]"
    )
    _console.print()
