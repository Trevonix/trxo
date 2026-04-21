"""
SAML import commands.

This module provides import functionality for
PingOne Advanced Identity Cloud SAML configurations.
"""

import base64
import json
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote

import httpx

from trxo_lib.config.api_headers import get_headers
from trxo_lib.config.constants import DEFAULT_REALM
from trxo_lib.logging import error, info, success, warning

from trxo_lib.imports.processor import BaseImporter


class SamlImporter(BaseImporter):
    """Importer for SAML with dependency handling."""

    def __init__(self, realm: str = DEFAULT_REALM):
        super().__init__()
        self.realm = realm
        self.imported_scripts = set()  # Track imported scripts

    def get_required_fields(self) -> List[str]:
        return []

    def get_item_type(self) -> str:
        return "saml"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        # This is a placeholder - actual endpoint depends on location
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/" "realm-config/saml2",
        )

    def import_from_file(
        self,
        file_path=None,
        realm=None,
        src_realm=None,
        jwk_path=None,
        sa_id=None,
        base_url=None,
        project_name=None,
        auth_mode=None,
        onprem_username=None,
        onprem_password=None,
        onprem_realm=None,
        force_import: bool = False,
        branch: str = None,
        diff: bool = False,
        sync: bool = False,
        cherry_pick: str = None,
    ) -> Any:
        """
        Override import flow for SAML only.
        Keeps BaseImporter behavior unchanged.
        """

        # ✅ Let BaseImporter handle diff mode
        if diff:
            return super().import_from_file(
                file_path=file_path,
                realm=realm,
                src_realm=src_realm,
                jwk_path=jwk_path,
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
                cherry_pick=cherry_pick,
            )

        info(f"Loading saml from local file: {file_path}")

        # Load JSON
        raw = self.file_loader.load_from_local_file(file_path)

        # Initialize auth (same as BaseImporter)
        token, api_base_url = self.initialize_auth(
            jwk_path=jwk_path,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
        )

        # Unwrap export format
        if isinstance(raw, list):
            saml_data = raw[0] if raw else {}
        elif isinstance(raw, dict):
            saml_data = raw.get("data", raw)
        else:
            saml_data = raw

        ok = self.import_saml_data(
            data=saml_data,
            token=token,
            base_url=api_base_url,
            cherry_pick_ids=cherry_pick,
        )

        if ok and sync:
            self._handle_sync_deletions(
                token=token,
                base_url=api_base_url,
                file_path=file_path,
                realm=realm,
                src_realm=src_realm,
                jwk_path=jwk_path,
                sa_id=sa_id,
                project_name=project_name,
                auth_mode=auth_mode,
                onprem_username=onprem_username,
                onprem_password=onprem_password,
                onprem_realm=onprem_realm,
                force=True,
            )

        return ok

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
                    if hasattr(self, "rollback_manager") and self.rollback_manager:
                        error("Failure detected. Stopping import for rollback.")
                        return False

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
        """Extract script IDs needed by selected entities, including recursive dependencies."""
        needed_ids = set()

        # Initial set from entities
        for location in ("hosted", "remote"):
            for entity in data.get(location, []):
                entity_id = entity.get("entityId") or entity.get("_id")
                if entity_id in selected_entity_ids:
                    needed_ids.update(self._extract_script_ids_from_config(entity))

        # Recursive discovery from scripts themselves
        all_scripts = {s.get("_id"): s for s in data.get("scripts", []) if s.get("_id")}

        to_check = list(needed_ids)
        checked = set()

        while to_check:
            sid = to_check.pop(0)
            if sid in checked:
                continue
            checked.add(sid)

            script_obj = all_scripts.get(sid)
            if script_obj:
                deps = self._extract_script_ids_from_config(script_obj)
                for dsid in deps:
                    if dsid not in needed_ids:
                        needed_ids.add(dsid)
                        to_check.append(dsid)

        return needed_ids

    def _extract_script_ids_from_config(self, config: Dict[str, Any]) -> Set[str]:
        """Recursively extract script IDs from configuration."""
        script_ids = set()

        def find_scripts(data: Any):
            if isinstance(data, dict):
                for key, value in data.items():
                    # Check keys like "attributeMapperScript", "adapterScript", etc.
                    if key.endswith("Script") and isinstance(value, str) and value:
                        if len(value) > 10 and ("-" in value or len(value) == 36):
                            script_ids.add(value)
                    elif isinstance(value, (dict, list)):
                        find_scripts(value)
            elif isinstance(data, list):
                for item in data:
                    find_scripts(item)

        find_scripts(config)
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

        headers = get_headers("saml")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, json.dumps(payload_data))
            info(f"✓ Imported script: {script_name}")
            if hasattr(self, "rollback_manager") and self.rollback_manager:
                # check if it existed in baseline
                baseline = self.rollback_manager.baseline_snapshot.get(
                    "scripts", {}
                ).get(script_id)
                action = "updated" if baseline else "created"
                self.rollback_manager.track_import(
                    f"script::{script_id}", action, baseline
                )
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

        headers = get_headers("saml_metadata_check")
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

        headers = get_headers("saml")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "POST", headers, json.dumps(payload))
            info(f"✓ Imported metadata for: {entity_id}")
            if hasattr(self, "rollback_manager") and self.rollback_manager:
                self.rollback_manager.track_import(entity_id + "_metadata", "created")
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

        headers = get_headers("saml")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            # Capture baseline for rollback (if available)
            baseline = None
            if hasattr(self, "rollback_manager") and self.rollback_manager:
                baseline = self.rollback_manager.baseline_snapshot.get(str(entity_id))

            # Special handling for hosted entities
            if location == "hosted":
                with httpx.Client(timeout=30.0) as client:
                    response = client.put(
                        url, headers=headers, data=json.dumps(payload_data)
                    )

                    if response.status_code == 404:
                        # Entity doesn't exist → Create
                        post_hosted_url = self._construct_api_url(
                            base_url,
                            f"/am/json/realms/root/realms/{self.realm}/"
                            "realm-config/saml2/hosted?_action=create",
                        )

                        self.make_http_request(
                            post_hosted_url,
                            "POST",
                            headers,
                            json.dumps(payload_data),
                        )

                        info(f"✓ Created hosted entity: {entity_name}")

                        if hasattr(self, "rollback_manager") and self.rollback_manager:
                            self.rollback_manager.track_import(
                                entity_id, "created", {"_location": "hosted"}
                            )

                        return True

                    # Existing entity → Update
                    response.raise_for_status()
                    info(f"✓ Updated hosted entity: {entity_name}")

                    if hasattr(self, "rollback_manager") and self.rollback_manager:
                        baseline_with_loc = baseline.copy() if baseline else {}
                        baseline_with_loc["_location"] = "hosted"
                        self.rollback_manager.track_import(
                            entity_id,
                            "updated",
                            baseline_with_loc,
                        )

                    return True

            else:
                # Remote entity → PUT upsert
                self.make_http_request(url, "PUT", headers, json.dumps(payload_data))
                info(f"✓ Imported {location} entity: {entity_name}")

                if hasattr(self, "rollback_manager") and self.rollback_manager:
                    baseline_with_loc = baseline.copy() if baseline else {}
                    baseline_with_loc["_location"] = "remote"
                    self.rollback_manager.track_import(
                        entity_id,
                        "updated",
                        baseline_with_loc,
                    )

                return True

        except Exception as e:
            error(f"Failed to import {location} entity '{entity_name}': {str(e)}")
            return False

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """SAML import is handled by import_saml_data."""
        return True

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete a single SAML entity (hosted or remote) via API"""
        # Try hosted first
        hosted_url = self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/realm-config/saml2/hosted/{item_id}",
        )
        auth_headers = self.build_auth_headers(token)
        saml_headers = get_headers("saml")

        headers = {**saml_headers, **auth_headers}

        try:
            # Check if it's hosted
            response = self.make_http_request(hosted_url, "GET", headers)
            if response.status_code == 200:
                self.make_http_request(hosted_url, "DELETE", headers)
                info(f"Successfully deleted hosted SAML entity: {item_id}")
                return True
        except Exception:
            pass

        # Try remote
        remote_url = self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/realm-config/saml2/remote/{item_id}",
        )
        try:
            self.make_http_request(remote_url, "DELETE", headers)
            info(f"Successfully deleted remote SAML entity: {item_id}")
            return True
        except Exception as e:
            error(f"Failed to delete SAML entity '{item_id}': {e}")
            return False


class SamlImportService:
    """Service wrapper for saml import operations."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        from trxo_lib.config.constants import DEFAULT_REALM

        realm = self.kwargs.get("realm", DEFAULT_REALM)
        importer = SamlImporter(realm=realm)

        # Typer passes 'file' which maps to 'file_path' in SamlImporter
        if "file" in self.kwargs:
            self.kwargs["file_path"] = self.kwargs.pop("file")

        # SamlImporter.import_from_file doesn't accept 'rollback' yet
        self.kwargs.pop("rollback", None)
        self.kwargs.pop("am_base_url", None)
        self.kwargs.pop("idm_base_url", None)
        self.kwargs.pop("idm_username", None)
        self.kwargs.pop("idm_password", None)

        return importer.import_from_file(**self.kwargs)
