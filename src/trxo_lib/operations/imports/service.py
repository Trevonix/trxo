"""
Import Service entry point.

Provides a clean interface for CLI tools to access import functions.
"""

from typing import Any

from trxo_lib.operations.imports.scripts import ScriptsImportService


class ImportService:
    def import_scripts(self, **kwargs) -> Any:
        """
        Import scripts execution endpoint.
        Receives arguments and passes them to ScriptsImportService for execution.
        """
        return ScriptsImportService(**kwargs).execute()
