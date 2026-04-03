"""
Authentication settings import command (authn).

Imports authentication settings to realm using PUT.
"""

import json
from typing import Any, Dict, List


from trxo_lib.config.api_headers import get_headers
from trxo_lib.constants import DEFAULT_REALM
from trxo_lib.utils.console import error, info

from trxo_lib.operations.imports.base_importer import BaseImporter


class AuthnImporter(BaseImporter):

    def __init__(self, realm: str = DEFAULT_REALM):
        super().__init__()
        self.realm = realm

    def get_required_fields(self) -> List[str]:
        return []

    def get_item_type(self) -> str:
        return "authn"

    def get_item_id(self, item: Dict[str, Any]) -> str:
        return "authn_settings"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/" "realm-config/authentication",
        )

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """PUT whole settings document after removing _rev"""

        filtered = {k: v for k, v in item_data.items() if k != "_rev"}
        payload = json.dumps(filtered)

        url = self.get_api_endpoint("", base_url)

        headers = get_headers("authn")

        headers = {**headers, **self.build_auth_headers(token)}

        try:
            response = self.make_http_request(url, "PUT", headers, payload)

            if hasattr(response, "status_code") and response.status_code >= 400:
                error(
                    f"Failed to update authentication settings: {response.status_code}"
                )
                return False

            info("Updated authentication settings")
            return True

        except Exception as e:
            error(f"Failed to update authentication settings: {e}")
            return False


class AuthnImportService:
    """Service wrapper for authn import operations."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        realm = self.kwargs.get("realm", DEFAULT_REALM)
        importer = AuthnImporter(realm=realm)

        # Typer passes 'file' which maps to 'file_path' in BaseImporter
        if "file" in self.kwargs:
            self.kwargs["file_path"] = self.kwargs.pop("file")

        return importer.import_from_file(**self.kwargs)
