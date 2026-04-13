"""
Agents import commands.

Import functionality for PingOne Advanced Identity Cloud agents.
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
)
from trxo.config.api_headers import get_headers
from trxo.constants import DEFAULT_REALM
from trxo.utils.console import error, info

from .base_importer import BaseImporter

# Base path template
AGENTS_BASE = "/am/json/realms/root/realms/{realm}/realm-config/agents"


class AgentsImporter(BaseImporter):
    """Generic importer for AM Agents of a specific type."""

    def __init__(self, agent_type: str, realm: str = DEFAULT_REALM):
        super().__init__()
        self.agent_type = agent_type
        self.realm = realm

    def get_required_fields(self) -> List[str]:
        # For create, AM typically needs an identifier; we do not hard-enforce here
        # because user may include _id in payload or type-specific fields.
        return []

    def get_item_type(self) -> str:
        if self.agent_type == "WebAgent":
            return "agents_web"
        elif self.agent_type == "J2EEAgent":
            return "agents_java"
        elif self.agent_type == "IdentityGatewayAgent":
            return "agents_gateway"

        return "agents"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/realm-config/agents/{self.agent_type}/{item_id}",
        )

    def _build_payload(self, item_data: Dict[str, Any]) -> str:

        forbidden_fields = {
            "_rev",
            "_type",
            "repositoryLocation",
            "disableJwtAudit",
            "jwtAuditWhitelist",
            "secretLabelIdentifier",
        }

        def clean(data):

            if isinstance(data, dict):
                cleaned = {}

                for k, v in data.items():

                    if k in forbidden_fields:
                        continue

                    # remove null / empty values
                    if v is None or v == [] or v == {}:
                        continue

                    cleaned_value = clean(v)

                    if cleaned_value not in (None, "", [], {}):
                        cleaned[k] = cleaned_value

                return cleaned

            if isinstance(data, list):
                cleaned_list = [clean(v) for v in data if v not in (None, [], {})]
                return [v for v in cleaned_list if v not in (None, "", [], {})]

            return data

        filtered = clean(item_data)

        return json.dumps(filtered)

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:

        item_id = item_data.get("_id")

        if not item_id:
            error("Agent missing '_id'; required for upsert")
            return False

        update_url = self.get_api_endpoint(item_id, base_url)

        headers = get_headers("agents")
        headers = {**headers, **self.build_auth_headers(token)}

        payload = self._build_payload(item_data)

        try:
            self.make_http_request(update_url, "PUT", headers, payload)

            info(f"Upserted {self.agent_type} agent: {item_id}")
            return True

        except Exception as e:
            error(f"Failed to upsert {self.agent_type} agent '{item_id}' : {e}")
            return False

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete an agent via API"""
        url = self.get_api_endpoint(item_id, base_url)

        headers = get_headers("agents")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "DELETE", headers)
            info(f"Successfully deleted {self.agent_type}: {item_id}")
            return True
        except Exception as e:
            error(f"Failed to delete {self.agent_type} '{item_id}': {e}")
            return False


def create_agents_import_command():
    """Create the agents import subcommands (gateway, java, web)."""

    def import_identity_gateway_agents(
        file: InputFileOpt = None,
        realm: RealmOpt = DEFAULT_REALM,
        src_realm: SrcRealmOpt = None,
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
        force_import: ForceImportOpt = False,
        diff: DiffOpt = False,
        branch: BranchOpt = None,
        rollback: RollbackOpt = False,
        continue_on_error: ContinueOnErrorOpt = False,
        dry_run: DryRunOpt = False,
    ):
        importer = AgentsImporter("IdentityGatewayAgent", realm=realm)
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
            cherry_pick=cherry_pick,
            diff=diff,
            rollback=rollback,
            continue_on_error=continue_on_error,
            sync=sync,
            dry_run=dry_run,
        )

    def import_java_agents(
        file: InputFileOpt = None,
        realm: RealmOpt = DEFAULT_REALM,
        src_realm: SrcRealmOpt = None,
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
        force_import: ForceImportOpt = False,
        diff: DiffOpt = False,
        branch: BranchOpt = None,
        rollback: RollbackOpt = False,
        continue_on_error: ContinueOnErrorOpt = False,
        dry_run: DryRunOpt = False,
    ):
        importer = AgentsImporter("J2EEAgent", realm=realm)
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
            cherry_pick=cherry_pick,
            diff=diff,
            rollback=rollback,
            continue_on_error=continue_on_error,
            sync=sync,
            dry_run=dry_run,
        )

    def import_web_agents(
        file: InputFileOpt = None,
        realm: RealmOpt = DEFAULT_REALM,
        src_realm: SrcRealmOpt = None,
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
        force_import: ForceImportOpt = False,
        diff: DiffOpt = False,
        branch: BranchOpt = None,
        rollback: RollbackOpt = False,
        continue_on_error: ContinueOnErrorOpt = False,
        dry_run: DryRunOpt = False,
    ):
        importer = AgentsImporter("WebAgent", realm=realm)
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
            cherry_pick=cherry_pick,
            rollback=rollback,
            continue_on_error=continue_on_error,
            sync=sync,
            dry_run=dry_run,
        )

    return (
        import_identity_gateway_agents,
        import_java_agents,
        import_web_agents,
    )


def create_agents_callback():
    """Create agents callback function for import group"""

    def agents_callback(ctx: typer.Context):
        if ctx.invoked_subcommand is None:
            from trxo.utils.console import console, info, warning

            console.print()
            warning("No agents subcommand selected.")
            info("Agents has three subcommands:")
            info("  • gateway")
            info("  • java")
            info("  • web")
            console.print()
            info("Run one of:")
            info("  trxo import agent gateway --help")
            info("  trxo import agent java --help")
            info("  trxo import agent web --help")
            console.print()
            info("Tip: use --help on any command to see options.")
            console.print()
            raise typer.Exit(code=0)

    return agents_callback
