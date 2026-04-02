"""
Export Service entry point.

Provides a clean interface for CLI tools to access export functions.
"""

from typing import Any

from trxo_lib.operations.export.scripts import ScriptsExportService
from trxo_lib.operations.export.mappings import MappingsExportService
from trxo_lib.operations.export.applications import ApplicationsExportService


class ExportService:
    def export_scripts(self, **kwargs) -> Any:
        """
        Export scripts execution endpoint.
        Receives arguments and passes them to ScriptsExportService for execution.
        """
        return ScriptsExportService(**kwargs).execute()

    def export_mappings(self, **kwargs) -> Any:
        return MappingsExportService(**kwargs).execute()

    def export_applications(self, **kwargs) -> Any:
        return ApplicationsExportService(**kwargs).execute()
