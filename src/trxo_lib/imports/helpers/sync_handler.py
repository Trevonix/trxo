"""
Sync handler for import operations.

Handles sync mode deletion of orphaned items.
Returns pure data — presentation is the caller's responsibility.
"""

from typing import Any, Dict, List, Optional

from trxo_lib.logging import get_logger
from trxo_lib.state.delete import DeletionManager
from trxo_lib.state.diff.diff_engine import DiffItem
from trxo_lib.state.diff.diff_manager import DiffManager

logger = get_logger(__name__)


class SyncResult:
    """Structured result from sync analysis."""

    def __init__(
        self,
        diff_result,
        items_to_delete: List[DiffItem],
        deletion_summary: Optional[Dict[str, Any]] = None,
    ):
        self.diff_result = diff_result
        self.items_to_delete = items_to_delete
        self.deletion_summary = deletion_summary


class SyncHandler:
    """Handles sync mode operations for import.

    Two-phase workflow:
      1. ``analyze()`` — perform diff and return items to delete (no IO).
      2. ``execute_deletions()`` — execute the deletions and return a summary.

    The CLI calls the presenter between the two phases for user confirmation.
    """

    @staticmethod
    def analyze(
        command_name: str,
        file_path: Optional[str] = None,
        realm: Optional[str] = None,
        jwk_path: Optional[str] = None,
        sa_id: Optional[str] = None,
        base_url: Optional[str] = None,
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
    ) -> Optional[SyncResult]:
        """Perform diff analysis and return items to delete.

        This is a pure data operation — no user prompts, no display.

        Returns:
            SyncResult with diff_result and items_to_delete, or None if diff failed.
        """
        logger.info("Sync mode: Checking for orphaned items to delete...")

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
            generate_html=False,
        )

        if not diff_result:
            logger.warning("Could not perform diff analysis for sync mode")
            return None

        deletion_manager = DeletionManager()
        items_to_delete = deletion_manager.get_items_to_delete(diff_result)

        return SyncResult(
            diff_result=diff_result,
            items_to_delete=items_to_delete,
        )

    @staticmethod
    def execute_deletions(
        items_to_delete: List[DiffItem],
        delete_func: callable,
        token: str,
        base_url: str,
    ) -> Dict[str, Any]:
        """Execute deletions and return a summary dict.

        Call this only after the CLI has confirmed with the user.
        """
        logger.info(f"Deleting {len(items_to_delete)} orphaned item(s)...")
        deletion_manager = DeletionManager()
        return deletion_manager.execute_deletions(
            items_to_delete=items_to_delete,
            delete_func=delete_func,
            token=token,
            base_url=base_url,
        )

    # ------------------------------------------------------------------
    # Legacy convenience wrapper (preserves old call signature for
    # callers that have not yet migrated to the two-phase API).
    # ------------------------------------------------------------------

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
        """Legacy one-shot sync deletion (analyze → confirm → execute).

        Uses the CLI presenter for confirmation / display.
        """
        from trxo.utils.diff_presenter import SyncPresenter

        sync_result = SyncHandler.analyze(
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
        )

        if not sync_result:
            return None

        if not sync_result.items_to_delete:
            logger.info("No orphaned items found — nothing to delete")
            return None

        # CLI confirmation
        if not SyncPresenter.confirm_deletions(
            sync_result.items_to_delete, item_type, force
        ):
            logger.warning("Deletion cancelled by user")
            return None

        summary = SyncHandler.execute_deletions(
            items_to_delete=sync_result.items_to_delete,
            delete_func=delete_func,
            token=token,
            base_url=base_url,
        )

        SyncPresenter.display_deletion_summary(summary)
        return summary
