"""
Realm import commands.

Import functionality for AM realms (global-config/realms).
- If item has _id: PUT to /am/json/global-config/realms/{_id}
- Else: POST to /am/json/global-config/realms
Payload fields supported: name, active, parentPath, aliases
"""

from trxo.commands.shared.options import (
    AmBaseUrlOpt,
    AuthModeOpt,
    BaseUrlOpt,
    BranchOpt,
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
    SaIdOpt,
)
from trxo_lib.operations.imports.service import ImportService


def create_realms_import_command():
    """Create the realms import command function"""

    def import_realms(
        file: InputFileOpt = ...,
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
    ):
        """Import realms from JSON file. Updates when _id present; otherwise creates."""
        kwargs = locals()
        return ImportService().import_realms(**kwargs)

    return import_realms
