"""
Themes export command.

This module provides export functionality for PingOne Advanced Identity Cloud UI themes.
Exports from /openidm/config/ui/themerealm endpoint.
"""

from trxo.commands.shared.options import (
    AmBaseUrlOpt,
    AuthModeOpt,
    BaseUrlOpt,
    BranchOpt,
    CommitMessageOpt,
    ContinueOnErrorOpt,
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
    ContinueOnErrorOpt,
    VersionOpt,
    ViewColumnsOpt,
    ViewOpt,
)
from trxo.config.api_headers import get_headers

from .base_exporter import BaseExporter


def create_themes_export_command():
    """Create the themes export command function"""

    def export_themes(
        realm: RealmOpt = None,
        view: ViewOpt = False,
        view_columns: ViewColumnsOpt = None,
        version: VersionOpt = None,
        no_version: NoVersionOpt = False,
        branch: BranchOpt = None,
        commit: CommitMessageOpt = None,
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
        continue_on_error: ContinueOnErrorOpt = False,
    ):
        """Export UI themes configuration

        Default: fetch full /openidm/config/ui/themerealm.
        With --realm: fetch only that realm via /openidm/config/ui/themerealm?_fields=realm/{realm}
        """
        exporter = BaseExporter()

        headers = get_headers("themes")

        endpoint = (
            "/openidm/config/ui/themerealm"
            if not realm
            else f"/openidm/config/ui/themerealm?_fields=realm/{realm}"
        )

        exporter.export_data(
            command_name="themes",
            api_endpoint=endpoint,
            headers=headers,
            view=view,
            view_columns=view_columns,
            jwk_path=jwk_path,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            output_dir=output_dir,
            output_file=output_file,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            idm_base_url=idm_base_url,
            idm_username=idm_username,
            idm_password=idm_password,
            am_base_url=am_base_url,
            version=version,
            no_version=no_version,
            branch=branch,
            commit_message=commit,
            continue_on_error=continue_on_error,
        )

    return export_themes
