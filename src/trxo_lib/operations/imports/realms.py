"""
Realm import commands.

Import functionality for AM realms (global-config/realms).
- If item has _id: PUT to /am/json/global-config/realms/{_id}
- Else: POST to /am/json/global-config/realms
Payload fields supported: name, active, parentPath, aliases
"""

import json
from typing import Any, Dict, List, Optional


from trxo_lib.config.api_headers import get_headers
from trxo_lib.utils.console import error, info

from trxo_lib.operations.imports.base_importer import BaseImporter

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



class RealmsImportService:
    """Service wrapper for realms import operations."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        importer = RealmImporter()

        # Typer passes 'file' which maps to 'file_path' in BaseImporter
        if 'file' in self.kwargs:
            self.kwargs['file_path'] = self.kwargs.pop('file')

        # Realms are global config, realm should be None for auth
        self.kwargs['realm'] = None

        return importer.import_from_file(**self.kwargs)
