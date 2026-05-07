"""
IDM Connectors import command.

Import functionality for PingIDM connectors.
"""

from trxo.commands.shared.options import (
    AmBaseUrlOpt,
    AuthModeOpt,
    BaseUrlOpt,
    BranchOpt,
    CherryPickOpt,
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
    RollbackOpt,
    SaIdOpt,
    SyncOpt,
    ContinueOnErrorOpt,
)
from trxo_lib.imports.service import ImportService


def create_connectors_import_command():
    """Create the connectors import command function"""

    def import_connectors(
        cherry_pick: CherryPickOpt = None,
        diff: DiffOpt = False,
        dry_run: DryRunOpt = False,
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
        sync: SyncOpt = False,
        continue_on_error: ContinueOnErrorOpt = False,
    ):
        """Import IDM connectors from JSON file (local mode) or Git repository (Git mode).

        Updates existing connectors by _id or creates new ones (upsert).
        """
        from trxo.utils.imports.cli_handler import CLIImportHandler

        kwargs = locals()
        handler = CLIImportHandler()
        return handler.handle_import(
            "connectors", ImportService().import_connectors, kwargs
        )

    return import_connectors
