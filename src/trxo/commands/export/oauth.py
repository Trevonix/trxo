"""
OAuth export commands.

This module provides export functionality for
PingOne Advanced Identity Cloud OAuth2 clients with script dependencies.
"""

import base64
import typer
from typing import Any, Dict, Set
from trxo.utils.console import warning, error, info, success
from .base_exporter import BaseExporter
from trxo.constants import DEFAULT_REALM, IGNORED_SCRIPT_IDS


class OAuthExporter(BaseExporter):
    """Enhanced OAuth exporter that fetches complete data and handles script dependencies"""

    def __init__(self, realm: str = DEFAULT_REALM):
        super().__init__()
        self.realm = realm

    def extract_script_ids(self, oauth_data: Dict[str, Any]) -> Set[str]:
        """Extract script IDs from OAuth client configuration"""
        script_ids = set()

        def find_scripts_in_dict(data: Dict[str, Any], path: str = ""):
            """Recursively find script IDs in nested dictionaries"""
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key

                # Only check for fields ending with "Script"
                if key.endswith("Script"):
                    # Only add if value is a non-empty string
                    if isinstance(value, str) and value.strip() != "[Empty]":
                        script_ids.add(value.strip())
                elif isinstance(value, dict):
                    find_scripts_in_dict(value, current_path)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            find_scripts_in_dict(item, f"{current_path}[{i}]")

        find_scripts_in_dict(oauth_data)
        return script_ids

    def fetch_script_data(
        self, script_id: str, token: str, base_url: str
    ) -> Dict[str, Any]:
        """Fetch individual script data by ID"""
        url = self._construct_api_url(
            base_url, f"/am/json/realms/root/realms/{self.realm}/scripts/{script_id}"
        )
        headers = {
            "Accept-API-Version": "protocol=2.1,resource=1.0",
            "Content-Type": "application/json",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            response = self.make_http_request(url, "GET", headers)
            script_data = response.json()

            # Decode script field if present (similar to scripts export)
            if "script" in script_data and isinstance(script_data["script"], str):
                try:
                    decoded_bytes = base64.b64decode(
                        script_data["script"], validate=True
                    )
                    decoded_text = decoded_bytes.decode("utf-8")
                    script_data["script"] = decoded_text.splitlines()
                except Exception as e:
                    warning(f"Failed to decode script {script_id}: {str(e)}")

            return script_data
        except Exception as e:
            # Handle 403 Forbidden gracefully (likely internal/protected scripts)
            if "403" in str(e) or "Forbidden" in str(e):
                # warning(f"Skipping script {script_id}: Access denied (likely internal)")
                return {}

            error(f"Failed to fetch script {script_id}: {str(e)}")
            return {}

    def fetch_oauth_client_data(
        self, client_id: str, token: str, base_url: str
    ) -> Dict[str, Any]:
        """Fetch individual OAuth client data by ID"""
        url = self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}"
            f"/realm-config/agents/OAuth2Client/{client_id}",
        )
        headers = {
            "Accept-API-Version": "protocol=2.1,resource=1.0",
            "Content-Type": "application/json",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            response = self.make_http_request(url, "GET", headers)
            data = response.json()
            data.pop("_rev", None)
            return data
        except Exception as e:
            error(f"Failed to fetch OAuth client {client_id}: {str(e)}")
            return {}


def create_oauth_export_command():
    """Create the OAuth export command function"""
    # Use global IGNORED_SCRIPT_IDS from constants

    def export_oauth(
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Target realm name (default: {DEFAULT_REALM})",
        ),
        view: bool = typer.Option(
            False,
            "--view",
            help="Display data in table format instead of exporting to file",
        ),
        view_columns: str = typer.Option(
            None,
            "--view-columns",
            help="Comma-separated list of columns to display (e.g., '_id,name,active')",
        ),
        version: str = typer.Option(
            None, "--version", help="Custom version name (default: auto)"
        ),
        no_version: bool = typer.Option(
            False, "--no-version", help="Disable auto versioning for legacy filenames"
        ),
        branch: str = typer.Option(
            None, "--branch", help="Git branch to use for export (Git mode only)"
        ),
        commit: str = typer.Option(
            None, "--commit", help="Custom commit message (Git mode only)"
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
        output_dir: str = typer.Option(
            None, "--dir", help="Output directory for JSON files"
        ),
        output_file: str = typer.Option(
            None, "--file", help="Output filename (without .json extension)"
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
        idm_base_url: str = typer.Option(
            None, "--idm-base-url", help="On-Prem IDM base URL"
        ),
        idm_username: str = typer.Option(
            None, "--idm-username", help="On-Prem IDM username"
        ),
        idm_password: str = typer.Option(
            None, "--idm-password", help="On-Prem IDM password", hide_input=True
        ),
    ):
        """Export OAuth2 clients configuration with script dependencies"""
        oauth_exporter = OAuthExporter(realm=realm)

        try:
            # Initialize authentication
            token, api_base_url = oauth_exporter.initialize_auth(
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
            )

            # First, get list of OAuth clients using query filter
            list_url = oauth_exporter._construct_api_url(
                api_base_url,
                (
                    f"/am/json/realms/root/realms/{realm}/realm-config/"
                    "agents/OAuth2Client?_queryFilter=true"
                ),
            )
            headers = {
                "Accept-API-Version": "protocol=2.1,resource=1.0",
                "Content-Type": "application/json",
            }
            headers = {**headers, **oauth_exporter.build_auth_headers(token)}

            response = oauth_exporter.make_http_request(list_url, "GET", headers)
            list_data = response.json()

            if not isinstance(list_data, dict) or "result" not in list_data:
                error("Invalid response format from OAuth clients list")
                return

            oauth_clients = list_data["result"]

            info("Fetching OAuth2 clients data...\n")
            # Fetch complete data for each client and collect script dependencies
            complete_clients = []
            all_script_ids = set()

            for client in oauth_clients:
                client_id = client.get("_id")
                if not client_id:
                    warning("Skipping client without _id")
                    continue

                complete_client = oauth_exporter.fetch_oauth_client_data(
                    client_id, token, api_base_url
                )

                if complete_client:
                    complete_clients.append(complete_client)
                    # Extract script dependencies
                    script_ids = oauth_exporter.extract_script_ids(complete_client)
                    all_script_ids.update(script_ids)

            # Fetch all dependent scripts
            scripts_data = []
            # print("\nscript ids: ", all_script_ids)
            if all_script_ids:
                for script_id in all_script_ids:
                    if script_id in IGNORED_SCRIPT_IDS:
                        continue
                    script_data = oauth_exporter.fetch_script_data(
                        script_id, token, api_base_url
                    )
                    if script_data:
                        scripts_data.append(script_data)

            # Create combined export data structure following standard format
            combined_data = {"clients": complete_clients, "scripts": scripts_data}

            # Create standard export structure with metadata
            from datetime import datetime, timezone

            total_items = len(complete_clients)

            export_data = {
                "metadata": {
                    "export_type": "oauth",
                    "realm": realm,
                    "timestamp": datetime.now(timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "version": None,  # Will be filled during save_response
                    "total_items": total_items,
                },
                "data": combined_data,
            }

            # Handle view mode
            if view:
                # oauth_exporter._display_table_view(export_data, "oauth", view_columns)
                oauth_exporter._handle_view_mode(export_data, "oauth", view_columns)
                return

            # Save to file using the base exporter's file handling
            file_path = oauth_exporter.save_response(
                data=export_data,
                command_name="oauth",
                output_dir=output_dir,
                output_file=output_file,
                version=version,
                no_version=no_version,
                branch=branch,
                commit_message=commit,
            )

            # Create and save hash for data integrity (only for local storage mode)
            storage_mode = oauth_exporter._get_storage_mode()
            if storage_mode == "local" and file_path:
                # Hash the raw data (combined_data) just like standard exports hash filtered_data
                hash_value = oauth_exporter.hash_manager.create_hash(
                    combined_data, "oauth"
                )
                oauth_exporter.hash_manager.save_export_hash(
                    "oauth", hash_value, file_path
                )

            print()
            success("OAuth2 clients exported successfully")
        except Exception as e:
            error(f"OAuth export failed: {str(e)}")
            raise

    return export_oauth
