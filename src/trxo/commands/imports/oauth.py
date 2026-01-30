"""
OAuth import commands.

This module provides import functionality for PingOne Advanced Identity Cloud OAuth2 clients with script dependencies.
"""

import json
from typing import List, Dict, Any, Optional
import typer
from trxo.utils.console import error, info, warning
from .base_importer import BaseImporter
from pathlib import Path
from trxo.constants import DEFAULT_REALM
from .scripts import ScriptImporter


class OAuthImporter(BaseImporter):
    """Enhanced importer for PingOne Advanced Identity Cloud OAuth2 Clients with script dependencies"""

    def __init__(self, realm: str = DEFAULT_REALM):
        super().__init__()
        self.realm = realm
        self.script_importer = ScriptImporter(realm=realm)
        self._pending_scripts: List[Dict[str, Any]] = []
        self._oauth_export_data: Optional[Dict[str, Any]] = None

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "OAuth2_Clients"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/"
            f"realm-config/agents/OAuth2Client/{item_id}",
        )

    def _parse_oauth_data(self, data: Any) -> List[Dict[str, Any]]:
        """Helper to parse OAuth data structure from file content"""
        clients = []

        # Check for new structure with 'data'
        if isinstance(data, dict) and "data" in data:
            data_section = data["data"]
            if (
                isinstance(data_section, dict)
                and "clients" in data_section
                and "scripts" in data_section
            ):
                info("Detected OAuth export format (standard) with clients and scripts")
                self._oauth_export_data = data_section

                # Add scripts to pending
                new_scripts = data_section.get("scripts", [])
                if new_scripts:
                    self._pending_scripts.extend(new_scripts)

                clients = data_section.get("clients", [])
            elif isinstance(data_section, list):
                # Standard list format
                clients = data_section
            elif isinstance(data_section, dict) and "result" in data_section:
                # Standard result wrapper
                clients = data_section.get("result", [])
            else:
                # Single item?
                clients = [data_section]

        # Check for legacy structure
        elif isinstance(data, dict) and "clients" in data and "scripts" in data:
            info("Detected OAuth export format (legacy) with clients and scripts")
            self._oauth_export_data = data

            new_scripts = data.get("scripts", [])
            if new_scripts:
                self._pending_scripts.extend(new_scripts)

            clients = data.get("clients", [])

        else:
            # Fallback to standard loading
            if isinstance(data, list):
                clients = data
            else:
                clients = [data]

        return clients

    def _import_from_git(
        self, realm: Optional[str], force_import: bool, branch: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Override to handle OAuth structure from Git files"""
        item_type = self.get_item_type()

        # Determine effective realm
        effective_realm = self._determine_effective_realm(realm, item_type, branch)

        # Setup Git manager
        git_manager = self._setup_git_manager(branch)
        repo_path = Path(git_manager.local_path)

        # Discover files
        discovered_files = self.file_loader.discover_git_files(
            repo_path, item_type, effective_realm
        )

        if not discovered_files:
            self._handle_no_git_files_found(item_type, effective_realm, realm)
            return []

        all_clients = []

        for file_path in discovered_files:
            try:
                info(f"Loading from: {file_path.relative_to(repo_path)}")

                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Parse
                parsed_clients = self._parse_oauth_data(data)
                all_clients.extend(parsed_clients)

            except Exception as e:
                warning(f"Failed to load {file_path.name}: {e}")
                continue

        return all_clients

    def _import_from_local(
        self, file_path: str, force_import: bool
    ) -> List[Dict[str, Any]]:
        """Override to handle OAuth structure manually"""
        import os

        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            raise typer.Exit(1)

        info(f"Loading OAuth2_Clients from local file: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            clients = self._parse_oauth_data(data)

            # Trigger hash validation
            self._validate_items(clients)

            if not self.validate_import_hash(clients, force_import):
                from trxo.utils.console import error

                error("Import validation failed: Hash mismatch with exported data")
                raise typer.Exit(1)

            return clients

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to load OAuth2_Clients: {str(e)}")

    def process_items(
        self,
        items: List[Dict[str, Any]],
        token: str,
        base_url: str,
        rollback_manager: Optional[object] = None,
        rollback_on_failure: bool = False,
    ) -> None:
        """Override to process pending scripts first"""

        # 1. Process pending scripts if any
        if self._pending_scripts:
            self._import_pending_scripts(token, base_url)

        # 2. Process clients using base implementation
        super().process_items(
            items, token, base_url, rollback_manager, rollback_on_failure
        )

    def _import_pending_scripts(self, token: str, base_url: str):
        """Import extracted script dependencies"""
        info(f"Importing {len(self._pending_scripts)} script dependencies first...")

        self.script_importer.auth_mode = self.auth_mode

        for script in self._pending_scripts:
            script_id = script.get("_id")
            if not script_id:
                warning("Script missing _id field, skipping")
                continue

            try:
                # Use script importer to update
                if self.script_importer.update_item(script, token, base_url):
                    info(f"Successfully imported script dependency: {script_id}")
                else:
                    warning(f"Failed to import script dependency: {script_id}")
            except Exception as e:
                warning(f"Error importing script {script_id}: {str(e)}")

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Update a single OAuth2 Client via API"""
        item_id = item_data.get("_id")

        if not item_id:
            error(f"OAuth2 Client '{item_id}' missing _id field, skipping")
            return False

        # Construct URL with OAuth2 Client ID
        url = self.get_api_endpoint(item_id, base_url)

        # Prepare payload by excluding _id and _rev fields
        filtered_data = {k: v for k, v in item_data.items() if k not in ["_id", "_rev"]}
        payload = json.dumps(filtered_data)

        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, payload)
            info(f"Successfully updated OAuth2 Client: (ID: {item_id})")
            return True

        except Exception as e:
            error(f"Error updating OAuth2 Client '{item_id}': {str(e)}")
            return False

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete a single OAuth2 Client via API"""
        url = self.get_api_endpoint(item_id, base_url)

        headers = {
            "Accept-API-Version": "resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "DELETE", headers)
            info(f"Successfully deleted OAuth2 Client: {item_id}")
            return True
        except Exception as e:
            error(f"Error deleting OAuth2 Client '{item_id}': {str(e)}")
            return False


def create_oauth_import_command():
    """Create the OAuth import command function"""

    def import_oauth(
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Target realm name (default: {DEFAULT_REALM})",
        ),
        cherry_pick: str = typer.Option(
            None,
            "--cherry-pick",
            help=(
                "Import only specific OAuth2 clients with these IDs(_id) "
                "(comma-separated for multiple IDs, e.g., id1,id2,id3)"
            ),
        ),
        sync: bool = typer.Option(
            False,
            "--sync",
            help="Sync mode: delete items not in source (mirror source to destination)",
        ),
        diff: bool = typer.Option(
            False, "--diff", help="Show differences before import"
        ),
        file: str = typer.Option(
            None, "--file", help="Path to JSON file containing OAuth2 Clients data"
        ),
        force_import: bool = typer.Option(
            False, "--force-import", "-f", help="Skip hash validation and force import"
        ),
        rollback: bool = typer.Option(
            False,
            "--rollback",
            help=(
                "Automatically rollback imported items on first failure "
                "(requires git storage)"
            ),
        ),
        branch: str = typer.Option(
            None, "--branch", help="Git branch to import from (Git mode only)"
        ),
        jwk_path: str = typer.Option(
            None, "--jwk-path", help="Path to JWK private key file"
        ),
        client_id: str = typer.Option(None, "--client-id", help="Client ID"),
        sa_id: str = typer.Option(None, "--sa-id", help="Service Account ID"),
        base_url: str = typer.Option(
            None,
            "--base-url",
            help="Base URL for PingOne Advanced Identity Cloud instance",
        ),
        project_name: str = typer.Option(
            None,
            "--project-name",
            help="Project name for argument mode (optional)",
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
    ):
        """Import OAuth2 Clients with script dependencies."""
        importer = OAuthImporter(realm=realm)
        importer.import_from_file(
            file_path=file,
            realm=realm,
            jwk_path=jwk_path,
            client_id=client_id,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            force_import=force_import,
            branch=branch,
            diff=diff,
            rollback=rollback,
            sync=sync,
            cherry_pick=cherry_pick,
        )

    return import_oauth
