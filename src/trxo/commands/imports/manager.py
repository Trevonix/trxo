"""
Import commands manager.

This module provides the main import CLI application that registers
all import commands from the modular command files.
"""

import typer
# Import commands alphabetically
from .agents import create_agents_import_command, create_agents_callback
from .applications import create_applications_import_command
from .authn import create_authn_import_command
from .connectors import create_connectors_import_command
from .email_templates import create_email_templates_import_command
from .endpoints import create_endpoints_import_command
from .esv import create_esv_commands, create_esv_callback
from .journeys import create_journey_import_command
from .managed import create_managed_import_command
from .mappings import create_mappings_import_command
from .oauth import create_oauth_import_command
from .policies import create_policies_import_command
from .privileges import create_privileges_import_command
from .saml import create_saml_import_command
from .scripts import create_script_import_command
from .services import create_services_import_command
from .themes import create_themes_import_command
from .webhooks import create_webhooks_import_command


app = typer.Typer(help="Import configurations")

# Register individual import commands (alphabetically)
app.command("applications")(create_applications_import_command())
app.command("authn")(create_authn_import_command())
app.command("connectors")(create_connectors_import_command())
app.command("email")(create_email_templates_import_command())
app.command("endpoints")(create_endpoints_import_command())
app.command("journeys")(create_journey_import_command())
app.command("managed")(create_managed_import_command())
app.command("mappings")(create_mappings_import_command())
app.command("oauth")(create_oauth_import_command())
app.command("policies")(create_policies_import_command())
app.command("privileges")(create_privileges_import_command())
app.command("saml")(create_saml_import_command())
app.command("scripts")(create_script_import_command())
app.command("services")(create_services_import_command())
app.command("themes")(create_themes_import_command())
app.command("webhooks")(create_webhooks_import_command())

# Create subcommand groups (alphabetically)

# Create Agents subcommand group
agents_app = typer.Typer(help="Import Agents")
agents_app.callback(invoke_without_command=True)(create_agents_callback())

# Register Agent commands (alphabetically)
import_ig, import_java, import_web = create_agents_import_command()
agents_app.command("gateway")(import_ig)
agents_app.command("java")(import_java)
agents_app.command("web")(import_web)

# Create ESV subcommand group
esv_app = typer.Typer(help="""Import Environment Secrets and Variables (ESV)""")
esv_app.callback(invoke_without_command=True)(create_esv_callback())

# Register ESV commands (alphabetically)
import_esv_variables, import_esv_secrets = create_esv_commands()
esv_app.command("secrets", help="""Import Environment Secrets \n
NOTE: The File should contain the base64 encoded value""")(import_esv_secrets)
esv_app.command("variables", help="""Import Environment Variables \n
NOTE: The File should contain the base64 encoded value""")(import_esv_variables)

# Register groups under import (alphabetically)
app.add_typer(agents_app, name="agent", help="Import Agents")
app.add_typer(esv_app, name="esv", help="Import Environment Secrets and Variables")
