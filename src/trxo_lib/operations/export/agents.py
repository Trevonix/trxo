"""
Agents export commands.

This module provides export functionality for PingOne Advanced Identity
Cloud Identity Gateway, java and web agents.
"""

from typing import Any
from trxo_lib.config.api_headers import get_headers
from trxo_lib.constants import DEFAULT_REALM
from trxo_lib.operations.export.base_exporter import BaseExporter


class AgentsGatewayExportService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        realm = self.kwargs.get("realm", DEFAULT_REALM)
        exporter = BaseExporter()
        headers = get_headers("agents")

        safe_kwargs = self.kwargs.copy()
        if "commit" in safe_kwargs:
            safe_kwargs["commit_message"] = safe_kwargs.pop("commit")

        return exporter.export_data(
            command_name="agents_gateway",
            api_endpoint=(
                f"/am/json/realms/root/realms/{realm}/realm-config/agents/"
                "IdentityGatewayAgent?_queryFilter=true"
            ),
            headers=headers,
            **safe_kwargs,
        )


class AgentsJavaExportService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        realm = self.kwargs.get("realm", DEFAULT_REALM)
        exporter = BaseExporter()
        headers = get_headers("agents")

        safe_kwargs = self.kwargs.copy()
        if "commit" in safe_kwargs:
            safe_kwargs["commit_message"] = safe_kwargs.pop("commit")

        return exporter.export_data(
            command_name="agents_java",
            api_endpoint=(
                f"/am/json/realms/root/realms/{realm}/realm-config/agents/"
                "J2EEAgent?_queryFilter=true"
            ),
            headers=headers,
            **safe_kwargs,
        )


class AgentsWebExportService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        realm = self.kwargs.get("realm", DEFAULT_REALM)
        exporter = BaseExporter()
        headers = get_headers("agents")

        safe_kwargs = self.kwargs.copy()
        if "commit" in safe_kwargs:
            safe_kwargs["commit_message"] = safe_kwargs.pop("commit")

        return exporter.export_data(
            command_name="agents_web",
            api_endpoint=(
                f"/am/json/realms/root/realms/{realm}/realm-config/agents/"
                "WebAgent?_queryFilter=true"
            ),
            headers=headers,
            **safe_kwargs,
        )
