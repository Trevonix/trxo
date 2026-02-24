"""
Data fetcher utility for diff functionality.

This module provides utilities to fetch current server data for comparison
by reusing the existing export functionality without saving files.
"""

import json
from typing import Dict, Any, Optional
from pathlib import Path
from trxo.utils.console import info, error, warning
from trxo.commands.export.base_exporter import BaseExporter
from trxo.commands.export.scripts import decode_script_response
from trxo.constants import DEFAULT_REALM


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
            info(f"Fetching current {command_name} data from server...")

            # Use a custom data capture approach
            original_save_method = self.exporter.save_response
            captured_data = None

            def capture_data(data, *args, **kwargs):
                nonlocal captured_data
                captured_data = data
                # Return a dummy path since we're not actually saving
                return Path("/tmp/dummy_path.json")

            # Temporarily replace save_response to capture data
            self.exporter.save_response = capture_data

            try:
                # Call export_data but capture the data instead of saving
                self.exporter.export_data(
                    command_name=command_name,
                    api_endpoint=api_endpoint,
                    headers={
                        "Content-Type": "application/json",
                        "Accept-API-Version": "resource=1.0",
                    },
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

                return captured_data

            finally:
                # Restore original save method
                self.exporter.save_response = original_save_method

        except Exception as e:
            error(f"Failed to fetch {command_name} data: {str(e)}")
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
            from trxo.utils.config_store import ConfigStore

            config_store = ConfigStore()
            storage_mode = self._get_storage_mode(config_store, project_name)

            if storage_mode == "git":
                return self._fetch_from_git(command_name, branch, project_name, realm)
            else:
                return self._fetch_from_local_file(file_path)

        except Exception as e:
            error(f"Failed to fetch data from file/git: {str(e)}")
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

    def _fetch_from_local_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Fetch data from local JSON file"""
        try:
            if not file_path or not Path(file_path).exists():
                error(f"File not found: {file_path}")
                return None

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                info(f"📁 Loaded data from {file_path}")
                return data

        except Exception as e:
            error(f"Failed to read file {file_path}: {str(e)}")
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
            from trxo.utils.git import get_repo_base_path
            from trxo.utils.config_store import ConfigStore

            config_store = ConfigStore()

            # Get Git credentials to find repo name
            git_credentials = config_store.get_git_credentials(project_name)
            if not git_credentials or not all(git_credentials.values()):
                error(
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
                warning(f"Local Git repository not found at {repo_path}")
                warning(
                    "Please run an export command first to initialize "
                    "the Git repository"
                )
                return None

            info(f"📂 Using local Git repository: {repo_path}")

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
                warning(
                    f"No {command_name} files found in Git repository, "
                    "so please run an export first."
                )
                return None

            # Use the first match (repo ordering) — callers can refine if needed
            file_path = matching_files[0]
            info(f"🔄 Loading {command_name} data from Git: {file_path.name}")

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data

        except Exception as e:
            error(f"Failed to fetch from Git: {str(e)}")
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
            None,
        ),
        "authn": (
            f"/am/json/realms/root/realms/{realm}/realm-config/authentication",
            None,
        ),
        "themes": (f"/openidm/config/ui/themerealm?_fields=realm/{realm}", None),
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
            f"/am/json/realms/root/realms/{realm}"
            "/realm-config/federation/entityproviders/saml2?_queryFilter=true",
            None,
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
        "Applications": (
            f"/openidm/managed/{realm}_application?_queryFilter=true",
            None,
        ),
        "managed": ("/openidm/config/managed", None),
        "managed_objects": ("/openidm/config/managed", None),
        "mappings": ("/openidm/config/sync", None),
        "connectors": ('/openidm/config?_queryFilter=_id+sw+"provisioner"', None),
        "endpoints": ('/openidm/config?_queryFilter=_id+sw+"endpoint"', None),
        "email": ('/openidm/config?_queryFilter=_id co "emailTemplate"', None),
        "Environment_Secrets": ("/environment/secrets", None),
        "privileges": ('/openidm/config?_queryFilter=_id co "privilege"', None),
        "Environment_Variables": ("/environment/variables", None),
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
