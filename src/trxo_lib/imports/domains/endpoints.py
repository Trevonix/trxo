"""
Endpoints import command.

Import functionality for PingIDM custom endpoints.
- Uses PUT with _id in endpoint: /openidm/config/{_id}
- Keeps complete data as payload (no field removal)
- Works as upsert (create or update)
"""

import json
from typing import Any, Dict, List


from trxo_lib.config.api_headers import get_headers
from trxo_lib.logging import error, info

from trxo_lib.imports.processor import BaseImporter


class EndpointsImporter(BaseImporter):
    """Importer for PingIDM custom endpoints"""

    def __init__(self):
        super().__init__()
        self.product = "idm"

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "custom endpoints"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/openidm/config/{item_id}"

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Upsert custom endpoint using PUT"""
        item_id = item_data.get("_id")
        if not item_id:
            error("Endpoint missing '_id'; required for upsert")
            return False

        # Keep complete data as payload (no field removal as per requirement)
        payload = json.dumps(item_data)

        url = self.get_api_endpoint(item_id, base_url)
        headers = get_headers("endpoints")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, payload)
            info(f"Upserted custom endpoint: {item_id}")
            return True
        except Exception as e:
            error(f"Failed to upsert custom endpoint '{item_id}': {e}")
            return False

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete a custom endpoint via API"""
        url = self.get_api_endpoint(item_id, base_url)
        headers = get_headers("endpoints")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "DELETE", headers)
            info(f"Deleted custom endpoint: {item_id}")
            return True
        except Exception as e:
            error(f"Failed to delete custom endpoint '{item_id}': {e}")
            return False



class EndpointsImportService:
    """Service wrapper for endpoints import operations."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        importer = EndpointsImporter()

        # Typer passes 'file' which maps to 'file_path' in BaseImporter
        if 'file' in self.kwargs:
            self.kwargs['file_path'] = self.kwargs.pop('file')

        # Endpoints are root-level config, realm should be None
        self.kwargs['realm'] = None

        return importer.import_from_file(**self.kwargs)
