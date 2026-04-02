"""
Managed objects export command.

This module provides export functionality for PingOne Advanced Identity Cloud managed objects.
Exports from /openidm/config/managed endpoint.
"""

from typing import Any
from trxo_lib.config.api_headers import get_headers
from trxo_lib.operations.export.base_exporter import BaseExporter


class ManagedExportService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        exporter = BaseExporter()
        headers = get_headers("managed")

        safe_kwargs = self.kwargs.copy()
        if "commit" in safe_kwargs:
            safe_kwargs["commit_message"] = safe_kwargs.pop("commit")

        return exporter.export_data(
            command_name="managed",
            api_endpoint="/openidm/config/managed",
            headers=headers,
            **safe_kwargs,
        )
