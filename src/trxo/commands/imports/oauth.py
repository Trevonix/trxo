"""
OAuth import commands.

This module provides import functionality for PingOne Advanced Identity Cloud OAuth2
clients with script dependencies.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer

from trxo.commands.shared.options import (
    AmBaseUrlOpt,
    AuthModeOpt,
    BaseUrlOpt,
    BranchOpt,
    CherryPickOpt,
    DiffOpt,
    DryRunOpt,
    ForceImportOpt,
    IdmBaseUrlOpt,
    IdmPasswordOpt,
    IdmUsernameOpt,
    InputFileOpt,
    JwkPathOpt,
    OnPremPasswordOpt,
    OnPremRealmOpt,
    OnPremUsernameOpt,
    ProjectNameOpt,
    RealmOpt,
    RollbackOpt,
    SaIdOpt,
    SrcRealmOpt,
    SyncOpt,
    ContinueOnErrorOpt,
)
from trxo.config.api_headers import get_headers
from trxo.constants import DEFAULT_REALM
from trxo.utils.console import error, info, warning

from .base_importer import BaseImporter
from .scripts import ScriptImporter


class OAuthImporter(BaseImporter):
    """Enhanced importer for PingOne Advanced Identity Cloud OAuth2 Clients with script dependencies"""

    def __init__(self, realm: str = DEFAULT_REALM):
        super().__init__()
        self.realm = realm
        self.script_importer = ScriptImporter(realm=realm)
        self._pending_scripts: List[Dict[str, Any]] = []
        self._oauth_export_data: Optional[Dict[str, Any]] = None

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "OAuth2_Clients"

    def get_item_id(self, item: Dict[str, Any]) -> Optional[str]:
        return item.get("_id")

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/realm-config/agents/OAuth2Client/{item_id}",
        )

    def get_provider_api_endpoint(self, base_url: str) -> str:
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/realm-config/oauth-oidc",
        )

    def get_provider_api_endpoints(self, base_url: str) -> List[str]:
        return []

    def _parse_oauth_data(self, data: Any) -> List[Dict[str, Any]]:
        """Helper to parse OAuth data structure from file content"""
        clients = []

        if isinstance(data, dict) and "data" in data:
            data_section = data["data"]

            if (
                isinstance(data_section, dict)
                and "clients" in data_section
                and "scripts" in data_section
            ):
                # Standard list format: {"clients": [...], "scripts": [...]}
                info("Detected OAuth export format (standard) with clients and scripts")
                self._oauth_export_data = data_section

                new_scripts = data_section.get("scripts", [])

                # Normalize scripts into list
                if isinstance(new_scripts, dict):
                    new_scripts = list(new_scripts.values())

                # Ensure it's a list
                if not isinstance(new_scripts, list):
                    new_scripts = []

                # Filter valid script objects
                valid_scripts = [
                    s for s in new_scripts if isinstance(s, dict) and s.get("_id")
                ]

                if valid_scripts:
                    info(f"Discovered {len(valid_scripts)} script(s) in export")
                    self._pending_scripts.extend(valid_scripts)

                clients = data_section.get("clients", [])
                if isinstance(clients, dict):
                    clients = list(clients.values())

            elif (
                isinstance(data_section, dict)
                and "data" in data_section
                and "scripts" in data_section
            ):
                # Nested dict format from git export:
                # data.data = {client_id: client_obj}, data.scripts = {script_id: script_obj}
                info("Detected OAuth export format (standard) with clients and scripts")
                inner_clients = data_section.get("data", {})
                inner_scripts = data_section.get("scripts", {})

                if isinstance(inner_clients, dict):
                    clients = list(inner_clients.values())
                elif isinstance(inner_clients, list):
                    clients = inner_clients

                if isinstance(inner_scripts, dict):
                    scripts_list = list(inner_scripts.values())
                elif isinstance(inner_scripts, list):
                    scripts_list = inner_scripts
                else:
                    scripts_list = []

                if scripts_list:
                    self._pending_scripts.extend(scripts_list)
                self._oauth_export_data = data_section

            elif isinstance(data_section, list):
                clients = data_section

            elif isinstance(data_section, dict) and "result" in data_section:
                clients = data_section.get("result", [])

            else:
                clients = [data_section]

        elif isinstance(data, dict) and "clients" in data and "scripts" in data:
            info("Detected OAuth export format (legacy) with clients and scripts")
            self._oauth_export_data = data

            new_scripts = data.get("scripts", [])
            if isinstance(new_scripts, dict):
                new_scripts = list(new_scripts.values())
            if new_scripts:
                self._pending_scripts.extend(new_scripts)

            clients = data.get("clients", [])
            if isinstance(clients, dict):
                clients = list(clients.values())

        else:
            if isinstance(data, list):
                clients = data
            else:
                clients = [data]

        return clients

    def _import_from_git(
        self, realm: Optional[str], force_import: bool, branch: Optional[str] = None
    ) -> List[Dict[str, Any]]:

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

        all_clients = []

        for file_path in discovered_files:
            try:
                info(f"Loading from: {file_path.relative_to(repo_path)}")

                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                parsed_clients = self._parse_oauth_data(data)
                all_clients.extend(parsed_clients)

            except Exception as e:
                warning(f"Failed to load {file_path.name}: {e}")
                continue

        return all_clients

    def _import_from_local(
        self, file_path: str, force_import: bool
    ) -> List[Dict[str, Any]]:

        import os

        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            raise typer.Exit(1)

        info(f"Loading OAuth2_Clients from local file: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            clients = self._parse_oauth_data(data)

            self._validate_items(clients)

            if not self.validate_import_hash(data, force_import):
                error("Import validation failed: Hash mismatch with exported data")
                raise typer.Exit(1)

            return clients

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to load OAuth2_Clients: {str(e)}")

    def process_items(
        self,
        items: List[Dict[str, Any]],
        token: str,
        base_url: str,
        rollback_manager: Optional[object] = None,
        rollback_on_failure: bool = False,
        continue_on_error: bool = False,
    ) -> None:

        # Process scripts first (scripts intentionally not rolled back)
        if self._pending_scripts:
            info(f"Importing {len(self._pending_scripts)} script dependencies first...")

            self.script_importer.auth_mode = self.auth_mode

            self.script_importer.rollback_manager = rollback_manager

            self.script_importer.process_items(
                self._pending_scripts,
                token,
                base_url,
                rollback_manager=rollback_manager,
                rollback_on_failure=rollback_on_failure,
                continue_on_error=continue_on_error,
            )
        if rollback_manager and isinstance(rollback_manager.baseline_snapshot, dict):
            if "data" in rollback_manager.baseline_snapshot:
                flattened = {}
                flattened.update(rollback_manager.baseline_snapshot.get("data", {}))
                flattened["scripts"] = rollback_manager.baseline_snapshot.get(
                    "scripts", {}
                )
                rollback_manager.baseline_snapshot = flattened
            self._pending_scripts = []

        # Process OAuth clients normally with rollback
        super().process_items(
            items,
            token,
            base_url,
            rollback_manager=rollback_manager,
            rollback_on_failure=rollback_on_failure,
            continue_on_error=continue_on_error,
        )

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:

        item_id = item_data.get("_id")

        if not item_id:
            print(
                f"DEBUG oauth update_item: no _id found. Keys={list(item_data.keys())[:10]}"
            )
            error("OAuth2 Client missing '_id'")
            return False

        url = self.get_api_endpoint(item_id, base_url)

        headers = get_headers("oauth")
        headers = {
            **headers,
            **self.build_auth_headers(token),
        }

        filtered_data = {
            k: v for k, v in item_data.items() if k not in {"_id", "_rev", "_provider"}
        }

        payload = json.dumps(filtered_data, indent=2)

        try:
            response = self.make_http_request(url, "PUT", headers, payload)

            if hasattr(response, "status_code") and response.status_code >= 400:
                raise Exception(
                    f"Failed to process OAuth2 Client '{item_id}': {response.status_code}"
                )

            info(f"Successfully processed OAuth2 Client: {item_id}")
            return True

        except Exception as e:
            error(f"Failed to process OAuth2 Client '{item_id}': {e}")
            raise

    def update_provider(
        self, provider_data: Dict[str, Any], token: str, base_url: str
    ) -> bool:
        """Upsert OAuth/OIDC provider config."""
        if not isinstance(provider_data, dict):
            error("OAuth2 Provider payload must be an object")
            return False

        headers = get_headers("oauth")
        headers = {**headers, **self.build_auth_headers(token)}

        filtered_data = {
            k: v for k, v in provider_data.items() if k not in {"_id", "_rev"}
        }
        payload = json.dumps(filtered_data, indent=2)

        # Discover OAuth/OIDC-like service IDs and only target those endpoints.
        dynamic_urls: List[str] = []
        try:
            list_url = self._construct_api_url(
                base_url,
                f"/am/json/realms/root/realms/{self.realm}/realm-config/services?_queryFilter=true",
            )
            list_response = self.make_http_request(list_url, "GET", headers)
            list_data = list_response.json()
            if isinstance(list_data, dict) and isinstance(
                list_data.get("result"), list
            ):
                for item in list_data["result"]:
                    if not isinstance(item, dict):
                        continue
                    sid = item.get("_id")
                    if not isinstance(sid, str):
                        continue
                    lower = sid.lower()
                    if "oauth" in lower or "oidc" in lower or "openid" in lower:
                        dynamic_urls.append(
                            self._construct_api_url(
                                base_url,
                                f"/am/json/realms/root/realms/{self.realm}/realm-config/services/{sid}",
                            )
                        )
        except Exception:
            pass

        if not dynamic_urls:
            warning(
                "No OAuth/OIDC provider service endpoint discovered in realm services; "
                "skipping provider import."
            )
            return True

        last_error = ""
        tried = set()
        for url in [*self.get_provider_api_endpoints(base_url), *dynamic_urls]:
            if url in tried:
                continue
            tried.add(url)
            try:
                response = self.make_http_request(url, "PUT", headers, payload)
                if hasattr(response, "status_code") and response.status_code >= 400:
                    raise Exception(
                        "Failed to process OAuth2 Provider: " f"{response.status_code}"
                    )
                info("Successfully processed OAuth2 Provider configuration")
                return True
            except Exception as e:
                last_error = str(e)
                continue

        error(
            "Failed to process OAuth2 Provider using known endpoints"
            + (f": {last_error}" if last_error else "")
        )
        raise Exception(last_error or "Unknown provider import error")

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete a single OAuth2 Client via API"""
        url = self.get_api_endpoint(item_id, base_url)

        headers = get_headers("oauth")
        headers = {
            **headers,
            **self.build_auth_headers(token),
        }

        try:
            self.make_http_request(url, "DELETE", headers)
            info(f"Successfully deleted OAuth2 Client: {item_id}")
            return True
        except Exception as e:
            error(f"Failed to delete OAuth2 Client '{item_id}': {e}")
            return False


