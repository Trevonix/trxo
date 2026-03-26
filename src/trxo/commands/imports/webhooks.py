"""
Webhooks import command.

Imports AM realm webhooks with PUT upsert.
Endpoint: /am/json/realms/root/realms/{realm}/realm-config/webhooks/{_id}
- Removes _rev from payload before sending
- Uses PUT for upsert (create/update)
"""

import json
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
    SrcRealmOpt,
    RollbackOpt,
    SaIdOpt,
    SyncOpt,
)
from trxo.config.api_headers import get_headers
from trxo.constants import DEFAULT_REALM
from trxo.utils.console import error, info

from .base_importer import BaseImporter


class WebhooksImporter(BaseImporter):
    """Importer for AM webhooks"""

    def __init__(self, realm: str = DEFAULT_REALM):
        super().__init__()
        self.realm = realm

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "webhooks"

    def get_item_id(self, item: Dict[str, Any]) -> str:
        return item.get("_id")

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/"
            f"realm-config/webhooks/{item_id}",
        )

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        item_id = item_data.get("_id")
        if not item_id:
            error("Webhook missing '_id'; required for upsert")
            return False

        payload_obj = dict(item_data)
        payload_obj.pop("_rev", None)
        payload = json.dumps(payload_obj)

        url = self.get_api_endpoint(item_id, base_url)

        headers = get_headers("webhooks")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            response = self.make_http_request(url, "PUT", headers, payload)

            if response.status_code == 201:
                info(f"Created webhook ({self.realm}): {item_id}")
            else:
                info(f"Updated webhook ({self.realm}): {item_id}")

            return True

        except Exception as e:
            error(
                f"Failed to upsert webhook '{item_id}' in realm " f"'{self.realm}': {e}"
            )
            return False

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete a single Webhook via API"""
        url = self.get_api_endpoint(item_id, base_url)
        headers = get_headers("webhooks")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "DELETE", headers)
            info(f"Successfully deleted Webhook: {item_id}")
            return True
        except Exception as e:
            error(f"Failed to delete Webhook '{item_id}': {e}")
            return False


def create_webhooks_import_command():
    """Create the webhooks import command function"""

    def import_webhooks(
        realm: RealmOpt = DEFAULT_REALM,
        src_realm: SrcRealmOpt = None,
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
        """Import webhooks from JSON file to specified realm"""
        importer = WebhooksImporter(realm=realm)
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
            sync=sync,
        )

    return import_webhooks
