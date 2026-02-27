"""
Sync handler for import operations.

Handles sync mode deletion of orphaned items.
"""

from typing import Optional, Dict, Any
from trxo.utils.console import info, warning, success
from trxo.utils.diff.diff_manager import DiffManager
from trxo.utils.deletion_manager import DeletionManager


class SyncHandler:
    """Handles sync mode operations for import"""

    @staticmethod
    def handle_sync_deletions(
        command_name: str,
        item_type: str,
        delete_func: callable,
        token: str,
        base_url: str,
        file_path: Optional[str] = None,
        realm: Optional[str] = None,
        jwk_path: Optional[str] = None,
        sa_id: Optional[str] = None,
        project_name: Optional[str] = None,
        auth_mode: Optional[str] = None,
        onprem_username: Optional[str] = None,
        onprem_password: Optional[str] = None,
        onprem_realm: Optional[str] = None,
        idm_base_url: Optional[str] = None,
        idm_username: Optional[str] = None,
        idm_password: Optional[str] = None,
        am_base_url: Optional[str] = None,
        branch: Optional[str] = None,
        force: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Handle deletion of orphaned items in sync mode.

        Args:
            command_name: Command name for diff analysis
            item_type: Type of items being synced
            delete_func: Function to delete items
            token: Authentication token
            base_url: API base URL
            file_path: Path to source file (local mode)
            realm: Realm name
            jwk_path: JWK path for auth
            sa_id: Service account ID
            project_name: Project name
            auth_mode: Authentication mode
            onprem_username: On-prem AM username
            onprem_password: On-prem AM password
            onprem_realm: On-prem AM realm
            idm_base_url: On-prem IDM base URL
            idm_username: On-prem IDM username
            idm_password: On-prem IDM password
            am_base_url: On-prem AM base URL
            branch: Git branch (git mode)
            force: Force deletion without confirmation

        Returns:
            Deletion summary or None if no deletions needed
        """
        info("\n🔄 Sync mode: Checking for orphaned items to delete...")

        # Perform diff to identify removed items
        diff_manager = DiffManager()
        diff_result = diff_manager.perform_diff(
            command_name=command_name,
            file_path=file_path,
            realm=realm,
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
            am_base_url=am_base_url,
            branch=branch,
            generate_html=False,  # Don't generate HTML for sync operations
        )

        if not diff_result:
            warning("Could not perform diff analysis for sync mode")
            return None

        # Get items to delete
        deletion_manager = DeletionManager()
        items_to_delete = deletion_manager.get_items_to_delete(diff_result)

        if not items_to_delete:
            success("✓ No orphaned items found - nothing to delete")
            return None

        # Get user confirmation
        if not deletion_manager.confirm_deletions(items_to_delete, item_type, force):
            warning("Deletion cancelled by user")
            return None

        # Execute deletions
        info(f"\nDeleting {len(items_to_delete)} orphaned item(s)...")
        summary = deletion_manager.execute_deletions(
            items_to_delete=items_to_delete,
            delete_func=delete_func,
            token=token,
            base_url=base_url,
        )

        # Print summary
        deletion_manager.print_summary(summary)

        return summary
