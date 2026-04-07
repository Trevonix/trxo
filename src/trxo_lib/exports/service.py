"""
Export Service entry point.

Provides a clean interface for CLI tools to access export functions.
"""

from typing import Any

from trxo_lib.exports.domains.scripts import ScriptsExportService
from trxo_lib.exports.domains.mappings import MappingsExportService
from trxo_lib.exports.domains.applications import ApplicationsExportService
from trxo_lib.exports.domains.managed import ManagedExportService
from trxo_lib.exports.domains.oauth import OauthExportService
from trxo_lib.exports.domains.saml import SamlExportService
from trxo_lib.exports.domains.journeys import JourneysExportService
from trxo_lib.exports.domains.services import ServicesExportService
from trxo_lib.exports.domains.policies import PoliciesExportService
from trxo_lib.exports.domains.authn import AuthnExportService
from trxo_lib.exports.domains.agents import (
    AgentsGatewayExportService,
    AgentsJavaExportService,
    AgentsWebExportService,
)
from trxo_lib.exports.domains.email_templates import EmailTemplatesExportService
from trxo_lib.exports.domains.endpoints import EndpointsExportService
from trxo_lib.exports.domains.connectors import ConnectorsExportService
from trxo_lib.exports.domains.esv import (
    EsvSecretsExportService,
    EsvVariablesExportService,
)
from trxo_lib.exports.domains.privileges import PrivilegesExportService
from trxo_lib.exports.domains.realms import RealmsExportService
from trxo_lib.exports.domains.themes import ThemesExportService
from trxo_lib.exports.domains.webhooks import WebhooksExportService


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

    def export_managed(self, **kwargs) -> Any:
        return ManagedExportService(**kwargs).execute()

    def export_oauth(self, **kwargs) -> Any:
        return OauthExportService(**kwargs).execute()

    def export_saml(self, **kwargs) -> Any:
        return SamlExportService(**kwargs).execute()

    def export_journeys(self, **kwargs) -> Any:
        return JourneysExportService(**kwargs).execute()

    def export_services(self, **kwargs) -> Any:
        return ServicesExportService(**kwargs).execute()

    def export_policies(self, **kwargs) -> Any:
        return PoliciesExportService(**kwargs).execute()

    def export_authn(self, **kwargs) -> Any:
        return AuthnExportService(**kwargs).execute()

    def export_agents_gateway(self, **kwargs) -> Any:
        return AgentsGatewayExportService(**kwargs).execute()

    def export_agents_java(self, **kwargs) -> Any:
        return AgentsJavaExportService(**kwargs).execute()

    def export_agents_web(self, **kwargs) -> Any:
        return AgentsWebExportService(**kwargs).execute()

    def export_email_templates(self, **kwargs) -> Any:
        return EmailTemplatesExportService(**kwargs).execute()

    def export_endpoints(self, **kwargs) -> Any:
        return EndpointsExportService(**kwargs).execute()

    def export_connectors(self, **kwargs) -> Any:
        return ConnectorsExportService(**kwargs).execute()

    def export_esv_secrets(self, **kwargs) -> Any:
        return EsvSecretsExportService(**kwargs).execute()

    def export_esv_variables(self, **kwargs) -> Any:
        return EsvVariablesExportService(**kwargs).execute()

    def export_privileges(self, **kwargs) -> Any:
        return PrivilegesExportService(**kwargs).execute()

    def export_realms(self, **kwargs) -> Any:
        return RealmsExportService(**kwargs).execute()

    def export_themes(self, **kwargs) -> Any:
        return ThemesExportService(**kwargs).execute()

    def export_webhooks(self, **kwargs) -> Any:
        return WebhooksExportService(**kwargs).execute()
