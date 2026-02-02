"""
Metadata builder for export operations.

Builds standardized metadata for exported data including realm detection.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class MetadataBuilder:
    """Builds metadata for exported data"""

    @staticmethod
    def detect_realm(api_endpoint: str, command_name: str) -> Optional[str]:
        """
        Detect realm from API endpoint or command name.

        Args:
            api_endpoint: API endpoint URL
           command_name: Command name

        Returns:
            Detected realm name or None
        """
        realm_value = None

        try:
            # AM realm pattern: /realms/root/realms/{realm}/
            am_marker = "/realms/root/realms/"
            if am_marker in api_endpoint:
                after = api_endpoint.split(am_marker, 1)[1]
                realm_value = after.split("/", 1)[0].split("?", 1)[0]

            # IDM themerealm _fields=realm/{realm}
            if not realm_value and "_fields=realm/" in api_endpoint:
                after = api_endpoint.split("_fields=realm/", 1)[1]
                realm_value = after.split("&", 1)[0].split("/", 1)[0]

            # Fallback to command_name hint e.g., services_realm_alpha
            if not realm_value and "_realm_" in command_name:
                realm_value = command_name.split("_realm_", 1)[1]
        except Exception:
            realm_value = None

        return realm_value

    @staticmethod
    def count_items(data: Any) -> int:
        """
        Count total items in data structure.

        Args:
            data: Data to count items from

        Returns:
            Number of items
        """
        if isinstance(data, dict) and "result" in data and isinstance(data["result"], list):
            return len(data["result"])
        elif isinstance(data, list):
            return len(data)
        elif isinstance(data, dict):
            return 1
        return 0

    @staticmethod
    def build_metadata(
        command_name: str,
        api_endpoint: str,
        data: Any,
        version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build metadata dictionary for export.

        Args:
            command_name: Export command name
            api_endpoint: API endpoint used
            data: Exported data
            version: Version string (optional)

        Returns:
            Metadata dictionary
        """
        # Normalize export type
        export_type = (
            command_name
            .replace("services_realm_", "services")
            .replace("services_global", "services")
            )

        # Detect realm
        realm = MetadataBuilder.detect_realm(api_endpoint, command_name)

        # Count items
        total_items = MetadataBuilder.count_items(data)

        # Build metadata
        metadata = {
            "export_type": export_type,
            "realm": realm,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "version": version,
            "total_items": total_items,
        }

        return metadata
