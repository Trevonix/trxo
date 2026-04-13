"""
Applications import command.

Import functionality for PingOne Advanced Identity Cloud Applications.
"""

import copy
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
    CherryPickOpt,
    ContinueOnErrorOpt,
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
    WithDepsOpt,
    ContinueOnErrorOpt,
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


def _normalize_provider_block(value: Any) -> List[Dict[str, Any]]:
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

    def _reset_dependencies(self):
        """Ensure clean state before every import"""
        self._pending_clients = []
        self._pending_scripts = []
        self._pending_providers = []

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "Applications"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/openidm/managed/{self.realm}_application/{item_id}"

    def load_data_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        self._reset_dependencies()

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

            # Extract provider from client._provider
            for client in new_clients:
                provider = client.get("_provider")
                if isinstance(provider, dict):
                    self._pending_providers.append(provider)

            # Deduplicate providers
            unique_providers = []
            seen_provider_keys = set()

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

            if (
                not self._pending_clients
                and not self._pending_scripts
                and not self._pending_providers
            ):
                warning(
                    "No OAuth2 clients, scripts, or providers found; importing applications only."
                )

        # Handle multiple formats
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

    def process_items(
        self,
        items: List[Dict[str, Any]],
        token: str,
        base_url: str,
        rollback_manager: Optional[object] = None,
        rollback_on_failure: bool = False,
        continue_on_error: bool = False,
    ) -> None:
        extra_ok = 0
        extra_fail = 0

        if self.include_am_dependencies and self._pending_scripts:
            info(f"Importing {len(self._pending_scripts)} script dependencies...")
            script_imp = ScriptImporter(realm=self.realm)
            script_imp.auth_mode = self.auth_mode
            script_imp.process_items(
                self._pending_scripts,
                token,
                base_url,
                rollback_manager=rollback_manager,
                rollback_on_failure=rollback_on_failure,
                continue_on_error=continue_on_error,
            )
            extra_ok += script_imp.successful_updates
            extra_fail += script_imp.failed_updates

        if self.include_am_dependencies and self._pending_providers:
            info(f"Importing {len(self._pending_providers)} providers...")
            oauth_imp = OAuthImporter(realm=self.realm)
            oauth_imp.auth_mode = self.auth_mode

            for provider in self._pending_providers:
                pid = (
                    provider.get("_id") if isinstance(provider, dict) else "<provider>"
                )
                try:
                    oauth_imp.update_provider(provider, token, base_url)
                    extra_ok += 1
                except typer.Exit:
                    raise
                except Exception as e:
                    error(f"Provider import failed ({pid}): {e}")
                    extra_fail += 1
                    if rollback_on_failure and rollback_manager:
                        self._execute_rollback_and_exit(
                            rollback_manager, token, base_url, pid
                        )
                    if not continue_on_error:
                        raise typer.Exit(1)

        if self.include_am_dependencies and self._pending_clients:
            info(f"Importing {len(self._pending_clients)} clients...")
            oauth_imp = OAuthImporter(realm=self.realm)
            oauth_imp.auth_mode = self.auth_mode

            for client in self._pending_clients:
                payload = copy.deepcopy(client)
                cid = payload.get("_id")
                payload.pop("_provider", None)

                try:
                    oauth_imp.update_item(payload, token, base_url)
                    extra_ok += 1
                except typer.Exit:
                    raise
                except Exception as e:
                    error(f"Client import failed ({cid}): {e}")
                    extra_fail += 1
                    if rollback_on_failure and rollback_manager:
                        self._execute_rollback_and_exit(
                            rollback_manager, token, base_url, cid
                        )
                    if not continue_on_error:
                        raise typer.Exit(1)

        super().process_items(
            items,
            token,
            base_url,
            rollback_manager=rollback_manager,
            rollback_on_failure=rollback_on_failure,
            continue_on_error=continue_on_error,
        )

        self.successful_updates += extra_ok
        self.failed_updates += extra_fail


def create_applications_import_command():
    def import_applications(
        file: InputFileOpt = None,
        realm: RealmOpt = DEFAULT_REALM,
        src_realm: SrcRealmOpt = None,
        force_import: ForceImportOpt = False,
        diff: DiffOpt = False,
        rollback: RollbackOpt = False,
        branch: BranchOpt = None,
        cherry_pick: CherryPickOpt = None,
        sync: SyncOpt = False,
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
        continue_on_error: ContinueOnErrorOpt = False,
        dry_run: DryRunOpt = False,
    ):
        importer = ApplicationsImporter(realm=realm)
        importer.include_am_dependencies = with_deps

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
            cherry_pick=cherry_pick,
            sync=sync,
            dry_run=dry_run,
        )

    return import_applications
