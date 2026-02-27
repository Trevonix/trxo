"""
Webhooks import command.

Imports AM realm webhooks with PUT upsert.
Endpoint: /am/json/realms/root/realms/{realm}/realm-config/webhooks/{_id}
- Removes _rev from payload before sending
- Uses PUT for upsert (create/update)
"""

import json
from typing import List, Dict, Any
import typer
from trxo.utils.console import error, info
from .base_importer import BaseImporter
from trxo.constants import DEFAULT_REALM


class WebhooksImporter(BaseImporter):
    """Importer for AM webhooks"""

    def __init__(self, realm: str = DEFAULT_REALM):
        super().__init__()
        self.realm = realm

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return f"webhooks ({self.realm})"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/"
            f"realm-config/webhooks/{item_id}",
        )

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Upsert webhook via PUT after stripping _rev"""
        item_id = item_data.get("_id")
        if not item_id:
            error("Webhook missing '_id'; required for upsert")
            return False

        # Make a copy and remove _rev if present
        payload_obj = dict(item_data)
        payload_obj.pop("_rev", None)
        payload = json.dumps(payload_obj)

        url = self.get_api_endpoint(item_id, base_url)
        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=1.0,resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, payload)
            info(f"Upserted webhook ({self.realm}): {item_id}")
            return True
        except Exception as e:
            error(
                f"Failed to upsert webhook '{item_id}' in realm " f"'{self.realm}': {e}"
            )
            return False


def create_webhooks_import_command():
    """Create the webhooks import command function"""

    def import_webhooks(
        file: str = typer.Option(
            None, "--file", help="Path to JSON file containing webhooks"
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
        force_import: bool = typer.Option(
            False, "--force-import", "-f", help="Skip hash validation and force import"
        ),
        diff: bool = typer.Option(
            False, "--diff", help="Show differences before import"
        ),
        branch: str = typer.Option(
            None, "--branch", help="Git branch to import from (Git mode only)"
        ),
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Target realm name (default: {DEFAULT_REALM})",
        ),
    ):
        """Import webhooks from JSON file to specified realm"""
        importer = WebhooksImporter(realm=realm)
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
            idm_password=idm_password, am_base_url=am_base_url,
            force_import=force_import,
            branch=branch,
            diff=diff,
        )

    return import_webhooks
