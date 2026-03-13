"""
Scripts export commands.

This module provides export functionality for
PingOne Advanced Identity Cloud scripts.
"""

import base64
from typing import Any, Dict

import typer

from trxo.commands.shared.options import (
    AmBaseUrlOpt,
    AuthModeOpt,
    BaseUrlOpt,
    BranchOpt,
    CommitMessageOpt,
    IdmBaseUrlOpt,
    IdmPasswordOpt,
    IdmUsernameOpt,
    JwkPathOpt,
    NoVersionOpt,
    OnPremPasswordOpt,
    OnPremRealmOpt,
    OnPremUsernameOpt,
    OutputDirOpt,
    OutputFileOpt,
    ProjectNameOpt,
    RealmOpt,
    SaIdOpt,
    VersionOpt,
    ViewColumnsOpt,
    ViewOpt,
)
from trxo.config.api_headers import get_headers
from trxo.constants import DEFAULT_REALM
from trxo.utils.console import warning

from .base_exporter import BaseExporter


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
        realm: RealmOpt = DEFAULT_REALM,
        view: ViewOpt = None,
        view_columns: ViewColumnsOpt = None,
        version: VersionOpt = None,
        no_version: NoVersionOpt = False,
        branch: BranchOpt = None,
        commit: CommitMessageOpt = None,
        jwk_path: JwkPathOpt = None,
        sa_id: SaIdOpt = None,
        base_url: BaseUrlOpt = None,
        project_name: ProjectNameOpt = None,
        output_dir: OutputDirOpt = None,
        output_file: OutputFileOpt = None,
        auth_mode: AuthModeOpt = None,
        onprem_username: OnPremUsernameOpt = None,
        onprem_password: OnPremPasswordOpt = None,
        onprem_realm: OnPremRealmOpt = "root",
        am_base_url: AmBaseUrlOpt = None,
        idm_base_url: IdmBaseUrlOpt = None,
        idm_username: IdmUsernameOpt = None,
        idm_password: IdmPasswordOpt = None,
    ):
        """Export scripts configuration"""
        exporter = BaseExporter()

        headers = get_headers("scripts")

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
            idm_password=idm_password,
            am_base_url=am_base_url,
            version=version,
            no_version=no_version,
            branch=branch,
            commit_message=commit,
            response_filter=decode_script_response,
        )

    return export_scripts
