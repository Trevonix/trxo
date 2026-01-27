"""
Deletion manager for sync/mirror operations.

Handles identification and deletion of orphaned items during sync imports.
"""

from typing import List, Dict, Any, Callable
from trxo.utils.console import warning, info, error, success
from trxo.utils.diff.diff_engine import DiffResult, DiffItem
import typer


class DeletionManager:
    """Manages safe deletion of items during sync operations"""

    def __init__(self):
        self.deleted_items = []
        self.failed_deletions = []

    def get_items_to_delete(self, diff_result: DiffResult) -> List[DiffItem]:
        """
        Extract items to delete from diff result
        
        Args:
            diff_result: DiffResult from diff engine
            
        Returns:
            List of DiffItem objects marked for removal
        """
        return diff_result.removed_items

    def confirm_deletions(
        self, 
        items_to_delete: List[DiffItem], 
        item_type: str,
        force: bool = False
    ) -> bool:
        """
        Show deletion preview and get user confirmation
        
        Args:
            items_to_delete: List of items to delete
            item_type: Type of items (e.g., 'scripts', 'oauth')
            force: Skip confirmation if True
            
        Returns:
            True if user confirms or force=True, False otherwise
        """
        if not items_to_delete:
            info("No items to delete")
            return True
        
        warning(f"\n{'='*60}")
        warning(f"SYNC MODE: {len(items_to_delete)} {item_type} will be DELETED")
        warning(f"{'='*60}")
        
        for item in items_to_delete:
            warning(f"  ❌ {item.item_name or item.item_id}")
        
        warning(f"{'='*60}\n")
        
        if force:
            info("Force mode enabled, skipping confirmation")
            return True
        
        confirm = typer.confirm(
            "⚠️  Are you sure you want to DELETE these items?",
            default=False
        )
        return confirm

    def execute_deletions(
        self,
        items_to_delete: List[DiffItem],
        delete_func: Callable[[str, str, str], bool],
        token: str,
        base_url: str
    ) -> Dict[str, Any]:
        """
        Execute deletions using provided delete function
        
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
                    info(f"Deleted: {item.item_name or item.item_id}")
                else:
                    self.failed_deletions.append({
                        "id": item.item_id,
                        "error": "Delete function returned False"
                    })
            except Exception as e:
                self.failed_deletions.append({
                    "id": item.item_id,
                    "error": str(e)
                })
                error(f"Failed to delete {item.item_id}: {str(e)}")
        
        return self._create_summary()

    def _create_summary(self) -> Dict[str, Any]:
        """Create deletion summary report"""
        return {
            "deleted_count": len(self.deleted_items),
            "failed_count": len(self.failed_deletions),
            "deleted_items": self.deleted_items,
            "failed_deletions": self.failed_deletions
        }

    def print_summary(self, summary: Dict[str, Any]) -> None:
        """Print deletion summary"""
        if summary["deleted_count"] > 0:
            success(f"\n✓ Successfully deleted {summary['deleted_count']} item(s)")
        
        if summary["failed_count"] > 0:
            error(f"\n✗ Failed to delete {summary['failed_count']} item(s)")
            for failed in summary["failed_deletions"]:
                error(f"  • {failed['id']}: {failed['error']}")
