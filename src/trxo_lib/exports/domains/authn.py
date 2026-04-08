"""
Authentication settings export command (authn).

Exports realm authentication settings from realm:
  GET /am/json/realms/root/realms/{realm-name}/realm-config/authentication
"""

from trxo_lib.config.api_headers import get_headers
from trxo_lib.config.constants import DEFAULT_REALM

from trxo_lib.exports.processor import BaseExporter
from typing import Any


class AuthnExportService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        realm = self.kwargs.get("realm", DEFAULT_REALM)
        exporter = BaseExporter()
        headers = get_headers("authn")

        safe_kwargs = self.kwargs.copy()
        if "commit" in safe_kwargs:
            safe_kwargs["commit_message"] = safe_kwargs.pop("commit")

        return exporter.export_data(
            command_name="authn",
            api_endpoint=f"/am/json/realms/root/realms/{realm}/realm-config/authentication",
            headers=headers,
            **safe_kwargs,
        )
