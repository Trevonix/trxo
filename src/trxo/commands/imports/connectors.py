"""
IDM Connectors import command.

Import functionality for PingIDM connectors.
- Uses PUT with _id in endpoint: /openidm/config/{_id}
- Keeps complete data as payload (no field removal)
- Works as upsert (create or update) based on _id
"""

import json
from typing import Any, Dict, List, Optional

import typer

from trxo.utils.console import error, success

from .base_importer import BaseImporter


class ConnectorsImporter(BaseImporter):
    """Importer for PingIDM connectors"""

    def __init__(self):
        super().__init__()
        self.product = "idm"

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "connectors"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/openidm/config/{item_id}"

    def load_data_from_git(self, git_manager, item_type, realm, branch):
        """
        Normalize connectors export format when loading from Git.
        """

        raw_items = self.file_loader.load_git_files(
            git_manager, item_type, realm, branch
        )

        normalized = []

        for item in raw_items:

            # unwrap export wrapper
            if isinstance(item, dict) and "data" in item:
                data = item["data"]

                # standard TRXO export format
                if isinstance(data, dict) and "result" in data:
                    normalized.extend(data["result"])
                    continue

            # already list of connectors
            if isinstance(item, list):
                normalized.extend(item)

            # already connector dict
            if isinstance(item, dict) and "_id" in item:
                normalized.append(item)

        return normalized

    def load_data_from_file(self, file_path: str):

        with open(file_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        data = raw.get("data", raw)

        # Correct TRXO export format
        if isinstance(data, dict) and "result" in data:
            return data["result"]

        # fallback
        if isinstance(data, list):
            return data

        return []

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:

        item_id = item_data["_id"]
        url = self.get_api_endpoint(item_id, base_url)

        payload = item_data.copy()
        payload.pop("_rev", None)
        payload.pop("_type", None)

        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=2.0,resource=1.0",
        }

        if hasattr(self, "rollback_manager") and self.rollback_manager:
            headers.update(self.rollback_manager._build_auth_headers(token, url))

        import httpx

        with httpx.Client() as client:
            resp = client.put(url, headers=headers, json=payload)

        if resp.status_code in (200, 201, 204):
            success(f"Successfully upserted connector: {item_id}")
            return True

        error(f"Failed to upsert connector '{item_id}'")
        return False

    def _import_from_git(
        self, realm: Optional[str], force_import: bool, branch: Optional[str] = None
    ) -> List[Dict[str, Any]]:

        item_type = self.get_item_type()

        effective_realm = self._determine_effective_realm(realm, item_type, branch)

        git_manager = self._setup_git_manager(branch)

        all_items = self.file_loader.load_git_files(
            git_manager, item_type, effective_realm, branch
        )

        normalized_items = []

        for item in all_items:

            # unwrap connector structures accidentally returned as dict keys
            if isinstance(item, dict) and "_id" in item:
                normalized_items.append(item)

        if not normalized_items:
            self._handle_no_git_files_found(item_type, effective_realm, realm)
            return []

        return normalized_items


def create_connectors_import_command():
    """Create the connectors import command function"""

    def import_connectors(
        cherry_pick: str = typer.Option(
            None,
            "--cherry-pick",
            help="Cherry-pick specific connectors by name (comma-separated)",
        ),
        diff: bool = typer.Option(
            False, "--diff", help="Show differences before import"
        ),
        file: str = typer.Option(
            None, "--file", help="Path to JSON file containing IDM connectors"
        ),
        force_import: bool = typer.Option(
            False, "--force-import", "-f", help="Skip hash validation and force import"
        ),
        branch: str = typer.Option(
            None, "--branch", help="Git branch to import from (Git mode only)"
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
        rollback: bool = typer.Option(
            False,
            "--rollback",
            help="Automatically rollback imported connectors on first failure",
        ),
    ):
        """Import IDM connectors from JSON file (local mode) or Git repository (Git mode).

        Updates existing connectors by _id or creates new ones (upsert).
        """
        importer = ConnectorsImporter()

        importer.import_from_file(
            file_path=file,
            realm=None,  # Root-level config
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
            cherry_pick=cherry_pick,
            rollback=rollback,
        )

    return import_connectors
