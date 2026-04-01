"""
Privileges export command.

This module provides export functionality for PingOne Advanced Identity Cloud Privilege.
Filters /openidm/config?_queryFilter=true to only include items with _id containing "privilege/".
"""

from typing import Any, Dict

import typer

from trxo.commands.shared.options import (
    AmBaseUrlOpt,
    AuthModeOpt,
    BaseUrlOpt,
    BranchOpt,
    CommitMessageOpt,
    IdmBaseUrlOpt,
    IdmPasswordOpt,
    IdmUsernameOpt,
    JwkPathOpt,
    NoVersionOpt,
    OnPremPasswordOpt,
    OnPremRealmOpt,
    OnPremUsernameOpt,
    OutputDirOpt,
    OutputFileOpt,
    ProjectNameOpt,
    RealmOpt,
    SaIdOpt,
    VersionOpt,
    ViewColumnsOpt,
    ViewOpt,
)
from trxo_lib.config.api_headers import get_headers

from trxo_lib.operations.export.base_exporter import BaseExporter


def create_privileges_export_command():
    """Create the privileges export command function"""

    def export_privileges(
        realm: RealmOpt = None,
        view: ViewOpt = False,
        view_columns: ViewColumnsOpt = None,
        version: VersionOpt = None,
        no_version: NoVersionOpt = False,
        branch: BranchOpt = None,
        commit: CommitMessageOpt = None,
        jwk_path: JwkPathOpt = None,
        sa_id: SaIdOpt = None,
        base_url: BaseUrlOpt = None,
        project_name: ProjectNameOpt = None,
        output_dir: OutputDirOpt = None,
        output_file: OutputFileOpt = None,
        auth_mode: AuthModeOpt = None,
        onprem_username: OnPremUsernameOpt = None,
        onprem_password: OnPremPasswordOpt = None,
        onprem_realm: OnPremRealmOpt = "root",
        am_base_url: AmBaseUrlOpt = None,
        idm_base_url: IdmBaseUrlOpt = None,
        idm_username: IdmUsernameOpt = None,
        idm_password: IdmPasswordOpt = None,
    ):
        """Export privileges configuration

        Default: Export all privileges
        With --realm: Export realm-specific privileges (realmOrgPrivileges + privilegeAssignments)
        """
        exporter = BaseExporter()

        headers = get_headers("privileges")

        # Build optional response filter for realm-specific export
        response_filter = None
        if realm:
            realm_clean = realm.strip()
            wanted_ids = {f"{realm_clean}OrgPrivileges", "privilegeAssignments"}

            def _filter(raw: Dict[str, Any]) -> Dict[str, Any]:
                if isinstance(raw, dict) and isinstance(raw.get("result"), list):
                    filtered = [
                        item
                        for item in raw["result"]
                        if isinstance(item, dict) and item.get("_id") in wanted_ids
                    ]
                    return {**raw, "result": filtered}
                return raw

            response_filter = _filter

        # Single call; same format as before. If --realm provided, only keep matching IDs
        exporter.export_data(
            command_name="privileges",
            api_endpoint='/openidm/config?_queryFilter=_id co "privilege"',
            headers=headers,
            view=view,
            view_columns=view_columns,
            jwk_path=jwk_path,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            output_dir=output_dir,
            output_file=output_file,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            idm_base_url=idm_base_url,
            idm_username=idm_username,
            idm_password=idm_password,
            am_base_url=am_base_url,
            response_filter=response_filter,
            version=version,
            no_version=no_version,
            branch=branch,
            commit_message=commit,
        )

    return export_privileges
