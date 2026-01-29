"""
Export commands manager.

This module provides the main export CLI application that registers
all export commands from the modular command files.
"""

import typer

# Import commands alphabetically
from .agents import create_agents_export_command, create_agents_callback
from .applications import create_applications_export_command
from .authn import create_authn_export_command
from .connectors import create_connectors_export_command
from .email_templates import create_email_export_command
from .endpoints import create_endpoints_export_command
from .esv import create_esv_commands, create_esv_callback
from .journeys import create_journeys_export_command
from .managed import create_managed_export_command
from .mappings import create_mappings_export_command
from .oauth import create_oauth_export_command
from .policies import create_policies_export_command
from .privileges import create_privileges_export_command
from .realms import create_realms_export_command
from .saml import create_saml_export_command
from .scripts import create_scripts_export_command
from .services import create_services_export_command
from .themes import create_themes_export_command
from .webhooks import create_webhooks_export_command


app = typer.Typer(help="Export configurations")

# Register individual export commands (alphabetically)
app.command("applications")(create_applications_export_command())
app.command("authn")(create_authn_export_command())
app.command("connectors")(create_connectors_export_command())
app.command("email")(create_email_export_command())
app.command("endpoints")(create_endpoints_export_command())
app.command("journeys")(create_journeys_export_command())
app.command("managed")(create_managed_export_command())
app.command("mappings")(create_mappings_export_command())
app.command("oauth")(create_oauth_export_command())
app.command("policies")(create_policies_export_command())
app.command("privileges")(create_privileges_export_command())
app.command("realms")(create_realms_export_command())
app.command("saml")(create_saml_export_command())
app.command("scripts")(create_scripts_export_command())
app.command("services")(create_services_export_command())
app.command("themes")(create_themes_export_command())
app.command("webhooks")(create_webhooks_export_command())

# Create subcommand groups (alphabetically)

# Create Agents subcommand group
agents_app = typer.Typer(help="Export Agents")
agents_app.callback(invoke_without_command=True)(create_agents_callback())

# Register Agent commands (alphabetically)
export_identity_gateway_agents, export_java_agents, export_web_agents = (
    create_agents_export_command()
)
agents_app.command("gateway")(export_identity_gateway_agents)
agents_app.command("java")(export_java_agents)
agents_app.command("web")(export_web_agents)

# Create ESV subcommand group
esv_app = typer.Typer(help="""Export Environment Secrets and Variables (ESV)""")
esv_app.callback(invoke_without_command=True)(create_esv_callback())

# Register ESV commands (alphabetically)
export_esv_secrets, export_esv_variables = create_esv_commands()
esv_app.command(
    "secrets",
    help="""Export Environment Secrets \n
                 NOTE: The exported JSON will not include the actual secret value ""
                 "(e.g., passwords, API keys).""
                 " Only metadata (ID, description, encoding) is returned for security reasons.""",
)(export_esv_secrets)
esv_app.command(
    "variables",
    help="""Export Environment Variables \n
NOTE: The exported JSON will include the base64 encoded value, as variables are non-sensitive.""",
)(export_esv_variables)

# Register groups under export (alphabetically)
app.add_typer(agents_app, name="agent", help="Export Agents")
app.add_typer(esv_app, name="esv", help="Environment Secrets and Variables")
