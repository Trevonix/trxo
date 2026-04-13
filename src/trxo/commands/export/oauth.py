"""
OAuth export commands.

This module provides export functionality for
PingOne Advanced Identity Cloud OAuth2 clients with script dependencies.
"""

import base64
from typing import Any, Dict, Set

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
from trxo.constants import DEFAULT_REALM, IGNORED_SCRIPT_IDS
from trxo.utils.console import error, info, warning

from .base_exporter import BaseExporter


def process_oauth_response(exporter_instance: "OAuthExporter", realm: str):
    """
    Process OAuth response to fetch complete client data and scripts.

    Args:
        exporter_instance: The OAuthExporter instance
        realm: The realm name

    Returns:
        Function that processes the initial API response
    """

    def filter_function(response_data: Any, **kwargs) -> Dict[str, Any]:
        if not isinstance(response_data, dict) or "result" not in response_data:
            error("Invalid response format from OAuth clients list")
            return {"clients": [], "scripts": []}

        oauth_clients = response_data["result"]
        token, api_base_url = exporter_instance.get_current_auth()

        info("Fetching OAuth2 clients data...\n")
        complete_clients = []
        all_script_ids = set()

        for client in oauth_clients:
            client_id = client.get("_id")
            if not client_id:
                warning("Skipping client without _id")
                continue

            complete_client = exporter_instance.fetch_oauth_client_data(
                client_id, token, api_base_url
            )

            if complete_client:
                complete_clients.append(complete_client)
                # Extract script dependencies
                script_ids = exporter_instance.extract_script_ids(complete_client)
                all_script_ids.update(script_ids)

        # Fetch all dependent scripts
        scripts_data = []
        if all_script_ids:
            for script_id in all_script_ids:
                if script_id in IGNORED_SCRIPT_IDS:
                    continue
                script_data = exporter_instance.fetch_script_data(
                    script_id, token, api_base_url
                )
                if script_data:
                    scripts_data.append(script_data)

        return {"clients": complete_clients, "scripts": scripts_data}

    return filter_function


class OAuthExporter(BaseExporter):
    """Enhanced OAuth exporter that fetches complete data and handles script dependencies"""

    def __init__(self, realm: str = DEFAULT_REALM):
        super().__init__()
        self.realm = realm

    def extract_script_ids(self, oauth_data: Dict[str, Any]) -> Set[str]:
        """Extract script IDs from OAuth client configuration"""
        script_ids = set()

        def find_scripts(obj: Any):
            """Recursively find script IDs"""
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if (
                        k.endswith("Script")
                        and isinstance(v, str)
                        and v.strip()
                        and v.strip() != "[Empty]"
                    ):
                        val = v.strip()
                        if len(val) > 10 and ("-" in val or len(val) == 36):
                            script_ids.add(val)
                    elif isinstance(v, (dict, list)):
                        find_scripts(v)
            elif isinstance(obj, list):
                for item in obj:
                    find_scripts(item)

        find_scripts(oauth_data)
        return script_ids

    def fetch_script_data(
        self, script_id: str, token: str, base_url: str
    ) -> Dict[str, Any]:
        """Fetch individual script data by ID"""
        url = self._construct_api_url(
            base_url, f"/am/json/realms/root/realms/{self.realm}/scripts/{script_id}"
        )
        headers = get_headers("oauth")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            response = self.make_http_request(url, "GET", headers)
            script_data = response.json()

            # Decode script field if present (similar to scripts export)
            if "script" in script_data and isinstance(script_data["script"], str):
                try:
                    decoded_bytes = base64.b64decode(
                        script_data["script"], validate=True
                    )
                    decoded_text = decoded_bytes.decode("utf-8")
                    script_data["script"] = decoded_text.splitlines()
                except Exception as e:
                    warning(f"Failed to decode script {script_id}: {str(e)}")

            return script_data
        except Exception as e:
            error(f"Failed to fetch script {script_id}: {str(e)}")
<<<<<<< HEAD
            if not self.continue_on_error:
                raise
            return {}
=======
            if getattr(self, "continue_on_error", False):
                return {}
            raise
>>>>>>> 8dc291c548055214e3452c4e135d037eaf02a366

    def fetch_oauth_client_data(
        self, client_id: str, token: str, base_url: str
    ) -> Dict[str, Any]:
        """Fetch individual OAuth client data by ID"""
        url = self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}"
            f"/realm-config/agents/OAuth2Client/{client_id}",
        )
        headers = get_headers("oauth")
        headers = {**headers, **self.build_auth_headers(token)}
        try:
            response = self.make_http_request(url, "GET", headers)
            data = response.json()
            data.pop("_rev", None)
            return data
        except Exception as e:
            error(f"Failed to fetch OAuth client {client_id}: {str(e)}")
<<<<<<< HEAD
            if not self.continue_on_error:
                raise
            return {}
=======
            if getattr(self, "continue_on_error", False):
                return {}
            raise
