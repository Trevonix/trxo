"""
SAML import commands.

This module provides import functionality for
PingOne Advanced Identity Cloud SAML configurations.
"""

import base64
import json
import httpx
from typing import List, Dict, Any, Set, Optional
import typer
from urllib.parse import quote
from trxo.utils.console import error, info, warning, success
from .base_importer import BaseImporter
from trxo.constants import DEFAULT_REALM


class SamlImporter(BaseImporter):
    """Importer for SAML with dependency handling."""

    def __init__(self, realm: str = DEFAULT_REALM):
        super().__init__()
        self.realm = realm
        self.imported_scripts = set()  # Track imported scripts

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "saml"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        # This is a placeholder - actual endpoint depends on location
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/" "realm-config/saml2",
        )

    def import_saml_data(
        self,
        data: Dict[str, Any],
        token: str,
        base_url: str,
        cherry_pick_ids: Optional[str] = None,
    ) -> bool:
        """
        Import SAML data including scripts, metadata, and entities.

        Args:
            data: SAML export data with hosted, remote, metadata, and scripts
            token: Authentication token
            base_url: API base URL
            cherry_pick_ids: Optional comma-separated entity IDs to import

        Returns:
            True if import successful, False otherwise
        """
        success_count = 0
        error_count = 0

        # Parse cherry-pick IDs if provided
        selected_entity_ids = None
        if cherry_pick_ids:
            selected_entity_ids = [id.strip() for id in cherry_pick_ids.split(",")]
            info(
                f"Cherry-pick mode: importing only entities: "
                f"{', '.join(selected_entity_ids)}"
            )

        # Step 1: Import scripts (dependencies must be imported first)
        scripts_data = data.get("scripts", [])
        if scripts_data:
            info(f"Found {len(scripts_data)} script(s) to import")
            script_success = self._import_scripts(
                scripts_data, token, base_url, selected_entity_ids, data
            )
            if not script_success:
                warning("Some scripts failed to import, but continuing...")

        # Step 2: Import remote metadata (only for remote entities)
        metadata_data = data.get("metadata", [])
        remote_entities = data.get("remote", [])

        if metadata_data and remote_entities:
            info(
                f"Processing {len(metadata_data)} metadata item(s) "
                "for remote entities"
            )
            metadata_success = self._import_metadata(
                metadata_data, remote_entities, token, base_url, selected_entity_ids
            )
            if not metadata_success:
                warning("Some metadata imports failed, but continuing...")

        # Step 3: Upsert hosted entities
        hosted_entities = data.get("hosted", [])
        if hosted_entities:
            filtered_hosted = self._filter_entities(
                hosted_entities, selected_entity_ids
            )
            info(f"Importing {len(filtered_hosted)} hosted entit(y/ies)")
            for entity in filtered_hosted:
                if self._upsert_entity(entity, "hosted", token, base_url):
                    success_count += 1
                else:
                    error_count += 1

        # Step 4: Upsert remote entities
        if remote_entities:
            filtered_remote = self._filter_entities(
                remote_entities, selected_entity_ids
            )
            info(f"Importing {len(filtered_remote)} remote entit(y/ies)")
            for entity in filtered_remote:
                if self._upsert_entity(entity, "remote", token, base_url):
                    success_count += 1
                else:
                    error_count += 1

        # Print summary
        total = success_count + error_count
        if total > 0:
            success(f"SAML import completed: {success_count}/{total} successful")
        else:
            warning("No SAML entities to import")

        return error_count == 0

    def _filter_entities(
        self, entities: List[Dict[str, Any]], selected_ids: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Filter entities based on cherry-pick selection"""
        if not selected_ids:
            return entities

        filtered = []
        for entity in entities:
            entity_id = entity.get("entityId") or entity.get("_id")
            if entity_id in selected_ids:
                filtered.append(entity)

        return filtered

    def _import_scripts(
        self,
        scripts: List[Dict[str, Any]],
        token: str,
        base_url: str,
        selected_entity_ids: Optional[List[str]],
        full_data: Dict[str, Any],
    ) -> bool:
        """Import scripts needed by selected entities."""
        # If cherry-pick, determine which scripts are actually needed
        if selected_entity_ids:
            needed_script_ids = self._get_needed_script_ids(
                full_data, selected_entity_ids
            )
            scripts_to_import = [
                s for s in scripts if s.get("_id") in needed_script_ids
            ]
            info(
                f"Cherry-pick: importing {len(scripts_to_import)} required " "script(s)"
            )
        else:
            scripts_to_import = scripts

        success_count = 0
        for script in scripts_to_import:
            script_id = script.get("_id")
            if script_id and script_id not in self.imported_scripts:
                if self._import_single_script(script, token, base_url):
                    self.imported_scripts.add(script_id)
                    success_count += 1

        if success_count > 0:
            info(f"Successfully imported {success_count} script(s)")

        return True

    def _get_needed_script_ids(
        self, data: Dict[str, Any], selected_entity_ids: List[str]
    ) -> Set[str]:
        """Extract script IDs needed by selected entities"""
        needed_ids = set()

        # Check hosted entities
        for entity in data.get("hosted", []):
            entity_id = entity.get("entityId") or entity.get("_id")
            if entity_id in selected_entity_ids:
                needed_ids.update(self._extract_script_ids_from_entity(entity))

        # Check remote entities
        for entity in data.get("remote", []):
            entity_id = entity.get("entityId") or entity.get("_id")
            if entity_id in selected_entity_ids:
                needed_ids.update(self._extract_script_ids_from_entity(entity))

        return needed_ids

    def _extract_script_ids_from_entity(self, entity: Dict[str, Any]) -> Set[str]:
        """Recursively extract script IDs from entity configuration."""
        script_ids = set()

        def find_scripts(data: Any):
            if isinstance(data, dict):
                if key.endswith("Script") and isinstance(value, str) and value:
                    if len(value) > 10 and ("-" in value or len(value) == 36):
                        script_ids.add(value)
                elif isinstance(value, (dict, list)):
                    find_scripts(value)
            elif isinstance(data, list):
                for item in data:
                    find_scripts(item)

        find_scripts(entity)
        return script_ids

    def _import_single_script(
        self, script_data: Dict[str, Any], token: str, base_url: str
    ) -> bool:
        """Import a single script with base64 encoding"""
        script_id = script_data.get("_id")
        script_name = script_data.get("name", "Unknown")

        if not script_id:
            error(f"Script '{script_name}' missing _id field, skipping")
            return False

        # Make a copy to avoid modifying original data
        payload_data = script_data.copy()

        # Encode script field from array of lines back to base64
        if "script" in payload_data:
            script_value = payload_data["script"]

            # Handle script as array of lines or string
            if isinstance(script_value, list):
                script_text = "\n".join(script_value)
            elif isinstance(script_value, str):
                script_text = script_value
            else:
                error(
                    f"Script '{script_name}' has invalid type: " f"{type(script_value)}"
                )
                return False

            if script_text:
                try:
                    # Encode to base64
                    encoded_bytes = script_text.encode("utf-8")
                    encoded_script = base64.b64encode(encoded_bytes).decode("ascii")
                    payload_data["script"] = encoded_script
                except Exception as e:
                    error(f"Failed to encode script '{script_name}': {str(e)}")
                    return False

        # Remove _rev if present
        payload_data.pop("_rev", None)

        # Construct URL
        url = self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/scripts/{script_id}",
        )

        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=2.1,resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, json.dumps(payload_data))
            info(f"✓ Imported script: {script_name}")
            return True
        except Exception as e:
            error(f"Failed to import script '{script_name}': {str(e)}")
            return False

    def _import_metadata(
        self,
        metadata_list: List[Dict[str, Any]],
        remote_entities: List[Dict[str, Any]],
        token: str,
        base_url: str,
        selected_entity_ids: Optional[List[str]],
    ) -> bool:
        """Import metadata for remote entities only"""
        # Get entity IDs from remote entities
        remote_entity_ids = {e.get("entityId") or e.get("_id") for e in remote_entities}

        success_count = 0
        for metadata_item in metadata_list:
            entity_id = metadata_item.get("entityId")
            metadata_xml = metadata_item.get("xml")

            if not entity_id or not metadata_xml:
                warning("Skipping metadata with missing entityId or xml")
                continue

            # Skip if not a remote entity
            if entity_id not in remote_entity_ids:
                continue

            if selected_entity_ids and entity_id not in selected_entity_ids:
                continue

            if self._import_single_metadata(entity_id, metadata_xml, token, base_url):
                success_count += 1

        if success_count > 0:
            info(f"Successfully imported {success_count} metadata item(s)")

        return True

    def _import_single_metadata(
        self, entity_id: str, metadata_xml: str, token: str, base_url: str
    ) -> bool:
        """Check if metadata exists and import if needed"""
        # Step 1: Check if metadata already exists
        check_url = self._construct_api_url(
            base_url,
            f"/am/saml2/jsp/exportmetadata.jsp?entityid="
            f"{quote(entity_id)}&realm={self.realm}",
        )

        headers = {
            "Accept-API-Version": "protocol=2.1,resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            # Check existing metadata
            response = self.make_http_request(check_url, "GET", headers)
            response_text = response.text

            # Check if metadata doesn't exist
            if "ERROR" in response_text and "No metadata for entity" in response_text:
                # Metadata doesn't exist, need to import
                info(f"Metadata not found for '{entity_id}', importing...")
                return self._post_metadata(entity_id, metadata_xml, token, base_url)
            else:
                # Metadata exists, then no need to import
                info(f"Metadata exists for '{entity_id}'")

        except Exception as e:
            # If check fails, try to import anyway
            warning(
                f"Could not check metadata for '{entity_id}': {str(e)}, "
                "attempting import..."
            )
            return self._post_metadata(entity_id, metadata_xml, token, base_url)

    def _post_metadata(
        self, entity_id: str, metadata_xml: str, token: str, base_url: str
    ) -> bool:
        """POST metadata to create/update remote entity"""
        url = self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/realm-config/"
            "saml2/remote/?_action=importEntity",
        )

        # Base64 URL encode the metadata XML
        try:
            encoded_metadata = base64.urlsafe_b64encode(
                metadata_xml.encode("utf-8")
            ).decode("ascii")
        except Exception as e:
            error(f"Failed to encode metadata for '{entity_id}': {str(e)}")
            return False

        payload = {"standardMetadata": encoded_metadata}

        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=2.1,resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "POST", headers, json.dumps(payload))
            info(f"✓ Imported metadata for: {entity_id}")
            return True
        except Exception as e:
            error(f"Failed to import metadata for '{entity_id}': {str(e)}")
            return False

    def _upsert_entity(
        self, entity_data: Dict[str, Any], location: str, token: str, base_url: str
    ) -> bool:
        """Upsert a SAML entity (hosted or remote)"""
        entity_id = entity_data.get("_id")
        entity_name = entity_data.get("entityId", "Unknown")

        if not entity_id:
            error(f"Entity '{entity_name}' missing _id field, skipping")
            return False

        # Make a copy and remove _rev
        payload_data = entity_data.copy()
        payload_data.pop("_rev", None)

        # Construct URL with location and ID
        url = self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/realm-config/"
            f"saml2/{location}/{entity_id}",
        )

        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=2.1,resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            # Special handling for hosted entities
            if location == "hosted":
                # Use httpx directly to avoid automatic 404 logging
                with httpx.Client(timeout=30.0) as client:
                    response = client.put(
                        url, headers=headers, data=json.dumps(payload_data)
                    )

                    if response.status_code == 404:
                        # Entity doesn't exist, Create it
                        post_hosted_url = self._construct_api_url(
                            base_url,
                            f"/am/json/realms/root/realms/{self.realm}/"
                            "realm-config/saml2/hosted?_action=create",
                        )
                        # Use make_http_request for creation
                        self.make_http_request(
                            post_hosted_url,
                            "POST",
                            headers,
                            json.dumps(payload_data),
                        )
                        info(f"✓ Created hosted entity: {entity_name}")
                        return True

                    # If not 404, check for other errors
                    response.raise_for_status()
                    info(f"✓ Updated hosted entity: {entity_name}")
                    return True
            else:
                # For remote entities, use standard PUT upsert
                self.make_http_request(url, "PUT", headers, json.dumps(payload_data))
                info(f"✓ Imported {location} entity: {entity_name}")
                return True

        except Exception as e:
            error(f"Failed to import {location} entity '{entity_name}': {str(e)}")
            return False

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """SAML import is handled by import_saml_data."""
        return True


def create_saml_import_command():
    """Create the SAML import command function"""

    def import_saml(
        file: str = typer.Option(
            None, "--file", help="Path to JSON file containing SAML data"
        ),
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Target realm name (default: {DEFAULT_REALM})",
        ),
        cherry_pick: str = typer.Option(
            None,
            "--cherry-pick",
            help=(
                "Import only specific entities by entityId "
                "(comma-separated, e.g., entity1,entity2)"
            ),
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
    ):
        """Import SAML configurations."""
        importer = SamlImporter(realm=realm)

        try:
            # Initialize authentication
            token, api_base_url = importer.initialize_auth(
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
            )

            # Handle diff mode
            if diff:
                info("Diff mode is not yet implemented for SAML")
                return

            # Load data from file (local or git)
            storage_mode = importer._get_storage_mode()

            if storage_mode == "git":
                git_manager = importer._setup_git_manager(branch)
                # Load from git (construct path manually as get_file_path doesn't exist)
                from pathlib import Path

                git_base = Path(git_manager.local_path)
                file_path = git_base / realm / "saml" / f"{realm}_saml.json"

                if not file_path.exists():
                    error(f"SAML data not found at {file_path}")
                    # Try discovery if specific file missing?
                    # For now hard fail as per SAML structure assumption
                    raise typer.Exit(1)

                with open(file_path, "r") as f:
                    export_data = json.load(f)
            else:
                # Load from local file
                if not file:
                    error("--file parameter is required in local storage mode")
                    raise typer.Exit(1)

                with open(file, "r") as f:
                    export_data = json.load(f)

            # Extract data section
            if "data" in export_data:
                data = export_data["data"]
            else:
                data = export_data

            # Perform hash validation (local mode only)
            if storage_mode == "local" and not importer.validate_import_hash(
                export_data, force_import
            ):
                raise typer.Exit(1)

            # Perform import
            success = importer.import_saml_data(
                data=data,
                token=token,
                base_url=api_base_url,
                cherry_pick_ids=cherry_pick,
            )

            if success:
                from trxo.utils.console import success as console_success

                console_success("SAML import completed successfully!")
            else:
                error("SAML import completed with errors")
                raise typer.Exit(1)

        except Exception as e:
            error(f"SAML import failed: {str(e)}")
            raise typer.Exit(1)
        finally:
            importer.cleanup()

    return import_saml
