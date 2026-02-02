import typer
from trxo.commands import config, project
from trxo.commands.imports import app as import_app
from trxo.commands.export import app as export_app
from trxo.commands.batch import app as batch_app
from trxo.commands import logs
from trxo.logging import setup_logging, get_logger

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
def callback(ctx: typer.Context):
    """
    [bold blue]TRXO[/bold blue] - PingOne Advanced Identity Cloud "\
        "Configuration Management Tool

    A CLI tool for managing PingOne configurations across environments.
    """
    if not ctx.invoked_subcommand:
        print(
            "Welcome to the TRXO CLI! Manage your configurations effortlessly."
            "To proceed type trxo --help"
        )


def main():
    # Initialize logging early
    setup_logging()
    logger = get_logger("trxo.main")
    logger.info("TRxO CLI started")

    try:
        app()
    except Exception as e:
        logger.error(f"Unhandled exception in main: {str(e)}")
        raise
    finally:
        logger.info("TRxO CLI finished")


if __name__ == "__main__":
    main()
