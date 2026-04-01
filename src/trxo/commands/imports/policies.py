"""
Policies import command.

Import functionality for PingOne Advanced Identity Cloud policies.
- Uses PUT with _id in endpoint: /am/json/realms/root/realms/{realm}/policies/{_id}
- Keeps complete data as payload (no field removal)
- Works as upsert (create or update)
"""

import json
from typing import Any, Dict, List, Optional

from trxo.commands.shared.options import (
    AmBaseUrlOpt,
    AuthModeOpt,
    BaseUrlOpt,
    BranchOpt,
    CherryPickOpt,
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
    RollbackOpt,
    SaIdOpt,
    SrcRealmOpt,
    SyncOpt,
)
from trxo_lib.config.api_headers import get_headers
from trxo_lib.constants import DEFAULT_REALM
from trxo_lib.utils.console import error, info

from trxo_lib.operations.imports.base_importer import BaseImporter


class PoliciesImporter(BaseImporter):
    """Importer for PingOne Advanced Identity Cloud policies"""

    def __init__(self, realm: str = DEFAULT_REALM):
        super().__init__()
        self.realm = realm

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return f"policies ({self.realm})"

    def get_item_id(self, item: Dict[str, Any]) -> Optional[str]:
        return item.get("_id")

    def get_api_endpoint(
        self, item_id: str, base_url: str, is_policy_set: bool = False
    ) -> str:
        if is_policy_set:
            return self._construct_api_url(
                base_url,
                f"/am/json/realms/root/realms/{self.realm}/applications/{item_id}",
            )
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/policies/{item_id}",
        )

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Upsert policy or policy set using PUT"""
        item_id = item_data.get("_id")
        if not item_id:
            error("Item missing '_id'; required for upsert")
            return False

        # Policy Sets don't have "applicationName" indicating an owner
        is_policy_set = "applicationName" not in item_data

        # Keep complete data as payload (no field removal as per requirement)
        payload = json.dumps(item_data)

        url = self.get_api_endpoint(item_id, base_url, is_policy_set)
        headers = get_headers("policy_sets" if is_policy_set else "policies")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, payload)
            item_type = "policy set" if is_policy_set else "policy"
            info(f"Upserted {item_type} ({self.realm}): {item_id}")
            return True
        except Exception as e:
            item_type = "policy set" if is_policy_set else "policy"
            error(
                f"Failed to upsert {item_type} '{item_id}' in realm '{self.realm}': {e}"
            )
            return False

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete a single policy or policy set via API"""
        # Try as policy first
        url = self.get_api_endpoint(item_id, base_url, is_policy_set=False)
        headers = get_headers("policies")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "DELETE", headers)
            info(f"Successfully deleted policy ({self.realm}): {item_id}")
            return True
        except Exception:
            # Fallback to policy set
            url = self.get_api_endpoint(item_id, base_url, is_policy_set=True)
            headers = get_headers("policy_sets")
            headers = {**headers, **self.build_auth_headers(token)}

            try:
                self.make_http_request(url, "DELETE", headers)
                info(f"Successfully deleted policy set ({self.realm}): {item_id}")
                return True
            except Exception as e:
                error(f"Failed to delete '{item_id}' in realm '{self.realm}': {e}")
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
        sync: SyncOpt = False,
        rollback: RollbackOpt = False,
        cherry_pick: CherryPickOpt = None,
        branch: BranchOpt = None,
        realm: RealmOpt = DEFAULT_REALM,
        src_realm: SrcRealmOpt = None,
    ):
        """
        Import policies from JSON file (local mode) or
        Git repository (Git mode)
        """
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
            sync=sync,
            rollback=rollback,
            cherry_pick=cherry_pick,
        )

    return import_policies
