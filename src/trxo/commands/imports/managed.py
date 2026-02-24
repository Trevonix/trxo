"""
Managed objects import command.

Import functionality for PingOne Advanced Identity Cloud managed objects with smart upsert logic:
- If object exists by name → PATCH to update
- If object doesn't exist → PUT to add to the list
- Handles both single objects and multiple objects
"""

import json
from typing import List, Dict, Any
import typer
from trxo.utils.console import error, info, warning
from .base_importer import BaseImporter


class ManagedObjectsImporter(BaseImporter):
    """Importer for PingOne Advanced Identity Cloud managed objects with smart upsert logic"""

    def __init__(self):
        super().__init__()
        self.product = "idm"

    def get_required_fields(self) -> List[str]:
        return []

    def get_item_type(self) -> str:
        return "managed_objects"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/openidm/config/managed"

    def _get_current_managed_config(self, token: str, base_url: str) -> Dict[str, Any]:
        """Fetch current managed objects configuration"""
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
            error(f"Failed to fetch current managed objects configuration: {e}")
            return {}

    def _find_object_by_name(self, objects_list: List[Dict], name: str) -> tuple:
        """Find object by name in the objects list. Returns (index, object) or (-1, None)"""
        for index, obj in enumerate(objects_list):
            if obj.get("name") == name:
                return index, obj
        return -1, None

    def _generate_patch_operations(
        self,
        existing_object: Dict[str, Any],
        new_object: Dict[str, Any],
        base_path: str = "",
    ) -> List[Dict[str, Any]]:
        """Generate PATCH operations by comparing existing and new objects"""
        operations = []

        # Handle all keys from new object
        for key, new_value in new_object.items():
            current_path = f"{base_path}/{key}" if base_path else f"/{key}"
            existing_value = existing_object.get(key)

            if existing_value != new_value:
                if isinstance(new_value, dict) and isinstance(existing_value, dict):
                    # Recursively handle nested objects
                    nested_ops = self._generate_patch_operations(
                        existing_value, new_value, current_path
                    )
                    operations.extend(nested_ops)
                else:
                    # Value changed or new field
                    operations.append(
                        {
                            "operation": "replace" if key in existing_object else "add",
                            "field": current_path,
                            "value": new_value,
                        }
                    )

        return operations

    def _get_server_schema_properties(
        self, object_name: str, token: str, base_url: str
    ) -> Dict[str, Any]:
        """Fetch all properties from server schema for a managed object"""
        url = f"{base_url}/openidm/schema/managed/{object_name}"
        info(
            f"[DEBUG] Fetching server schema properties for '{object_name}' from: {url}"
        )
        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=2.1,resource=2.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            response = self.make_http_request(url, "GET", headers)
            schema_data = response.json()
            properties = schema_data.get("properties", {})
            info(
                f"[DEBUG] Found {len(properties)} properties on server for '{object_name}'"
            )
            return properties
        except Exception as e:
            warning(f"Failed to fetch server schema for '{object_name}': {e}")
            return {}

    def _delete_orphaned_properties(
        self,
        object_name: str,
        source_properties: Dict[str, Any],
        token: str,
        base_url: str,
    ):
        """Delete properties that exist on server but not in
        source to ensure source and destination are identical"""
        info(f"[DEBUG] Checking for orphaned properties for '{object_name}'...")

        # Get all properties from server
        server_properties = self._get_server_schema_properties(
            object_name, token, base_url
        )
        if not server_properties:
            info(
                f"[DEBUG] No server properties found for '{object_name}',"
                " skipping orphaned property check"
            )
            return

        # Find properties that exist on server but not in source
        source_prop_names = (
            set(source_properties.keys()) if source_properties else set()
        )
        server_prop_names = set(server_properties.keys())

        info(
            f"[DEBUG] Source has {len(source_prop_names)} properties: {sorted(source_prop_names)}"
        )
        info(
            f"[DEBUG] Server has {len(server_prop_names)} properties: {sorted(server_prop_names)}"
        )

        orphaned_props = server_prop_names - source_prop_names

        # Exclude system properties that should not be deleted
        excluded_properties = {"_meta", "_notifications"}
        orphaned_props = orphaned_props - excluded_properties

        if not orphaned_props:
            info(
                f"[DEBUG] No orphaned properties found for '{object_name}' "
                "- source and server are in sync"
            )
            return

        info(
            f"[DEBUG] Found {len(orphaned_props)} orphaned property/"
            f"properties to delete for '{object_name}': {sorted(orphaned_props)}"
        )

        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=2.1,resource=2.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        for prop_name in orphaned_props:
            url = f"{base_url}/openidm/schema/managed/{object_name}/properties/{prop_name}"
            info(
                f"[DEBUG] Deleting orphaned property '{prop_name}' from '{object_name}' "
                f"via DELETE: {url}"
            )
            try:
                self.make_http_request(url, "DELETE", headers, timeout=60.0)
                info(
                    f"✓ Deleted orphaned property: {prop_name} from managed object: {object_name}"
                )
            except Exception as e:
                # Log error but continue with other deletions
                error(
                    f"✗ Failed to delete orphaned property '{prop_name}' for '{object_name}': {e}"
                )

    def _update_relationship_properties(
        self, object_name: str, object_data: Dict[str, Any], token: str, base_url: str
    ):
        """Update relationship properties for a managed object via specific endpoint

        This is called after PATCH/PUT to ensure relationship properties are updated
        in the repo.ds config as well, since PATCH/PUT operations don't automatically
        update the schema endpoint configuration.
        """
        info(f"[DEBUG] Starting relationship properties update for '{object_name}'...")
        schema = object_data.get("schema", {})
        if not schema or not isinstance(schema, dict):
            info(
                f"[DEBUG] No schema found for '{object_name}',"
                "skipping relationship property updates"
            )
            return

        properties = schema.get("properties", {})
        if not properties or not isinstance(properties, dict):
            info(
                f"[DEBUG] No properties found in schema for '{object_name}', "
                "skipping relationship property updates"
            )
            return

        relationship_props = [
            prop_name
            for prop_name, prop_data in properties.items()
            if isinstance(prop_data, dict) and prop_data.get("type") == "relationship"
        ]

        if not relationship_props:
            info(
                f"[DEBUG] No relationship properties found for '{object_name}', "
                "skipping relationship property updates"
            )
            return

        info(
            f"[DEBUG] Found {len(relationship_props)} relationship property/"
            f"properties to update for '{object_name}': {relationship_props}"
        )

        for prop_name, prop_data in properties.items():
            if isinstance(prop_data, dict) and prop_data.get("type") == "relationship":
                url = f"{base_url}/openidm/schema/managed/{object_name}/properties/{prop_name}"
                info(
                    f"[DEBUG] Processing relationship property '{prop_name}' for '{object_name}'"
                )

                headers = {
                    "Content-Type": "application/json",
                    "Accept-API-Version": "protocol=2.1,resource=2.0",
                }
                headers = {**headers, **self.build_auth_headers(token)}

                # Try to fetch existing property schema to preserve robust configuration
                existing_prop_data = None
                try:
                    info(
                        f"[DEBUG] Fetching existing property schema for '{prop_name}' from: {url}"
                    )
                    response = self.make_http_request(url, "GET", headers)
                    existing_prop_data = response.json()
                    info(
                        f"[DEBUG] Successfully fetched existing property schema for '{prop_name}'"
                    )
                except Exception as e:
                    # Likely property doesn't exist yet or other error;
                    # ignore and proceed with fresh data
                    info(
                        f"[DEBUG] Could not fetch existing property schema for '{prop_name}' "
                        f"(may be new): {e}"
                    )

                # Fix for Schema endpoint strictness on reverse relationships
                # The schema endpoint requires 'reverseProperty' in resourceCollection items
                # matching 'reversePropertyName' when reverseRelationship is True.
                if prop_data.get("reverseRelationship") is True:
                    info(
                        f"[DEBUG] Property '{prop_name}' has reverseRelationship=True, "
                        "processing reverse property logic"
                    )
                    rev_name = prop_data.get("reversePropertyName")
                    res_collection = prop_data.get("resourceCollection")

                    if rev_name and isinstance(res_collection, list):
                        # We work on a copy to avoid modifying
                        # the original data structure unexpectedly
                        prop_data = prop_data.copy()
                        new_res_collection = []

                        existing_collection_map = {}
                        if (
                            existing_prop_data
                            and "resourceCollection" in existing_prop_data
                        ):
                            info(
                                f"[DEBUG] Building existing collection map from "
                                f"server data for '{prop_name}'"
                            )
                            for item in existing_prop_data["resourceCollection"]:
                                if isinstance(item, dict) and "path" in item:
                                    existing_collection_map[item["path"]] = item

                        for res in res_collection:
                            if isinstance(res, dict):
                                res_copy = res.copy()
                                if "reverseProperty" not in res_copy:
                                    # Strategy 1: Try to recover from existing server config
                                    matched_existing = existing_collection_map.get(
                                        res_copy.get("path")
                                    )
                                    if (
                                        matched_existing
                                        and "reverseProperty" in matched_existing
                                    ):
                                        info(
                                            f"[DEBUG] Recovered reverseProperty from "
                                            f"server config for path '{res_copy.get('path')}'"
                                        )
                                        res_copy["reverseProperty"] = matched_existing[
                                            "reverseProperty"
                                        ]
                                    else:
                                        # Strategy 2: Inject default structure
                                        # required by schema endpoint
                                        info(
                                            f"[DEBUG] Injecting default 'reverseProperty' schema "
                                            f"for relationship '{prop_name}' "
                                            f"(path: {res_copy.get('path')})"
                                        )
                                        res_copy["reverseProperty"] = {
                                            "type": "relationship",
                                            "validate": False,
                                            "resourceCollection": {
                                                "notify": False,
                                                "query": {
                                                    "fields": ["_id"],
                                                    "queryFilter": "true",
                                                },
                                            },
                                        }
                                new_res_collection.append(res_copy)
                            else:
                                new_res_collection.append(res)
                        prop_data["resourceCollection"] = new_res_collection

                try:
                    payload = json.dumps(prop_data)
                    info(
                        f"[DEBUG] Waiting 15 seconds before updating property '{prop_name}' "
                        f"to allow schema changes to propagate..."
                    )
                    import time

                    time.sleep(15)  # Buffer time needed for schema changes to propagate
                    info(
                        f"[DEBUG] Updating relationship property '{prop_name}' via PUT: {url}"
                    )
                    info(
                        f"[DEBUG] Payload for '{prop_name}': {payload[:200]}..."
                        if len(payload) > 200
                        else f"[DEBUG] Payload for '{prop_name}': {payload}"
                    )
                    # Use a longer timeout (60s) for property updates as they trigger schema reloads
                    self.make_http_request(url, "PUT", headers, payload, timeout=60.0)
                    info(
                        f"✓ Updated relationship property: {prop_name} "
                        f"for managed object: {object_name}"
                    )
                except Exception as e:
                    # We log error but don't fail the entire operation as the main object is updated
                    error(
                        f"✗ Failed to update relationship"
                        f"property '{prop_name}' for '{object_name}': {e}"
                    )

        info(f"[DEBUG] Completed relationship properties update for '{object_name}'")

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Smart upsert for managed objects using PATCH for updates, PUT for creates"""
        # Support both single managed object and full config structures
        # - If a full managed config with 'objects' is provided, iterate and process each object
        if (
            isinstance(item_data, dict)
            and "objects" in item_data
            and isinstance(item_data["objects"], list)
        ):
            url = self.get_api_endpoint("", base_url)
            headers = {
                "Content-Type": "application/json",
                "Accept-API-Version": "protocol=2.1,resource=1.0",
            }
            headers = {**headers, **self.build_auth_headers(token)}

            # Get current configuration once, keep a local copy updated as we go
            current_config = self._get_current_managed_config(token, base_url)
            if not current_config:
                error("Could not retrieve current managed objects configuration")
                return False

            current_objects = current_config.get("objects", [])
            all_ok = True
            for obj in item_data["objects"]:
                if not isinstance(obj, dict):
                    warning("Skipping non-dict entry in 'objects'")
                    continue
                name = obj.get("name")
                if not isinstance(name, str) or not name:
                    warning("Skipping managed object without a valid 'name'")
                    continue

                idx, existing_object = self._find_object_by_name(current_objects, name)
                if idx >= 0:
                    info(
                        f"[DEBUG] Managed object '{name}' exists at index {idx}, "
                        "generating PATCH operations..."
                    )
                    patch_operations = self._generate_patch_operations(
                        existing_object, obj, f"/objects/{idx}"
                    )
                    if not patch_operations:
                        info(f"[DEBUG] No changes needed for managed object: {name}")
                        info(f"No changes needed for managed object: {name}")
                        # Still check for orphaned properties even if no patch operations
                        source_schema = obj.get("schema", {})
                        source_properties = (
                            source_schema.get("properties", {})
                            if isinstance(source_schema, dict)
                            else {}
                        )
                        self._delete_orphaned_properties(
                            name, source_properties, token, base_url
                        )
                    else:
                        payload = json.dumps(patch_operations)
                        try:
                            info(
                                f"[DEBUG] Applying PATCH to update '{name}' "
                                f"with {len(patch_operations)} operations..."
                            )
                            self.make_http_request(url, "PATCH", headers, payload)
                            info(
                                f"✓ Updated existing managed object: "
                                f"{name} ({len(patch_operations)} changes)"
                            )

                            # Update relationship properties (required to update repo.ds config)
                            info(
                                f"[DEBUG] Starting post-PATCH operations for '{name}'..."
                            )
                            source_schema = obj.get("schema", {})
                            source_properties = (
                                source_schema.get("properties", {})
                                if isinstance(source_schema, dict)
                                else {}
                            )
                            self._update_relationship_properties(
                                name, obj, token, base_url
                            )

                            # Delete orphaned properties to
                            # ensure source and destination are identical
                            self._delete_orphaned_properties(
                                name, source_properties, token, base_url
                            )

                            # Keep local state in sync
                            current_objects[idx] = obj
                            info(f"[DEBUG] Completed all operations for '{name}'")
                        except Exception as e:
                            error(f"✗ Failed to update managed object '{name}': {e}")
                            all_ok = False
                else:
                    info(
                        f"[DEBUG] Managed object '{name}' does not exist, will create new object..."
                    )
                    updated_objects = current_objects + [obj]
                    updated_config = {**current_config, "objects": updated_objects}
                    payload = json.dumps(updated_config)
                    try:
                        info(
                            f"[DEBUG] Applying PUT to create new managed object '{name}'..."
                        )
                        self.make_http_request(url, "PUT", headers, payload)
                        info(f"✓ Added new managed object: {name}")

                        # Update relationship properties (required to update repo.ds config)
                        info(f"[DEBUG] Starting post-PUT operations for '{name}'...")
                        source_schema = obj.get("schema", {})
                        source_properties = (
                            source_schema.get("properties", {})
                            if isinstance(source_schema, dict)
                            else {}
                        )
                        self._update_relationship_properties(name, obj, token, base_url)

                        # Delete orphaned properties to ensure source and destination are identical
                        self._delete_orphaned_properties(
                            name, source_properties, token, base_url
                        )

                        # Keep local state in sync
                        current_objects = updated_objects
                        current_config = updated_config
                        info(f"[DEBUG] Completed all operations for '{name}'")
                    except Exception as e:
                        error(f"✗ Failed to add managed object '{name}': {e}")
                        all_ok = False
            return all_ok

        # Fallback: treat item_data as single managed object dict
        selected_object = item_data

        object_name = (
            selected_object.get("name") if isinstance(selected_object, dict) else None
        )
        if not object_name or not isinstance(object_name, str):
            error("Managed object missing a valid 'name'; required for upsert")
            return False

        # Get current configuration
        current_config = self._get_current_managed_config(token, base_url)
        if not current_config:
            error("Could not retrieve current managed objects configuration")
            return False

        current_objects = current_config.get("objects", [])

        # Find if object exists
        index, existing_object = self._find_object_by_name(current_objects, object_name)

        url = self.get_api_endpoint("", base_url)
        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=2.1,resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        if index >= 0:
            # Object exists - use PATCH for efficient updates
            info(
                f"[DEBUG] Managed object '{object_name}' exists at index {index}, "
                "generating PATCH operations..."
            )
            patch_operations = self._generate_patch_operations(
                existing_object, selected_object, f"/objects/{index}"
            )

            if not patch_operations:
                info(f"[DEBUG] No changes needed for managed object: {object_name}")
                info(f"No changes needed for managed object: {object_name}")
                # Still check for orphaned properties even if no patch operations
                source_schema = selected_object.get("schema", {})
                source_properties = (
                    source_schema.get("properties", {})
                    if isinstance(source_schema, dict)
                    else {}
                )
                self._delete_orphaned_properties(
                    object_name, source_properties, token, base_url
                )
                return True

            payload = json.dumps(patch_operations)

            try:
                info(
                    f"[DEBUG] Applying PATCH to update '{object_name}' "
                    f"with {len(patch_operations)} operations..."
                )
                self.make_http_request(url, "PATCH", headers, payload)
                info(
                    "✓ Updated existing managed object: "
                    f"{object_name} ({len(patch_operations)} changes)"
                )

                # Update relationship properties (required to update repo.ds config)
                info(f"[DEBUG] Starting post-PATCH operations for '{object_name}'...")
                source_schema = selected_object.get("schema", {})
                source_properties = (
                    source_schema.get("properties", {})
                    if isinstance(source_schema, dict)
                    else {}
                )
                self._update_relationship_properties(
                    object_name, selected_object, token, base_url
                )

                # Delete orphaned properties to ensure source and destination are identical
                self._delete_orphaned_properties(
                    object_name, source_properties, token, base_url
                )

                info(f"[DEBUG] Completed all operations for '{object_name}'")
                return True
            except Exception as e:
                error(f"✗ Failed to update managed object '{object_name}': {e}")
                return False
        else:
            # Object doesn't exist - use PUT to add to the objects array
            info(
                f"[DEBUG] Managed object '{object_name}' does not exist, will create new object..."
            )
            updated_objects = current_objects + [selected_object]
            updated_config = {**current_config, "objects": updated_objects}
            payload = json.dumps(updated_config)

            try:
                info(
                    f"[DEBUG] Applying PUT to create new managed object '{object_name}'..."
                )
                self.make_http_request(url, "PUT", headers, payload)
                info(f"✓ Added new managed object: {object_name}")

                # Update relationship properties (required to update repo.ds config)
                info(f"[DEBUG] Starting post-PUT operations for '{object_name}'...")
                source_schema = selected_object.get("schema", {})
                source_properties = (
                    source_schema.get("properties", {})
                    if isinstance(source_schema, dict)
                    else {}
                )
                self._update_relationship_properties(
                    object_name, selected_object, token, base_url
                )

                # Delete orphaned properties to ensure source and destination are identical
                self._delete_orphaned_properties(
                    object_name, source_properties, token, base_url
                )

                info(f"[DEBUG] Completed all operations for '{object_name}'")
                return True
            except Exception as e:
                error(f"✗ Failed to add managed object '{object_name}': {e}")
                return False

    def _load_managed_objects_file(self, file_path: str) -> Any:
        """Load managed objects file with flexible format support"""
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
                # Raw managed objects data
                return data
        elif isinstance(data, list):
            # Array of managed objects
            return data
        else:
            raise ValueError("Invalid file format. Expected JSON object or array")

    def load_data_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Load managed objects with flexible format support

        Override to handle multiple managed object file formats while
        allowing base class to handle hash validation and options.
        """
        # Load file with custom format support
        data = self._load_managed_objects_file(file_path)

        # Normalize into a list of managed-object dicts
        objects_to_process: List[Dict[str, Any]] = []

        if isinstance(data, dict):
            if "objects" in data and isinstance(data["objects"], list):
                # Full config format: {"objects": [...]}
                objects_to_process = [o for o in data["objects"] if isinstance(o, dict)]
            else:
                # Single managed object dict
                objects_to_process = [data]
        elif isinstance(data, list):
            # Could be a list of objects, or a single wrapper dict with objects
            if (
                len(data) == 1
                and isinstance(data[0], dict)
                and "objects" in data[0]
                and isinstance(data[0]["objects"], list)
            ):
                # Wrapped config: [{"objects": [...]}]
                objects_to_process = [
                    o for o in data[0]["objects"] if isinstance(o, dict)
                ]
            else:
                # Direct list of objects
                objects_to_process = [o for o in data if isinstance(o, dict)]
        else:
            raise ValueError(
                "Invalid file format. Expected object or array of managed objects"
            )

        if not objects_to_process:
            warning("No managed objects found to process in the provided file")

        return objects_to_process


def create_managed_import_command():
    """Create the managed objects import command function"""

    def import_managed(
        file: str = typer.Option(
            None, "--file", help="Path to JSON file containing managed objects"
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
        rollback: bool = typer.Option(
            False,
            "--rollback",
            help="Automatically rollback imported items on first failure (requires git storage)",
        ),
    ):
        """Import managed objects from JSON file (local mode) or Git repository (Git mode).

        Updates existing objects by name (PATCH) or adds new ones (PUT).
        """
        importer = ManagedObjectsImporter()
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
            rollback=rollback,
        )

    return import_managed
