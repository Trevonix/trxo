"""
SAML import commands.

This module provides import functionality for
PingOne Advanced Identity Cloud SAML configurations.
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
    RealmOpt,
    RollbackOpt,
    SaIdOpt,
    SrcRealmOpt,
    SyncOpt,
    ContinueOnErrorOpt,
)
from trxo_lib.config.constants import DEFAULT_REALM
from trxo_lib.imports.service import ImportService


def create_saml_import_command():
    """Create the SAML import command function"""

    def import_saml(
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
        force_import: ForceImportOpt = False,
        diff: DiffOpt = False,
        dry_run: DryRunOpt = False,
        branch: BranchOpt = None,
        cherry_pick: CherryPickOpt = None,
        rollback: RollbackOpt = False,
        realm: RealmOpt = DEFAULT_REALM,
        src_realm: SrcRealmOpt = None,
        am_base_url: AmBaseUrlOpt = None,
        idm_base_url: IdmBaseUrlOpt = None,
        idm_username: IdmUsernameOpt = None,
        idm_password: IdmPasswordOpt = None,
    ):
        """Import SAML configurations."""
        from trxo.utils.imports.cli_handler import CLIImportHandler

        kwargs = locals()
        handler = CLIImportHandler()
        return handler.handle_import("saml", ImportService().import_saml, kwargs)

    return import_saml
