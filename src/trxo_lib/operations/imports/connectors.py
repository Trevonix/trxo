"""
IDM Connectors import command.

Import functionality for PingIDM connectors.
- Uses PUT with _id in endpoint: /openidm/config/{_id}
- Keeps complete data as payload (no field removal)
- Works as upsert (create or update) based on _id
"""

import json
from typing import Any, Dict, List, Optional


from trxo_lib.config.api_headers import get_headers
from trxo_lib.utils.console import error, success

from trxo_lib.operations.imports.base_importer import BaseImporter


class ConnectorsImporter(BaseImporter):
    """Importer for PingIDM connectors"""

    def __init__(self):
        super().__init__()
        self.product = "idm"

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "connectors"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/openidm/config/{item_id}"

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete a connector using DELETE /openidm/config/{item_id}"""
        url = self.get_api_endpoint(item_id, base_url)
        headers = get_headers("connectors")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "DELETE", headers)
            return True
        except Exception as e:
            error(f"Failed to delete connector '{item_id}': {e}")
            return False

    def load_data_from_git(self, git_manager, item_type, realm, branch):
        """
        Normalize connectors export format when loading from Git.
        """

        raw_items = self.file_loader.load_git_files(
            git_manager, item_type, realm, branch
        )

        normalized = []

        for item in raw_items:

            # unwrap export wrapper
            if isinstance(item, dict) and "data" in item:
                data = item["data"]

                if isinstance(data, dict) and "result" in data:
                    normalized.extend(data["result"])
                    continue

            # already list
            if isinstance(item, list):
                normalized.extend(item)
                continue

            # already connector dict
            if isinstance(item, dict) and "_id" in item:
                normalized.append(item)

        return normalized

    def load_data_from_file(self, file_path: str):

        with open(file_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        data = raw.get("data", raw)

        # Correct TRXO export format
        if isinstance(data, dict) and "result" in data:
            return data["result"]

        # fallback
        if isinstance(data, list):
            return data

        return []

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:

        item_id = item_data["_id"]
        url = self.get_api_endpoint(item_id, base_url)

        payload = item_data.copy()
        payload.pop("_rev", None)
        payload.pop("_type", None)

        headers = get_headers("connectors")

        headers.update(self.build_auth_headers(token))

        import httpx

        try:
            with httpx.Client(timeout=60) as client:
                resp = client.put(url, headers=headers, json=payload)

            if resp.status_code in (200, 201, 204):
                success(f"Successfully upserted connector: {item_id}")
                return True

            error(
                f"Failed to upsert connector '{item_id}': "
                f"{resp.status_code} - {resp.text}"
            )
            return False

        except Exception as e:
            error(f"Connector import error for '{item_id}': {str(e)}")
            return False

    def _import_from_git(
        self, realm: Optional[str], force_import: bool, branch: Optional[str] = None
    ) -> List[Dict[str, Any]]:

        item_type = self.get_item_type()

        effective_realm = self._determine_effective_realm(realm, item_type, branch)

        git_manager = self._setup_git_manager(branch)

        raw_items = self.file_loader.load_git_files(
            git_manager, item_type, effective_realm, branch
        )

        normalized = []

        for item in raw_items:

            if isinstance(item, dict) and "data" in item:
                data = item["data"]

                if isinstance(data, dict) and "result" in data:
                    normalized.extend(data["result"])
                    continue

            if isinstance(item, list):
                normalized.extend(item)
                continue

            if isinstance(item, dict) and "_id" in item:
                normalized.append(item)

        if not normalized:
            self._handle_no_git_files_found(item_type, effective_realm, realm)
            return []

        return normalized



class ConnectorsImportService:
    """Service wrapper for connectors import operations."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        importer = ConnectorsImporter()

        # Typer passes 'file' which maps to 'file_path' in BaseImporter
        if 'file' in self.kwargs:
            self.kwargs['file_path'] = self.kwargs.pop('file')

        # Connectors are root-level config, realm should be None
        self.kwargs['realm'] = None

        return importer.import_from_file(**self.kwargs)
