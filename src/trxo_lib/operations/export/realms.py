"""
Realms export service.
"""

from typing import Any
from trxo_lib.config.api_headers import get_headers
from trxo_lib.operations.export.base_exporter import BaseExporter


class RealmsExportService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        exporter = BaseExporter()
        headers = get_headers("realms")

        safe_kwargs = self.kwargs.copy()
        if "commit" in safe_kwargs:
            safe_kwargs["commit_message"] = safe_kwargs.pop("commit")

        return exporter.export_data(
            command_name="realms",
            api_endpoint="/am/json/global-config/realms?_queryFilter=true",
            headers=headers,
            **safe_kwargs,
        )
