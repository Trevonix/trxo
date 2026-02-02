"""
Cherry-pick filter for import operations.

Handles filtering items based on cherry-pick IDs.
"""

from typing import List, Dict, Any
from trxo.utils.console import error, info


class CherryPickFilter:
    """Handles cherry-pick filtering for import operations"""

    @staticmethod
    def apply_filter(items: List[Dict[str, Any]], cherry_pick_ids: str) -> List[Dict[str, Any]]:
        """
        Filter items to only include those with the specified IDs for cherry-pick import.

        Args:
            items: List of items to filter
            cherry_pick_ids: Comma-separated IDs of items to cherry-pick

        Returns:
            List containing only the matching items, or empty list if none found
        """
        # Parse comma-separated IDs
        target_ids = [id.strip() for id in cherry_pick_ids.split(',') if id.strip()]

        if not target_ids:
            error("Cherry-pick: No valid IDs provided")
            return []

        filtered_items = []
        found_ids = []

        for target_id in target_ids:
            item_found = False

            for item in items:
                # Check for _id field first (primary identifier)
                item_id = item.get("_id")
                if item_id == "":
                    item_id = item.get("_type", {}).get("_id")

                if item_id == target_id:
                    filtered_items.append(item)
                    found_ids.append(target_id)
                    info(f"Cherry-pick: Found item with _id '{target_id}'")
                    item_found = True
                    break

                # Fallback to other common ID fields if _id not found
                for id_field in ["id", "name"]:
                    if item.get(id_field) == target_id:
                        filtered_items.append(item)
                        found_ids.append(target_id)
                        info(f"Cherry-pick: Found item with {id_field} '{target_id}'")
                        item_found = True
                        break

                if item_found:  # Break inner loop if item found
                    break

        # Report any missing IDs
        missing_ids = [id for id in target_ids if id not in found_ids]
        if missing_ids:
            if len(missing_ids) == 1:
                error(f"Cherry-pick: Item with ID '{missing_ids[0]}' not found in export file")
            else:
                error(f"Cherry-pick: Items with IDs {missing_ids} not found in export file")

        return filtered_items

    @staticmethod
    def validate_cherry_pick_argument(cherry_pick: str) -> bool:
        """
        Validate cherry-pick argument to ensure it's not a filename or other option.

        Args:
            cherry_pick: Cherry-pick argument to validate

        Returns:
            True if valid, False otherwise
        """
        # Check if it looks like a filename or other option
        if cherry_pick.endswith('.json') or cherry_pick.startswith('--') or \
           cherry_pick in ['alpha', 'bravo', 'charlie']:
            return False
        return True