>>>>>>> 8dc291c548055214e3452c4e135d037eaf02a366

    def _discover_provider_service_endpoints(
        self, token: str, base_url: str
    ) -> list[str]:
        """Discover OAuth/OIDC provider service endpoints from realm services."""
        headers = get_headers("oauth")
        headers = {**headers, **self.build_auth_headers(token)}
        list_ep = (
            f"/am/json/realms/root/realms/{self.realm}/"
            "realm-config/services?_queryFilter=true"
        )
        list_url = self._construct_api_url(base_url, list_ep)
        response = self.make_http_request(list_url, "GET", headers)
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get("result"), list):
            return []

        endpoints: list[str] = []
        for item in data["result"]:
            if not isinstance(item, dict):
                continue
            sid = item.get("_id")
            if not isinstance(sid, str):
                continue
            lower = sid.lower()
            if "oauth" in lower or "oidc" in lower or "openid" in lower:
                endpoints.append(
                    f"/am/json/realms/root/realms/{self.realm}/realm-config/services/{sid}"
                )
        return endpoints

    def fetch_oauth_provider_data(self, token: str, base_url: str) -> Dict[str, Any]:
        """Fetch OAuth/OIDC provider configuration for a realm."""
        headers = get_headers("oauth")
        headers = {**headers, **self.build_auth_headers(token)}
        endpoints: list[str] = []
        try:
            endpoints = self._discover_provider_service_endpoints(token, base_url)
        except Exception:
            if not self.continue_on_error:
                raise
            return {}

        if not endpoints:
            return {}

        last_error = ""
        for ep in endpoints:
            try:
                url = self._construct_api_url(base_url, ep)
                response = self.make_http_request(url, "GET", headers)
                data = response.json()
                if isinstance(data, dict):
                    data.pop("_rev", None)
                    return data
            except Exception as e:
                last_error = str(e)
                continue

        if last_error:
<<<<<<< HEAD
            warning(f"Failed to fetch OAuth provider config: {last_error}")
            if not self.continue_on_error:
                raise Exception(last_error)
=======
            if getattr(self, "continue_on_error", False):
                warning(f"Failed to fetch OAuth provider config: {last_error}")
            else:
                error(f"Failed to fetch OAuth provider config: {last_error}")
                raise RuntimeError(last_error) from None
>>>>>>> 8dc291c548055214e3452c4e135d037eaf02a366
        return {}


def create_oauth_export_command():
    """Create the OAuth export command function"""

    def export_oauth(
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
        continue_on_error: ContinueOnErrorOpt = False,
    ):
        """Export OAuth2 clients configuration with script dependencies"""

        exporter = OAuthExporter(realm=realm)
        exporter.continue_on_error = continue_on_error

        headers = get_headers("oauth")

        exporter.export_data(
            command_name="oauth",
            api_endpoint=(
                f"/am/json/realms/root/realms/{realm}/realm-config/"
                "agents/OAuth2Client?_queryFilter=true"
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
            response_filter=process_oauth_response(exporter, realm),
        )

        # ✅ FIXED BLOCK STARTS HERE
        token, api_base_url = exporter.get_current_auth()

        try:
            list_url = exporter._construct_api_url(
                api_base_url,
                f"/am/json/realms/root/realms/{realm}/realm-config/agents/OAuth2Client?_queryFilter=true",
            )

            headers = {**get_headers("oauth"), **exporter.build_auth_headers(token)}

            response = exporter.make_http_request(list_url, "GET", headers)
            list_data = response.json()

            if not isinstance(list_data, dict) or "result" not in list_data:
                error("Invalid response format from OAuth clients list")
                return

            oauth_clients = list_data["result"]

            info("Fetching OAuth2 clients data...\n")

            complete_clients = []
            all_script_ids = set()

            for client in oauth_clients:
                client_id = client.get("_id")
                if not client_id:
                    warning("Skipping client without _id")
                    continue

                complete_client = exporter.fetch_oauth_client_data(
                    client_id, token, api_base_url
                )

                if complete_client:
                    complete_clients.append(complete_client)
                    script_ids = exporter.extract_script_ids(complete_client)
                    all_script_ids.update(script_ids)

            scripts_data = []
            for script_id in all_script_ids:
                if script_id in IGNORED_SCRIPT_IDS:
                    continue

                script_data = exporter.fetch_script_data(
                    script_id, token, api_base_url
                )
                if script_data:
                    scripts_data.append(script_data)

            from datetime import datetime, timezone

            combined_data = {"clients": complete_clients, "scripts": scripts_data}

            export_data = {
                "metadata": {
                    "export_type": "oauth",
                    "realm": realm,
                    "timestamp": datetime.now(timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "version": None,
                    "total_items": len(complete_clients),
                },
                "data": combined_data,
            }

            if view:
                exporter._handle_view_mode(export_data, "oauth", view_columns)
                return

            file_path = exporter.save_response(
                data=export_data,
                command_name="oauth",
                output_dir=output_dir,
                output_file=output_file,
                version=version,
                no_version=no_version,
                branch=branch,
                commit_message=commit,
            )

            if exporter._get_storage_mode() == "local" and file_path:
                hash_value = exporter.hash_manager.create_hash(combined_data, "oauth")
                exporter.hash_manager.save_export_hash(
                    "oauth", hash_value, file_path
                )

            print()
            info("OAuth2 clients exported successfully")

        except Exception as e:
            error(f"OAuth export failed: {str(e)}")
            if not continue_on_error:
                raise typer.Exit(1)
            return

    return export_oauth
