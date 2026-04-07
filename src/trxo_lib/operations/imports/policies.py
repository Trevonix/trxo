"""
Policies import command.

Import functionality for PingOne Advanced Identity Cloud policies.
- Uses PUT with _id in endpoint: /am/json/realms/root/realms/{realm}/policies/{_id}
- Keeps complete data as payload (no field removal)
- Works as upsert (create or update)
"""

import json
from typing import Any, Dict, List, Optional

from trxo_lib.config.api_headers import get_headers
from trxo_lib.constants import DEFAULT_REALM
from trxo.utils.console import error, info

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



from typing import Any

class PoliciesImportService:
    """Service wrapper for policies import operations."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        from trxo_lib.constants import DEFAULT_REALM
        realm = self.kwargs.get('realm', DEFAULT_REALM)
        importer = PoliciesImporter(realm=realm)

        # Typer passes 'file' which maps to 'file_path' in BaseImporter
        if 'file' in self.kwargs:
            self.kwargs['file_path'] = self.kwargs.pop('file')

        return importer.import_from_file(**self.kwargs)
