"""
Policies export command.

This module provides export functionality for PingOne Advanced Identity Cloud policies.
Exports from /am/json/realms/root/realms/alpha/policies?_queryFilter=true endpoint.
"""

from typing import Any

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
from trxo_lib.utils.console import error

from trxo_lib.operations.export.base_exporter import BaseExporter


def process_policies_response(exporter_instance: BaseExporter, realm: str):
    """
    Process policies response to fetch and merge policy sets.

    Args:
        exporter_instance: The BaseExporter instance for making API calls
        realm: The realm name

    Returns:
        Function that processes the initial API response
    """

    def filter_function(data: Any, **kwargs) -> Any:
        # Get authentication details from the exporter instance
        token, api_base_url = exporter_instance.get_current_auth()

        url = exporter_instance._construct_api_url(
            api_base_url,
            f"/am/json/realms/root/realms/{realm}/applications?_queryFilter=true",
        )
        headers = get_headers("policy_sets")
        headers = {**headers, **exporter_instance.build_auth_headers(token)}

        try:
            response = exporter_instance.make_http_request(url, "GET", headers)
            policy_sets_data = response.json()
            policy_sets = policy_sets_data.get("result", [])

            if isinstance(data, dict) and isinstance(data.get("result"), list):
                # Prepend policy sets so they are processed first on import
                data["result"] = policy_sets + data["result"]
                data["resultCount"] = len(data["result"])
        except Exception as e:
            error(f"Failed to fetch policy sets: {str(e)}")

        return data

    return filter_function


class PoliciesExporter(BaseExporter):
    """Custom exporter to fetch policy sets and merge them with policies."""

    def __init__(self, realm: str):
        super().__init__()
        self.realm = realm


def create_policies_export_command():
    """Create the policies export command function"""

    def export_policies(
        realm: RealmOpt = DEFAULT_REALM,
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
    ):
        """Export policies configuration from specified realm"""
        exporter = PoliciesExporter(realm=realm)

        headers = get_headers("policies")

        exporter.export_data(
            command_name="policies",
            api_endpoint=(
                f"/am/json/realms/root/realms/{realm}/" "policies?_queryFilter=true"
            ),
            headers=headers,
            view=view,
            view_columns=view_columns,
            jwk_path=jwk_path,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            output_dir=output_dir,
            output_file=output_file,
            response_filter=process_policies_response(exporter, realm),
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
        )

    return export_policies
