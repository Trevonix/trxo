"""
Themes import command.
"""

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
    RollbackOpt,
    SaIdOpt,
    SrcRealmOpt,
    SyncOpt,
    ContinueOnErrorOpt,
)
from trxo_lib.config.constants import DEFAULT_REALM
from trxo_lib.imports.service import ImportService


def create_themes_import_command():
    """Create the themes import command function."""

    def import_themes(
        cherry_pick: CherryPickOpt = None,
        file: InputFileOpt = None,
        realm: RealmOpt = DEFAULT_REALM,
        src_realm: SrcRealmOpt = None,
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
        sync: SyncOpt = False,
        continue_on_error: ContinueOnErrorOpt = False,
    ):
        """Import themes from JSON file or Git repository."""
        from trxo.utils.imports.cli_handler import CLIImportHandler

        kwargs = locals()
        handler = CLIImportHandler()
        return handler.handle_import("themes", ImportService().import_themes, kwargs)

    return import_themes
