"""
Applications import command.

Import functionality for PingOne Advanced Identity Cloud Applications.
"""

import json
import os
from typing import Any, Dict, List, Optional

import typer

from trxo.commands.imports.oauth import OAuthImporter
from trxo.commands.imports.scripts import ScriptImporter
from trxo.commands.shared.options import (
    AmBaseUrlOpt,
    AuthModeOpt,
    BaseUrlOpt,
    BranchOpt,
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
    WithDepsOpt,
)
from trxo.config.api_headers import get_headers
from trxo.constants import DEFAULT_REALM
from trxo.utils.console import error, info, warning
from trxo.utils.imports.file_loader import FileLoader

from .base_importer import BaseImporter


def _normalize_dep_block(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict) and x.get("_id")]
    if isinstance(value, dict):
        return [x for x in value.values() if isinstance(x, dict) and x.get("_id")]
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

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "Applications"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/openidm/managed/{self.realm}_application/{item_id}"

    def load_data_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Load applications; optionally pick up clients/scripts from the same export."""
        self._pending_clients = []
        self._pending_scripts = []

        path = os.path.abspath(file_path) if not os.path.isabs(file_path) else file_path

        if self.include_am_dependencies:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            data = raw.get("data") if isinstance(raw, dict) else None
            if isinstance(data, dict):
                self._pending_clients = _normalize_dep_block(data.get("clients"))
                self._pending_scripts = _normalize_dep_block(data.get("scripts"))
            if self.include_am_dependencies and not self._pending_clients and not self._pending_scripts:
                warning(
                    "No OAuth2 clients or scripts found under data.clients / data.scripts; "
                    "importing applications only."
                )

        return FileLoader.load_from_local_file(file_path)

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

        if self.include_am_dependencies and self._pending_clients:
            info(
                f"Importing {len(self._pending_clients)} OAuth2 client dependency(ies) "
                "before applications..."
            )
            oauth_imp = OAuthImporter(realm=self.realm)
            oauth_imp.auth_mode = self.auth_mode
            for client in self._pending_clients:
                cid = client.get("_id")
                try:
                    oauth_imp.update_item(client, token, base_url)
                    extra_ok += 1
                except typer.Exit:
                    raise
                except Exception:
                    extra_fail += 1
                    if rollback_on_failure and rollback_manager:
                        self._execute_rollback_and_exit(
                            rollback_manager, token, base_url, cid
                        )
                    raise typer.Exit(1)

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


def create_applications_import_command():
    """Create the Applications import command function"""

    def import_applications(
        file: InputFileOpt = None,
        realm: RealmOpt = DEFAULT_REALM,
        force_import: ForceImportOpt = False,
        diff: DiffOpt = False,
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
        with_deps: WithDepsOpt = False,
    ):
        """Import applications from file or Git repository."""
        importer = ApplicationsImporter(realm=realm)
        importer.include_am_dependencies = with_deps
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
        )

    return import_applications
