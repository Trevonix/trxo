"""
Realm import commands.

Import functionality for AM realms (global-config/realms).
- If item has _id: PUT to /am/json/global-config/realms/{_id}
- Else: POST to /am/json/global-config/realms
Payload fields supported: name, active, parentPath, aliases
"""

import json
from typing import List, Dict, Any, Optional
import typer
from trxo.utils.console import error, info
from .base_importer import BaseImporter


REALMS_COLLECTION = "/am/json/global-config/realms"


class RealmImporter(BaseImporter):
    """Importer for AM realms"""

    def get_required_fields(self) -> List[str]:
        # Require name for create; update can work with _id only, but we validate per item
        return ["name"]

    def get_item_type(self) -> str:
        return "realms"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return self._construct_api_url(base_url, f"{REALMS_COLLECTION}/{item_id}")

    def _build_payload(self, item_data: Dict[str, Any]) -> str:
        # Include only supported fields
        payload_obj = {
            k: item_data.get(k)
            for k in ["name", "active", "parentPath", "aliases"]
            if k in item_data
        }
        return json.dumps(payload_obj)

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Create or update realm based on _id presence"""
        item_id: Optional[str] = item_data.get("_id")
        item_name: str = item_data.get("name", "Unknown")

        # Determine URL and method
        if item_id:
            url = self.get_api_endpoint(item_id, base_url)
            method = "PUT"
        else:
            # Create requires at least name
            if not item_name or item_name == "Unknown":
                error("Realm missing 'name' for creation, skipping")
                return False
            url = self._construct_api_url(base_url, REALMS_COLLECTION)
            method = "POST"

        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=2.1,resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}
        payload = self._build_payload(item_data)

        try:
            resp = self.make_http_request(url, method, headers, payload)
            if method == "PUT":
                info(f"Updated realm: {item_name} (id={item_id})")
            else:
                info(f"Created realm: {item_name}")
            return True
        except Exception as e:
            action = "update" if item_id else "create"
            error(f"Failed to {action} realm '{item_name}': {str(e)}")
            return False


def create_realms_import_command():
    """Create the realms import command function"""

    def import_realms(
        file: str = typer.Option(
            ..., "--file", help="Path to JSON file containing realms data"
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
        force_import: bool = typer.Option(
            False, "--force-import", "-f", help="Skip hash validation and force import"
        ),
        diff: bool = typer.Option(
            False, "--diff", help="Show differences before import"
        ),
        branch: str = typer.Option(
            None, "--branch", help="Git branch to import from (Git mode only)"
        ),
        # diff: bool = typer.Option(False, "--diff", help="Show differences before import"),
    ):
        """Import realms from JSON file. Updates when _id present; otherwise creates."""
        importer = RealmImporter()
        importer.import_from_file(
            file_path=file,
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
        )

    return import_realms
