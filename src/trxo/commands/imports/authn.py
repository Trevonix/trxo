"""
Authentication settings import command (authn).

Imports authentication settings to realm using PUT.
"""

import json
from typing import Any, Dict, List

import typer

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
    SrcRealmOpt,
    RollbackOpt,
    SaIdOpt,
)
from trxo.config.api_headers import get_headers
from trxo.constants import DEFAULT_REALM
from trxo.utils.console import error, info

from .base_importer import BaseImporter


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


def create_authn_import_command():
    def import_authn(
        realm: RealmOpt = DEFAULT_REALM,
        src_realm: SrcRealmOpt = None,
        diff: DiffOpt = False,
        file: InputFileOpt = None,
        force_import: ForceImportOpt = False,
        branch: BranchOpt = None,
        jwk_path: JwkPathOpt = None,
        sa_id: SaIdOpt = None,
        base_url: BaseUrlOpt = None,
        project_name: ProjectNameOpt = None,
        auth_mode: AuthModeOpt = None,
        rollback: RollbackOpt = False,
        onprem_username: OnPremUsernameOpt = None,
        onprem_password: OnPremPasswordOpt = None,
        onprem_realm: OnPremRealmOpt = "root",
        am_base_url: AmBaseUrlOpt = None,
        idm_base_url: IdmBaseUrlOpt = None,
        idm_username: IdmUsernameOpt = None,
        idm_password: IdmPasswordOpt = None,
    ):
        """Import authentication settings from file or Git repository."""
        importer = AuthnImporter(realm=realm)
        importer.import_from_file(
            file_path=file,
            realm=realm,
            src_realm=src_realm,
            jwk_path=jwk_path,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            auth_mode=auth_mode,
            rollback=rollback,
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
        )

    return import_authn
