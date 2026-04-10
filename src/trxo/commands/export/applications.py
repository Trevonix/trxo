"""
applications export command.

This module provides export functionality for PingOne Advanced Identity
Cloud applications.
Exports from /openidm/config?_queryFilter=true endpoint, filtered to
only include items with _id containing "application/".
"""

from typing import Any, Dict, List

import typer

from trxo.commands.export.oauth import OAuthExporter
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
    ContinueOnErrorOpt,
    VersionOpt,
    ViewColumnsOpt,
    ViewOpt,
    WithDepsOpt,
)
from trxo.config.api_headers import get_headers
from trxo.constants import DEFAULT_REALM, IGNORED_SCRIPT_IDS
from trxo.utils.console import error, info, success, warning
from trxo.utils.export import MetadataBuilder

from .base_exporter import BaseExporter


def _collect_oidc_client_ids(applications: List[Dict[str, Any]]) -> List[str]:
    """Unique OAuth2 client names from managed application ssoEntities.oidcId."""
    out: List[str] = []
    seen: set[str] = set()
    for app in applications:
        if not isinstance(app, dict):
            continue
        se = app.get("ssoEntities")
        if not isinstance(se, dict):
            continue
        oid = se.get("oidcId")
        if isinstance(oid, str):
            oid = oid.strip()
            if oid and oid not in seen:
                seen.add(oid)
                out.append(oid)
    return out


