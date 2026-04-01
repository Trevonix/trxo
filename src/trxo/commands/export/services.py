"""
Services export commands.

This module provides export functionality for PingOne Advanced Identity
Cloud services.
Supports both global and realm-based services with flexible realm selection.
Fetches complete service configurations by individual service ID.
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
from trxo_lib.utils.console import warning

from trxo_lib.operations.export.base_exporter import BaseExporter


def services_response_filter(data, *, exporter, scope, realm, headers):
    """Filter to fetch complete service configurations"""
    if not isinstance(data, dict) or "result" not in data:
        return data

    services_list = data["result"]
    if not services_list:
        return data

    token, api_base_url = exporter.get_current_auth()
    if not token or not api_base_url:
        warning("Authentication not available for detailed service fetch")
        return data

    complete_services = []
    auth_headers = {**headers, **exporter.build_auth_headers(token)}

    for service_summary in services_list:
        service_id = service_summary.get("_id")
        if not service_id:
            complete_services.append(service_summary)
            continue

        if service_id == "DataStoreService":
            continue

        if scope.lower() == "global":
            detail_url = exporter._construct_api_url(
                api_base_url, f"/am/json/global-config/services/{service_id}"
            )
        else:
            detail_url = exporter._construct_api_url(
                api_base_url,
                f"/am/json/realms/root/realms/{realm}/realm-config/services/{service_id}",
            )

        try:
            detail_response = exporter.make_http_request(
                detail_url, "GET", auth_headers
            )
            complete_service = detail_response.json()

            try:
                nd_url = f"{detail_url}?_action=nextdescendents"
                nd_response = exporter.make_http_request(nd_url, "POST", auth_headers)
                nd_result = nd_response.json()
                descendants = nd_result.get("result", [])
                complete_service["nextDescendents"] = [
                    {k: v for k, v in d.items() if k != "_rev"} for d in descendants
                ]

            except Exception:
                complete_service["nextDescendents"] = []

            complete_services.append(complete_service)
        except Exception as e:
            warning(f"Failed to fetch complete config for service '{service_id}': {e}")
            complete_services.append(service_summary)

    return {**data, "result": complete_services}


class ServicesExporter(BaseExporter):
    """Custom exporter for services that fetches complete configurations"""

    def export_as_dict(
        self,
        scope: str = "realm",
        realm: str = DEFAULT_REALM,
        jwk_path=None,
        client_id=None,
        sa_id=None,
        base_url=None,
        project_name=None,
        auth_mode=None,
        onprem_username=None,
        onprem_password=None,
        onprem_realm="root",
    ):
        headers = get_headers("services")

        if scope.lower() == "global":
            api_endpoint = "/am/json/global-config/services?_queryFilter=true"
        else:
            api_endpoint = f"/am/json/realms/root/realms/{realm}/realm-config/services?_queryFilter=true"

        captured = {}
        original_save_response = self.save_response

        def capture_save_response(payload, *args, **kwargs):
            if isinstance(payload, dict) and "data" in payload:
                captured["data"] = payload["data"]
            else:
                captured["data"] = payload
            return None

        self.save_response = capture_save_response

        try:
            self.export_data(
                command_name="services",
                api_endpoint=api_endpoint,
                headers=headers,
                view=False,
                jwk_path=jwk_path,
                client_id=client_id,
                sa_id=sa_id,
                base_url=base_url,
                project_name=project_name,
                auth_mode=auth_mode,
                onprem_username=onprem_username,
                onprem_password=onprem_password,
                onprem_realm=onprem_realm,
                response_filter=lambda data: services_response_filter(
                    data,
                    exporter=self,
                    scope=scope,
                    realm=realm,
                    headers=headers,
                ),
            )
        finally:
            self.save_response = original_save_response

        return captured.get("data")


def create_services_export_command():
    """Create the services export command function"""

    def export_services(
        scope: str = typer.Option(
            "realm",
            "--scope",
            help="Service scope: 'global' for global services or 'realm' for realm services",
        ),
        realm: RealmOpt = DEFAULT_REALM,
        view: ViewOpt = False,
        view_columns: ViewColumnsOpt = None,
        version: VersionOpt = None,
        no_version: NoVersionOpt = False,
        branch: BranchOpt = None,
        commit: CommitMessageOpt = None,
        jwk_path: JwkPathOpt = None,
        client_id: str = typer.Option(None, "--client-id"),
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
        exporter = ServicesExporter()

        headers = get_headers("services")

        if scope.lower() == "global":
            api_endpoint = "/am/json/global-config/services?_queryFilter=true"
        else:
            api_endpoint = f"/am/json/realms/root/realms/{realm}/realm-config/services?_queryFilter=true"

        exporter.export_data(
            command_name="services",
            api_endpoint=api_endpoint,
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
            response_filter=lambda data: services_response_filter(
                data,
                exporter=exporter,
                scope=scope,
                realm=realm,
                headers=headers,
            ),
            idm_base_url=idm_base_url,
            idm_username=idm_username,
            idm_password=idm_password,
            am_base_url=am_base_url,
            version=version,
            no_version=no_version,
            branch=branch,
            commit_message=commit,
        )

    return export_services
