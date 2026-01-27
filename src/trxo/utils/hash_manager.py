"""
Hash Manager for data integrity verification.

This module provides centralized hash management for export/import operations,
ensuring data integrity through checksum verification.
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from trxo.utils.console import success, error, warning
from trxo.constants import DEFAULT_REALM


class HashManager:
    """Manages hash creation, storage, and validation for export/import operations"""

    def __init__(self, config_store):
        """Initialize with ConfigStore instance"""
        self.config_store = config_store
        self.checksums_file = config_store.base_dir / "checksums.json"

    def create_hash(self, data: Any, command_name: str) -> str:
        """Create a normalized hash for any data structure"""
        # Step 1: Remove all dynamic fields that change between export/import
        cleaned_data = self._remove_dynamic_fields(data)

        # Step 2: Normalize structure to always be a list of items
        normalized_items = self._extract_items_for_hash(cleaned_data)

        # Step 3: Sort items by _id or name for consistent ordering
        sorted_items = self._sort_items_for_hash(normalized_items)

        # Step 4: Create hash from sorted, cleaned items
        hash_input = json.dumps(sorted_items, sort_keys=True, separators=(",", ":"))
        hash_value = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        return hash_value

    def save_export_hash(
        self, command_name: str, hash_value: str, file_path: Optional[str] = None
    ) -> None:
        """Save hash with metadata for exported data"""
        metadata = {
            "hash": hash_value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": "export",
            "file_path": str(file_path) if file_path else None,
        }

        self._save_hash_with_metadata(command_name, metadata)

    def validate_import_hash(
        self, data: Any, command_name: str, force: bool = False
    ) -> bool:
        """Validate import data against stored export hash"""
        if force:
            warning("Force import enabled - skipping integrity check")
            return True

        try:
            # Generate hash for import data
            import_hash = self.create_hash(data, command_name)

            # Get stored export hash
            stored_metadata = self._get_hash_metadata(command_name)

            if not stored_metadata:
                error(
                    f"Integrity metadata not found for command "
                    f"'{command_name}'. Please export data first."
                )
                return False

            stored_hash = stored_metadata.get("hash")
            if not stored_hash:
                error(f"Invalid integrity metadata for command '{command_name}'")
                return False

            # Compare hashes
            if import_hash == stored_hash:
                success("Data integrity verified - import data matches exported data")
                return True
            else:
                error(
                    "Data integrity check failed - import data differs from exported data"
                )
                error("This could indicate:")
                error("  - File has been modified after export")
                error("  - Different data source")
                error("  - Data corruption")
                error("  - Use --force-import to bypass validation")
                return False

        except Exception as e:
            error(f"Data integrity check error: {str(e)}")
            return False

    def get_hash_info(self, command_name: str) -> Optional[Dict[str, Any]]:
        """Get hash information for a command"""
        return self._get_hash_metadata(command_name)

    def list_all_hashes(self) -> Dict[str, Any]:
        """List all stored hashes with metadata"""
        if not self.checksums_file.exists():
            return {}

        try:
            with open(self.checksums_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _remove_dynamic_fields(self, data: Any) -> Any:
        """Remove all fields that change between export/import"""
        if isinstance(data, dict):
            cleaned = {}
            # Fields that should never affect hash comparison
            skip_fields = {
                "_rev",
                "lastModified",
                "createdDate",
                "modifiedDate",
                "resultCount",
                "remainingPagedResults",
                "totalPagedResults",
                "timestamp",  # metadata timestamp
            }

            for key, value in data.items():
                if key not in skip_fields:
                    cleaned[key] = self._remove_dynamic_fields(value)
            return cleaned

        elif isinstance(data, list):
            return [self._remove_dynamic_fields(item) for item in data]

        return data

    def _extract_items_for_hash(self, data: Any) -> List[Dict[str, Any]]:
        """Extract actual items from any data structure format"""
        if isinstance(data, list):
            # Direct list of items - check if it's a list of config objects
            if data and isinstance(data[0], dict):
                # If first item has typical config structure, treat as list of items
                first_item = data[0]
                if self._is_config_object(first_item):
                    return data
                # If it's a simple list of values, wrap in single object
                return [{"items": data}]
            return data

        if isinstance(data, dict):
            # Check for standard API response format with 'result' array
            if "result" in data and isinstance(data["result"], list):
                return data["result"]

            # Check for 'data' field (our export format)
            if "data" in data:
                return self._extract_items_for_hash(data["data"])

            # Check for managed objects format with 'objects' array
            if "objects" in data and isinstance(data["objects"], list):
                # Managed objects have specific structure: {"objects": [...]}
                # Extract just the objects array for consistent hashing
                return data["objects"]

            # Check if this is a single configuration object (like authn settings)
            if self._is_config_object(data):
                return [data]

            # Check for nested structures (like themes with realm data)
            # Only extract nested arrays if they contain config objects
            items = []
            for key, value in data.items():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    # Only extend if the list contains config objects
                    if self._is_config_object(value[0]):
                        items.extend(value)
                elif isinstance(value, dict) and self._looks_like_realm_structure(
                    key, value
                ):
                    # Handle realm-specific nested structures
                    nested_items = self._extract_items_for_hash(value)
                    items.extend(nested_items)

            if items:
                return items
            else:
                # Single object
                return [data]

        return []

    def _is_config_object(self, obj: Dict[str, Any]) -> bool:
        """Check if an object looks like a configuration object"""
        if not isinstance(obj, dict):
            return False

        # Check for common config object indicators
        config_indicators = [
            "_id",
            "_type",
            "name",
            "security",
            "core",
            "general",
            "trees",
        ]
        return any(key in obj for key in config_indicators)

    def _looks_like_realm_structure(self, key: str, value: Dict[str, Any]) -> bool:
        """Check if this looks like a realm-specific structure (like themes)"""
        if not isinstance(value, dict):
            return False

        realm_indicators = ["realm", DEFAULT_REALM, "beta", "root"]
        if not any(indicator in key.lower() for indicator in realm_indicators):
            return False

        # Check if the value contains arrays of config objects
        for v in value.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return True

        return False

    def _sort_items_for_hash(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort items consistently for hash calculation"""
        if not items:
            return items

        # Try to sort by _id, then name, then first available key
        def get_sort_key(item):
            if isinstance(item, dict):
                if "_id" in item:
                    return str(item["_id"])
                elif "name" in item:
                    return str(item["name"])
                elif "id" in item:
                    return str(item["id"])
                elif item:
                    # Use first available key's value
                    first_key = next(iter(item.keys()))
                    return str(item[first_key])
            return str(item)

        try:
            return sorted(items, key=get_sort_key)
        except (TypeError, KeyError):
            # If sorting fails, return as-is (better than crashing)
            return items

    def _save_hash_with_metadata(
        self, command_name: str, metadata: Dict[str, Any]
    ) -> None:
        """Save hash with metadata to checksums file"""
        # Load existing hashes or create new structure
        if self.checksums_file.exists():
            try:
                with open(self.checksums_file, "r", encoding="utf-8") as f:
                    hashes = json.load(f)
            except (json.JSONDecodeError, IOError):
                hashes = {}
        else:
            hashes = {}

        # Update hash for command
        hashes[command_name] = metadata

        # Ensure parent directory exists
        self.checksums_file.parent.mkdir(parents=True, exist_ok=True)

        # Save back to file
        with open(self.checksums_file, "w", encoding="utf-8") as f:
            json.dump(hashes, f, indent=2)

    def _get_hash_metadata(self, command_name: str) -> Optional[Dict[str, Any]]:
        """Get hash metadata for a command"""
        if not self.checksums_file.exists():
            return None

        try:
            with open(self.checksums_file, "r", encoding="utf-8") as f:
                hashes = json.load(f)
            return hashes.get(command_name)
        except (json.JSONDecodeError, IOError):
            return None


