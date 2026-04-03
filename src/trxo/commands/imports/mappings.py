"""
Mappings import command.

Import functionality for PingIDM sync mappings with smart upsert logic:
- If mapping exists by name → PATCH to update
- If mapping doesn't exist → PUT to add to the mappings array
- Handles both single mappings and multiple mappings
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
    RollbackOpt,
    SaIdOpt,
    SyncOpt,
)
from trxo_lib.operations.imports.service import ImportService


def create_mappings_import_command():
    """Create the mappings import command function"""

    def import_mappings(
        cherry_pick: CherryPickOpt = None,
        file: InputFileOpt = None,
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
        sync: SyncOpt = False,
        rollback: RollbackOpt = False,
    ):
        """Import sync mappings from JSON file (local mode) or Git repository (Git mode).

        Updates existing mappings by name (PATCH) or adds new ones (PUT).
        """
        kwargs = locals()
        return ImportService().import_mappings(**kwargs)

    return import_mappings
