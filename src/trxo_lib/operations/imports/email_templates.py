"""
Email templates import command.

Import functionality for PingIDM Email Templates.
- Uses PUT with _id in endpoint: /openidm/config/{_id}
- Keeps complete data as payload (no field removal)
- Works as upsert (create or update)
"""

import json
from typing import Any, Dict, List

from trxo_lib.config.api_headers import get_headers
from trxo_lib.utils.console import error, info

from trxo_lib.operations.imports.base_importer import BaseImporter


class EmailTemplatesImporter(BaseImporter):
    """Importer for PingIDM Email Templates"""

    def __init__(self):
        super().__init__()
        self.product = "idm"

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "Email Templates"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/openidm/config/{item_id}"

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Upsert Email Template using PUT"""

        item_id = item_data.get("_id")

        if not item_id:
            error("Email template missing '_id'; required for upsert")
            return False

        payload = json.dumps(item_data)

        url = self.get_api_endpoint(item_id, base_url)

        headers = get_headers("email_templates")

        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, payload)
            info(f"Upserted Email Template: {item_id}")
            return True

        except Exception as e:
            error(f"Failed to upsert Email Template '{item_id}': {e}")
            return False

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete an Email Template via API"""
        url = self.get_api_endpoint(item_id, base_url)
        headers = get_headers("email_templates")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "DELETE", headers)
            info(f"Deleted Email Template: {item_id}")
            return True
        except Exception as e:
            error(f"Failed to delete Email Template '{item_id}': {e}")
            return False

