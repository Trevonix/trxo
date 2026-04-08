"""
Agents import commands.

Import functionality for PingOne Advanced Identity Cloud agents.
"""

from trxo_lib.exceptions import TrxoAbort
import json
from typing import Any, Dict, List, Optional


from trxo_lib.config.api_headers import get_headers
from trxo_lib.config.constants import DEFAULT_REALM
from trxo.utils.console import error, info

from trxo_lib.imports.processor import BaseImporter

# Base path template
AGENTS_BASE = "/am/json/realms/root/realms/{realm}/realm-config/agents"


class AgentsImporter(BaseImporter):
    """Generic importer for AM Agents of a specific type."""

    def __init__(self, agent_type: str, realm: str = DEFAULT_REALM):
        super().__init__()
        self.agent_type = agent_type
        self.realm = realm

    def get_required_fields(self) -> List[str]:
        # For create, AM typically needs an identifier; we do not hard-enforce here
        # because user may include _id in payload or type-specific fields.
        return []

    def get_item_type(self) -> str:
        if self.agent_type == "WebAgent":
            return "agents_web"
        elif self.agent_type == "J2EEAgent":
            return "agents_java"
        elif self.agent_type == "IdentityGatewayAgent":
            return "agents_gateway"

        return "agents"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/realm-config/agents/{self.agent_type}/{item_id}",
        )

    def _build_payload(self, item_data: Dict[str, Any]) -> str:

        forbidden_fields = {
            "_rev",
            "_type",
            "repositoryLocation",
            "disableJwtAudit",
            "jwtAuditWhitelist",
            "secretLabelIdentifier",
        }

        def clean(data):

            if isinstance(data, dict):
                cleaned = {}

                for k, v in data.items():

                    if k in forbidden_fields:
                        continue

                    # remove null / empty values
                    if v is None or v == [] or v == {}:
                        continue

                    cleaned_value = clean(v)

                    if cleaned_value not in (None, "", [], {}):
                        cleaned[k] = cleaned_value

                return cleaned

            if isinstance(data, list):
                cleaned_list = [clean(v) for v in data if v not in (None, [], {})]
                return [v for v in cleaned_list if v not in (None, "", [], {})]

            return data

        filtered = clean(item_data)

        return json.dumps(filtered)

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:

        item_id = item_data.get("_id")

        if not item_id:
            error("Agent missing '_id'; required for upsert")
            return False

        update_url = self.get_api_endpoint(item_id, base_url)

        headers = get_headers("agents")
        headers = {**headers, **self.build_auth_headers(token)}

        payload = self._build_payload(item_data)

        try:
            self.make_http_request(update_url, "PUT", headers, payload)

            info(f"Upserted {self.agent_type} agent: {item_id}")
            return True

        except Exception as e:
            error(f"Failed to upsert {self.agent_type} agent '{item_id}' : {e}")
            return False

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete an agent via API"""
        url = self.get_api_endpoint(item_id, base_url)

        headers = get_headers("agents")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "DELETE", headers)
            info(f"Successfully deleted {self.agent_type}: {item_id}")
            return True
        except Exception as e:
            error(f"Failed to delete {self.agent_type} '{item_id}': {e}")
            return False


def create_agents_callback():
    """Create agents callback function for import group"""

    def agents_callback(ctx=None):
        if getattr(ctx, "invoked_subcommand", None) is None:
            from trxo.utils.console import console, info, warning

            console.print()
            warning("No agents subcommand selected.")
            info("Agents has three subcommands:")
            info("  • gateway")
            info("  • java")
            info("  • web")
            console.print()
            info("Run one of:")
            info("  trxo import agent gateway --help")
            info("  trxo import agent java --help")
            info("  trxo import agent web --help")
            console.print()
            info("Tip: use --help on any command to see options.")
            console.print()
            raise TrxoAbort(code=0)

    return agents_callback


class AgentsImportService:
    """Service wrapper for agents import operations."""

    def __init__(self, agent_type: str, **kwargs):
        self.agent_type = agent_type
        self.kwargs = kwargs

    def execute(self) -> Any:
        from trxo_lib.config.constants import DEFAULT_REALM
        realm = self.kwargs.get('realm', DEFAULT_REALM)
        importer = AgentsImporter(agent_type=self.agent_type, realm=realm)

        # Typer passes 'file' which maps to 'file_path' in BaseImporter
        if 'file' in self.kwargs:
            self.kwargs['file_path'] = self.kwargs.pop('file')

        return importer.import_from_file(**self.kwargs)
