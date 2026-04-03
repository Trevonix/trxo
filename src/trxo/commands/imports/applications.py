"""
Applications import command.

Import functionality for PingOne Advanced Identity Cloud Applications.
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
    WithDepsOpt,
)
from trxo_lib.constants import DEFAULT_REALM
from trxo_lib.operations.imports.service import ImportService


def create_applications_import_command():
    """Create the Applications import command function"""

    def import_applications(
        file: InputFileOpt = None,
        realm: RealmOpt = DEFAULT_REALM,
        src_realm: SrcRealmOpt = None,
        force_import: ForceImportOpt = False,
        diff: DiffOpt = False,
        rollback: RollbackOpt = False,
        branch: BranchOpt = None,
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
        with_deps: WithDepsOpt = False,
    ):
        """Import applications from file or Git repository."""
        kwargs = locals()
        ImportService().import_applications(**kwargs)

    return import_applications
