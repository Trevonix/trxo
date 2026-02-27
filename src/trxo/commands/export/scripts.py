"""
Scripts export commands.

This module provides export functionality for
PingOne Advanced Identity Cloud scripts.
"""

import base64
import typer
from typing import Any, Dict
from trxo.utils.console import warning
from .base_exporter import BaseExporter
from trxo.constants import DEFAULT_REALM


def decode_script_response(response_data: Any) -> Any:
    """
    Decode base64-encoded script fields in the response data.

    This filter processes the API response before saving to make scripts
    human-readable in exported JSON files.

    Args:
        response_data: The API response data (dict with 'result' or list)

    Returns:
        Modified response data with decoded script fields
    """

    def decode_script_field(script_obj: Dict[str, Any]) -> None:
        """Decode the 'script' field in a script object if present."""
        if not isinstance(script_obj, dict):
            return

        script_field = script_obj.get("script")
        if not script_field or not isinstance(script_field, str):
            return

        try:
            # Decode base64 to bytes, then to UTF-8 string
            decoded_bytes = base64.b64decode(script_field, validate=True)
            decoded_text = decoded_bytes.decode("utf-8")

            # Split into array of lines for better readability (Frodo format)
            script_lines = decoded_text.splitlines()
            script_obj["script"] = script_lines
        except Exception as e:
            # If decoding fails, keep original value and log a warning
            script_name = script_obj.get("name", script_obj.get("_id", "Unknown"))
            warning(f"Failed to decode script field for '{script_name}': {str(e)}")

    # Handle different response structures
    if isinstance(response_data, dict):
        # Standard AM API response: {"result": [...], ...}
        if "result" in response_data and isinstance(response_data["result"], list):
            for script_obj in response_data["result"]:
                decode_script_field(script_obj)
        # Single script object
        else:
            decode_script_field(response_data)
    elif isinstance(response_data, list):
        # Direct list of scripts
        for script_obj in response_data:
            decode_script_field(script_obj)

    return response_data


def create_scripts_export_command():
    """Create the scripts export command function"""

    def export_scripts(
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Target realm name (default: {DEFAULT_REALM})",
        ),
        view: bool = typer.Option(None, "--view", help="View: all scripts"),
        view_columns: str = typer.Option(
            None,
            "--view-columns",
            help=(
                "Comma-separated list of columns to display "
                "(e.g., '_id,name,active')"
            ),
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
        """Export scripts configuration"""
        exporter = BaseExporter()

        headers = {
            "Accept-API-Version": "protocol=1.0,resource=1.0",
            "Content-Type": "application/json",
        }

        exporter.export_data(
            command_name="scripts",
            api_endpoint=(
                f"/am/json/realms/root/realms/{realm}/" "scripts?_queryFilter=true"
            ),
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
            response_filter=decode_script_response,
        )

    return export_scripts