def _normalize_provider_export(provider_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize provider object for export shape compatibility."""
    if not isinstance(provider_obj, dict):
        return {}
    normalized = dict(provider_obj)
    normalized.setdefault(
        "_type",
        {"_id": "oauth-oidc", "collection": False, "name": "OAuth2 Provider"},
    )
    normalized.setdefault("_id", "")
    return normalized


def _export_applications_with_deps(
    realm: str,
    version: str | None,
    no_version: bool,
    branch: str | None,
    commit: str | None,
    jwk_path: str | None,
    sa_id: str | None,
    base_url: str | None,
    project_name: str | None,
    output_dir: str | None,
    output_file: str | None,
    auth_mode: str | None,
    onprem_username: str | None,
    onprem_password: str | None,
    onprem_realm: str | None,
    am_base_url: str | None,
    idm_base_url: str | None,
    idm_username: str | None,
    idm_password: str | None,
    continue_on_error: bool = False,
) -> None:
    """Export managed applications plus referenced OAuth2 clients/provider/scripts."""
    base = BaseExporter()
    oauth_gate: OAuthExporter | None = None
    api_endpoint = f"/openidm/managed/{realm}_application?_queryFilter=true"
    base.product = "idm"

    try:
        token_idm, idm_api_url = base.initialize_auth(
            jwk_path=jwk_path,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            idm_base_url=idm_base_url,
            idm_username=idm_username,
            idm_password=idm_password,
            am_base_url=am_base_url,
        )

        if base.auth_mode == "onprem" and base.product == "idm" and base._idm_base_url:
            idm_api_url = base._idm_base_url

        idm_headers = {
            **get_headers("applications"),
            **base.build_auth_headers(token_idm, product="idm"),
        }
        idm_url = base._construct_api_url(idm_api_url, api_endpoint)
        response = base.make_http_request(idm_url, "GET", idm_headers)
        raw_data = response.json()
        aggregated = base._handle_pagination(
            raw_data, api_endpoint, idm_headers, idm_api_url
        )
        filtered_data = base.remove_rev_fields(aggregated)

        applications_list: List[Dict[str, Any]] = []
        if isinstance(filtered_data, dict) and isinstance(
            filtered_data.get("result"), list
        ):
            applications_list = [
                x for x in filtered_data["result"] if isinstance(x, dict)
            ]

        if base.auth_mode != "onprem":
            am_token = token_idm
            am_api_base = idm_api_url
        else:
            oauth_gate = OAuthExporter(realm=realm)
            oauth_gate.product = "am"
            am_token, am_api_base = oauth_gate.initialize_auth(
                jwk_path=jwk_path,
                sa_id=sa_id,
                base_url=base_url,
                project_name=project_name,
                auth_mode=auth_mode,
                onprem_username=onprem_username,
                onprem_password=onprem_password,
                onprem_realm=onprem_realm,
                idm_base_url=idm_base_url,
                idm_username=idm_username,
                idm_password=idm_password,
                am_base_url=am_base_url,
            )

        oauth_helper = OAuthExporter(realm=realm)
        oauth_helper.continue_on_error = continue_on_error
        client_ids = _collect_oidc_client_ids(applications_list)
        complete_clients: List[Dict[str, Any]] = []
        all_script_ids: set[str] = set()
        provider_data: Dict[str, Any] = {}

        for cid in client_ids:
            client_obj = oauth_helper.fetch_oauth_client_data(
                cid, am_token, am_api_base
            )
            if client_obj:
                complete_clients.append(client_obj)
                all_script_ids.update(oauth_helper.extract_script_ids(client_obj))

        provider_obj = oauth_helper.fetch_oauth_provider_data(am_token, am_api_base)
        if provider_obj:
            provider_data = _normalize_provider_export(provider_obj)
            all_script_ids.update(oauth_helper.extract_script_ids(provider_data))

        scripts_data: List[Dict[str, Any]] = []
        for script_id in all_script_ids:
            if script_id in IGNORED_SCRIPT_IDS:
                continue
            script_obj = oauth_helper.fetch_script_data(
                script_id, am_token, am_api_base
            )
            if script_obj:
                scripts_data.append(script_obj)

        if not isinstance(filtered_data, dict):
            filtered_data = {"applications": applications_list}
        elif "result" in filtered_data:
            filtered_data["applications"] = filtered_data.pop("result")

        combined_data = {
            **filtered_data,
            "clients": complete_clients,
            "providers": [provider_data] if provider_data else [],
            "scripts": scripts_data,
        }

        metadata = MetadataBuilder.build_metadata(
            command_name="applications",
            api_endpoint=api_endpoint,
            data=combined_data,
            version=None,
        )
        metadata["with_deps"] = True

        export_payload = {"metadata": metadata, "data": combined_data}

        info("Exporting Applications (with OAuth2 clients and scripts)...")
        print()

        file_path = base.save_response(
            data=export_payload,
            command_name="applications",
            output_dir=output_dir,
            output_file=output_file,
            version=version,
            no_version=no_version,
            branch=branch,
            commit_message=commit,
        )

        storage_mode = base._get_storage_mode()
        if storage_mode == "local" and file_path:
            hash_value = base.hash_manager.create_hash(combined_data, "applications")
            base.hash_manager.save_export_hash("applications", hash_value, file_path)

        print()
        if response.status_code == 200:
            success("Applications (with dependencies) exported successfully")
        else:
            error(f"Export completed with unexpected status: {response.status_code}")

    except Exception as e:
        error(f"Export failed: {str(e)}")
        raise typer.Exit(1)
    finally:
        if oauth_gate is not None:
            oauth_gate.cleanup()
        base.cleanup()


def create_applications_export_command():
    """Create the applications export command function"""

    def export_applications(
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
        with_deps: WithDepsOpt = False,
        continue_on_error: ContinueOnErrorOpt = False,
    ):
        """Export custom applications configuration"""
        if with_deps:
            if view:
                warning("--with-deps is ignored when using --view")
            else:
                _export_applications_with_deps(
                    realm=realm,
                    version=version,
                    no_version=no_version,
                    branch=branch,
                    commit=commit,
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
                    am_base_url=am_base_url,
                    idm_base_url=idm_base_url,
                    idm_username=idm_username,
                    idm_password=idm_password,
                    continue_on_error=continue_on_error,
                )
                return

        exporter = BaseExporter()

        headers = get_headers("applications")

        exporter.export_data(
            command_name="applications",
            api_endpoint=(f"/openidm/managed/{realm}_application?_queryFilter=true"),
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

    return export_applications
