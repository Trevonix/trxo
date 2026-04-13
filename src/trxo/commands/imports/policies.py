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
    ContinueOnErrorOpt,
    DiffOpt,
    DryRunOpt,
    ForceImportOpt,
    GlobalOpt,
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
    ContinueOnErrorOpt,
)
from trxo.config.api_headers import get_headers
from trxo.constants import DEFAULT_REALM
from trxo.utils.console import error, info

from .base_importer import BaseImporter


class PoliciesImporter(BaseImporter):
    """Importer for PingOne Advanced Identity Cloud policies"""

    def __init__(self, realm: str = DEFAULT_REALM, global_policy: bool = False):
        super().__init__()
        self.realm = realm
        self.global_policy = global_policy

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return f"policies ({self.realm})"

    def get_item_id(self, item: Dict[str, Any]) -> Optional[str]:
        return item.get("_id")

    def load_data_from_items(
        self, all_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract items from the structured format buckets.

        Args:
            all_items: List of raw items or bucket dictionaries

        Returns:
            Flattened and filtered list of items
        """
        final_items = []
        for item in all_items:
            # If it's a bucket dictionary from our new format
            if isinstance(item, dict) and ("am" in item or "global" in item):
                am_items = item.get("am", [])
                for am_item in am_items:
                    if isinstance(am_item, dict):
                        am_item["_is_global"] = False
                final_items.extend(am_items)

                # Only include global policies if flag is set
                if self.global_policy:
                    global_items = item.get("global", [])
                    for g_item in global_items:
                        if isinstance(g_item, dict):
                            g_item["_is_global"] = True
                    final_items.extend(global_items)
                else:
                    info(
                        "Skipping global policies (use --global-policy to include them)"
                    )

            # Backward compatibility for flat lists or single items
            elif isinstance(item, dict):
                final_items.append(item)
            elif isinstance(item, list):
                final_items.extend(item)

        return final_items

    def load_data_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Load policies from file, handling both legacy flat format
        and new structured (am/global) format.
        """
        import os

        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            error(f"Failed to load file {file_path}: {str(e)}")
            return []

        # Extract the content under 'data' -> 'result'
        if not isinstance(data, dict) or "data" not in data:
            return []

        inner_data = data["data"]
        # Extraction: handling both legacy (with 'result') and new flattened format
        result = inner_data.get("result", inner_data)

        # Wrap in a list for load_data_from_items
        raw_items = result if isinstance(result, list) else [result]
        return self.load_data_from_items(raw_items)

    def get_api_endpoint(
        self,
        item_id: str,
        base_url: str,
        is_policy_set: bool = False,
        is_idm_policy: bool = False,
    ) -> str:
        if is_idm_policy:
            return self._construct_api_url(base_url, f"/openidm/config/{item_id}")
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
        """Upsert policy, policy set, or IDM policy using PUT"""
        item_id = item_data.get("_id")
        if not item_id:
            error("Item missing '_id'; required for upsert")
            return False

        # Detect item type
        # Use explicitly tagged bucket info if available (v2 format)
        # Otherwise fallback to ID-based detection (v1 format)
        is_idm_policy = item_data.get("_is_global")
        if is_idm_policy is None:
            is_idm_policy = item_id.startswith("policy/") or item_id.startswith(
                "fieldPolicy/"
            )

        # Remove the tag before sending to API
        payload_dict = item_data.copy()
        payload_dict.pop("_is_global", None)

        is_policy_set = not is_idm_policy and "applicationName" not in payload_dict

        # Keep complete data as payload
        if is_idm_policy:
            payload_dict.pop("_rev", None)
            payload_dict.pop("_type", None)

        payload = json.dumps(payload_dict)

        url = self.get_api_endpoint(
            item_id, base_url, is_policy_set, is_idm_policy=is_idm_policy
        )

        if is_idm_policy:
            headers = get_headers("default")
        else:
            headers = get_headers("policy_sets" if is_policy_set else "policies")

        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, payload)
            if is_idm_policy:
                info(f"Upserted Global policy (root): {item_id}")
            else:

                item_type = "policy set" if is_policy_set else "policy"
                info(f"Upserted {item_type} ({self.realm}): {item_id}")
            return True
        except Exception as e:
            if is_idm_policy:
                error(f"Failed to upsert IDM policy '{item_id}': {e}")
            else:
                item_type = "policy set" if is_policy_set else "policy"
                error(
                    f"Failed to upsert {item_type} '{item_id}' in realm '{self.realm}': {e}"
                )
            return False

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete a single policy, policy set, or IDM policy via API"""
        is_idm_policy = item_id.startswith("policy/") or item_id.startswith(
            "fieldPolicy/"
        )

        if is_idm_policy:
            url = self.get_api_endpoint(item_id, base_url, is_idm_policy=True)
            headers = get_headers("default")
            headers = {**headers, **self.build_auth_headers(token)}
            try:
                self.make_http_request(url, "DELETE", headers)
                info(f"Successfully deleted Global policy (root): {item_id}")
                return True
            except Exception as e:
                error(f"Failed to delete Global policy '{item_id}': {e}")
                return False

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
        global_policy: GlobalOpt = False,
        diff: DiffOpt = False,
        sync: SyncOpt = False,
        rollback: RollbackOpt = False,
        continue_on_error: ContinueOnErrorOpt = False,
        cherry_pick: CherryPickOpt = None,
        branch: BranchOpt = None,
        realm: RealmOpt = DEFAULT_REALM,
        src_realm: SrcRealmOpt = None,
        dry_run: DryRunOpt = False,
    ):
        """
        Import policies from JSON file (local mode) or
        Git repository (Git mode)
        """
        importer = PoliciesImporter(realm=realm, global_policy=global_policy)
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
            continue_on_error=continue_on_error,
            cherry_pick=cherry_pick,
            global_policy=global_policy,
            dry_run=dry_run,
        )

    return import_policies
