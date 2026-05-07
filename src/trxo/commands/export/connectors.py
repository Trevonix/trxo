"""
IDM Connectors export command.

This module provides export functionality for PingOne Advanced Identity
Cloud IDM connectors.
Filters /openidm/config?_queryFilter=true to only include items with
_id starting with "provisioner".
"""

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
    SaIdOpt,
    VersionOpt,
    ViewColumnsOpt,
    ViewOpt,
    ContinueOnErrorOpt,
)

from trxo_lib.exports.service import ExportService


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
        view: ViewOpt = False,
        view_columns: ViewColumnsOpt = None,
    ):
        """Export IDM connectors configuration"""
        kwargs = locals()
        from trxo.utils.export.cli_handler import CLIExportHandler
        CLIExportHandler().handle_export("connectors", ExportService().export_connectors, kwargs)

    return export_connectors
