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
)
from trxo_lib.config.constants import DEFAULT_REALM
from trxo_lib.imports.service import ImportService


def create_oauth_import_command():
    """Create the OAuth import command function"""

    def import_oauth(
        realm: RealmOpt = DEFAULT_REALM,
        src_realm: SrcRealmOpt = None,
        cherry_pick: CherryPickOpt = None,
        sync: SyncOpt = False,
        diff: DiffOpt = False,
        file: InputFileOpt = None,
        force_import: ForceImportOpt = False,
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
        """Import OAuth2 Clients with script dependencies."""
        from trxo.utils.imports.cli_handler import CLIImportHandler

        kwargs = locals()
        handler = CLIImportHandler()
        return handler.handle_import("oauth", ImportService().import_oauth, kwargs)

    return import_oauth
