"""
Import Service entry point.

Provides a clean interface for CLI tools to access import functions.
"""

from typing import Any

from trxo_lib.operations.imports.scripts import ScriptsImportService
from trxo_lib.operations.imports.applications import ApplicationsImportService
from trxo_lib.operations.imports.authn import AuthnImportService
from trxo_lib.operations.imports.managed import ManagedImportService
from trxo_lib.operations.imports.journeys import JourneyImportService
from trxo_lib.operations.imports.mappings import MappingsImportService
from trxo_lib.operations.imports.oauth import OAuthImportService
from trxo_lib.operations.imports.privileges import PrivilegesImportService
from trxo_lib.operations.imports.policies import PoliciesImportService
from trxo_lib.operations.imports.saml import SamlImportService
from trxo_lib.operations.imports.services import ServicesImportService
from trxo_lib.operations.imports.themes import ThemesImportService
from trxo_lib.operations.imports.agents import AgentsImportService
from trxo_lib.operations.imports.connectors import ConnectorsImportService
from trxo_lib.operations.imports.email_templates import EmailTemplatesImportService
from trxo_lib.operations.imports.endpoints import EndpointsImportService
from trxo_lib.operations.imports.webhooks import WebhooksImportService


class ImportService:
    def import_scripts(self, **kwargs) -> Any:
        return ScriptsImportService(**kwargs).execute()

    def import_applications(self, **kwargs) -> Any:
        return ApplicationsImportService(**kwargs).execute()

    def import_authn(self, **kwargs) -> Any:
        return AuthnImportService(**kwargs).execute()

    def import_managed(self, **kwargs) -> Any:
        return ManagedImportService(**kwargs).execute()

    def import_journeys(self, **kwargs) -> Any:
        return JourneyImportService(**kwargs).execute()

    def import_oauth(self, **kwargs) -> Any:
        return OAuthImportService(**kwargs).execute()

    def import_policies(self, **kwargs) -> Any:
        return PoliciesImportService(**kwargs).execute()

    def import_saml(self, **kwargs) -> Any:
        return SamlImportService(**kwargs).execute()

    def import_services(self, **kwargs) -> Any:
        return ServicesImportService(**kwargs).execute()

    def import_themes(self, **kwargs) -> Any:
        return ThemesImportService(**kwargs).execute()

    def import_agents(self, agent_type: str, **kwargs) -> Any:
        return AgentsImportService(agent_type=agent_type, **kwargs).execute()

    def import_connectors(self, **kwargs) -> Any:
        return ConnectorsImportService(**kwargs).execute()

    def import_email_templates(self, **kwargs) -> Any:
        return EmailTemplatesImportService(**kwargs).execute()

    def import_endpoints(self, **kwargs) -> Any:
        return EndpointsImportService(**kwargs).execute()

    def import_mappings(self, **kwargs) -> Any:
        return MappingsImportService(**kwargs).execute()

    def import_privileges(self, **kwargs) -> Any:
        return PrivilegesImportService(**kwargs).execute()

    def import_webhooks(self, **kwargs) -> Any:
        return WebhooksImportService(**kwargs).execute()
