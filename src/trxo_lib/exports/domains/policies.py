"""
Policies export command.

This module provides export functionality for PingOne Advanced Identity Cloud policies.
Exports from /am/json/realms/root/realms/alpha/policies?_queryFilter=true endpoint.
"""

from typing import Any

from trxo_lib.config.api_headers import get_headers
from trxo_lib.config.constants import DEFAULT_REALM
from trxo.utils.console import error

from trxo_lib.exports.processor import BaseExporter


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


class PoliciesExportService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        realm = self.kwargs.get("realm", DEFAULT_REALM)
        exporter = PoliciesExporter(realm=realm)
        headers = get_headers("policies")

        safe_kwargs = self.kwargs.copy()
        if "commit" in safe_kwargs:
            safe_kwargs["commit_message"] = safe_kwargs.pop("commit")

        return exporter.export_data(
            command_name="policies",
            api_endpoint=f"/am/json/realms/root/realms/{realm}/policies?_queryFilter=true",
            headers=headers,
            response_filter=process_policies_response(exporter, realm),
            **safe_kwargs,
        )
