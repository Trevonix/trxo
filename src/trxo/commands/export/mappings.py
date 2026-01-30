"""
Mappings export command.

This module provides export functionality for PingOne Advanced Identity Cloud sync mappings.
Exports from /openidm/config/sync endpoint.
"""

import typer
from .base_exporter import BaseExporter


def create_mappings_export_command():
    """Create the mappings export command function"""

    def export_mappings(
        view: bool = typer.Option(
            False,
            "--view",
            help="Display data in table format instead of exporting to file",
        ),
        view_columns: str = typer.Option(
            None,
            "--view-columns",
            help="Comma-separated list of columns to display "
            "(e.g., 'name,displayName,source,target')",
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
    ):
        """Export sync mappings configuration"""
        exporter = BaseExporter()

        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=2.1,resource=1.0",
        }

        exporter.export_data(
            command_name="mappings",
            api_endpoint="/openidm/config/sync",
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

    return export_mappings
