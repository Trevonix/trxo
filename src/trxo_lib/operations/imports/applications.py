"""
Applications import command.

Import functionality for PingOne Advanced Identity Cloud Applications.
"""

from trxo_lib.exceptions import TrxoAbort
import copy
import json
import os
from typing import Any, Dict, List, Optional


from trxo_lib.operations.imports.oauth import OAuthImporter
from trxo_lib.operations.imports.scripts import ScriptImporter
from trxo_lib.config.api_headers import get_headers
from trxo_lib.constants import DEFAULT_REALM
from trxo_lib.utils.console import error, info, warning

from trxo_lib.operations.imports.base_importer import BaseImporter


def _normalize_dep_block(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict) and x.get("_id")]
    if isinstance(value, dict):
        return [x for x in value.values() if isinstance(x, dict) and x.get("_id")]
    return []


def _normalize_provider_block(value: Any) -> List[Dict[str, Any]]:
    """Normalize provider dependency blocks into a provider list."""
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        if "_type" in value or "coreOAuth2Config" in value or "pluginsConfig" in value:
            return [value]
        return [x for x in value.values() if isinstance(x, dict)]
    return []


class ApplicationsImporter(BaseImporter):
    """Importer for PingOne Advanced Identity Cloud Applications"""

    def __init__(self, realm: str = DEFAULT_REALM):
        super().__init__()
        self.realm = realm
        self.product = "idm"
        self.include_am_dependencies: bool = False
        self._pending_clients: List[Dict[str, Any]] = []
        self._pending_scripts: List[Dict[str, Any]] = []
        self._pending_providers: List[Dict[str, Any]] = []

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "Applications"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/openidm/managed/{self.realm}_application/{item_id}"

    def load_data_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Load applications; optionally pick up clients/scripts from the same export."""
        path = os.path.abspath(file_path) if not os.path.isabs(file_path) else file_path

        with open(path, encoding="utf-8") as f:
            raw = json.load(f)

        data = raw.get("data") if isinstance(raw, dict) else raw

        if self.include_am_dependencies and isinstance(data, dict):
            new_clients = _normalize_dep_block(data.get("clients"))
            self._pending_clients.extend(new_clients)
            self._pending_scripts.extend(_normalize_dep_block(data.get("scripts")))
            self._pending_providers.extend(
                _normalize_provider_block(data.get("providers") or data.get("provider"))
            )

            # Frodo format compatibility: extract provider from each client._provider
            for client in new_clients:
                provider = client.get("_provider")
                if isinstance(provider, dict):
                    self._pending_providers.append(provider)

            # De-duplicate provider payloads while preserving order
            unique_providers: List[Dict[str, Any]] = []
            seen_provider_keys: set[str] = set()
            for provider in self._pending_providers:
                key = (
                    provider.get("_id")
                    or (
                        provider.get("_type", {}).get("_id")
                        if isinstance(provider.get("_type"), dict)
                        else ""
                    )
                    or json.dumps(provider, sort_keys=True, default=str)
                )
                if key in seen_provider_keys:
                    continue
                seen_provider_keys.add(key)
                unique_providers.append(provider)
            self._pending_providers = unique_providers

        # Parse local vs backwards compatible data formats without FileLoader
        if isinstance(raw, dict) and "data" in raw:
            inner = raw["data"]
            if isinstance(inner, dict):
                if "applications" in inner:
                    items = inner["applications"]
                    return items if isinstance(items, list) else [items]
                elif "result" in inner:
                    items = inner["result"]
                    return items if isinstance(items, list) else [items]
            return [inner] if inner else []

        if isinstance(raw, dict):
            return [raw]
        elif isinstance(raw, list):
            return raw
        return []

    def _import_from_local(
        self, file_path: str, force_import: bool
    ) -> List[Dict[str, Any]]:
        """Intercept local import to reset pending dependencies."""
        self._pending_clients = []
        self._pending_scripts = []
        self._pending_providers = []
        return super()._import_from_local(file_path, force_import)

    def _import_from_git(
        self, realm: Optional[str], force_import: bool, branch: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Intercept git import to use applications loader directly over all discovered files."""
        self._pending_clients = []
        self._pending_scripts = []
        self._pending_providers = []

        from pathlib import Path

        item_type = self.get_item_type()
        effective_realm = self._determine_effective_realm(realm, item_type, branch)
        git_manager = self._setup_git_manager(branch)
        repo_path = Path(git_manager.local_path)

        discovered_files = self.file_loader.discover_git_files(
            repo_path, item_type, effective_realm
        )

        if not discovered_files:
            self._handle_no_git_files_found(item_type, effective_realm, realm)
            return []

        all_items = []
        for file_path in discovered_files:
            try:
                info(f"Loading from: {file_path.relative_to(repo_path)}")
                items = self.load_data_from_file(str(file_path))
                all_items.extend(items)
            except Exception as e:
                warning(f"Failed to load {file_path.name}: {e}")
                continue

        if (
            self.include_am_dependencies
            and not self._pending_clients
            and not self._pending_scripts
        ):
            warning(
                "No OAuth2 clients or scripts found in Git payload; "
                "importing applications only."
            )

        normalized_items = []
        for item in all_items:
            if not isinstance(item, dict) or self._get_item_identifier(item) is None:
                continue
            normalized_items.append(item)

        return normalized_items

    def process_items(
        self,
        items: List[Dict[str, Any]],
        token: str,
        base_url: str,
        rollback_manager: Optional[object] = None,
        rollback_on_failure: bool = False,
    ) -> None:
        extra_ok = 0
        extra_fail = 0

        if self.include_am_dependencies and self._pending_scripts:
            info(
                f"Importing {len(self._pending_scripts)} script dependency(ies) "
                "before applications..."
            )
            script_imp = ScriptImporter(realm=self.realm)
            script_imp.auth_mode = self.auth_mode
            script_imp.process_items(
                self._pending_scripts,
                token,
                base_url,
                rollback_manager=rollback_manager,
                rollback_on_failure=rollback_on_failure,
            )
            extra_ok += script_imp.successful_updates
            extra_fail += script_imp.failed_updates

        if self.include_am_dependencies and self._pending_providers:
            info(
                f"Importing {len(self._pending_providers)} OAuth2 provider "
                "dependency(ies) before OAuth2 clients..."
            )
            oauth_imp = OAuthImporter(realm=self.realm)
            oauth_imp.auth_mode = self.auth_mode
            for provider in self._pending_providers:
                pid = (
                    provider.get("_id") if isinstance(provider, dict) else "<provider>"
                )
                try:
                    oauth_imp.update_provider(provider, token, base_url)
                    extra_ok += 1
                except TrxoAbort:
                    raise
                except Exception:
                    extra_fail += 1
                    if rollback_on_failure and rollback_manager:
                        self._execute_rollback_and_exit(
                            rollback_manager, token, base_url, pid
                        )
                    raise TrxoAbort(code=1)

        if self.include_am_dependencies and self._pending_clients:
            info(
                f"Importing {len(self._pending_clients)} OAuth2 client dependency(ies) "
                "before applications..."
            )
            oauth_imp = OAuthImporter(realm=self.realm)
            oauth_imp.auth_mode = self.auth_mode
            for client in self._pending_clients:
                client_payload = copy.deepcopy(client)
                cid = client_payload.get("_id")
                client_payload.pop("_provider", None)
                try:
                    oauth_imp.update_item(client_payload, token, base_url)
                    extra_ok += 1
                except TrxoAbort:
                    raise
                except Exception:
                    extra_fail += 1
                    if rollback_on_failure and rollback_manager:
                        self._execute_rollback_and_exit(
                            rollback_manager, token, base_url, cid
                        )
                    raise TrxoAbort(code=1)

        super().process_items(
            items,
            token,
            base_url,
            rollback_manager=rollback_manager,
            rollback_on_failure=rollback_on_failure,
        )
        self.successful_updates += extra_ok
        self.failed_updates += extra_fail

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Upsert application using PUT"""
        item_id = item_data.get("_id")
        if not item_id:
            error("application missing '_id'; required for upsert")
            return False

        # Keep complete data as payload (no field removal as per requirement)
        payload = json.dumps(item_data)

        url = self.get_api_endpoint(item_id, base_url)
        headers = get_headers("applications")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, payload)
            info(f"Upserted application: {item_id}")
            return True
        except Exception as e:
            error(f"Failed to upsert application '{item_id}': {e}")
            return False

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete an Application via API"""
        url = self.get_api_endpoint(item_id, base_url)
        headers = get_headers("applications")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "DELETE", headers)
            info(f"Deleted application: {item_id}")
            return True
        except Exception as e:
            error(f"Failed to delete application '{item_id}': {e}")
            return False


class ApplicationsImportService:
    """Service wrapper for application import operations."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        realm = self.kwargs.get("realm", DEFAULT_REALM)
        importer = ApplicationsImporter(realm=realm)
        importer.include_am_dependencies = self.kwargs.get("with_deps", False)

        # Typer passes 'file' which maps to 'file_path' in BaseImporter
        if "file" in self.kwargs:
            self.kwargs["file_path"] = self.kwargs.pop("file")

        return importer.import_from_file(**self.kwargs)
