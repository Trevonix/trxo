"""
Mappings export command.

This module provides export functionality for PingOne Advanced Identity Cloud sync mappings.
Exports from /openidm/config/sync endpoint.
"""

from typing import Any
from trxo_lib.config.api_headers import get_headers
from trxo_lib.exports.processor import BaseExporter


class MappingsExportService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        exporter = BaseExporter()
        headers = get_headers("mappings")

        kwargs = self.kwargs.copy()
        if "commit" in kwargs:
            kwargs["commit_message"] = kwargs.pop("commit")

        return exporter.export_data(
            command_name="mappings",
            api_endpoint="/openidm/config/sync",
            headers=headers,
            **kwargs,
        )
