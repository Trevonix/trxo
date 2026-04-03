"""
Import Service entry point.

Provides a clean interface for CLI tools to access import functions.
"""

from typing import Any

from trxo_lib.operations.imports.scripts import ScriptsImportService
from trxo_lib.operations.imports.applications import ApplicationsImportService
from trxo_lib.operations.imports.authn import AuthnImportService


class ImportService:
    def import_scripts(self, **kwargs) -> Any:
        """
        Import scripts execution endpoint.
        Receives arguments and passes them to ScriptsImportService for execution.
        """
        return ScriptsImportService(**kwargs).execute()

    def import_applications(self, **kwargs) -> Any:
        return ApplicationsImportService(**kwargs).execute()

    def import_authn(self, **kwargs) -> Any:
        return AuthnImportService(**kwargs).execute()
