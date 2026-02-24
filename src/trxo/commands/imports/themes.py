"""
Themes import command.

Safe import for Ping AIC ui/themerealm configuration using PATCH.
"""

import json
from typing import List, Dict, Any
import typer
from trxo.utils.console import error, info
from .base_importer import BaseImporter
from trxo.constants import DEFAULT_REALM


class ThemesImporter(BaseImporter):
    """Safe PATCH importer for Ping AIC ui/themerealm"""

    def __init__(self):
        super().__init__()
        self.product = "idm"

    def get_required_fields(self) -> List[str]:
        # No strict requirements - supports partial realm updates
        return []

    def get_item_type(self) -> str:
        return "themes (ui/themerealm)"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        # Single resource endpoint
        return f"{base_url}/openidm/config/ui/themerealm"

    def _fetch_current(self, token: str, base_url: str) -> Dict[str, Any]:
        url = self.get_api_endpoint("", base_url)
        headers = {"Accept-API-Version": "protocol=2.1,resource=1.0"}
        headers = {**headers, **self.build_auth_headers(token)}
        resp = self.make_http_request(url, "GET", headers)
        try:
            return resp.json()
        except Exception:
            return {}

    def _build_patch_ops(
        self, current: Dict[str, Any], incoming: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        ops: List[Dict[str, Any]] = []
        current_realms = (current or {}).get("realm", {}) or {}
        incoming_realms = (incoming or {}).get("realm", {}) or {}

        # For each realm in the incoming file
        for realm_name, realm_arr in incoming_realms.items():
            # If the entire realm is missing in current -> add the array
            if realm_name not in current_realms:
                ops.append(
                    {
                        "operation": "add",
                        "field": f"/realm/{realm_name}",
                        "value": realm_arr,
                    }
                )
                continue

            # Ensure array structure
            curr_arr = current_realms.get(realm_name) or []
            if not isinstance(curr_arr, list) or not curr_arr:
                # Replace the whole realm array
                ops.append(
                    {
                        "operation": "replace",
                        "field": f"/realm/{realm_name}",
                        "value": realm_arr,
                    }
                )
                continue

            # Compare first object fields (index 0) per the example structure
            curr_obj = curr_arr[0] if isinstance(curr_arr[0], dict) else {}
            in_obj = (
                realm_arr[0]
                if (
                    isinstance(realm_arr, list)
                    and realm_arr
                    and isinstance(realm_arr[0], dict)
                )
                else {}
            )

            # Add or replace each incoming field
            for key, in_val in in_obj.items():
                if key in curr_obj:
                    if curr_obj.get(key) != in_val:
                        ops.append(
                            {
                                "operation": "replace",
                                "field": f"/realm/{realm_name}/0/{key}",
                                "value": in_val,
                            }
                        )
                else:
                    ops.append(
                        {
                            "operation": "add",
                            "field": f"/realm/{realm_name}/0/{key}",
                            "value": in_val,
                        }
                    )

            # Do not remove any existing keys; only add/replace

        return ops

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Compute and apply safe PATCH operations for ui/themerealm"""
        # Accept both wrapped export format { data: {...} } and raw object
        incoming = item_data
        # Build operations against current server state
        current = self._fetch_current(token, base_url)
        ops = self._build_patch_ops(current, incoming)

        if not ops:
            info("No changes detected for ui/themerealm; skipping PATCH")
            return True

        url = self.get_api_endpoint("", base_url)
        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=2.1,resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PATCH", headers, json.dumps(ops))
            info(f"Patched ui/themerealm with {len(ops)} operation(s)")
            return True
        except Exception as e:
            error(f"Failed to patch ui/themerealm: {e}")
            return False


def create_themes_import_command():
    """Create the themes import command function"""

    def import_themes(
        file: str = typer.Option(
            None,
            "--file",
            help="Path to JSON file containing themes configuration",
        ),
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Target realm name (default: {DEFAULT_REALM})",
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
        idm_base_url: str = typer.Option(
            None, "--idm-base-url", help="On-Prem IDM base URL"
        ),
        idm_username: str = typer.Option(
            None, "--idm-username", help="On-Prem IDM username"
        ),
        idm_password: str = typer.Option(
            None, "--idm-password", help="On-Prem IDM password", hide_input=True
        ),
        force_import: bool = typer.Option(
            False,
            "--force-import",
            "-f",
            help="Skip hash validation and force import",
        ),
        diff: bool = typer.Option(
            False, "--diff", help="Show differences before import"
        ),
        branch: str = typer.Option(
            None, "--branch", help="Git branch to import from (Git mode only)"
        ),
    ):
        """Import themes from JSON file or Git repository."""
        importer = ThemesImporter()
        importer.import_from_file(
            file_path=file,
            realm=realm,
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
            force_import=force_import,
            branch=branch,
            diff=diff,
        )

    return import_themes
