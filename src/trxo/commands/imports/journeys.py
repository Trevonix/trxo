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
from trxo_lib.imports.service import ImportService


def create_journey_import_command():
    """Create the journey import command function"""

    def import_journeys(
        realm: RealmOpt = "alpha",
        src_realm: SrcRealmOpt = None,
        cherry_pick: CherryPickOpt = None,
        file: InputFileOpt = None,
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
        force_import: ForceImportOpt = False,
        diff: DiffOpt = False,
        rollback: RollbackOpt = False,
        sync: SyncOpt = False,
        continue_on_error: ContinueOnErrorOpt = False,
    ):
        """Import journeys from JSON file (local mode) or Git repository (Git mode)."""
        from trxo.utils.imports.cli_handler import CLIImportHandler

        kwargs = locals()
        handler = CLIImportHandler()
        return handler.handle_import(
            "journeys", ImportService().import_journeys, kwargs
        )

    return import_journeys
