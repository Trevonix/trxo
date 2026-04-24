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
from trxo_lib.config.constants import DEFAULT_REALM
from trxo_lib.logging import error, info

from trxo_lib.imports.processor import BaseImporter


class PoliciesImporter(BaseImporter):
    """Importer for PingOne Advanced Identity Cloud policies"""

    def __init__(self, realm: str = DEFAULT_REALM, global_policies: bool = False):
        super().__init__()
        self.realm = realm
        self.global_policies = global_policies

    def load_data_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Load data from file and handle the split am/global structure."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                full_data = json.load(f)

            data_block = full_data.get("data", {})
            am_items = data_block.get("am", [])
            
            # If it's an old format file, fallback to 'result' or root list
            if not am_items and isinstance(data_block, dict):
                am_items = data_block.get("result", [])
            if not am_items and isinstance(data_block, list):
                am_items = data_block

            # Mark AM items
            for item in am_items:
                if isinstance(item, dict):
                    item["__product__"] = "am"
            
            final_items = am_items

            # Load global policies if requested
            if self.global_policies:
                global_items = data_block.get("global", [])
                for item in global_items:
                    if isinstance(item, dict):
                        item["__product__"] = "idm"
                final_items += global_items
            
            return final_items
        except Exception as e:
            error(f"Failed to load policies from file: {e}")
            return []

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return f"policies ({self.realm})"

    def get_item_id(self, item: Dict[str, Any]) -> Optional[str]:
        return item.get("_id")

    def get_api_endpoint(
        self, item_id: str, base_url: str, is_policy_set: bool = False, product: str = "am"
    ) -> str:
        if product == "idm":
            return self._construct_api_url(
                base_url,
                f"/openidm/config/{item_id}",
            )
            
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
        """Upsert policy using PUT"""
        # Create a copy so we don't pollute the actual data with our marker
        item = item_data.copy()
        product = item.pop("__product__", "am")
        
        item_id = item.get("_id")
        if not item_id:
            error("Item missing '_id'; required for upsert")
            return False

        # Determine target base URL (IDM might have its own base URL in onprem mode)
        target_base_url = base_url
        if product == "idm" and hasattr(self, "_idm_base_url") and self._idm_base_url:
            target_base_url = self._idm_base_url

        # Policy Sets don't have "applicationName" indicating an owner
        is_policy_set = "applicationName" not in item and product == "am"

        # Keep complete data as payload
        payload = json.dumps(item)

        url = self.get_api_endpoint(item_id, target_base_url, is_policy_set, product)
        
        # Determine headers based on product
        if product == "idm":
            # Some IDM versions are picky about version headers on /config
            headers = get_headers("default")
        else:
            headers = get_headers("policy_sets" if is_policy_set else "policies")
            
        headers = {**headers, **self.build_auth_headers(token, product=product)}

        try:
            self.make_http_request(url, "PUT", headers, payload)
            item_type = "policy set" if is_policy_set else "policy"
            if product == "idm":
                item_type = f"global {item_type}"
            info(f"Upserted {item_type} ({self.realm if product == 'am' else 'global'}): {item_id}")
            return True
        except Exception as e:
            item_type = "policy set" if is_policy_set else "policy"
            dest = f"realm '{self.realm}'" if product == "am" else "global config"
            error(
                f"Failed to upsert {item_type} '{item_id}' in {dest}: {e}"
            )
            return False

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete a single policy via API (used for sync)"""
        if item_id.startswith("fieldPolicy/") or item_id == "policy":
            products_to_try = [("idm", False), ("am", False), ("am", True)]
        else:
            products_to_try = [("am", False), ("am", True), ("idm", False)]

        for product, is_policy_set in products_to_try:
            target_base_url = base_url
            if product == "idm" and hasattr(self, "_idm_base_url") and self._idm_base_url:
                target_base_url = self._idm_base_url

            url = self.get_api_endpoint(item_id, target_base_url, is_policy_set, product)
            headers = get_headers("default" if product == "idm" else ("policy_sets" if is_policy_set else "policies"))
            headers = {**headers, **self.build_auth_headers(token, product=product)}

            try:
                self.make_http_request(url, "DELETE", headers)
                info(f"Successfully deleted {product} {item_id}")
                return True
            except Exception:
                continue
                
        error(f"Failed to delete '{item_id}' in realm '{self.realm}' or global config")
        return False


from typing import Any

class PoliciesImportService:
    """Service wrapper for policies import operations."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        from trxo_lib.config.constants import DEFAULT_REALM
        realm = self.kwargs.get('realm', DEFAULT_REALM)
        global_policies = self.kwargs.get('global_policies', False)
        
        importer = PoliciesImporter(realm=realm, global_policies=global_policies)

        # Typer passes 'file' which maps to 'file_path' in BaseImporter
        if 'file' in self.kwargs:
            self.kwargs['file_path'] = self.kwargs.pop('file')

        # Filter out global_policies from kwargs as BaseImporter doesn't expect it in its signature
        safe_kwargs = self.kwargs.copy()
        safe_kwargs.pop('global_policies', None)

        return importer.import_from_file(**safe_kwargs)
