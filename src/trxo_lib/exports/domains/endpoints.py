"""
Endpoints export command.

This module provides export functionality for PingOne Advanced Identity Cloud custom endpoints.
Filters /openidm/config?_queryFilter=true to only include items with _id containing "endpoint/".
"""

from typing import Any
from trxo_lib.config.api_headers import get_headers
from trxo_lib.exports.processor import BaseExporter


class EndpointsExportService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        exporter = BaseExporter()
        headers = get_headers("endpoints")

        safe_kwargs = self.kwargs.copy()
        if "commit" in safe_kwargs:
            safe_kwargs["commit_message"] = safe_kwargs.pop("commit")

        return exporter.export_data(
            command_name="endpoints",
            api_endpoint='/openidm/config?_queryFilter=_id sw "endpoint"',
            headers=headers,
            **safe_kwargs,
        )
