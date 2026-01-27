from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import List

console = Console()


def success(message: str):
    """Display success message"""
    console.print(f"✔ {message}", style="bold green")


def error(message: str):
    """Display error message"""
    console.print(f"✖ {message}", style="bold red")


def warning(message: str):
    """Display warning message"""
    console.print(f"⚠  {message}", style="bold yellow")


def info(message: str):
    """Display info message"""
    console.print(f"{message}", style="cyan")


def create_table(title: str, columns: List[str]) -> Table:
    """Create a rich table"""
    table = Table(title=title, show_header=True, header_style="bold magenta")
    for column in columns:
        table.add_column(column)
    return table


def display_panel(content: str, title: str, style: str = "blue"):
    """Display content in a panel"""
    console.print(Panel(content, title=title, border_style=style))
