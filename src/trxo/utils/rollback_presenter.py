"""
CLI Rollback Presenter.

Rich-formatted presentation of rollback operations for the CLI.
Delegates to the library RollbackManager for data; handles all
console output and user-facing formatting.
"""

from typing import Any, Dict

from trxo.utils.console import error, info, success, warning


class RollbackPresenter:
    """Presents rollback results in a rich, modern CLI format."""

    @staticmethod
    def display_rollback_report(report: Dict[str, Any]) -> None:
        """Display a Rich-formatted rollback report.

        Args:
            report: Dict with 'rolled_back' and 'errors' lists
        """
        rolled_back = report.get("rolled_back", [])
        errors = report.get("errors", [])

        if rolled_back:
            success(
                f"ROLLBACK REPORT: Successfully rolled back "
                f"{len(rolled_back)} item(s)"
            )
            for item in rolled_back:
                if "action" in item and "id" not in item:
                    info(f"  Rolled back: {item['action']}")
                else:
                    item_id = item.get("id", "unknown")
                    action = item.get("action", "unknown")
                    info(f"  Rolled back: {item_id} ({action})")
        else:
            info("No items were rolled back, as the first item failed.")

        if errors:
            warning(f"Failed to roll back {len(errors)} item(s)")
            for error_item in errors:
                item_id = error_item.get("id", "unknown")
                error_msg = error_item.get("error", "unknown error")
                error(f"  Rollback failed: {item_id}: {error_msg}")

    @staticmethod
    def display_baseline_status(message: str) -> None:
        """Display baseline creation progress."""
        info(message)
