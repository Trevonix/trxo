"""
Services import commands.

Import functionality for PingOne Advanced Identity Cloud services.
Supports both global and realm-based services:
- Global: PUT only (update existing services, no creation)
- Realm: PUT with upsert capability (create or update)

Future-ready with flexible realm selection.
"""

import json
from typing import Any, Dict, List, Optional


from trxo_lib.config.api_headers import get_headers
from trxo_lib.constants import DEFAULT_REALM
from trxo_lib.utils.console import error, info, warning

from trxo_lib.operations.imports.base_importer import BaseImporter


class ServicesImporter(BaseImporter):
    """Importer for PingOne Advanced Identity Cloud services with scope-aware behavior"""

    def __init__(self, scope: str = "global", realm: str = DEFAULT_REALM):
        super().__init__()
        self.scope = scope.lower()
        self.realm = realm

    def get_required_fields(self) -> List[str]:
        return []  # We need _type object which contains _id

    def get_item_type(self) -> str:
        # Use consistent naming for hash validation
        return "services"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        if self.scope == "global":
            return self._construct_api_url(
                base_url, f"/am/json/global-config/services/{item_id}"
            )
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/"
            f"realm-config/services/{item_id}",
        )

    def _get_item_identifier(self, item: Dict[str, Any]) -> Optional[str]:
        """
        Override identifier logic for services.
        Services use _type._id as real identifier.
        """
        if not isinstance(item, dict):
            return None

        # Services often have empty "_id"
        type_info = item.get("_type", {})
        service_id = type_info.get("_id")

        if service_id:
            return service_id

        # Fallback to base logic
        return super()._get_item_identifier(item)

    def _prepare_service_payload(self, item_data: Dict[str, Any]) -> str:
        """Prepare service payload by removing dynamic fields."""
        # Remove dynamic fields that should not be imported
        excluded_fields = {
            "_rev",
            "_lastModified",
            "_lastModifiedBy",
            "_id",
            "_type",
        }

        # Keep all service configuration data except excluded fields
        service_config = {
            k: v for k, v in item_data.items() if k not in excluded_fields
        }

        return json.dumps(service_config, indent=2)

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Update service based on scope (global=update only, realm=upsert)"""
        # Get service ID from _type._id field
        item_id = item_data.get("_id")
        if not item_id:
            type_info = item_data.get("_type", {})
            item_id = type_info.get("_id")
            if not item_id:
                error("Service missing '_type._id'; required for service operations")
                return False

        # Extract nextDescendents before processing existing payload
        next_descendents = item_data.pop("nextDescendents", [])

        # Preserve type_info for creation
        type_info = item_data.get("_type")

        # Prepare base payload (for PUT)
        payload = self._prepare_service_payload(item_data)

        url = self.get_api_endpoint(item_id, base_url)
        headers = get_headers("services")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            try:
                # Try PUT first (update existing)
                self.make_http_request(url, "PUT", headers, payload)
                if self.scope == "global":
                    info(f"Updated global service: {item_id}")
                else:
                    info(f"Upserted realm service ({self.realm}): {item_id}")
            except Exception as put_error:
                # If realm scope and PUT failed (probably 404), try create
                if self.scope == "realm":
                    try:
                        # For creation, we might need _type in the payload
                        # Some services support creation at the specific ID URL
                        create_url = f"{url}?_action=create"

                        creation_data = item_data.copy()
                        # Cleanup creation data (remove metadata but keep ID/Type if needed)
                        for k in ["_rev", "_lastModified", "_lastModifiedBy"]:
                            creation_data.pop(k, None)

                        # Use the instance-specific URL for creation (works for many AM services)
                        self.make_http_request(
                            create_url,
                            "POST",
                            headers,
                            json.dumps(creation_data, indent=2),
                        )
                        info(f"Created realm service ({self.realm}): {item_id}")
                    except Exception as create_error:
                        raise create_error
                else:
                    raise put_error

            # Process descendants if any
            if next_descendents:
                info(
                    f"Processing {len(next_descendents)} descendants for "
                    f"service '{item_id}'..."
                )
                for descendant in next_descendents:
                    desc_type = descendant.get("_type", {}).get("_id")
                    desc_id = descendant.get("_id")
                    if desc_type and desc_id:
                        # Construct URL: service_url / type / id
                        desc_url = f"{url}/{desc_type}/{desc_id}"

                        # Prepare payload (remove _rev)
                        desc_payload_data = {
                            k: v for k, v in descendant.items() if k not in ["_rev"]
                        }
                        desc_payload = json.dumps(desc_payload_data, indent=2)

                        # Fetch schema to ensure payload completeness
                        desc_schema_url = f"{url}/{desc_type}?_action=schema"
                        try:
                            desc_schema_response = self.make_http_request(
                                desc_schema_url, "POST", headers
                            )
                            if (
                                desc_schema_response
                                and desc_schema_response.status_code == 200
                            ):
                                desc_schema = desc_schema_response.json()
                                schema_properties = desc_schema.get("properties", {})

                                # Compare and add missing fields
                                for prop, prop_def in schema_properties.items():
                                    if prop not in desc_payload_data:
                                        # Determine default value based on type
                                        prop_type = prop_def.get("type", "string")
                                        default_val = ""

                                        if prop_type == "boolean":
                                            default_val = False
                                        elif (
                                            prop_type == "integer"
                                            or prop_type == "number"
                                        ):
                                            default_val = 0
                                        elif prop_type == "array":
                                            default_val = []
                                        elif prop_type == "object":
                                            default_val = {}

                                        desc_payload_data[prop] = default_val

                                # Update payload with added fields
                                desc_payload = json.dumps(desc_payload_data, indent=2)
                        except Exception as e:
                            # Log warning but proceed with original payload
                            warning(
                                f"Could not validate schema for descendant "
                                f"{desc_id}: {e}"
                            )
                        try:
                            self.make_http_request(
                                desc_url, "PUT", headers, desc_payload
                            )
                        except Exception as de:
                            warning(
                                f"Failed to update descendant {desc_id} for "
                                f"service {item_id}: {de}"
                            )
                    else:
                        warning(
                            f"Skipping descendant without _type._id or _id in "
                            f"service {item_id}"
                        )

            return True
        except Exception as e:
            action = "update" if self.scope == "global" else "upsert"
            error(f"Failed to {action} service '{item_id}': {e}")
            return False

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """Delete a single service configuration via API"""
        url = self.get_api_endpoint(item_id, base_url)
        headers = get_headers("services")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "DELETE", headers)
            info(f"Deleted realm service ({self.realm}): {item_id}")
            return True
        except Exception as e:
            error(f"Failed to delete service '{item_id}': {e}")
            return False

