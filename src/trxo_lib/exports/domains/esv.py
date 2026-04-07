"""
ESV export services.
"""

from typing import Any
from trxo_lib.config.api_headers import get_headers
from trxo_lib.exports.processor import BaseExporter


class EsvSecretsExportService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        exporter = BaseExporter()
        headers = get_headers("esv")

        safe_kwargs = self.kwargs.copy()
        if "commit" in safe_kwargs:
            safe_kwargs["commit_message"] = safe_kwargs.pop("commit")

        return exporter.export_data(
            command_name="esv_secrets",
            api_endpoint="/environment/secrets",
            headers=headers,
            **safe_kwargs,
        )


class EsvVariablesExportService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        exporter = BaseExporter()
        headers = get_headers("esv")

        safe_kwargs = self.kwargs.copy()
        if "commit" in safe_kwargs:
            safe_kwargs["commit_message"] = safe_kwargs.pop("commit")

        return exporter.export_data(
            command_name="esv_variables",
            api_endpoint="/environment/variables",
            headers=headers,
            **safe_kwargs,
        )
