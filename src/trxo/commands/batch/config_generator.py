"""
Configuration generator for batch operations.

Generates template configuration files for batch import/export.
"""

import typer
import json
from trxo.utils.console import info, success


def create_config_generator_command():
    """Create the config generator command function"""

    def generate_config(
        output_file: str = typer.Option(
            "batch_config.json", "--output", "-o", help="Output file name"
        ),
        template_type: str = typer.Option(
            "import", "--type", "-t", help="Config type: import or export"
        ),
        include_all: bool = typer.Option(
            False, "--all", help="Include all available commands"
        ),
    ):
        """Generate template configuration files for batch operations"""

        if template_type == "import":
            config = {"description": "Batch import configuration", "imports": []}

            # Available import commands with examples
            import_commands = {
                "authn": {"file": "authn_export.json", "realm": "fido"},
                "scripts": {"file": "scripts_export.json", "realm": "fido"},
                "services": {
                    "file": "services_export.json",
                    "scope": "realm",
                    "realm": "fido",
                },
                "themes": {"file": "themes_export.json", "realm": "fido"},
                "journeys": {"file": "journeys_export.json", "realm": "fido"},
                "webhooks": {
                    "file": "webhooks_export.json",
                    "realm": "fido",
                },
                "endpoints": {"file": "endpoints_export.json"},
                "managed": {"file": "managed_export.json"},
                "privileges": {
                    "file": "privileges_export.json",
                    "realm": "fido",
                },
            }

            if include_all:
                for cmd, params in import_commands.items():
                    config["imports"].append({"command": cmd, **params})
            else:
                # Add a few examples
                config["imports"] = [
                    {
                        "command": "authn",
                        "file": "authn_export.json",
                        "realm": "fido",
                    },
                    {
                        "command": "services",
                        "file": "scripts_export.json",
                        "scope": "realm",
                        "realm": "fido",
                    },
                    {"command": "managed", "file": "managed_export.json"},
                ]

        elif template_type == "export":
            config = {
                "description": "Batch export configuration",
                "exports": {"output_dir": "batch_exports", "commands": []},
            }

            export_commands = [
                "realms",
                "services",
                "themes",
                "scripts",
                "saml",
                "journeys",
                "oauth",
                "users",
                "agents",
                "authn",
                "email_templates",
                "endpoints",
                "policies",
                "managed",
                "mappings",
                "connectors",
            ]

            if include_all:
                config["exports"]["commands"] = export_commands
            else:
                config["exports"]["commands"] = [
                    "realms",
                    "services",
                    "themes",
                    "managed",
                ]

        else:
            typer.echo("Invalid template type. Use 'import' or 'export'")
            raise typer.Exit(1)

        # Write config file
        with open(output_file, "w") as f:
            json.dump(config, f, indent=2)

        success(f"Generated {template_type} config: {output_file}")
        info(f"Edit the file to customize your batch {template_type} config")

    return generate_config
