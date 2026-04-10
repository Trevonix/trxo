"""
Mappings import command.

Import functionality for PingIDM sync mappings with smart upsert logic:
- If mapping exists by name → PATCH to update
- If mapping doesn't exist → PUT to add to the mappings array
- Handles both single mappings and multiple mappings
"""

import json
from typing import Any, Dict, List

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
    RollbackOpt,
    SaIdOpt,
    SyncOpt,
    ContinueOnErrorOpt,
)
from trxo.config.api_headers import get_headers
from trxo.utils.console import error, info, warning

from .base_importer import BaseImporter


class MappingsImporter(BaseImporter):
    """Importer for PingIDM sync mappings with smart upsert logic"""

    def __init__(self):
        super().__init__()
        self.product = "idm"

    def get_required_fields(self) -> List[str]:
        return ["name"]

    def get_item_type(self) -> str:
        return "sync mappings"

    def get_item_id(self, item: Dict[str, Any]) -> str:
        """Use mapping name as identifier for rollback tracking"""
        return item.get("name")

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/openidm/config/sync"

    def _wrap_for_diff(self, data):
        """
        Adapt IDM sync config to the default diff shape expected by BaseImporter.
        BaseImporter expects: { "result": [ ...items... ] }
        IDM sync config is:   { "mappings": [ ... ] }
        """
        if isinstance(data, dict) and "mappings" in data:
            return {"result": data["mappings"]}
        if isinstance(data, list):
            return {"result": data}
        return {"result": [data]}

    def _get_current_sync_config(self, token: str, base_url: str) -> Dict[str, Any]:
        """Fetch current sync configuration"""
        url = self.get_api_endpoint("", base_url)
        headers = get_headers("mappings")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            response = self.make_http_request(url, "GET", headers)
            return response.json()
        except Exception as e:
            error(f"Failed to fetch current sync configuration: {e}")
            return {}

    def _find_mapping_by_name(self, mappings_list: List[Dict], name: str) -> tuple:
        """Find mapping by name in the mappings list. Returns (index, mapping) or (-1, None)"""
        for index, mapping in enumerate(mappings_list):
            if mapping.get("name") == name:
                return index, mapping
        return -1, None

    def _generate_patch_operations(
        self,
        existing_mapping: Dict[str, Any],
        new_mapping: Dict[str, Any],
        base_path: str = "",
    ) -> List[Dict[str, Any]]:
        """Generate PATCH operations by comparing existing and new mappings"""
        operations = []

        # Handle all keys from new mapping
        for key, new_value in new_mapping.items():
            current_path = f"{base_path}/{key}" if base_path else f"/{key}"
            existing_value = existing_mapping.get(key)

            if existing_value != new_value:
                if isinstance(new_value, dict) and isinstance(existing_value, dict):
                    # Recursively handle nested objects
                    nested_ops = self._generate_patch_operations(
                        existing_value, new_value, current_path
                    )
                    operations.extend(nested_ops)
                elif isinstance(new_value, list) and isinstance(existing_value, list):
                    # For arrays (like policies, properties), replace the entire array
                    operations.append(
                        {
                            "operation": "replace",
                            "field": current_path,
                            "value": new_value,
                        }
                    )
                else:
                    # Value changed or new field
                    operations.append(
                        {
                            "operation": (
                                "replace" if key in existing_mapping else "add"
                            ),
                            "field": current_path,
                            "value": new_value,
                        }
                    )

        return operations

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Smart upsert for sync mappings using PATCH for updates, PUT for creates"""
        # Ignore sync wrapper object

        # Handle sync wrapper object safely
        if item_data.get("_id") == "sync":
            mappings = item_data.get("mappings", [])

            success = True
            for mapping in mappings:
                if not mapping.get("name"):
                    continue  # skip invalid mapping

                if not self.update_item(mapping, token, base_url):
                    success = False

            return success

        mapping_name = item_data.get("name")
        if not mapping_name:
            error("Sync mapping missing 'name'; required for upsert")
            return False

        # Get current configuration
        current_config = self._get_current_sync_config(token, base_url)
        if not current_config:
            error("Could not retrieve current sync configuration")
            return False

        current_mappings = current_config.get("mappings", [])

        # Find if mapping exists
        index, existing_mapping = self._find_mapping_by_name(
            current_mappings, mapping_name
        )

        url = self.get_api_endpoint("", base_url)
        headers = get_headers("mappings")
        headers = {**headers, **self.build_auth_headers(token)}

        if index >= 0:
            # Mapping exists - use PATCH for efficient updates
            patch_operations = self._generate_patch_operations(
                existing_mapping, item_data, f"/mappings/{index}"
            )

            if not patch_operations:
                info(f"No changes needed for sync mapping: {mapping_name}")
                return True

            payload = json.dumps(patch_operations)

            try:
                self.make_http_request(url, "PATCH", headers, payload)
                info(
                    f"Updated existing sync mapping: {mapping_name} "
                    f"({len(patch_operations)} changes)"
                )
                return True
            except Exception as e:
                error(f"Failed to update sync mapping '{mapping_name}': {e}")
                return False
        else:
            # Mapping doesn't exist - use PUT to add to the mappings array
            updated_mappings = current_mappings + [item_data]
            updated_config = {**current_config, "mappings": updated_mappings}
            payload = json.dumps(updated_config)

            try:
                self.make_http_request(url, "PUT", headers, payload)
                info(f"Added new sync mapping: {mapping_name}")
                return True
            except Exception as e:
                error(f"Failed to add sync mapping '{mapping_name}': {e}")
                return False

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """
        Delete a sync mapping by removing it from the sync configuration.
        """
        # Get current configuration
        current_config = self._get_current_sync_config(token, base_url)
        if not current_config:
            error("Could not retrieve current sync configuration for deletion")
            return False

        current_mappings = current_config.get("mappings", [])

        # Find if mapping exists
        index, _ = self._find_mapping_by_name(current_mappings, item_id)

        if index < 0:
            warning(f"Sync mapping '{item_id}' not found; nothing to delete")
            return True

        # Remove the mapping
        updated_mappings = current_mappings[:index] + current_mappings[index + 1 :]
        updated_config = {**current_config, "mappings": updated_mappings}
        payload = json.dumps(updated_config)

        url = self.get_api_endpoint("", base_url)
        headers = get_headers("mappings")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, payload)
            info(f"Successfully deleted sync mapping: {item_id}")
            return True
        except Exception as e:
            error(f"Failed to delete sync mapping '{item_id}': {e}")
            return False

    def _load_mappings_file(self, file_path: str) -> Any:
        """Load mappings file with flexible format support"""
        import json
        import os

        # Convert to absolute path if relative
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read and parse JSON file
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Handle different file formats
        if isinstance(data, dict):
            # Check if it's an export file format
            if "data" in data:
                # Standard export format
                if "result" in data["data"]:
                    return data["data"]["result"]
                else:
                    return data["data"]
            else:
                # Raw sync config data
                return data
        elif isinstance(data, list):
            # Array of mappings
            return data
        else:
            raise ValueError("Invalid file format. Expected JSON object or array")

    def _convert_to_sync_format(self, data):
        """
        Convert keyed mappings format into IDM sync config format.
        """

        if not isinstance(data, dict):
            return data

        # Case 1 — keyed mappings inside data
        if "data" in data and isinstance(data["data"], dict):

            mappings = []

            for key, value in data["data"].items():
                if isinstance(value, dict):
                    mappings.append(value)

            return {"data": {"_id": "sync", "mappings": mappings}}

        return data

    def _normalize_mappings(self, data):
        """
        Normalize mappings input so importer always receives
        a list of mappings regardless of export format.
        """

        if isinstance(data, dict):

            # unwrap export wrapper
            if "data" in data:
                data = data["data"]

            # sync config format
            if isinstance(data, dict) and "mappings" in data:
                return data["mappings"]

            # keyed mappings format
            if isinstance(data, dict):
                return list(data.values())

        if isinstance(data, list):
            return data

        return []

    def load_data_from_file(self, file_path: str):
        """
        Ensure mappings importer receives individual mappings
        instead of the sync wrapper object.
        """

        import json

        with open(file_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # unwrap export structure
        data = raw.get("data", raw)

        # case 1 — sync export format
        if isinstance(data, dict) and "mappings" in data:
            return data["mappings"]

        # case 2 — keyed mapping format
        if isinstance(data, dict):
            return list(data.values())

        # case 3 — already list
        if isinstance(data, list):
            return data

        return []

    def load_data_from_git(self, git_manager, item_type, realm, branch):
        """Ensure mappings importer only processes individual mappings"""
        raw_items = self.file_loader.load_git_files(
            git_manager, item_type, realm, branch
        )

        normalized = []

        for item in raw_items:
            if isinstance(item, dict) and "mappings" in item:
                normalized.extend(item["mappings"])
            else:
                normalized.append(item)

        return normalized

    def _import_from_git(
        self, realm: str = "root", force_import: bool = False, branch: str = None
    ) -> List[Dict[str, Any]]:
        """
        Override Git loading to unwrap the IDM sync wrapper
        and return only individual mappings.
        """

        items = super()._import_from_git(realm, force_import, branch)

        normalized = []

        for item in items:
            if isinstance(item, dict) and item.get("_id") == "sync":
                normalized.extend(item.get("mappings", []))

            elif isinstance(item, dict) and "mappings" in item:
                normalized.extend(item["mappings"])

            else:
                normalized.append(item)

        return normalized

    def import_from_file(
        self,
        file_path: str = None,
        jwk_path: str = None,
        sa_id: str = None,
        base_url: str = None,
        project_name: str = None,
        auth_mode: str = None,
        onprem_username: str = None,
        onprem_password: str = None,
        onprem_realm: str = None,
        idm_base_url: str = None,
        idm_username: str = None,
        idm_password: str = None,
        am_base_url: str = None,
        force_import: bool = False,
        branch: str = None,
        diff: bool = False,
        cherry_pick: str = None,
        sync: bool = False,
        continue_on_error: bool = False,
        **kwargs,
    ) -> None:
        """Delegate to BaseImporter so sync/diff/rollback machinery runs correctly."""

        # For diff mode, adapt mappings to the shape expected by DiffEngine
        if diff:
            self._diff_adapter = self._wrap_for_diff

        # All modes (local, git, diff) go through super() so that
        # _handle_sync_deletions is invoked when sync=True.
        super().import_from_file(
            file_path=file_path,
            realm="root",
            src_realm=None,
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
            sync=sync,
            continue_on_error=continue_on_error,
            **kwargs,
        )


def create_mappings_import_command():
    """Create the mappings import command function"""

    def import_mappings(
        cherry_pick: CherryPickOpt = None,
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
        sync: SyncOpt = False,
        rollback: RollbackOpt = False,
        continue_on_error: ContinueOnErrorOpt = False,
    ):
        """Import sync mappings from JSON file (local mode) or Git repository (Git mode).

        Updates existing mappings by name (PATCH) or adds new ones (PUT).
        """
        importer = MappingsImporter()
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
            cherry_pick=cherry_pick,
            rollback=rollback,
            sync=sync,
            continue_on_error=continue_on_error,
        )

    return import_mappings
