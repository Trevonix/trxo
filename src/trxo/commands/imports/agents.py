"""
Agents import commands.

Import functionality for PingOne Advanced Identity Cloud agents.
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


def create_agents_import_command():
    """Create the agents import subcommands (gateway, java, web)."""

    def import_identity_gateway_agents(
        file: InputFileOpt = None,
        realm: RealmOpt = DEFAULT_REALM,
        src_realm: SrcRealmOpt = None,
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
        force_import: ForceImportOpt = False,
        diff: DiffOpt = False,
        branch: BranchOpt = None,
        rollback: RollbackOpt = False,
    ):
        kwargs = locals()
        return ImportService().import_agents(
            agent_type="IdentityGatewayAgent", **kwargs
        )

    def import_java_agents(
        file: InputFileOpt = None,
        realm: RealmOpt = DEFAULT_REALM,
        src_realm: SrcRealmOpt = None,
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
        force_import: ForceImportOpt = False,
        diff: DiffOpt = False,
        branch: BranchOpt = None,
        rollback: RollbackOpt = False,
    ):
        kwargs = locals()
        return ImportService().import_agents(agent_type="J2EEAgent", **kwargs)

    def import_web_agents(
        file: InputFileOpt = None,
        realm: RealmOpt = DEFAULT_REALM,
        src_realm: SrcRealmOpt = None,
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
        force_import: ForceImportOpt = False,
        diff: DiffOpt = False,
        branch: BranchOpt = None,
        rollback: RollbackOpt = False,
    ):
        kwargs = locals()
        return ImportService().import_agents(agent_type="WebAgent", **kwargs)

    return (
        import_identity_gateway_agents,
        import_java_agents,
        import_web_agents,
    )


def create_agents_callback():
    """Create agents callback function for import group"""

    def agents_callback(ctx: typer.Context):
        if ctx.invoked_subcommand is None:
            from trxo.utils.console import console, info, warning

            console.print()
            warning("No agents subcommand selected.")
            info("Agents has three subcommands:")
            info("  • gateway")
            info("  • java")
            info("  • web")
            console.print()
            info("Run one of:")
            info("  trxo import agent gateway --help")
            info("  trxo import agent java --help")
            info("  trxo import agent web --help")
            console.print()
            info("Tip: use --help on any command to see options.")
            console.print()
            raise typer.Exit(code=0)

    return agents_callback