def get_command_name_from_item_type(item_type: str) -> str:
    """Map item types to command names for hash lookup"""
    type_to_command = {
        "Environment_Secrets": "esv_secrets",
        "Environment_Variables": "esv_variables",
        "themes (ui/themerealm)": "themes",
        "managed_objects": "managed",
        "sync mappings": "mappings",
        "journeys": "journeys",
        "realms": "realms",
        "scripts": "scripts",
        "services": "services",
        "global services": "services",
        "realm services": "services",
        "policies": "policies",
        "OAuth2_Clients": "oauth",
        "saml entities": "saml",
        "authentication settings": "authn",
        "email templates": "email_templates",
        "custom endpoints": "endpoints",
        "connectors": "connectors",
        "applications": "applications",
        "Privileges": "privileges",
        "webhooks": "webhooks",
        # Agent mappings - match export command names
        "IdentityGatewayAgent agents": "agents_gateway",
        "J2EEAgent agents": "agents_java",
        "WebAgent agents": "agents_web",
        "items": "items",
    }

    # First check for exact match
    if item_type in type_to_command:
        return type_to_command[item_type]

    # Clean up realm suffixes before lookup
    clean_item_type = item_type
    if " (" in clean_item_type:
        clean_item_type = clean_item_type.split(" (")[0]

    # Check cleaned version
    if clean_item_type in type_to_command:
        return type_to_command[clean_item_type]

    # Fallback to default conversion
    command = clean_item_type.lower().replace(" ", "_")
    return command
