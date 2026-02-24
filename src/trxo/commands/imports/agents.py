"""
Agents import commands.

Import functionality for PingOne Advanced Identity Cloud agents.
"""

import json
from typing import List, Dict, Any
import typer
from trxo.utils.console import error, info
from .base_importer import BaseImporter
from trxo.constants import DEFAULT_REALM


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
        return f"{self.agent_type} agents"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        """Return the full endpoint for a specific agent id."""
        base_path = AGENTS_BASE.format(realm=self.realm)
        base = self._construct_api_url(base_url, f"{base_path}/{self.agent_type}")
        return f"{base}/{item_id}"

    def _build_payload(self, item_data: Dict[str, Any]) -> str:
        # Remove _rev only, keep all other fields as-is (including _id)
        filtered = {k: v for k, v in item_data.items() if k != "_rev"}
        return json.dumps(filtered)

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Upsert agent with PUT semantics only."""
        item_id = item_data.get("_id")
        if not item_id:
            error("Agent missing '_id'; required for upsert (PUT)")
            return False

        url = self.get_api_endpoint(item_id, base_url)
        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}
        payload = self._build_payload(item_data)

        try:
            self.make_http_request(url, "PUT", headers, payload)
            info(f"Upserted {self.agent_type} agent: {item_id}")
            return True
        except Exception as e:
            error(f"Failed to upsert {self.agent_type} agent '{item_id}' : {e}")
            return False


def create_agents_import_command():
    """Create the agents import subcommands (gateway, java, web)."""

    def import_identity_gateway_agents(
        file: str = typer.Option(
            None,
            "--file",
            help="Path to JSON file containing Identity Gateway agents",
        ),
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Target realm name (default: {DEFAULT_REALM})",
        ),
        cherry_pick: str = typer.Option(
            None, "--cherry-pick", help="Cherry-pick specific agents by ID"
        ),
        jwk_path: str = typer.Option(
            None, "--jwk-path", help="Path to JWK private key file"
        ),
        sa_id: str = typer.Option(None, "--sa-id", help="Service Account ID"),
        base_url: str = typer.Option(
            None,
            "--base-url",
            help="Base URL for PingOne Advanced Identity Cloud instance",
        ),
        project_name: str = typer.Option(
            None, "--project-name", help="Project name for argument mode (optional)"
        ),
        auth_mode: str = typer.Option(
            None, "--auth-mode", help="Auth mode override: service-account|onprem"
        ),
        onprem_username: str = typer.Option(
            None, "--onprem-username", help="On-Prem username"
        ),
        onprem_password: str = typer.Option(
            None, "--onprem-password", help="On-Prem password", hide_input=True
        ),
        onprem_realm: str = typer.Option(
            "root", "--onprem-realm", help="On-Prem realm"
        ),
        am_base_url: str = typer.Option(

            None, "--am-base-url", help="On-Prem AM base URL"

        ),
        idm_base_url: str = typer.Option(
            None, "--idm-base-url", help="On-Prem IDM base URL"
        ),
        idm_username: str = typer.Option(
            None, "--idm-username", help="On-Prem IDM username"
        ),
        idm_password: str = typer.Option(
            None, "--idm-password", help="On-Prem IDM password", hide_input=True
        ),
        force_import: bool = typer.Option(
            False,
            "--force-import",
            "-f",
            help="Skip hash validation and force import",
        ),
        diff: bool = typer.Option(
            False, "--diff", help="Show differences before import"
        ),
        branch: str = typer.Option(
            None, "--branch", help="Git branch to import from (Git mode only)"
        ),
    ):
        importer = AgentsImporter("IdentityGatewayAgent", realm=realm)
        importer.import_from_file(
            file_path=file,
            realm=realm,
            jwk_path=jwk_path,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            idm_base_url=idm_base_url,
            idm_username=idm_username,
            idm_password=idm_password, am_base_url=am_base_url,
            force_import=force_import,
            branch=branch,
            cherry_pick=cherry_pick,
            diff=diff,
        )

    def import_java_agents(
        file: str = typer.Option(
            None, "--file", help="Path to JSON file containing Java agents"
        ),
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Target realm name (default: {DEFAULT_REALM})",
        ),
        cherry_pick: str = typer.Option(
            None, "--cherry-pick", help="Cherry-pick specific agents by ID"
        ),
        jwk_path: str = typer.Option(
            None, "--jwk-path", help="Path to JWK private key file"
        ),
        sa_id: str = typer.Option(None, "--sa-id", help="Service Account ID"),
        base_url: str = typer.Option(
            None,
            "--base-url",
            help="Base URL for PingOne Advanced Identity Cloud instance",
        ),
        project_name: str = typer.Option(
            None, "--project-name", help="Project name for argument mode (optional)"
        ),
        auth_mode: str = typer.Option(
            None, "--auth-mode", help="Auth mode override: service-account|onprem"
        ),
        onprem_username: str = typer.Option(
            None, "--onprem-username", help="On-Prem username"
        ),
        onprem_password: str = typer.Option(
            None, "--onprem-password", help="On-Prem password", hide_input=True
        ),
        onprem_realm: str = typer.Option(
            "root", "--onprem-realm", help="On-Prem realm"
        ),
        am_base_url: str = typer.Option(

            None, "--am-base-url", help="On-Prem AM base URL"

        ),
        idm_base_url: str = typer.Option(
            None, "--idm-base-url", help="On-Prem IDM base URL"
        ),
        idm_username: str = typer.Option(
            None, "--idm-username", help="On-Prem IDM username"
        ),
        idm_password: str = typer.Option(
            None, "--idm-password", help="On-Prem IDM password", hide_input=True
        ),
        force_import: bool = typer.Option(
            False,
            "--force-import",
            "-f",
            help="Skip hash validation and force import",
        ),
        diff: bool = typer.Option(
            False, "--diff", help="Show differences before import"
        ),
        branch: str = typer.Option(
            None, "--branch", help="Git branch to import from (Git mode only)"
        ),
    ):
        importer = AgentsImporter("J2EEAgent", realm=realm)
        importer.import_from_file(
            file_path=file,
            realm=realm,
            jwk_path=jwk_path,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            idm_base_url=idm_base_url,
            idm_username=idm_username,
            idm_password=idm_password, am_base_url=am_base_url,
            force_import=force_import,
            branch=branch,
            cherry_pick=cherry_pick,
            diff=diff,
        )

    def import_web_agents(
        file: str = typer.Option(
            None, "--file", help="Path to JSON file containing Web agents"
        ),
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Target realm name (default: {DEFAULT_REALM})",
        ),
        cherry_pick: str = typer.Option(
            None, "--cherry-pick", help="Cherry-pick specific agents by ID"
        ),
        jwk_path: str = typer.Option(
            None, "--jwk-path", help="Path to JWK private key file"
        ),
        sa_id: str = typer.Option(None, "--sa-id", help="Service Account ID"),
        base_url: str = typer.Option(
            None,
            "--base-url",
            help="Base URL for PingOne Advanced Identity Cloud instance",
        ),
        project_name: str = typer.Option(
            None, "--project-name", help="Project name for argument mode (optional)"
        ),
        auth_mode: str = typer.Option(
            None, "--auth-mode", help="Auth mode override: service-account|onprem"
        ),
        onprem_username: str = typer.Option(
            None, "--onprem-username", help="On-Prem username"
        ),
        onprem_password: str = typer.Option(
            None, "--onprem-password", help="On-Prem password", hide_input=True
        ),
        onprem_realm: str = typer.Option(
            "root", "--onprem-realm", help="On-Prem realm"
        ),
        am_base_url: str = typer.Option(

            None, "--am-base-url", help="On-Prem AM base URL"

        ),
        idm_base_url: str = typer.Option(
            None, "--idm-base-url", help="On-Prem IDM base URL"
        ),
        idm_username: str = typer.Option(
            None, "--idm-username", help="On-Prem IDM username"
        ),
        idm_password: str = typer.Option(
            None, "--idm-password", help="On-Prem IDM password", hide_input=True
        ),
        force_import: bool = typer.Option(
            False,
            "--force-import",
            "-f",
            help="Skip hash validation and force import",
        ),
        diff: bool = typer.Option(
            False, "--diff", help="Show differences before import"
        ),
        branch: str = typer.Option(
            None, "--branch", help="Git branch to import from (Git mode only)"
        ),
    ):
        importer = AgentsImporter("WebAgent", realm=realm)
        importer.import_from_file(
            file_path=file,
            realm=realm,
            jwk_path=jwk_path,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            idm_base_url=idm_base_url,
            idm_username=idm_username,
            idm_password=idm_password, am_base_url=am_base_url,
            force_import=force_import,
            branch=branch,
            diff=diff,
            cherry_pick=cherry_pick,
        )

    return (
        import_identity_gateway_agents,
        import_java_agents,
        import_web_agents,
    )


def create_agents_callback():
    """Create agents callback function for import group"""

    def agents_callback(ctx: typer.Context):
        if ctx.invoked_subcommand is None:
            from trxo.utils.console import console, warning, info

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
            raise typer.Exit(code=0)

    return agents_callback
