"""
Agents export commands.

This module provides export functionality for PingOne Advanced Identity
Cloud Identity Gateway, java and web agents.
"""

import typer

from trxo.commands.shared.options import (
    AmBaseUrlOpt,
    AuthModeOpt,
    BaseUrlOpt,
    BranchOpt,
    CommitMessageOpt,
    IdmBaseUrlOpt,
    IdmPasswordOpt,
    IdmUsernameOpt,
    JwkPathOpt,
    NoVersionOpt,
    OnPremPasswordOpt,
    OnPremRealmOpt,
    OnPremUsernameOpt,
    OutputDirOpt,
    OutputFileOpt,
    ProjectNameOpt,
    RealmOpt,
    SaIdOpt,
    VersionOpt,
    ViewColumnsOpt,
    ViewOpt,
)
from trxo_lib.config.api_headers import get_headers
from trxo_lib.constants import DEFAULT_REALM
from trxo.utils.console import console, info, warning

from trxo_lib.operations.export.service import ExportService


def create_agents_export_command():
    """Create the agents export command function"""

    def export_identity_gateway_agents(
        realm: RealmOpt = DEFAULT_REALM,
        view: ViewOpt = None,
        view_columns: ViewColumnsOpt = None,
        jwk_path: JwkPathOpt = None,
        sa_id: SaIdOpt = None,
        base_url: BaseUrlOpt = None,
        project_name: ProjectNameOpt = None,
        output_dir: OutputDirOpt = None,
        output_file: OutputFileOpt = None,
        auth_mode: AuthModeOpt = None,
        onprem_username: OnPremUsernameOpt = None,
        onprem_password: OnPremPasswordOpt = None,
        onprem_realm: OnPremRealmOpt = "root",
        am_base_url: AmBaseUrlOpt = None,
        idm_base_url: IdmBaseUrlOpt = None,
        idm_username: IdmUsernameOpt = None,
        idm_password: IdmPasswordOpt = None,
        version: VersionOpt = None,
        no_version: NoVersionOpt = False,
        branch: BranchOpt = None,
        commit: CommitMessageOpt = None,
    ):
        """Export Identity Gateway Agents"""
        kwargs = locals()
        from trxo.utils.export.cli_handler import CLIExportHandler
        CLIExportHandler().handle_export("agents_gateway", ExportService().export_agents_gateway, kwargs)

    def export_java_agents(
        realm: RealmOpt = DEFAULT_REALM,
        view: ViewOpt = None,
        view_columns: ViewColumnsOpt = None,
        jwk_path: JwkPathOpt = None,
        sa_id: SaIdOpt = None,
        base_url: BaseUrlOpt = None,
        project_name: ProjectNameOpt = None,
        output_dir: OutputDirOpt = None,
        output_file: OutputFileOpt = None,
        auth_mode: AuthModeOpt = None,
        onprem_username: OnPremUsernameOpt = None,
        onprem_password: OnPremPasswordOpt = None,
        onprem_realm: OnPremRealmOpt = "root",
        am_base_url: AmBaseUrlOpt = None,
        idm_base_url: IdmBaseUrlOpt = None,
        idm_username: IdmUsernameOpt = None,
        idm_password: IdmPasswordOpt = None,
        version: VersionOpt = None,
        no_version: NoVersionOpt = False,
        branch: BranchOpt = None,
        commit: CommitMessageOpt = None,
    ):
        """Export Java Agents"""
        kwargs = locals()
        from trxo.utils.export.cli_handler import CLIExportHandler
        CLIExportHandler().handle_export("agents_java", ExportService().export_agents_java, kwargs)

    def export_web_agents(
        realm: RealmOpt = DEFAULT_REALM,
        view: ViewOpt = None,
        view_columns: ViewColumnsOpt = None,
        jwk_path: JwkPathOpt = None,
        sa_id: SaIdOpt = None,
        base_url: BaseUrlOpt = None,
        project_name: ProjectNameOpt = None,
        output_dir: OutputDirOpt = None,
        output_file: OutputFileOpt = None,
        auth_mode: AuthModeOpt = None,
        onprem_username: OnPremUsernameOpt = None,
        onprem_password: OnPremPasswordOpt = None,
        onprem_realm: OnPremRealmOpt = "root",
        am_base_url: AmBaseUrlOpt = None,
        idm_base_url: IdmBaseUrlOpt = None,
        idm_username: IdmUsernameOpt = None,
        idm_password: IdmPasswordOpt = None,
        version: VersionOpt = None,
        no_version: NoVersionOpt = False,
        branch: BranchOpt = None,
        commit: CommitMessageOpt = None,
    ):
        """Export Web Agents"""
        kwargs = locals()
        from trxo.utils.export.cli_handler import CLIExportHandler
        CLIExportHandler().handle_export("agents_web", ExportService().export_agents_web, kwargs)

    return export_identity_gateway_agents, export_java_agents, export_web_agents


def create_agents_callback():
    """Create agents callback function"""

    def agents_callback(ctx: typer.Context):
        """Top-level agents command.

        If run without a subcommand, prints a short guide to help the user.
        """
        if ctx.invoked_subcommand is None:
            console.print()
            warning("No agents subcommand selected.")
            info("Agents has three subcommands:")
            info("  • gateway")
            info("  • java")
            info("  • web")
            console.print()
            info("Run one of:")
            info("  trxo export agent gateway --help")
            info("  trxo export agent java --help")
            info("  trxo export agent web --help")
            console.print()
            info("Tip: use --help on any command to see options.")
            console.print()
            raise typer.Exit(code=0)

    return agents_callback
