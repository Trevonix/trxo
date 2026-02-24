"""
Journey import commands.

This module provides import functionality for
PingOne Advanced Identity Cloud journeys.
"""

import json
from typing import List, Dict, Any
import typer
from trxo.utils.console import error, info
from .base_importer import BaseImporter
from trxo.constants import DEFAULT_REALM


class JourneyImporter(BaseImporter):
    """Importer for PingOne Advanced Identity Cloud Journeys"""

    def __init__(self, realm: str = DEFAULT_REALM):
        super().__init__()
        self.realm = realm

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "journeys"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/realm-config/"
            f"authentication/authenticationtrees/trees/{item_id}",
        )

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Update a single journey via API"""
        item_id = item_data.get("_id")

        if not item_id:
            error(f"Journey '{item_id}' missing _id field, skipping")
            return False

        # Construct URL with journey ID
        url = self.get_api_endpoint(item_id, base_url)

        # Prepare payload
        filtered_data = {k: v for k, v in item_data.items() if k not in ["_id", "_rev"]}
        payload = json.dumps(filtered_data)

        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, payload)
            info(f"Successfully updated journey: (ID: {item_id})")
            return True

        except Exception as e:
            error(f"Error updating journey '{item_id}': {str(e)}")
            return False


def create_journey_import_command():
    """Create the journey import command function"""

    def import_journeys(
        file: str = typer.Option(
            None,
            "--file",
            help="Path to JSON file containing journeys data (local mode only)",
        ),
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Target realm name (default: {DEFAULT_REALM})",
        ),
        cherry_pick: str = typer.Option(
            None,
            "--cherry-pick",
            "-c",
            help=(
                "Import only specific journeys with these IDs(_id) "
                "(comma-separated for multiple IDs)"
            ),
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
        """Import journeys from JSON file or Git repository."""
        importer = JourneyImporter(realm=realm)
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
            cherry_pick=cherry_pick,
            diff=diff,
        )

    return import_journeys
