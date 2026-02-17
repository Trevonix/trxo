"""
Diff comparison engine for import commands.

Efficient comparison of nested data structures using deepdiff
for configurations.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
from deepdiff import DeepDiff
from trxo.utils.console import error
from trxo.utils.console import info
from trxo.commands.export.services import ServicesExporter


class ChangeType(Enum):
    """Types of changes detected in diff"""

    ADDED = "added"
    MODIFIED = "modified"
    REMOVED = "removed"
    UNCHANGED = "unchanged"


@dataclass
class DiffItem:
    """Represents a single item difference"""

    item_id: str
    item_name: Optional[str]
    realm: Optional[str]
    change_type: ChangeType
    changes_count: int
    summary: str
    detailed_changes: Dict[str, Any]


@dataclass
class DiffResult:
    """Complete diff result"""

    command_name: str
    realm: Optional[str]
    total_items_current: int
    total_items_new: int
    added_items: List[DiffItem]
    modified_items: List[DiffItem]
    removed_items: List[DiffItem]
    unchanged_items: List[DiffItem]
    raw_diff: Dict[str, Any]
    key_insights: List[str] = None  # Human-readable insights about the changes

    def __post_init__(self):
        """Initialize key_insights as empty list if not provided"""
        if self.key_insights is None:
            self.key_insights = []


class DiffEngine:
    """Engine for comparing Ping AIC configuration data"""

    def __init__(self):
        self.id_fields = ["_id", "id", "name"]
        self.ignore_fields = [
            "_rev",
            "lastModified",
            "createdDate",
            "modifiedDate",
        ]

    def _fetch_current_services(self, realm: Optional[str]):
        info("Fetching current services via ServicesExporter for diff")
        exporter = ServicesExporter()
        return exporter.export_as_dict(
            scope="realm",
            realm=realm,
        )

    def compare_data(
        self,
        current_data: Dict[str, Any],
        new_data: Dict[str, Any],
        command_name: str,
        realm: Optional[str] = None,
    ) -> DiffResult:
        """
        Compare current server data with new data to be imported

        Args:
            current_data: Current data from server
            new_data: New data to be imported
            command_name: Name of the command
            realm: Target realm

        Returns:
            DiffResult containing detailed comparison
        """
        try:
            info(f"\nComparing {command_name} data...")

            # Auto-fetch current data if not provided
            # Always fetch current data from server for services
            if command_name == "services":
                current_data = self._fetch_current_services(realm)

            if command_name == "authn":
                info("Notice: For authn command, diff is performed on individual config sections"
                     " rather than entire file to provide more actionable insights.")
            # Auto-fetch current data if not provided

            # Extract data arrays from the response structure
            current_items = self._extract_items(current_data)
            new_items = self._extract_items(new_data)

            # Create ID-based mappings
            current_map = self._create_id_map(current_items)
            new_map = self._create_id_map(new_items)

            # Find changes
            added_items = []
            modified_items = []
            removed_items = []
            unchanged_items = []

            # Check for added and modified items
            for item_id, new_item in new_map.items():
                if item_id not in current_map:
                    # New item
                    diff_item = self._create_diff_item(
                        item_id, new_item, None, ChangeType.ADDED, realm
                    )
                    added_items.append(diff_item)
                else:
                    # Compare existing item
                    current_item = current_map[item_id]
                    diff_result = self._compare_items(current_item, new_item)

                    if diff_result["has_changes"]:
                        diff_item = self._create_diff_item(
                            item_id,
                            new_item,
                            current_item,
                            ChangeType.MODIFIED,
                            realm,
                            diff_result,
                        )
                        modified_items.append(diff_item)
                    else:
                        diff_item = self._create_diff_item(
                            item_id,
                            new_item,
                            current_item,
                            ChangeType.UNCHANGED,
                            realm,
                        )
                        unchanged_items.append(diff_item)

            # Check for removed items
            for item_id, current_item in current_map.items():
                if item_id not in new_map:
                    diff_item = self._create_diff_item(
                        item_id, None, current_item, ChangeType.REMOVED, realm
                    )
                    removed_items.append(diff_item)

            # Create overall diff using deepdiff
            raw_diff = DeepDiff(
                current_items,
                new_items,
                ignore_order=True,
                verbose_level=2,
            )

            # Generate key insights
            from trxo.utils.diff.insights_generator import InsightsGenerator

            insights_gen = InsightsGenerator()
            key_insights = insights_gen.generate_key_insights(
                command_name=command_name,
                added_items=added_items,
                modified_items=modified_items,
                removed_items=removed_items,
            )

            return DiffResult(
                command_name=command_name,
                realm=realm,
                total_items_current=len(current_items),
                total_items_new=len(new_items),
                added_items=added_items,
                modified_items=modified_items,
                removed_items=removed_items,
                unchanged_items=unchanged_items,
                raw_diff=raw_diff.to_dict() if raw_diff else {},
                key_insights=key_insights,
            )

        except Exception as e:
            error(f"Failed to compare data: {str(e)}")
            raise

    def _extract_items(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract items array from response data"""
        if not data:
            return []

    # Unwrap top-level "data"
        if isinstance(data, dict) and "data" in data:
            data = data["data"]

    #  Handle result wrapper
        if isinstance(data, dict) and isinstance(data.get("result"), list):
            return data["result"]

    #  OAuth: data.clients
        if isinstance(data, dict) and isinstance(data.get("clients"), list):
            return data["clients"]

        # authn: split composite config into item-wise sections
        if isinstance(data, dict) and "postauthprocess" in data:
            items = []
            for section_key, section_value in data.items():
                # Skip metadata-like fields
                if section_key in ("_id", "_type"):
                    continue

        # Each section becomes its own diff item
                items.append({
                    "_id": section_key,
                    "value": section_value,
                })
            return items

    # objects / mappings
        if isinstance(data, dict) and any(k in data for k in ("objects", "mappings")):
            objects_data = data.get("objects") or data.get("mappings")
            if isinstance(objects_data, list):
                return objects_data

    # Single object
        if isinstance(data, dict) and "_id" in data:
            return [data]

    # Already a list
        if isinstance(data, list):
            return data

        return []

    def _create_id_map(self, items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Create a mapping of ID to item"""
        id_map = {}
        for item in items:
            item_id = self._get_item_id(item)
            if item_id:
                id_map[item_id] = item
        return id_map

    def _get_item_id(self, item: Dict[str, Any]) -> Optional[str]:
        """Get the ID of an item using various ID fields"""
        for field in self.id_fields:
            if field in item and item[field]:
                return str(item[field])

        type_info = item.get("_type")
        if isinstance(type_info, dict):
            service_id = type_info.get("_id")
            if service_id:
                return str(service_id)
        return None

    def _get_item_name(self, item: Dict[str, Any]) -> Optional[str]:
        """Get the display name of an item"""
        name_fields = ["name", "displayName", "title", "_id", "id"]
        for field in name_fields:
            if field in item and item[field]:
                return str(item[field])
        return None

    def _compare_items(
        self, current_item: Dict[str, Any], new_item: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare two items and return detailed differences"""
        clean_current = {
            k: v for k, v in current_item.items() if k not in self.ignore_fields
        }
        clean_new = {k: v for k, v in new_item.items() if k not in self.ignore_fields}

        diff = DeepDiff(clean_current, clean_new, ignore_order=True, verbose_level=2)

        has_changes = bool(diff)
        changes_count = 0

        if has_changes:
            # Count different types of changes
            changes_count += len(diff.get("values_changed", {}))
            changes_count += len(diff.get("dictionary_item_added", {}))
            changes_count += len(diff.get("dictionary_item_removed", {}))
            changes_count += len(diff.get("iterable_item_added", {}))
            changes_count += len(diff.get("iterable_item_removed", {}))

        return {
            "has_changes": has_changes,
            "changes_count": changes_count,
            "diff": diff.to_dict() if diff else {},
            "summary": self._create_change_summary(diff) if diff else "",
        }

    def _create_change_summary(self, diff: DeepDiff) -> str:
        """Create a human-readable summary of changes"""
        summary_parts = []

        if "values_changed" in diff:
            count = len(diff["values_changed"])
            summary_parts.append(f"{count} field{'s' if count != 1 else ''} modified")

        if "dictionary_item_added" in diff:
            count = len(diff["dictionary_item_added"])
            summary_parts.append(f"{count} field{'s' if count != 1 else ''} added")

        if "dictionary_item_removed" in diff:
            count = len(diff["dictionary_item_removed"])
            summary_parts.append(f"{count} field{'s' if count != 1 else ''} removed")

        if "iterable_item_added" in diff:
            count = len(diff["iterable_item_added"])
            summary_parts.append(
                f"{count} item{'s' if count != 1 else ''} added to arrays"
            )

        if "iterable_item_removed" in diff:
            count = len(diff["iterable_item_removed"])
            summary_parts.append(
                f"{count} item{'s' if count != 1 else ''} removed from arrays"
            )

        return ", ".join(summary_parts) if summary_parts else "No changes"

    def _create_diff_item(
        self,
        item_id: str,
        new_item: Optional[Dict[str, Any]],
        current_item: Optional[Dict[str, Any]],
        change_type: ChangeType,
        realm: Optional[str],
        diff_result: Optional[Dict[str, Any]] = None,
    ) -> DiffItem:
        """Create a DiffItem from comparison results"""

        # Get item name from new_item or current_item
        item_name = None
        if new_item:
            item_name = self._get_item_name(new_item)
        elif current_item:
            item_name = self._get_item_name(current_item)

        # Create summary based on change type
        if change_type == ChangeType.ADDED:
            summary = "New item to be created"
            changes_count = 1
            detailed_changes = {"new_item": new_item} if new_item else {}
        elif change_type == ChangeType.REMOVED:
            summary = "Item no longer exists in new data"
            changes_count = 1
            detailed_changes = {"removed_item": current_item} if current_item else {}
        elif change_type == ChangeType.MODIFIED:
            changes_count = diff_result.get("changes_count", 0) if diff_result else 0
            summary = (
                diff_result.get("summary", "Modified") if diff_result else "Modified"
            )
            # Attach structured diff and payloads
            detailed_changes = {
                "diff": diff_result.get("diff", {}) if diff_result else {},
                "current_item": current_item if current_item else {},
                "new_item": new_item if new_item else {},
            }
        else:  # UNCHANGED
            summary = "No changes"
            changes_count = 0
            detailed_changes = {}

        return DiffItem(
            item_id=item_id,
            item_name=item_name,
            realm=realm,
            change_type=change_type,
            changes_count=changes_count,
            summary=summary,
            detailed_changes=detailed_changes,
        )
