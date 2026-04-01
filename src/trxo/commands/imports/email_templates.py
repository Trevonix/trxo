"""
Email templates import command.

Import functionality for PingIDM Email Templates.
- Uses PUT with _id in endpoint: /openidm/config/{_id}
- Keeps complete data as payload (no field removal)
- Works as upsert (create or update)
"""

import json
from typing import Any, Dict, List

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
    RollbackOpt,
    SaIdOpt,
    SyncOpt,
)
from trxo_lib.config.api_headers import get_headers
from trxo_lib.utils.console import error, info

from trxo_lib.operations.imports.base_importer import BaseImporter


class EmailTemplatesImporter(BaseImporter):
    """Importer for PingIDM Email Templates"""

    def __init__(self):
        super().__init__()
        self.product = "idm"

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "Email Templates"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/openidm/config/{item_id}"

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Upsert Email Template using PUT"""

        item_id = item_data.get("_id")

        if not item_id:
            error("Email template missing '_id'; required for upsert")
            return False

        payload = json.dumps(item_data)

        url = self.get_api_endpoint(item_id, base_url)

        headers = get_headers("email_templates")

        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, payload)
            info(f"Upserted Email Template: {item_id}")
            return True

        except Exception as e:
            error(f"Failed to upsert Email Template '{item_id}': {e}")
            return False

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete an Email Template via API"""
        url = self.get_api_endpoint(item_id, base_url)
        headers = get_headers("email_templates")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "DELETE", headers)
            info(f"Deleted Email Template: {item_id}")
            return True
        except Exception as e:
            error(f"Failed to delete Email Template '{item_id}': {e}")
            return False


def create_email_templates_import_command():
    """Create the Email Templates import command function"""

    def import_email_templates(
        cherry_pick: CherryPickOpt = None,
        sync: SyncOpt = False,
        diff: DiffOpt = False,
        file: InputFileOpt = None,
        force_import: ForceImportOpt = False,
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
        rollback: RollbackOpt = False,
    ):
        """Import Email Templates from JSON file (local mode) or Git repository (Git mode)"""

        importer = EmailTemplatesImporter()

        importer.import_from_file(
            file_path=file,
            realm=None,  # Root-level config
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
            cherry_pick=cherry_pick,
            sync=sync,
        )

    return import_email_templates
