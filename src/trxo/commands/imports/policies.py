"""
Policies import command.

Import functionality for PingOne Advanced Identity Cloud policies.
- Uses PUT with _id in endpoint: /am/json/realms/root/realms/{realm}/policies/{_id}
- Keeps complete data as payload (no field removal)
- Works as upsert (create or update)
"""

import json
from typing import Any, Dict, List

import typer

from trxo.commands.shared.options import (
    AmBaseUrlOpt,
    AuthModeOpt,
    BaseUrlOpt,
    BranchOpt,
    DiffOpt,
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
    RealmOpt,
    SaIdOpt,
    SrcRealmOpt,
)
from trxo.config.api_headers import get_headers
from trxo.constants import DEFAULT_REALM
from trxo.utils.console import error, info

from .base_importer import BaseImporter


class PoliciesImporter(BaseImporter):
    """Importer for PingOne Advanced Identity Cloud policies"""

    def __init__(self, realm: str = DEFAULT_REALM):
        super().__init__()
        self.realm = realm

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return f"policies ({self.realm})"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/policies/{item_id}",
        )

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Upsert policy using PUT"""
        item_id = item_data.get("_id")
        if not item_id:
            error("Policy missing '_id'; required for upsert")
            return False

        # Keep complete data as payload (no field removal as per requirement)
        payload = json.dumps(item_data)

        url = self.get_api_endpoint(item_id, base_url)
        headers = get_headers("policies")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, payload)
            info(f"Upserted policy ({self.realm}): {item_id}")
            return True
        except Exception as e:
            error(
                f"Failed to upsert policy '{item_id}' in realm " f"'{self.realm}': {e}"
            )
            return False


def create_policies_import_command():
    """Create the policies import command function"""

    def import_policies(
        file: InputFileOpt = None,
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
        branch: BranchOpt = None,
        realm: RealmOpt = DEFAULT_REALM,
        src_realm: SrcRealmOpt = None,
    ):
        """Import policies from JSON file (local mode) or Git repository (Git mode)"""
        importer = PoliciesImporter(realm=realm)
        importer.import_from_file(
            file_path=file,
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
        )

    return import_policies
