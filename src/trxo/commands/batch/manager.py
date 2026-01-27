"""
Batch commands manager.

Registers batch export and import commands.
"""

import typer
from .batch_export import create_batch_export_command
from .batch_import import create_batch_import_command
from .config_generator import create_config_generator_command

# Create the batch commands app
app = typer.Typer(
    name="batch",
    help="Batch operations for multiple configurations",
    no_args_is_help=True
)

# Register batch commands
app.command("export")(create_batch_export_command())
app.command("import")(create_batch_import_command())
app.command("generate-config")(create_config_generator_command())