def create_oauth_import_command():
    """Create the OAuth import command function"""

    def import_oauth(
        realm: RealmOpt = DEFAULT_REALM,
        src_realm: SrcRealmOpt = None,
        cherry_pick: CherryPickOpt = None,
        sync: SyncOpt = False,
        diff: DiffOpt = False,
        file: InputFileOpt = None,
        force_import: ForceImportOpt = False,
        rollback: RollbackOpt = False,
        continue_on_error: ContinueOnErrorOpt = False,
        branch: BranchOpt = None,
        jwk_path: JwkPathOpt = None,
        sa_id: SaIdOpt = None,
        base_url: BaseUrlOpt = None,
        project_name: ProjectNameOpt = None,
        auth_mode: AuthModeOpt = None,
        onprem_username: OnPremUsernameOpt = None,
        onprem_password: OnPremPasswordOpt = None,
        onprem_realm: OnPremRealmOpt = "root",
        am_base_url: AmBaseUrlOpt = None,
        idm_base_url: IdmBaseUrlOpt = None,
        idm_username: IdmUsernameOpt = None,
        idm_password: IdmPasswordOpt = None,
        dry_run: DryRunOpt = False,
    ):
        """Import OAuth2 Clients with script dependencies."""
        importer = OAuthImporter(realm=realm)
        importer.import_from_file(
            file_path=file,
            realm=realm,
            src_realm=src_realm,
            jwk_path=jwk_path,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            idm_base_url=idm_base_url,
            idm_username=idm_username,
            idm_password=idm_password,
            am_base_url=am_base_url,
            force_import=force_import,
            branch=branch,
            diff=diff,
            rollback=rollback,
            continue_on_error=continue_on_error,
            sync=sync,
            cherry_pick=cherry_pick,
            dry_run=dry_run,
        )

    return import_oauth
