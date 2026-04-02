"""
Export Service entry point.

Provides a clean interface for CLI tools to access export functions.
"""

from typing import Any

from trxo_lib.operations.export.scripts import ScriptsExportService


class ExportService:
    def export_scripts(self, **kwargs) -> Any:
        """
        Export scripts execution endpoint.
        Receives arguments and passes them to ScriptsExportService for execution.
        """
        return ScriptsExportService(**kwargs).execute()
