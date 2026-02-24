"""
ESV (Environment Secrets & Variables) export commands.

This module provides export functionality for PingOne Advanced Identity Cloud Environment
Secrets and Variables.
"""

import typer
from trxo.utils.console import console, warning, info
from .base_exporter import BaseExporter


def create_esv_commands():
    """Create ESV export command functions"""

    def export_esv_secrets(
        view: bool = typer.Option(None, "--view", help="View: all secrets"),
        view_columns: str = typer.Option(
            None,
            "--view-columns",
            help="Comma-separated list of columns to display (e.g., '_id,name,active')",
        ),
        version: str = typer.Option(
            None, "--version", help="Custom version name (default: auto)"
        ),
        no_version: bool = typer.Option(
            False, "--no-version", help="Disable auto versioning for legacy filenames"
        ),
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
        project_name: str = typer.Option(
            None, "--project-name", help="Project name for argument mode (optional)"
        ),
        output_dir: str = typer.Option(
            None, "--dir", help="Output directory for JSON files"
        ),
        output_file: str = typer.Option(
            None, "--file", help="Output filename (without .json extension)"
        ),
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
        am_base_url: str = typer.Option(

            None, "--am-base-url", help="On-Prem AM base URL"

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
    ):
        """Export Environment Secrets"""
        exporter = BaseExporter()

        headers = {
            "Accept-API-Version": "resource=2.0",
            "Content-Type": "application/json",
        }

        exporter.export_data(
            command_name="esv_secrets",
            api_endpoint="/environment/secrets",
            headers=headers,
            view=view,
            view_columns=view_columns,
            jwk_path=jwk_path,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            output_dir=output_dir,
            output_file=output_file,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            idm_base_url=idm_base_url,
            idm_username=idm_username,
            idm_password=idm_password, am_base_url=am_base_url,
            version=version,
            no_version=no_version,
            branch=branch,
            commit_message=commit,
        )

    def export_esv_variables(
        view: bool = typer.Option(None, "--view", help="View: all variables"),
        view_columns: str = typer.Option(
            None,
            "--view-columns",
            help="Comma-separated list of columns to display (e.g., '_id,name,active')",
        ),
        version: str = typer.Option(
            None, "--version", help="Custom version name (default: auto)"
        ),
        no_version: bool = typer.Option(
            False, "--no-version", help="Disable auto versioning for legacy filenames"
        ),
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
        project_name: str = typer.Option(
            None, "--project-name", help="Project name for argument mode (optional)"
        ),
        output_dir: str = typer.Option(
            None, "--dir", help="Output directory for JSON files"
        ),
        output_file: str = typer.Option(
            None, "--file", help="Output filename (without .json extension)"
        ),
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
        am_base_url: str = typer.Option(

            None, "--am-base-url", help="On-Prem AM base URL"

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
    ):
        """Export Environment Variables"""
        exporter = BaseExporter()

        headers = {
            "Accept-API-Version": "resource=1.0",
            "Content-Type": "application/json",
        }

        exporter.export_data(
            command_name="esv_variables",
            api_endpoint="/environment/variables",
            headers=headers,
            view=view,
            view_columns=view_columns,
            jwk_path=jwk_path,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            output_dir=output_dir,
            output_file=output_file,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            idm_base_url=idm_base_url,
            idm_username=idm_username,
            idm_password=idm_password, am_base_url=am_base_url,
            version=version,
            no_version=no_version,
            branch=branch,
            commit_message=commit,
        )

    return export_esv_secrets, export_esv_variables


def create_esv_callback():
    """Create ESV callback function"""

    def esv_callback(ctx: typer.Context):
        """Top-level ESV command.

        If run without a subcommand, prints a short guide to help the user.
        """
        if ctx.invoked_subcommand is None:
            console.print()
            warning("No ESV subcommand selected.")
            info("ESV has two subcommands:")
            info("  • secrets")
            info("  • variables")
            console.print()
            info("Run one of:")
            info("  trxo export esv secrets --help")
            info("  trxo export esv variables --help")
            console.print()
            info("Tip: use --help on any command to see options.")
            console.print()
            raise typer.Exit(code=0)

    return esv_callback
