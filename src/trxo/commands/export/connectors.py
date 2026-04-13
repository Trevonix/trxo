"""
IDM Connectors export command.

This module provides export functionality for PingOne Advanced Identity
Cloud IDM connectors.
Filters /openidm/config?_queryFilter=true to only include items with
_id starting with "provisioner".
"""

import typer

from trxo.commands.shared.options import (
    AmBaseUrlOpt,
    AuthModeOpt,
    BaseUrlOpt,
    BranchOpt,
    CommitMessageOpt,
    ContinueOnErrorOpt,
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
    SaIdOpt,
    ContinueOnErrorOpt,
    VersionOpt,
    ViewColumnsOpt,
    ViewOpt,
)
from trxo.config.api_headers import get_headers

from .base_exporter import BaseExporter


def create_connectors_export_command():
    """Create the connectors export command function"""

    def export_connectors(
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
        continue_on_error: ContinueOnErrorOpt = False,
        view: ViewOpt = False,
        view_columns: ViewColumnsOpt = None,
    ):
        """Export IDM connectors configuration"""
        exporter = BaseExporter()

        headers = get_headers("connectors")

        exporter.export_data(
            command_name="connectors",
            api_endpoint=('/openidm/config?_queryFilter=_id+sw+"provisioner.openicf/"'),
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
            continue_on_error=continue_on_error,
            version=version,
            no_version=no_version,
            branch=branch,
            commit_message=commit,
        )

    return export_connectors
