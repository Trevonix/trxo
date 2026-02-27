"""
Batch export command for multiple configurations.

Allows exporting multiple configuration types in a single command.
"""

import typer
from typing import List
from pathlib import Path
from trxo.utils.console import info, success, error, warning
from ..export.manager import app as export_app
from trxo.constants import DEFAULT_REALM


def create_batch_export_command():
    """Create the batch export command function"""

    def batch_export(
        commands: List[str] = typer.Argument(
            None,
            help=(
                "List of export commands "
                "(e.g., realms services themes agent.gateway agent.java "
                "esv.secrets esv.variables). Use --all to export everything."
            ),
        ),
        output_dir: str = typer.Option(
            "batch_export", "--dir", help="Output directory for all exports"
        ),
        scope: str = typer.Option(
            "realm", "--scope", help="Scope for applicable commands (global/realm)"
        ),
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Realm for applicable commands (default: {DEFAULT_REALM})",
        ),
        view: bool = typer.Option(
            False, "--view", help="Display data in table format instead of exporting"
        ),
        all: bool = typer.Option(False, "--all", help="Export all configurations"),
        branch: str = typer.Option(
            None, "--branch", help="Git branch to use for export (Git mode only)"
        ),
        commit: str = typer.Option(
            None, "--commit", help="Custom commit message (Git mode only)"
        ),
        jwk_path: str = typer.Option(
            None, "--jwk-path", help="Path to JWK private key file"
        ),
        sa_id: str = typer.Option(None, "--sa-id", help="Service Account ID"),
        base_url: str = typer.Option(
            None,
            "--base-url",
            help="Base URL for PingOne Advanced Identity Cloud instance",
        ),
        project_name: str = typer.Option(None, "--project-name", help="Project name"),
        auth_mode: str = typer.Option(
            None, "--auth-mode", help="Auth mode override: service-account|onprem"
        ),
        onprem_username: str = typer.Option(
            None, "--onprem-username", help="On-Prem username"
        ),
        onprem_password: str = typer.Option(
            None, "--onprem-password", help="On-Prem password", hide_input=True
        ),
        onprem_realm: str = typer.Option(
            "root", "--onprem-realm", help="On-Prem realm"
        ),
        idm_base_url: str = typer.Option(
            None, "--idm-base-url", help="On-Prem IDM base URL"
        ),
        idm_username: str = typer.Option(
            None, "--idm-username", help="On-Prem IDM username"
        ),
        idm_password: str = typer.Option(
            None, "--idm-password", help="On-Prem IDM password", hide_input=True
        ),
        continue_on_error: bool = typer.Option(
            True,
            "--continue-on-error/--stop-on-error",
            help="Continue if one command fails",
        ),
    ):
        """Export multiple configurations in batch"""

        # Get available commands including sub-commands
        available_commands = typer.main.get_command(export_app).commands
        available_list = set(available_commands.keys())

        # Add sub-commands with dot notation
        esv = available_commands.get("esv")
        if esv:
            available_list |= {f"esv.{k}" for k in esv.commands.keys()}

        agent = available_commands.get("agent")
        if agent:
            available_list |= {f"agent.{k}" for k in agent.commands.keys()}

        # remove the agent and esv main commands
        available_list -= {"agent", "esv"}

        # Expand --all to every available command if no explicit commands provided
        if all and (not commands or len(commands) == 0):
            commands = sorted(list(available_list))
        # If commands provided AND --all also given, ignore --all and respect commands

        # Validate commands
        if not commands or len(commands) == 0:
            error("No commands specified. Provide commands or use --all.")
            raise typer.Exit(1)

        invalid_commands = set(commands) - available_list
        if invalid_commands:
            error(f"Invalid commands: {', '.join(invalid_commands)}")
            info(f"Available commands: {', '.join(sorted(available_list))}")
            raise typer.Exit(1)

        info(f"Starting batch export of {len(commands)} configurations...")
        info(f"Output directory: {output_dir}")

        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        success_count = 0
        failed_commands = []

        for i, command in enumerate(commands, 1):
            print()
            info("-" * 25 + f" [{i}/{len(commands)}] {command} " + "-" * 25)
            try:
                # Build kwargs dynamically and only include supported options
                kwargs = {
                    "output_dir": output_dir,
                    "view": view,
                    "branch": branch,
                    "commit": commit,
                    "jwk_path": jwk_path,
                    "sa_id": sa_id,
                    "base_url": base_url,
                    "project_name": project_name,
                    "auth_mode": auth_mode,
                    "onprem_username": onprem_username,
                    "onprem_password": onprem_password,
                    "onprem_realm": onprem_realm,
                }

                # Get the command (handle sub-commands with dot notation)
                if "." in command:
                    group, sub = command.split(".", 1)
                    sub_cmd = (
                        typer.main.get_command(export_app).commands[group].commands[sub]
                    )
                else:
                    sub_cmd = typer.main.get_command(export_app).commands[command]

                # Add scope/realm only if the subcommand supports them
                params = {p.name for p in sub_cmd.params}
                if "realm" in params:
                    kwargs["realm"] = realm
                if command == "services" and "scope" in params:
                    kwargs["scope"] = scope

                # Execute the export command with filtered kwargs
                sub_cmd.callback(**kwargs)
                success_count += 1
            except Exception as e:
                error(f"Failed to export {command}: {e}")
                failed_commands.append(command)
                if not continue_on_error:
                    error("Stopping batch export due to error")
                    raise typer.Exit(1)

        # Summary
        info("\nBatch Export Summary:")
        info(f"Successful: {success_count}/{len(commands)}")
        if failed_commands:
            info(f"❌ Failed: {', '.join(failed_commands)}")

        if success_count == len(commands):
            success("All exports completed successfully!")
        elif success_count > 0:
            warning(
                f"Partial success: {success_count}/{len(commands)} exports completed"
            )
        else:
            error("All exports failed!")
            raise typer.Exit(1)

    return batch_export
