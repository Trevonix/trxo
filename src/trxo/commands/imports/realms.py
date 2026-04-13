"""
Realm import commands.

Import functionality for AM realms (global-config/realms).
- If item has _id: PUT to /am/json/global-config/realms/{_id}
- Else: POST to /am/json/global-config/realms
Payload fields supported: name, active, parentPath, aliases
"""

import json
from typing import Any, Dict, List, Optional

import typer

from trxo.commands.shared.options import (
    AmBaseUrlOpt,
    AuthModeOpt,
    BaseUrlOpt,
    BranchOpt,
    ContinueOnErrorOpt,
    DiffOpt,
    DryRunOpt,
    ForceImportOpt,
    IdmBaseUrlOpt,
    IdmPasswordOpt,
    IdmUsernameOpt,
    InputFileOpt,
    JwkPathOpt,
    OnPremPasswordOpt,
    OnPremRealmOpt,
    OnPremUsernameOpt,
    ProjectNameOpt,
    SaIdOpt,
    ContinueOnErrorOpt,
)
from trxo.config.api_headers import get_headers
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

        headers = get_headers("realms")
        headers = {**headers, **self.build_auth_headers(token)}
        payload = self._build_payload(item_data)

        try:
            self.make_http_request(url, method, headers, payload)
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
        file: InputFileOpt = ...,
        jwk_path: JwkPathOpt = None,
        sa_id: SaIdOpt = None,
        base_url: BaseUrlOpt = None,
        project_name: ProjectNameOpt = None,
        auth_mode: AuthModeOpt = None,
        onprem_username: OnPremUsernameOpt = None,
        onprem_password: OnPremPasswordOpt = None,
        onprem_realm: OnPremRealmOpt = "root",
        am_base_url: AmBaseUrlOpt = None,
        idm_base_url: IdmBaseUrlOpt = None,
        idm_username: IdmUsernameOpt = None,
        idm_password: IdmPasswordOpt = None,
        force_import: ForceImportOpt = False,
        diff: DiffOpt = False,
        continue_on_error: ContinueOnErrorOpt = False,
        branch: BranchOpt = None,
        continue_on_error: ContinueOnErrorOpt = False,
        dry_run: DryRunOpt = False,
        # diff: bool = typer.Option(False, "--diff", help="Show differences before import"),
    ):
        """Import realms from JSON file. Updates when _id present; otherwise creates."""
        importer = RealmImporter()
        importer.import_from_file(
            file_path=file,
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
            continue_on_error=continue_on_error,
<<<<<<< HEAD
=======
            dry_run=dry_run,
>>>>>>> 8dc291c548055214e3452c4e135d037eaf02a366
        )

    return import_realms
