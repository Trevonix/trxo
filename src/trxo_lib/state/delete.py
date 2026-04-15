"""
Deletion manager for sync/mirror operations.

Handles identification and deletion of orphaned items during sync imports.
Returns pure data — all presentation is the caller's responsibility.
"""

from typing import Any, Callable, Dict, List

from trxo_lib.logging import get_logger
from trxo_lib.state.diff.diff_engine import DiffItem, DiffResult

logger = get_logger(__name__)


class DeletionManager:
    """Manages safe deletion of items during sync operations.

    This class is presentation-agnostic. It returns structured data
    and delegates all user-facing output to the CLI layer.
    """

    def __init__(self):
        self.deleted_items: List[str] = []
        self.failed_deletions: List[Dict[str, Any]] = []

    def get_items_to_delete(self, diff_result: DiffResult) -> List[DiffItem]:
        """
        Extract items to delete from diff result.

        Args:
            diff_result: DiffResult from diff engine

        Returns:
            List of DiffItem objects marked for removal
        """
        return diff_result.removed_items

    def execute_deletions(
        self,
        items_to_delete: List[DiffItem],
        delete_func: Callable[[str, str, str], bool],
        token: str,
        base_url: str,
    ) -> Dict[str, Any]:
        """
        Execute deletions using provided delete function.

        Args:
            items_to_delete: List of items to delete
            delete_func: Function that deletes a single item (item_id, token, base_url) -> bool
            token: Auth token
            base_url: API base URL

        Returns:
            Dictionary with deletion summary
        """
        self.deleted_items = []
        self.failed_deletions = []

        for item in items_to_delete:
            try:
                success_result = delete_func(item.item_id, token, base_url)
                if success_result:
                    self.deleted_items.append(item.item_id)
                    logger.info(f"Deleted: {item.item_name or item.item_id}")
                else:
                    self.failed_deletions.append(
                        {"id": item.item_id, "error": "Delete function returned False"}
                    )
            except Exception as e:
                self.failed_deletions.append({"id": item.item_id, "error": str(e)})
                logger.error(f"Failed to delete {item.item_id}: {str(e)}")

        return self._create_summary()

    def _create_summary(self) -> Dict[str, Any]:
        """Create deletion summary report."""
        return {
            "deleted_count": len(self.deleted_items),
            "failed_count": len(self.failed_deletions),
            "deleted_items": self.deleted_items,
            "failed_deletions": self.failed_deletions,
        }
