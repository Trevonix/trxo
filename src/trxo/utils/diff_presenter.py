"""
CLI Diff & Sync Presenter.

Unified CLI-side presentation for diff, sync, and delete operations.
Delegates to the library for data; handles all Rich console output,
user confirmation prompts, and HTML report linking.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import typer

from trxo.utils.console import error, info, success, warning
from trxo_lib.state.diff.diff_engine import DiffItem, DiffResult
from trxo_lib.state.diff.diff_reporter import DiffReporter


class DiffPresenter:
    """Presents diff results in a rich, modern CLI format."""

    def __init__(self):
        self._reporter = DiffReporter()

    # ------------------------------------------------------------------ #
    #  Diff display
    # ------------------------------------------------------------------ #

    def display_diff_summary(self, diff_result: DiffResult) -> None:
        """Display a full Rich summary of the diff result."""
        self._reporter.display_summary(diff_result)

    def generate_html_report(
        self,
        diff_result: DiffResult,
        current_data: Dict[str, Any],
        new_data: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> Optional[str]:
        """Generate an HTML diff report and print a clickable link."""
        html_path = self._reporter.generate_html_diff(
            diff_result=diff_result,
            current_data=current_data,
            new_data=new_data,
            output_dir=output_dir,
        )
        if html_path:
            html_uri = Path(html_path).absolute().as_uri()
            info(f"Open HTML report: [link={html_uri}]{html_uri}[/link]")
        return html_path


class SyncPresenter:
    """Presents sync/deletion operations in a rich, modern CLI format."""

    # ------------------------------------------------------------------ #
    #  Deletion preview & confirmation
    # ------------------------------------------------------------------ #

    @staticmethod
    def display_deletion_preview(
        items_to_delete: List[DiffItem], item_type: str
    ) -> None:
        """Show a Rich-formatted preview of items that will be deleted."""
        if not items_to_delete:
            info("No items to delete")
            return

        warning(f"{'=' * 60}")
        warning(f"SYNC MODE: {len(items_to_delete)} {item_type} will be DELETED")
        warning(f"{'=' * 60}")

        for item in items_to_delete:
            warning(f"  ❌ {item.item_name or item.item_id}")

        warning(f"{'=' * 60}\n")

    @staticmethod
    def confirm_deletions(
        items_to_delete: List[DiffItem],
        item_type: str,
        force: bool = False,
    ) -> bool:
        """Display deletion preview and prompt for user confirmation.

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

        SyncPresenter.display_deletion_preview(items_to_delete, item_type)

        if force:
            return True

        return typer.confirm(
            "⚠️  Are you sure you want to DELETE these items?", default=False
        )

    @staticmethod
    def display_deletion_summary(summary: Dict[str, Any]) -> None:
        """Display a Rich-formatted deletion summary."""
        if summary["deleted_count"] > 0:
            success(f"Successfully deleted {summary['deleted_count']} item(s)")

        if summary["failed_count"] > 0:
            error(f"Failed to delete {summary['failed_count']} item(s)")
            for failed in summary["failed_deletions"]:
                error(f"  • {failed['id']}: {failed['error']}")
