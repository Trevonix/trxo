"""
Webhooks import command.

Imports AM realm webhooks with PUT upsert.
Endpoint: /am/json/realms/root/realms/{realm}/realm-config/webhooks/{_id}
- Removes _rev from payload before sending
- Uses PUT for upsert (create/update)
"""

import json
from typing import Any, Dict, List, Optional


from trxo_lib.config.api_headers import get_headers
from trxo_lib.constants import DEFAULT_REALM
from trxo_lib.utils.console import error, info

from trxo_lib.operations.imports.base_importer import BaseImporter


class WebhooksImporter(BaseImporter):
    """Importer for AM webhooks"""

    def __init__(self, realm: str = DEFAULT_REALM):
        super().__init__()
        self.realm = realm

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "webhooks"

    def get_item_id(self, item: Dict[str, Any]) -> str:
        return item.get("_id")

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/"
            f"realm-config/webhooks/{item_id}",
        )

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        item_id = item_data.get("_id")
        if not item_id:
            error("Webhook missing '_id'; required for upsert")
            return False

        payload_obj = dict(item_data)
        payload_obj.pop("_rev", None)
        payload = json.dumps(payload_obj)

        url = self.get_api_endpoint(item_id, base_url)

        headers = get_headers("webhooks")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            response = self.make_http_request(url, "PUT", headers, payload)

            if response.status_code == 201:
                info(f"Created webhook ({self.realm}): {item_id}")
            else:
                info(f"Updated webhook ({self.realm}): {item_id}")

            return True

        except Exception as e:
            error(
                f"Failed to upsert webhook '{item_id}' in realm " f"'{self.realm}': {e}"
            )
            return False

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete a single Webhook via API"""
        url = self.get_api_endpoint(item_id, base_url)
        headers = get_headers("webhooks")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "DELETE", headers)
            info(f"Successfully deleted Webhook: {item_id}")
            return True
        except Exception as e:
            error(f"Failed to delete Webhook '{item_id}': {e}")
            return False

