"""
OAuth export commands.

This module provides export functionality for
PingOne Advanced Identity Cloud OAuth2 clients with script dependencies.
"""

import base64
from typing import Any, Dict, Set

from trxo_lib.config.api_headers import get_headers
from trxo_lib.config.constants import DEFAULT_REALM, IGNORED_SCRIPT_IDS
from trxo.utils.console import error, info, warning

from trxo_lib.exports.processor import BaseExporter


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
            # Handle 403 Forbidden gracefully (likely internal/protected scripts)
            if "403" in str(e) or "Forbidden" in str(e):
                # warning(f"Skipping script {script_id}: Access denied (likely internal)")
                return {}

            error(f"Failed to fetch script {script_id}: {str(e)}")
            return {}

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
            return {}

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
            warning(f"Failed to fetch OAuth provider config: {last_error}")
        return {}


class OauthExportService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        realm = self.kwargs.get("realm", DEFAULT_REALM)
        exporter = OAuthExporter(realm=realm)
        headers = get_headers("oauth")

        safe_kwargs = self.kwargs.copy()
        if "commit" in safe_kwargs:
            safe_kwargs["commit_message"] = safe_kwargs.pop("commit")

        return exporter.export_data(
            command_name="oauth",
            api_endpoint=(
                f"/am/json/realms/root/realms/{realm}/realm-config/"
                "agents/OAuth2Client?_queryFilter=true"
            ),
            headers=headers,
            response_filter=process_oauth_response(exporter, realm),
            **safe_kwargs,
        )
