"""
Log management commands for TRXO CLI.

This module provides commands for viewing, configuring, and managing
TRXO application logs.
"""

import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
from trxo.logging import get_logger, setup_logging
from trxo.logging.config import LogConfig, get_log_file_path, get_log_directory
from trxo.utils.console import error, info, warning
from trxo.constants import LOG_APP_NAME, LOG_LINES_TO_SHOW

app = typer.Typer(help="Manage TRXO logs")
console = Console()


@app.command("show")
def show_logs(
    lines: int = typer.Option(
        LOG_LINES_TO_SHOW, "--lines", "-n", help="Number of lines to show"
    ),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    level: Optional[str] = typer.Option(
        None, "--level", help="Filter by log level (DEBUG, INFO, WARNING, ERROR)"
    ),
) -> None:
    """Show recent log entries"""
    setup_logging()
    logger = get_logger("trxo.commands.logs")

    try:
        log_file = get_log_file_path()

        if not log_file.exists():
            warning(
                f"No log file found. Run some {LOG_APP_NAME} commands to generate logs."
            )
            return

        logger.info(f"Displaying last {lines} lines from log file")

        # Read log file
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()

        # Filter by level if specified
        if level:
            level_upper = level.upper()
            filtered_lines = [line for line in all_lines if level_upper in line]
            display_lines = filtered_lines[-lines:] if filtered_lines else []
        else:
            display_lines = all_lines[-lines:]

        if not display_lines:
            info("No log entries found matching the criteria.")
            return

        # Display logs with syntax highlighting
        log_content = "".join(display_lines)
        syntax = Syntax(log_content, "log", theme="monokai", line_numbers=False)
        console.print(syntax)

        if follow:
            info("Following log file... (Press Ctrl+C to stop)")
            # Simple follow implementation
            import time

            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    f.seek(0, 2)  # Go to end of file
                    while True:
                        line = f.readline()
                        if line:
                            if not level or level.upper() in line:
                                console.print(line.rstrip())
                        else:
                            time.sleep(0.1)
            except KeyboardInterrupt:
                info("\nStopped following logs.")

    except Exception as e:
        logger.error(f"Failed to show logs: {str(e)}")
        error(f"Failed to show logs: {str(e)}")
        raise typer.Exit(1)


@app.command("info")
def log_info() -> None:
    """Show log configuration and file information"""
    setup_logging()
    logger = get_logger("trxo.commands.logs")

    try:
        config = LogConfig()
        log_file = get_log_file_path(config)
        log_dir = get_log_directory()

        # Create info table
        table = Table(
            title=f"{LOG_APP_NAME} Log Information",
            show_header=True,
            header_style="bold blue",
        )
        table.add_column("Setting", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")

        # Basic info
        table.add_row("Log Directory", str(log_dir))
        table.add_row("Log File", str(log_file))
        table.add_row("Log Level", config.default_level.value)
        table.add_row("Rotation", "Daily at midnight")
        table.add_row("Retention Days", str(config.log_retention_days))

        # File info if exists
        if log_file.exists():
            stat = log_file.stat()
            size_mb = stat.st_size / (1024 * 1024)
            table.add_row("Current Size", f"{size_mb:.2f} MB")
            from datetime import datetime

            modified = datetime.fromtimestamp(stat.st_mtime)
            table.add_row("Last Modified", modified.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            table.add_row("Current Size", "File not found")
            table.add_row("Last Modified", "N/A")

        # Count rotated files
        rotated_files = list(log_dir.glob("trxo.log.*"))
        table.add_row("Rotated Files", str(len(rotated_files)))

        console.print(table)
        logger.info("Displayed log information")

    except Exception as e:
        logger.error(f"Failed to show log info: {str(e)}")
        error(f"Failed to show log info: {str(e)}")
        raise typer.Exit(1)
