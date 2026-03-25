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
    SyncOpt,
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

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/realm-config/agents/OAuth2Client/{item_id}",
        )

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
                info("Detected OAuth export format (standard) with clients and scripts")
                self._oauth_export_data = data_section

                new_scripts = data_section.get("scripts", [])
                if new_scripts:
                    self._pending_scripts.extend(new_scripts)

                clients = data_section.get("clients", [])

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
            if new_scripts:
                self._pending_scripts.extend(new_scripts)

            clients = data.get("clients", [])

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
    ) -> None:

        # Process scripts first (scripts intentionally not rolled back)
        if self._pending_scripts:
            info(f"Importing {len(self._pending_scripts)} script dependencies first...")

            self.script_importer.auth_mode = self.auth_mode

            self.script_importer.process_items(
                self._pending_scripts,
                token,
                base_url,
                rollback_manager=None,
                rollback_on_failure=False,
            )

            self._pending_scripts = []

        # Process OAuth clients normally with rollback
        super().process_items(
            items,
            token,
            base_url,
            rollback_manager=rollback_manager,
            rollback_on_failure=rollback_on_failure,
        )

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:

        item_id = item_data.get("_id")

        if not item_id:
            error("OAuth2 Client missing '_id'")
            return False

        url = self.get_api_endpoint(item_id, base_url)

        headers = get_headers("oauth")
        headers = {
            **headers,
            **self.build_auth_headers(token),
        }

        filtered_data = {k: v for k, v in item_data.items() if k not in {"_id", "_rev"}}

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
        cherry_pick: CherryPickOpt = None,
        sync: SyncOpt = False,
        diff: DiffOpt = False,
        file: InputFileOpt = None,
        force_import: ForceImportOpt = False,
        rollback: RollbackOpt = False,
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
    ):
        """Import OAuth2 Clients with script dependencies."""
        importer = OAuthImporter(realm=realm)
        importer.import_from_file(
            file_path=file,
            realm=realm,
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
            sync=sync,
            cherry_pick=cherry_pick,
        )

    return import_oauth
