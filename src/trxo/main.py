import sys
import typer

from trxo.commands import config, logs, project
from trxo.commands.batch import app as batch_app
from trxo.commands.export import app as export_app
from trxo.commands.imports import app as import_app
from trxo_lib.exceptions import TrxoAbort, TrxoError
from trxo.logging import get_logger, setup_logging
from trxo.utils.error_presenter import present_error, present_generic_error

app = typer.Typer(
    help="[bold blue]TRXO[/bold blue] - PingOne Advanced Identity Cloud "
    "Configuration Management Tool",
    rich_markup_mode="rich",
)

# Add command groups
app.add_typer(config.app, name="config")
app.add_typer(project.app, name="project")
app.add_typer(export_app, name="export")
app.add_typer(import_app, name="import")
app.add_typer(batch_app, name="batch")
app.add_typer(logs.app, name="logs")

# Add standalone commands
app.command("projects")(project.list_projects)


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    log_level: str = typer.Option(None, "--log-level", help="Override log level"),
    console_level: str = typer.Option(
        None, "--console-level", help="Override console level"
    ),
):
    """
    [bold blue]TRXO[/bold blue] - PingOne Advanced Identity Cloud "\
        "Configuration Management Tool

    A CLI tool for managing PingOne configurations across environments.
    """
    # Setup logging for all commands
    from trxo.logging.config import LogConfig, LogLevel

    config = LogConfig()
    if log_level:
        try:
            config.default_level = LogLevel(log_level.upper())
        except ValueError:
            pass

    if console_level:
        try:
            config.console_level = LogLevel(console_level.upper())
        except ValueError:
            pass

    setup_logging(config=config)

    if not ctx.invoked_subcommand:
        typer.echo(ctx.get_help())
        raise typer.Exit()


def main():
    # Override Python's exception hook to suppress ALL raw tracebacks.
    # Our handlers present errors cleanly; this is the final safety net.
    def _no_traceback_hook(exc_type, exc_value, exc_tb):
        pass

    sys.excepthook = _no_traceback_hook

    if sys.platform == "win32":
        # Enable UTF-8 support for console output symbols on Windows
        import subprocess

        try:
            subprocess.run(["chcp", "65001"], capture_output=True, shell=True)
        except Exception:
            pass

    # Initialize logging early
    setup_logging()
    logger = get_logger("trxo.main")
    logger.info("TRXO CLI started")

    try:
        app(standalone_mode=False)
    except typer.Exit as e:
        sys.exit(e.code)
    except typer.Abort:
        sys.exit(1)
    except TrxoAbort as e:
        # If the error was already presented by a handler, message might be empty
        if str(e):
            present_error(e)
        sys.exit(e.exit_code)
    except TrxoError as e:
        present_error(e)
        sys.exit(e.exit_code)
    except Exception as e:
        logger.error(f"Unhandled exception in main: {str(e)}")
        # Check if we should show a traceback (e.g. if log level is DEBUG)
        present_generic_error(e)
        sys.exit(1)
    finally:
        logger.info("TRXO CLI finished")


if __name__ == "__main__":
    main()
