"""
Themes export service.
"""

from typing import Any
from trxo_lib.config.api_headers import get_headers
from trxo_lib.operations.export.base_exporter import BaseExporter


class ThemesExportService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        realm = self.kwargs.get("realm")
        exporter = BaseExporter()
        headers = get_headers("themes")

        endpoint = (
            "/openidm/config/ui/themerealm"
            if not realm
            else f"/openidm/config/ui/themerealm?_fields=realm/{realm}"
        )

        safe_kwargs = self.kwargs.copy()
        if "commit" in safe_kwargs:
            safe_kwargs["commit_message"] = safe_kwargs.pop("commit")

        return exporter.export_data(
            command_name="themes", api_endpoint=endpoint, headers=headers, **safe_kwargs
        )
