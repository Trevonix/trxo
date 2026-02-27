"""
IDM Connectors import command.

Import functionality for PingIDM connectors.
- Uses PUT with _id in endpoint: /openidm/config/{_id}
- Keeps complete data as payload (no field removal)
- Works as upsert (create or update) based on _id
"""

import json
import time
from typing import List, Dict, Any
import typer
from trxo.utils.console import error, info, warning
from .base_importer import BaseImporter


class ConnectorsImporter(BaseImporter):
    """Importer for PingIDM connectors"""

    def __init__(self):
        super().__init__()
        self.product = "idm"
        self.max_retries = 3
        self.skip_delays = False
        self.wait_time = 5

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "IDM connectors"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/openidm/config/{item_id}"

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Upsert IDM connector using PUT with retry logic for metadata provider issues"""
        item_id = item_data.get("_id")
        if not item_id:
            error("Connector missing '_id'; required for upsert")
            return False

        # Validate that this is a connector (starts with "provisioner")
        if not item_id.startswith("provisioner"):
            error(f"Invalid connector ID '{item_id}'; must start with 'provisioner'")
            return False

        # Keep complete data as payload (no field removal as per requirement)
        payload = json.dumps(item_data)

        url = self.get_api_endpoint(item_id, base_url)
        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=2.1,resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        # Retry logic for metadata provider issues
        for attempt in range(self.max_retries):
            try:
                self.make_http_request(url, "PUT", headers, payload)

                # Determine if this was likely an update or create based on connector type
                if item_id == "provisioner.openicf.connectorinfoprovider":
                    info("Updated connector info provider configuration")
                    time.sleep(10)
                    # Give extra time for connector framework to initialize
                    if not self.skip_delays:
                        info(
                            f"Waiting {self.wait_time}s for connector framework to initialize..."
                        )
                        time.sleep(self.wait_time)
                else:
                    connector_name = item_data.get("connectorRef", {}).get(
                        "displayName", item_id
                    )
                    info(f"Upserted connector: {connector_name} ({item_id})")

                return True

            except Exception as e:
                error_message = str(e).lower()

                # Check if it's a metadata provider issue (multiple possible patterns)
                metadata_error_patterns = [
                    "meta-data provider",
                    "metadata provider",
                    "no meta-data provider available",
                    "retry later",
                    "connectorinfoprovider",
                ]

                is_metadata_error = any(
                    pattern in error_message for pattern in metadata_error_patterns
                )

                # Debug information
                if attempt == 0:  # Only show on first attempt
                    info(
                        f"Error analysis for '{item_id}': metadata_error={is_metadata_error}"
                    )
                    matches = [p for p in metadata_error_patterns if p in error_message]
                    info("Error message contains: %s", matches)

                if is_metadata_error:
                    if attempt < self.max_retries - 1:
                        wait_time = (
                            attempt + 1
                        ) * 8  # 5, 10, 15 seconds (increased wait time)
                        warning(
                            f"Metadata provider not ready for '{item_id}', retrying in {wait_time}"
                            f"s... (attempt {attempt + 1}/{self.max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        error(
                            f"Failed to upsert connector '{item_id}' after {self.max_retries} "
                            "attempts: Metadata provider not available"
                        )
                        error(
                            "Try running the command again after a few minutes, "
                            "or increase --max-retries"
                        )
                        return False
                else:
                    # Other errors, don't retry
                    error(f"Failed to upsert connector '{item_id}': {e}")
                    return False

        return False

    def _load_connectors_file(self, file_path: str) -> Any:
        """Load connectors file with flexible format support"""
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
            elif "_id" in data and data["_id"].startswith("provisioner"):
                # Single connector object
                return [data]
            else:
                # Unknown format
                return data
        elif isinstance(data, list):
            # Array of connectors
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
        am_base_url: str = None,
        force_import: bool = False,
        branch: str = None,
        diff: bool = False,
        **kwargs,
    ) -> None:
        """Override to handle both single connectors and arrays of connectors"""

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
                am_base_url=am_base_url,
                force_import=force_import,
                branch=branch,
                diff=diff,
                **kwargs,
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
                am_base_url=am_base_url,
            )

            # Load and parse file with flexible format support
            data = self._load_connectors_file(file_path)

            # Handle different input formats
            if isinstance(data, list):
                # Array of connectors
                connectors_to_process = data
                info(f"Processing {len(connectors_to_process)} connectors from array")
            elif isinstance(data, dict):
                if "_id" in data and data["_id"].startswith("provisioner"):
                    # Single connector
                    connectors_to_process = [data]
                    info("Processing single connector")
                else:
                    error(
                        "Invalid connector format. "
                        "Expected object with '_id' starting with 'provisioner'"
                    )
                    return
            else:
                error("Invalid file format. Expected object or array of connectors")
                return

            # Validate all connectors have required fields
            valid_connectors = []
            for connector in connectors_to_process:
                if not isinstance(connector, dict):
                    error("Invalid connector: must be an object")
                    continue

                connector_id = connector.get("_id")
                if not connector_id:
                    error("Connector missing '_id' field")
                    continue

                if not connector_id.startswith("provisioner"):
                    error(
                        f"Invalid connector ID '{connector_id}'; must start with 'provisioner'"
                    )
                    continue

                valid_connectors.append(connector)

            if not valid_connectors:
                error("No valid connectors found to process")
                return

            # Sort connectors to process connector info provider first
            def connector_priority(connector):
                connector_id = connector.get("_id", "")
                if connector_id == "provisioner.openicf.connectorinfoprovider":
                    return 0  # Highest priority
                elif connector_id.startswith("provisioner.openicf/"):
                    return 2  # OpenICF connectors after info provider
                else:
                    return 1  # Other provisioners in between

            sorted_connectors = sorted(valid_connectors, key=connector_priority)

            info(
                f"Processing {len(sorted_connectors)} connectors in dependency order..."
            )

            # Process each connector with proper ordering
            success_count = 0
            for i, connector in enumerate(sorted_connectors):
                connector_id = connector.get("_id")

                # Add delay between connectors to allow framework initialization
                if i > 0 and not self.skip_delays:
                    time.sleep(1)

                if self.update_item(connector, token, api_base_url):
                    success_count += 1
                else:
                    # If connector info provider fails, warn about subsequent failures
                    if connector_id == "provisioner.openicf.connectorinfoprovider":
                        warning(
                            "Connector info provider failed - "
                            "subsequent OpenICF connectors may also fail"
                        )

            info(
                f"Successfully processed {success_count}/{len(sorted_connectors)} connectors"
            )

        except Exception as e:
            error(f"Import failed: {str(e)}")


def create_connectors_import_command():
    """Create the connectors import command function"""

    def import_connectors(
        file: str = typer.Option(
            None, "--file", help="Path to JSON file containing IDM connectors"
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
            False, "--force-import", "-f", help="Skip hash validation and force import"
        ),
        diff: bool = typer.Option(
            False, "--diff", help="Show differences before import"
        ),
        branch: str = typer.Option(
            None, "--branch", help="Git branch to import from (Git mode only)"
        ),
        max_retries: int = typer.Option(
            3,
            "--max-retries",
            help="Maximum retry attempts for metadata provider issues",
        ),
        skip_delays: bool = typer.Option(
            False,
            "--skip-delays",
            help="Skip delays between connector processing (faster but may cause issues)",
        ),
        wait_time: int = typer.Option(
            5,
            "--wait-time",
            help="Seconds to wait after connector info provider update (default: 5)",
        ),
    ):
        """Import IDM connectors from JSON file (local mode) or Git repository (Git mode).

        Updates existing connectors by _id or creates new ones (upsert).
        """
        importer = ConnectorsImporter()
        # Pass additional parameters to the importer
        importer.max_retries = max_retries
        importer.skip_delays = skip_delays
        importer.wait_time = wait_time

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
            am_base_url=am_base_url,
            force_import=force_import,
            branch=branch,
            diff=diff,
        )

    return import_connectors
