"""
Services import commands.

Import functionality for PingOne Advanced Identity Cloud services.
"""

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
    RollbackOpt,
    SaIdOpt,
    SrcRealmOpt,
    SyncOpt,
)
from trxo_lib.constants import DEFAULT_REALM
from trxo_lib.operations.imports.service import ImportService


def create_services_import_command():
    """Create the services import command function"""

    def import_services(
        file: InputFileOpt = None,
        jwk_path: JwkPathOpt = None,
        sa_id: SaIdOpt = None,
        sync: SyncOpt = False,
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
        cherry_pick: CherryPickOpt = None,
        scope: str = typer.Option(
            "realm",
            "--scope",
            help="Service scope: 'global' (update only) or 'realm' (upsert)",
        ),
        realm: RealmOpt = DEFAULT_REALM,
        src_realm: SrcRealmOpt = None,
    ):
        """Import services from JSON file or Git repository."""
        kwargs = locals()
        return ImportService().import_services(**kwargs)

    return import_services
