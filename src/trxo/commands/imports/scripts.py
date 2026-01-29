"""
Script import commands.

This module provides import functionality for PingOne Advanced Identity Cloud scripts.
"""

import base64
import json
from typing import List, Dict, Any
import typer
from trxo.utils.console import error, info
from trxo.constants import (
    DEFAULT_REALM,
    IGNORED_SCRIPT_NAMES,
    IGNORED_SCRIPT_IDS,
)
from .base_importer import BaseImporter


def is_base64_encoded(value: str) -> bool:
    """
    Check if a string is already base64-encoded.

    Args:
        value: String to check

    Returns:
        True if the string appears to be base64-encoded, False otherwise
    """
    try:
        # Try to decode as base64
        decoded = base64.b64decode(value, validate=True)
        # Try to decode as UTF-8 - if it fails, it's likely already base64
        decoded.decode("utf-8")
        # If both succeeded, check if re-encoding gives us the same value
        # This helps detect if it's already encoded
        reencoded = base64.b64encode(decoded).decode("ascii")
        return reencoded == value
    except Exception:
        # If any step fails, assume it's not base64-encoded
        return False


class ScriptImporter(BaseImporter):
    """Importer for PingOne Advanced Identity Cloud scripts"""

    def __init__(self, realm: str = DEFAULT_REALM):
        super().__init__()
        self.realm = realm

    def get_required_fields(self) -> List[str]:
        return ["_id", "name"]

    def get_item_type(self) -> str:
        return "scripts"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/scripts/{item_id}",
        )

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Update a single script via API"""
        item_id = item_data.get("_id")
        item_name = item_data.get("name", "Unknown")

        if item_id in IGNORED_SCRIPT_IDS or item_name in IGNORED_SCRIPT_NAMES:
            info(f"Skipping internal script update: {item_name}")
            return True

        if not item_id:
            error(f"Script '{item_name}' missing _id field, skipping")
            return False

        # Make a copy to avoid modifying the original data
        payload_data = item_data.copy()

        # Encode script field if present and not already encoded
        if "script" in payload_data:
            script_value = payload_data["script"]

            # Handle script as array of lines (Frodo format) or string
            if isinstance(script_value, list):
                # Join array of lines into single string with newlines
                script_text = "\n".join(script_value)
            elif isinstance(script_value, str):
                script_text = script_value
            else:
                error(
                    f"Script field for '{item_name}' has invalid type: "
                    f"{type(script_value)}"
                )
                return False

            if script_text:
                # Check if already base64-encoded (backward compatibility)
                if not is_base64_encoded(script_text):
                    try:
                        # Encode the readable script to base64
                        encoded_bytes = script_text.encode("utf-8")
                        encoded_script = base64.b64encode(encoded_bytes).decode("ascii")
                        payload_data["script"] = encoded_script
                        # info(f"Encoded script field for: {item_name}")
                    except Exception as e:
                        error(
                            f"Failed to encode script field for '{item_name}': {str(e)}"
                        )
                        return False
                else:
                    # Already base64-encoded, use as-is
                    payload_data["script"] = script_text

        # Construct URL with script ID
        url = self.get_api_endpoint(item_id, base_url)

        # Prepare payload with potentially encoded script
        payload = json.dumps(payload_data)

        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, payload)
            info(f"Successfully updated script: {item_name} (ID: {item_id})")
            return True

        except Exception as e:
            error(f"Error updating script '{item_name}': {str(e)}")
            return False

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete a single script via API"""
        url = self.get_api_endpoint(item_id, base_url)

        headers = {
            "Accept-API-Version": "resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "DELETE", headers)
            info(f"Successfully deleted script: {item_id}")
            return True
        except Exception as e:
            error(f"Error deleting script '{item_id}': {str(e)}")
            return False


def create_script_import_command():
    """Create the script import command function"""

    def import_scripts(
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Target realm name (default: {DEFAULT_REALM})",
        ),
        cherry_pick: str = typer.Option(
            None,
            "--cherry-pick",
            help=(
                "Import only specific scripts with these IDs(_id) or name "
                "(comma-separated for multiple IDs, e.g., id1,id2,id3)"
            ),
        ),
        sync: bool = typer.Option(
            False,
            "--sync",
            help=(
                "Sync mode: delete items not in source "
                "(mirror source to destination)"
            ),
        ),
        diff: bool = typer.Option(
            False, "--diff", help="Show differences before import"
        ),
        file: str = typer.Option(
            None, "--file", help="Path to JSON file containing scripts data"
        ),
        force_import: bool = typer.Option(
            False,
            "--force-import",
            "-f",
            help="Skip hash validation and force import",
        ),
        rollback: bool = typer.Option(
            False,
            "--rollback",
            help=(
                "Automatically rollback imported items on first failure "
                "(requires git storage)"
            ),
        ),
        branch: str = typer.Option(
            None, "--branch", help="Git branch to import from (Git mode only)"
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
        """Import scripts from JSON file (local mode) or Git repository (Git mode)"""
        importer = ScriptImporter(realm=realm)
        importer.import_from_file(
            file_path=file,
            realm=realm,
            jwk_path=jwk_path,
            client_id=client_id,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            force_import=force_import,
            branch=branch,
            diff=diff,
            rollback=rollback,
            sync=sync,
            cherry_pick=cherry_pick,
        )

    return import_scripts
