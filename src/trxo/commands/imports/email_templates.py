"""
Email templates import command.

Import functionality for PingOne Advanced Identity Cloud email templates.
- Uses PUT with _id in endpoint: /openidm/config/{_id}
- Works as upsert (create or update)
"""

import json
from typing import List, Dict, Any
import typer
from trxo.utils.console import error, info
from .base_importer import BaseImporter


class EmailTemplatesImporter(BaseImporter):
    """Importer for PingOne Advanced Identity Cloud email templates"""

    def __init__(self):
        super().__init__()
        self.product = "idm"

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "email templates"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/openidm/config/{item_id}"

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Upsert email template using PUT"""
        item_id = item_data.get("_id")
        if not item_id:
            error("Email template missing '_id'; required for upsert")
            return False

        payload = json.dumps(item_data)

        url = self.get_api_endpoint(item_id, base_url)
        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=2.1,resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, payload)
            info(f"Upserted email template: {item_id}")
            return True
        except Exception as e:
            error(f"Failed to upsert email template '{item_id}': {e}")
            return False


def create_email_templates_import_command():
    """Create the email templates import command function"""

    def import_email_templates(
        cherry_pick: str = typer.Option(
            None,
            "--cherry-pick",
            help="Cherry-pick specific email templates by ID (Note: provide complete _id e.g., "
            "emailTemplate/registration) for multiple IDs,"
            " use comma-separated list e.g., id1,id2,id3",
        ),
        file: str = typer.Option(
            None, "--file", help="Path to JSON file containing email templates"
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
        """Import email templates from JSON file (local mode) or Git repository (Git mode)"""
        importer = EmailTemplatesImporter()
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
            force_import=force_import,
            branch=branch,
            diff=diff,
            cherry_pick=cherry_pick,
        )

    return import_email_templates
