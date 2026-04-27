"""
Data fetcher utility for diff functionality.

This module provides utilities to fetch current server data for comparison
by reusing the existing export functionality without saving files.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from trxo_lib.exports.processor import BaseExporter
from trxo_lib.exports.domains.oauth import OAuthExporter, process_oauth_response
from trxo_lib.exports.domains.policies import process_policies_response
from trxo_lib.exports.domains.saml import process_saml_response
from trxo_lib.exports.domains.services import services_response_filter
from trxo_lib.exports.domains.scripts import decode_script_response
from trxo_lib.config.api_headers import get_headers
from trxo_lib.config.constants import DEFAULT_REALM
from trxo_lib.logging import get_logger

logger = get_logger(__name__)


def _process_nodes_response(exporter: BaseExporter, realm: str):
    """Build a response-filter function for nodes endpoint.

    Nodes use POST action endpoint that returns all nodes.
    We return them organized by node ID.
    """

    def _filter(response_data: Any) -> Dict[str, Any]:
        # Extract items from response
        if isinstance(response_data, dict) and "result" in response_data:
            items = response_data["result"]
        elif isinstance(response_data, list):
            items = response_data
        else:
            items = []

        # Build mapping by node ID
        node_map = {}
        for node in items:
            if isinstance(node, dict) and "_id" in node:
                node_map[node["_id"]] = node

        return {"nodes": node_map}

    return _filter


def _process_email_templates_response(exporter: BaseExporter, realm: str):
    """Build a response-filter function for email_templates.

    Ensures the response is a list of items for the DiffEngine.
    """

    def _filter(response_data: Any) -> Dict[str, Any]:
        # Extract items from response
        if isinstance(response_data, dict) and "result" in response_data:
            items = response_data["result"]
        elif isinstance(response_data, list):
            items = response_data
        else:
            items = []

        # Return as a list under 'result' key so DiffEngine can extract it correctly
        return {"result": items}

    return _filter


def _fetch_nodes_direct(
    exporter: BaseExporter,
    realm: str,
    base_url: str,
    headers: Dict[str, str],
    command_name: str = "nodes",
) -> Optional[Dict[str, Any]]:
    """Fetch nodes/innerNodes directly using POST action endpoint.

    This bypasses export_data and makes a direct POST request to the
    nextdescendents action endpoint which is required for nodes.
    """
    try:
        # Both nodes and innerNodes use the same bulk fetch endpoint
        # The distinction (root vs inner) is made by the journey tree structure
        endpoint = (
            f"/am/json/realms/root/realms/{realm}"
            "/realm-config/authentication/authenticationtrees/nodes"
        )
        url = exporter._construct_api_url(base_url, endpoint)

        # Make POST request with nextdescendents action
        logger.info(f"Fetching {command_name} via POST {url}?_action=nextdescendents")
        resp = exporter.make_http_request(
            url + "?_action=nextdescendents", "POST", headers, "{}"
        )
        data = resp.json()

        # Extract items
        if isinstance(data, dict) and "result" in data:
            items = data.get("result", [])
        else:
            items = data if isinstance(data, list) else []

        # Return as mapping
        node_map = {}
        for node in items:
            if isinstance(node, dict) and "_id" in node:
                node_map[node["_id"]] = node

        logger.info(
            f"Fetched {len(node_map)} {command_name} from nextdescendents action"
        )

        # Return with appropriate key based on command_name
        return {command_name: node_map}
    except Exception as exc:
        logger.warning(f"Could not fetch {command_name} via nextdescendents: {exc}")
        return None


class DataFetcher:
    """Utility to fetch current server data for diff comparison"""

    def __init__(self):
        self.exporter = BaseExporter()

    def fetch_data(
        self,
        command_name: str,
        api_endpoint: str,
        realm: Optional[str] = None,
        jwk_path: Optional[str] = None,
        sa_id: Optional[str] = None,
        base_url: Optional[str] = None,
        project_name: Optional[str] = None,
        auth_mode: Optional[str] = None,
        onprem_username: Optional[str] = None,
        onprem_password: Optional[str] = None,
        onprem_realm: Optional[str] = None,
        idm_base_url: Optional[str] = None,
        idm_username: Optional[str] = None,
        idm_password: Optional[str] = None,
        am_base_url: Optional[str] = None,
        response_filter: Optional[callable] = None,
        branch: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch current server data using export functionality

        Args:
            command_name: Name of the command (e.g., 'journeys', 'scripts')
            api_endpoint: API endpoint to fetch from
            realm: Target realm
            jwk_path: Path to JWK file
            sa_id: Service account ID
            base_url: Base URL
            project_name: Project name
            auth_mode: Authentication mode
            onprem_username: On-premise AM username
            onprem_password: On-premise AM password
            onprem_realm: On-premise AM realm
            idm_base_url: On-premise IDM base URL
            idm_username: On-premise IDM username
            idm_password: On-premise IDM password
            am_base_url: On-premise AM base URL
            response_filter: Response filter function
            branch: Git branch (for Git mode)

        Returns:
            Dict containing the fetched data or None if failed
        """
        try:
            logger.info(f"Fetching current {command_name} data from server...")

            # Special handling for nodes - use direct POST action fetch
            if command_name == "nodes":
                # Initialize auth first
                token, api_base_url = self.exporter.initialize_auth(
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
                    idm_password=idm_password,
                    am_base_url=am_base_url,
                )

                # Build headers
                am_headers = get_headers("protocol_1_0")
                am_headers.update(self.exporter.build_auth_headers(token))

                # Fetch nodes directly via POST action
                result = _fetch_nodes_direct(
                    self.exporter,
                    realm or DEFAULT_REALM,
                    api_base_url,
                    am_headers,
                    command_name=command_name,
                )
                return result

            # Prepare headers with authentication
            # Headers are built inside export_data, we just provide the base ones
            
            if command_name == "nodes":
                response_filter = _process_nodes_response(self.exporter, realm)
            elif command_name == "email_templates":
                response_filter = _process_email_templates_response(
                    self.exporter, realm
                )
            elif command_name == "policies":
                from trxo_lib.exports.domains.policies import PoliciesExporter

                exporter = PoliciesExporter(realm=realm or DEFAULT_REALM)
                self.exporter = exporter
                response_filter = process_policies_response(
                    self.exporter, realm or DEFAULT_REALM
                )
            elif command_name == "oauth":
                exporter = OAuthExporter(realm=realm or DEFAULT_REALM)
                self.exporter = exporter
                response_filter = process_oauth_response(
                    self.exporter, realm or DEFAULT_REALM
                )
            elif command_name == "services":
                # For services, we need to pass scope and headers to the filter
                original_filter = response_filter
                response_filter = lambda data: original_filter(
                    data,
                    exporter=self.exporter,
                    scope="realm",
                    realm=realm or DEFAULT_REALM,
                    headers=get_headers("services"),
                )
            elif command_name == "saml":
                # For SAML, we need to initialize the filter with the exporter
                response_filter = process_saml_response(
                    self.exporter, realm or DEFAULT_REALM
                )

            # Suppress hash persistence: export_data calls
            # save_export_hash after every successful export, which would
            # overwrite the checksum stored for this command with the live
            # server's hash.  On the next real import the validator would
            # compare the file hash against the (now-wrong) server hash and
            # always fail.  We neutralise it for the duration of this call.
            original_save_export_hash = self.exporter.hash_manager.save_export_hash
            self.exporter.hash_manager.save_export_hash = lambda *a, **kw: None

            try:
                # Call export_data and capture the returned ExportResult
                result = self.exporter.export_data(
                    command_name=command_name,
                    api_endpoint=api_endpoint,
                    headers=get_headers(command_name),
                    view=False,  # Don't display
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
                    idm_password=idm_password,
                    am_base_url=am_base_url,
                    response_filter=response_filter,
                    branch=branch,
                    version=None,
                )

                if result and hasattr(result, "data"):
                    # The data is already filtered by export_data
                    if isinstance(result.data, dict) and "data" in result.data:
                        return result.data["data"]
                    return result.data
                return None

            finally:
                # Restore original methods
                self.exporter.hash_manager.save_export_hash = original_save_export_hash

        except Exception as e:
            logger.error(f"Failed to fetch {command_name} data: {str(e)}")
            return None

    def fetch_from_file_or_git(
        self,
        command_name: str,
        file_path: Optional[str] = None,
        branch: Optional[str] = None,
        project_name: Optional[str] = None,
        realm: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch data from local file or Git repository

        Args:
            command_name: Name of the command
            file_path: Path to local file (local mode)
            branch: Git branch (Git mode)
            project_name: Project name
            realm: Target realm

        Returns:
            Dict containing the data or None if failed
        """
        try:
            # Determine storage mode
            from trxo_lib.config.config_store import ConfigStore

            config_store = ConfigStore()
            storage_mode = self._get_storage_mode(config_store, project_name)

            if storage_mode == "git":
                return self._fetch_from_git(command_name, branch, project_name, realm)
            else:
                return self._fetch_from_local_file(file_path, command_name)

        except Exception as e:
            logger.error(f"Failed to fetch data from file/git: {str(e)}")
            return None

    def _get_storage_mode(
        self, config_store, project_name: Optional[str] = None
    ) -> str:
        """Get storage mode from project configuration"""
        try:
            current_project = project_name or config_store.get_current_project()
            if current_project:
                project_config = config_store.get_project_config(current_project)
                return (
                    project_config.get("storage_mode", "local")
                    if project_config
                    else "local"
                )
            return "local"
        except Exception:
            return "local"

    def _fetch_from_local_file(
        self, file_path: str, command_name: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Fetch data from local JSON file"""
        try:
            if not file_path or not Path(file_path).exists():
                logger.error(f"File not found: {file_path}")
                return None

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("data"), dict):
                    inner = data["data"]

                    if command_name == "applications":
                        if isinstance(inner.get("applications"), list):
                            return {"result": inner["applications"]}
                        if isinstance(inner.get("result"), list):
                            return {"result": inner["result"]}

                    if isinstance(inner.get("clients"), list):
                        return {"result": inner["clients"]}

                    if isinstance(inner.get("result"), list):
                        return {"result": inner["result"]}
                return data

        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {str(e)}")
            return None

    def _fetch_from_git(
        self,
        command_name: str,
        branch: Optional[str],
        project_name: Optional[str],
        realm: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch data from Git repository"""
        try:
            from trxo_lib.config.config_store import ConfigStore
            from trxo_lib.git import get_repo_base_path

            config_store = ConfigStore()

            # Get Git credentials to find repo name
            git_credentials = config_store.get_git_credentials(project_name)
            if not git_credentials or not all(git_credentials.values()):
                logger.error(
                    "Git credentials not found. Please run 'trxo config' "
                    "to set up Git integration."
                )
                return None

            # Extract repo name from URL
            repo_url = git_credentials["repo_url"]
            repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")

            # Find local repository path
            repo_base = get_repo_base_path()
            repo_path = repo_base / repo_name

            if not repo_path.exists() or not (repo_path / ".git").exists():
                logger.warning(f"Local Git repository not found at {repo_path}")
                logger.warning(
                    "Please run an export command first to initialize "
                    "the Git repository"
                )
                return None

            logger.info(f"Using local Git repository: {repo_path}")

            # Look for files matching the command pattern. Prefer realm-specific files
            effective_realm = realm or DEFAULT_REALM

            patterns = []
            # try patterns that include realm near filename
            patterns.append(f"**/*{command_name}*{effective_realm}*.json")
            patterns.append(f"**/*{effective_realm}*{command_name}*.json")
            # fallback to generic command name
            patterns.append(f"**/*{command_name}*.json")

            matching_files = []
            for pattern in patterns:
                matches = list(repo_path.glob(pattern))
                if matches:
                    matching_files = matches
                    break

            if not matching_files:
                logger.warning(
                    f"No {command_name} files found in Git repository, "
                    "so please run an export first."
                )
                return None

            # Use the first match (repo ordering) — callers can refine if needed
            file_path = matching_files[0]
            logger.info(f"Loading {command_name} data from Git: {file_path.name}")

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data

        except Exception as e:
            logger.error(f"Failed to fetch from Git: {str(e)}")
            return None


def get_command_api_endpoint(
    command_name: str, realm: str = DEFAULT_REALM
) -> tuple[str, Optional[callable]]:
    """
    Get the API endpoint and response filter for a given command name

    Args:
        command_name: Name of the command
        realm: Target realm

    Returns:
        Tuple of (API endpoint string, response filter function) or (None, None)
        if command not found
    """
    # Map command names to their API endpoints
    endpoint_map = {
        # Realm-specific endpoints
        "journeys": (
            f"/am/json/realms/root/realms/{realm}"
            "/realm-config/authentication/authenticationtrees/trees?_queryFilter=true",
            None,
        ),
        "scripts": (
            f"/am/json/realms/root/realms/{realm}/scripts?_queryFilter=true",
            decode_script_response,
        ),
        "services": (
            f"/am/json/realms/root/realms/{realm}/realm-config/services?_queryFilter=true",
            services_response_filter,
        ),
        "authn": (
            f"/am/json/realms/root/realms/{realm}/realm-config/authentication",
            None,
        ),
        "themes": ("/openidm/config/ui/themerealm", None),
        "oauth": (
            f"/am/json/realms/root/realms/{realm}"
            "/realm-config/agents/OAuth2Client?_queryFilter=true",
            None,
        ),
        "OAuth2_Clients": (
            f"/am/json/realms/root/realms/{realm}"
            "/realm-config/agents/OAuth2Client?_queryFilter=true",
            None,
        ),
        "saml": (
            f"/am/json/realms/root/realms/{realm}/realm-config/saml2?_queryFilter=true",
            process_saml_response,
        ),
        "policies": (
            f"/am/json/realms/root/realms/{realm}/policies?_queryFilter=true",
            None,
        ),
        "webhooks": (
            f"/am/json/realms/root/realms/{realm}/realm-config/webhooks?_queryFilter=true",
            None,
        ),
        "agent": (
            f"/am/json/realms/root/realms/{realm}/realm-config/agents?_queryFilter=true",
            None,
        ),
        # Root-level endpoints (no realm)
        "realms": ("/am/json/realms?_queryFilter=true", None),
        "applications": (
            f"/openidm/managed/{realm}_application?_queryFilter=true",
            None,
        ),
        "managed": ("/openidm/config/managed", None),
        "managed_objects": ("/openidm/config/managed", None),
        "mappings": ("/openidm/config/sync", None),
        "connectors": ('/openidm/config?_queryFilter=_id+sw+"provisioner"', None),
        "endpoints": ('/openidm/config?_queryFilter=_id+sw+"endpoint"', None),
        "email": ('/openidm/config?_queryFilter=_id co "emailTemplate"', None),
        "email_templates": (
            '/openidm/config?_queryFilter=_id co "emailTemplate"',
            None,
        ),
        "Environment_Secrets": ("/environment/secrets", None),
        "privileges": ('/openidm/config?_queryFilter=_id co "privilege"', None),
        "Environment_Variables": ("/environment/variables", None),
        # Nodes endpoint (both root nodes and inner nodes come from same endpoint)
        "nodes": (
            f"/am/json/realms/root/realms/{realm}"
            "/realm-config/authentication/authenticationtrees/nodes?_action=nextdescendents",
            None,
        ),
        # Agent endpoints
        "agents_gateway": (
            f"/am/json/realms/root/realms/{realm}"
            "/realm-config/agents/IdentityGatewayAgent?_queryFilter=true",
            None,
        ),
        "agents_java": (
            f"/am/json/realms/root/realms/{realm}/realm-config/agents/J2EEAgent?_queryFilter=true",
            None,
        ),
        "agents_web": (
            f"/am/json/realms/root/realms/{realm}/realm-config/agents/WebAgent?_queryFilter=true",
            None,
        ),
    }

    return endpoint_map.get(command_name, (None, None))
