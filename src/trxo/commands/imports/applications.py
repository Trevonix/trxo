"""
Applications import command.

Import functionality for PingOne Advanced Identity Cloud Applications.
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


class ApplicationsImporter(BaseImporter):
    """Importer for PingOne Advanced Identity Cloud Applications"""

    def __init__(self, realm: str = DEFAULT_REALM):
        super().__init__()
        self.realm = realm
        self.product = "idm"

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "Applications"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/openidm/managed/{self.realm}_application/{item_id}"

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
        src_realm: SrcRealmOpt = None,
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
    ):
        """Import applications from file or Git repository."""
        importer = ApplicationsImporter(realm=realm)
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
        )

    return import_applications
