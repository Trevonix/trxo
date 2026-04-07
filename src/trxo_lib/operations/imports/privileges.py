"""
Privileges import command.

Import functionality for PingIDM Privileges.
- Uses PUT with _id in Privilege: /openidm/config/{_id}
- Keeps complete data as payload (no field removal)
- Works as upsert (create or update)
"""

import json
from typing import Any, Dict, List


from trxo_lib.config.api_headers import get_headers
from trxo.utils.console import error, info

from trxo_lib.operations.imports.base_importer import BaseImporter


class PrivilegesImporter(BaseImporter):
    """Importer for PingIDM Privileges"""

    def __init__(self):
        super().__init__()
        self.product = "idm"

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "Privileges"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/openidm/config/{item_id}"

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete a Privilege using DELETE /openidm/config/{item_id}"""
        url = self.get_api_endpoint(item_id, base_url)
        headers = get_headers("privileges")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "DELETE", headers)
            return True
        except Exception as e:
            error(f"Failed to delete Privilege '{item_id}': {e}")
            return False

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Upsert Privilege using PUT"""
        item_id = item_data.get("_id")
        if not item_id:
            error("Privilege missing '_id'; required for upsert")
            return False

        # Keep complete data as payload (no field removal as per requirement)
        payload = json.dumps(item_data)

        url = self.get_api_endpoint(item_id, base_url)
        headers = get_headers("privileges")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, payload)
            info(f"Upserted Privilege: {item_id}")
            return True
        except Exception as e:
            error(f"Failed to upsert Privilege '{item_id}': {e}")
            return False



class PrivilegesImportService:
    """Service wrapper for privileges import operations."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        importer = PrivilegesImporter()

        # Typer passes 'file' which maps to 'file_path' in BaseImporter
        if 'file' in self.kwargs:
            self.kwargs['file_path'] = self.kwargs.pop('file')

        # Privileges are root-level config in IDM
        self.kwargs['realm'] = None

        return importer.import_from_file(**self.kwargs)
