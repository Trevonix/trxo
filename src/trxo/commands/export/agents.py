"""
Agents export commands.

This module provides export functionality for PingOne Advanced Identity
Cloud Identity Gateway, java and web agents.
"""

import typer
from trxo.utils.console import console, warning, info
from .base_exporter import BaseExporter
from trxo.constants import DEFAULT_REALM


def create_agents_export_command():
    """Create the agents export command function"""

    def export_identity_gateway_agents(
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Target realm name (default: {DEFAULT_REALM})",
        ),
        view: bool = typer.Option(
            None, "--view", help="View: all Identity Gateway agents"
        ),
        view_columns: str = typer.Option(
            None,
            "--view-columns",
            help=(
                "Comma-separated list of columns to display "
                "(e.g., '_id,name,active')"
            ),
        ),
        jwk_path: str = typer.Option(
            None, "--jwk-path", help="Path to JWK private key file"
        ),
        client_id: str = typer.Option(None, "--client-id", help="Client ID"),
        sa_id: str = typer.Option(None, "--sa-id", help="Service Account ID"),
        base_url: str = typer.Option(
            None,
            "--base-url",
            help="Base URL for PingOne Advanced Identity Cloud instance",
        ),
        project_name: str = typer.Option(
            None,
            "--project-name",
            help="Project name for argument mode (optional)",
        ),
        output_dir: str = typer.Option(
            None, "--dir", help="Output directory for JSON files"
        ),
        output_file: str = typer.Option(
            None, "--file", help="Output filename (without .json extension)"
        ),
        auth_mode: str = typer.Option(
            None,
            "--auth-mode",
            help="Auth mode override: service-account|onprem",
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
        version: str = typer.Option(
            None, "--version", help="Custom version name (default: auto)"
        ),
        no_version: bool = typer.Option(
            False,
            "--no-version",
            help="Disable auto versioning for legacy filenames",
        ),
        branch: str = typer.Option(
            None,
            "--branch",
            help="Git branch to use for export (Git mode only)",
        ),
        commit: str = typer.Option(
            None, "--commit", help="Custom commit message (Git mode only)"
        ),
    ):
        """Export Identity Gateway Agents"""
        exporter = BaseExporter()

        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "resource=1.0",
        }

        exporter.export_data(
            command_name="agents_gateway",
            api_endpoint=(
                f"/am/json/realms/root/realms/{realm}/realm-config/agents/"
                "IdentityGatewayAgent?_queryFilter=true"
            ),
            headers=headers,
            view=view,
            view_columns=view_columns,
            jwk_path=jwk_path,
            client_id=client_id,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            output_dir=output_dir,
            output_file=output_file,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            version=version,
            no_version=no_version,
            branch=branch,
            commit_message=commit,
        )

    def export_java_agents(
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Target realm name (default: {DEFAULT_REALM})",
        ),
        view: bool = typer.Option(None, "--view", help="View: all Java agents"),
        view_columns: str = typer.Option(
            None,
            "--view-columns",
            help=(
                "Comma-separated list of columns to display "
                "(e.g., '_id,name,active')"
            ),
        ),
        jwk_path: str = typer.Option(
            None, "--jwk-path", help="Path to JWK private key file"
        ),
        client_id: str = typer.Option(None, "--client-id", help="Client ID"),
        sa_id: str = typer.Option(None, "--sa-id", help="Service Account ID"),
        base_url: str = typer.Option(
            None,
            "--base-url",
            help="Base URL for PingOne Advanced Identity Cloud instance",
        ),
        project_name: str = typer.Option(
            None,
            "--project-name",
            help="Project name for argument mode (optional)",
        ),
        output_dir: str = typer.Option(
            None, "--dir", help="Output directory for JSON files"
        ),
        output_file: str = typer.Option(
            None, "--file", help="Output filename (without .json extension)"
        ),
        auth_mode: str = typer.Option(
            None,
            "--auth-mode",
            help="Auth mode override: service-account|onprem",
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
        version: str = typer.Option(
            None, "--version", help="Custom version name (default: auto)"
        ),
        no_version: bool = typer.Option(
            False,
            "--no-version",
            help="Disable auto versioning for legacy filenames",
        ),
        branch: str = typer.Option(
            None,
            "--branch",
            help="Git branch to use for export (Git mode only)",
        ),
        commit: str = typer.Option(
            None, "--commit", help="Custom commit message (Git mode only)"
        ),
    ):
        """Export Java Agents"""
        exporter = BaseExporter()

        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "resource=1.0",
        }

        exporter.export_data(
            command_name="agents_java",
            api_endpoint=(
                f"/am/json/realms/root/realms/{realm}/realm-config/agents/"
                "J2EEAgent?_queryFilter=true"
            ),
            headers=headers,
            view=view,
            view_columns=view_columns,
            jwk_path=jwk_path,
            client_id=client_id,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            output_dir=output_dir,
            output_file=output_file,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            version=version,
            no_version=no_version,
            branch=branch,
            commit_message=commit,
        )

    def export_web_agents(
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Target realm name (default: {DEFAULT_REALM})",
        ),
        view: bool = typer.Option(None, "--view", help="View: all Web agents"),
        view_columns: str = typer.Option(
            None,
            "--view-columns",
            help="Comma-separated list of columns to display (e.g., '_id,name,active')",
        ),
        jwk_path: str = typer.Option(
            None, "--jwk-path", help="Path to JWK private key file"
        ),
        client_id: str = typer.Option(None, "--client-id", help="Client ID"),
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
            None,
            "--auth-mode",
            help="Auth mode override: service-account|onprem",
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
        version: str = typer.Option(
            None, "--version", help="Custom version name (default: auto)"
        ),
        no_version: bool = typer.Option(
            False,
            "--no-version",
            help="Disable auto versioning for legacy filenames",
        ),
        branch: str = typer.Option(
            None,
            "--branch",
            help="Git branch to use for export (Git mode only)",
        ),
        commit: str = typer.Option(
            None, "--commit", help="Custom commit message (Git mode only)"
        ),
    ):
        """Export Web Agents"""
        exporter = BaseExporter()

        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "resource=1.0",
        }

        exporter.export_data(
            command_name="agents_web",
            api_endpoint=(
                f"/am/json/realms/root/realms/{realm}/realm-config/agents/"
                "WebAgent?_queryFilter=true"
            ),
            headers=headers,
            view=view,
            view_columns=view_columns,
            jwk_path=jwk_path,
            client_id=client_id,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            output_dir=output_dir,
            output_file=output_file,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            version=version,
            no_version=no_version,
            branch=branch,
            commit_message=commit,
        )

    return export_identity_gateway_agents, export_java_agents, export_web_agents


def create_agents_callback():
    """Create agents callback function"""

    def agents_callback(ctx: typer.Context):
        """Top-level agents command.

        If run without a subcommand, prints a short guide to help the user.
        """
        if ctx.invoked_subcommand is None:
            console.print()
            warning("No agents subcommand selected.")
            info("Agents has three subcommands:")
            info("  • gateway")
            info("  • java")
            info("  • web")
            console.print()
            info("Run one of:")
            info("  trxo export agent gateway --help")
            info("  trxo export agent java --help")
            info("  trxo export agent web --help")
            console.print()
            info("Tip: use --help on any command to see options.")
            console.print()
            raise typer.Exit(code=0)

    return agents_callback
