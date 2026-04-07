"""
Script import commands.

This module provides import functionality for PingOne Advanced Identity Cloud scripts.
"""

import base64
import json
from typing import Any, Dict, List, Optional

import httpx

from trxo_lib.config.api_headers import get_headers
from trxo_lib.constants import (
    DEFAULT_REALM,
    IGNORED_SCRIPT_IDS,
    IGNORED_SCRIPT_NAMES,
)
from trxo.utils.console import error, info

from trxo_lib.imports.processor import BaseImporter


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
        # Construct URL with script ID
        url = self.get_api_endpoint(item_id, base_url)

        headers = get_headers("scripts")
        headers = {**headers, **self.build_auth_headers(token)}

        payload = json.dumps(payload_data)

        try:
            # First try updating (PUT) using httpx directly to avoid noisy 404 logs
            # from make_http_request since a 404 here just means "needs creation"
            with httpx.Client(timeout=30.0) as client:
                response = client.put(url, headers=headers, json=payload_data)

                if response.status_code == 404:
                    # Switch to create logic
                    collection_url = self._construct_api_url(
                        base_url,
                        f"/am/json/realms/root/realms/{self.realm}/scripts?_action=create",
                    )
                    self.make_http_request(collection_url, "POST", headers, payload)
                else:
                    # Otherwise, raise if not successful
                    response.raise_for_status()

        except Exception as e:
            error(f"Error updating/creating script '{item_name}': {str(e)}")
            return False

        info(f"Successfully processed script: {item_name} (ID: {item_id})")
        if hasattr(self, "rollback_manager") and self.rollback_manager:
            baseline = self.rollback_manager.baseline_snapshot.get("scripts", {}).get(
                item_id
            )

            action = "updated" if baseline else "created"

            self.rollback_manager.track_import(
                f"script::{item_id}",
                action=action,
                baseline_item=baseline,
            )
        return True

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete a single script via API"""
        url = self.get_api_endpoint(item_id, base_url)
        headers = get_headers("scripts")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "DELETE", headers)
            info(f"Successfully deleted script: {item_id}")
            return True
        except Exception as e:
            error(f"Error deleting script '{item_id}': {str(e)}")
            return False

    def import_from_file(
        self,
        file_path: Optional[str] = None,
        realm: Optional[str] = None,
        src_realm: Optional[str] = None,
        jwk_path: Optional[str] = None,
        sa_id: Optional[str] = None,
        base_url: Optional[str] = None,
        project_name: Optional[str] = None,
        auth_mode: Optional[str] = None,
        onprem_username: Optional[str] = None,
        onprem_password: Optional[str] = None,
        onprem_realm: Optional[str] = None,
        idm_base_url: Optional[str] = None,
        idm_username: Optional[str] = None,
        idm_password: Optional[str] = None,
        am_base_url: Optional[str] = None,
        force_import: bool = False,
        branch: Optional[str] = None,
        diff: bool = False,
        rollback: bool = False,
        sync: bool = False,
        cherry_pick: Optional[str] = None,
    ) -> None:
        """Override to ensure automated sync (force=True)"""
        super().import_from_file(
            file_path=file_path,
            realm=realm,
            src_realm=src_realm,
            jwk_path=jwk_path,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            idm_base_url=idm_base_url,
            idm_username=idm_username,
            idm_password=idm_password,
            am_base_url=am_base_url,
            force_import=force_import,
            branch=branch,
            diff=diff,
            rollback=rollback,
            sync=sync,
            cherry_pick=cherry_pick,
        )


class ScriptsImportService:
    """Service wrapper for script import operations."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        realm = self.kwargs.get("realm", DEFAULT_REALM)
        importer = ScriptImporter(realm=realm)

        # Typer passes 'file' which maps to 'file_path' in BaseImporter
        if "file" in self.kwargs:
            self.kwargs["file_path"] = self.kwargs.pop("file")

        return importer.import_from_file(**self.kwargs)
