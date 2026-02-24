"""
Mappings import command.

Import functionality for PingIDM sync mappings with smart upsert logic:
- If mapping exists by name → PATCH to update
- If mapping doesn't exist → PUT to add to the mappings array
- Handles both single mappings and multiple mappings
"""

import json
from typing import List, Dict, Any
import typer
from trxo.utils.console import error, info
from .base_importer import BaseImporter


class MappingsImporter(BaseImporter):
    """Importer for PingIDM sync mappings with smart upsert logic"""

    def get_required_fields(self) -> List[str]:
        return ["name"]

    def get_item_type(self) -> str:
        return "sync mappings"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/openidm/config/sync"

    def _get_current_sync_config(self, token: str, base_url: str) -> Dict[str, Any]:
        """Fetch current sync configuration"""
        url = self.get_api_endpoint("", base_url)
        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=2.1,resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            response = self.make_http_request(url, "GET", headers)
            return response.json()
        except Exception as e:
            error(f"Failed to fetch current sync configuration: {e}")
            return {}

    def _find_mapping_by_name(self, mappings_list: List[Dict], name: str) -> tuple:
        """Find mapping by name in the mappings list. Returns (index, mapping) or (-1, None)"""
        for index, mapping in enumerate(mappings_list):
            if mapping.get("name") == name:
                return index, mapping
        return -1, None

    def _generate_patch_operations(
        self,
        existing_mapping: Dict[str, Any],
        new_mapping: Dict[str, Any],
        base_path: str = "",
    ) -> List[Dict[str, Any]]:
        """Generate PATCH operations by comparing existing and new mappings"""
        operations = []

        # Handle all keys from new mapping
        for key, new_value in new_mapping.items():
            current_path = f"{base_path}/{key}" if base_path else f"/{key}"
            existing_value = existing_mapping.get(key)

            if existing_value != new_value:
                if isinstance(new_value, dict) and isinstance(existing_value, dict):
                    # Recursively handle nested objects
                    nested_ops = self._generate_patch_operations(
                        existing_value, new_value, current_path
                    )
                    operations.extend(nested_ops)
                elif isinstance(new_value, list) and isinstance(existing_value, list):
                    # For arrays (like policies, properties), replace the entire array
                    operations.append(
                        {
                            "operation": "replace",
                            "field": current_path,
                            "value": new_value,
                        }
                    )
                else:
                    # Value changed or new field
                    operations.append(
                        {
                            "operation": (
                                "replace" if key in existing_mapping else "add"
                            ),
                            "field": current_path,
                            "value": new_value,
                        }
                    )

        return operations

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Smart upsert for sync mappings using PATCH for updates, PUT for creates"""
        mapping_name = item_data.get("name")
        if not mapping_name:
            error("Sync mapping missing 'name'; required for upsert")
            return False

        # Get current configuration
        current_config = self._get_current_sync_config(token, base_url)
        if not current_config:
            error("Could not retrieve current sync configuration")
            return False

        current_mappings = current_config.get("mappings", [])

        # Find if mapping exists
        index, existing_mapping = self._find_mapping_by_name(
            current_mappings, mapping_name
        )

        url = self.get_api_endpoint("", base_url)
        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=2.1,resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        if index >= 0:
            # Mapping exists - use PATCH for efficient updates
            patch_operations = self._generate_patch_operations(
                existing_mapping, item_data, f"/mappings/{index}"
            )

            if not patch_operations:
                info(f"No changes needed for sync mapping: {mapping_name}")
                return True

            payload = json.dumps(patch_operations)

            try:
                self.make_http_request(url, "PATCH", headers, payload)
                info(
                    f"Updated existing sync mapping: {mapping_name} "
                    f"({len(patch_operations)} changes)"
                )
                return True
            except Exception as e:
                error(f"Failed to update sync mapping '{mapping_name}': {e}")
                return False
        else:
            # Mapping doesn't exist - use PUT to add to the mappings array
            updated_mappings = current_mappings + [item_data]
            updated_config = {**current_config, "mappings": updated_mappings}
            payload = json.dumps(updated_config)

            try:
                self.make_http_request(url, "PUT", headers, payload)
                info(f"Added new sync mapping: {mapping_name}")
                return True
            except Exception as e:
                error(f"Failed to add sync mapping '{mapping_name}': {e}")
                return False

    def _load_mappings_file(self, file_path: str) -> Any:
        """Load mappings file with flexible format support"""
        import os
        import json

        # Convert to absolute path if relative
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read and parse JSON file
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Handle different file formats
        if isinstance(data, dict):
            # Check if it's an export file format
            if "data" in data:
                # Standard export format
                if "result" in data["data"]:
                    return data["data"]["result"]
                else:
                    return data["data"]
            else:
                # Raw sync config data
                return data
        elif isinstance(data, list):
            # Array of mappings
            return data
        else:
            raise ValueError("Invalid file format. Expected JSON object or array")

    def import_from_file(
        self,
        file_path: str,
        realm: str = None,
        jwk_path: str = None,
        sa_id: str = None,
        base_url: str = None,
        project_name: str = None,
        auth_mode: str = None,
        onprem_username: str = None,
        onprem_password: str = None,
        onprem_realm: str = None,
        idm_base_url: str = None,
        idm_username: str = None,
        idm_password: str = None,
        force_import: bool = False,
        branch: str = None,
        diff: bool = False,
    ) -> None:
        """Override to handle both single mappings and arrays of mappings"""

        # Check if we should use Git mode or local mode
        storage_mode = self._get_storage_mode()

        if storage_mode == "git" or file_path is None:
            # Use parent class Git mode logic
            super().import_from_file(
                file_path=file_path,
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
                idm_password=idm_password,
                force_import=force_import,
                branch=branch,
                diff=diff,
            )
            return

        # Local mode - use custom logic for flexible format support
        try:
            # Initialize authentication
            token, api_base_url = self.initialize_auth(
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

            # Load and parse file with flexible format support
            data = self._load_mappings_file(file_path)

            # Handle different input formats
            if isinstance(data, dict):
                if "mappings" in data:
                    # Full sync config with mappings array
                    mappings_to_process = data["mappings"]
                    info(
                        f"Processing {len(mappings_to_process)} sync mappings from full config"
                    )
                elif "name" in data:
                    # Single mapping
                    mappings_to_process = [data]
                    info("Processing single sync mapping")
                else:
                    error(
                        "Invalid sync mappings format. Expected object with "
                        "'name' or 'mappings' array"
                    )
                    return
            elif isinstance(data, list):
                # Array of mappings or single item list
                if (
                    len(data) == 1
                    and isinstance(data[0], dict)
                    and "mappings" in data[0]
                ):
                    # Single export item containing full config
                    mappings_to_process = data[0]["mappings"]
                    info(
                        f"Processing {len(mappings_to_process)} sync mappings from exported config"
                    )
                else:
                    # Array of mappings
                    mappings_to_process = data
                    info(
                        f"Processing {len(mappings_to_process)} sync mappings from array"
                    )
            else:
                error("Invalid file format. Expected object or array of sync mappings")
                return

            # Process each mapping
            success_count = 0
            for mapping in mappings_to_process:
                if self.update_item(mapping, token, api_base_url):
                    success_count += 1

            info(
                f"Successfully processed {success_count}/{len(mappings_to_process)} sync mappings"
            )

        except Exception as e:
            error(f"Import failed: {str(e)}")


def create_mappings_import_command():
    """Create the mappings import command function"""

    def import_mappings(
        file: str = typer.Option(
            None, "--file", help="Path to JSON file containing sync mappings"
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
            False, "--force-import", "-f", help="Skip hash validation and force import"
        ),
        diff: bool = typer.Option(
            False, "--diff", help="Show differences before import"
        ),
        branch: str = typer.Option(
            None, "--branch", help="Git branch to import from (Git mode only)"
        ),
    ):
        """Import sync mappings from JSON file (local mode) or Git repository (Git mode).

        Updates existing mappings by name (PATCH) or adds new ones (PUT).
        """
        importer = MappingsImporter()
        importer.import_from_file(
            file_path=file,
            realm=None,  # Root-level config
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
            force_import=force_import,
            branch=branch,
            diff=diff,
        )

    return import_mappings
