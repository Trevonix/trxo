"""
CLI import handler utility.

This module provides the central handler for CLI import commands.
It executes the library (SDK) import services and handles all CLI-specific
side effects such as logging, diff presentation, and confirmation logic.
"""

from typing import Any, Callable, Dict

from trxo.utils.console import error, info, warning
from trxo.utils.diff_presenter import DiffPresenter
from trxo_lib.state.diff.diff_engine import DiffResult
from trxo_lib.exceptions import TrxoAbort, TrxoError


class CLIImportHandler:
    """Handles CLI presentation and orchestration for import operations."""

    def __init__(self):
        self.diff_presenter = DiffPresenter()

    def handle_import(
        self,
        command_name: str,
        service_function: Callable[..., Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        """
        Execute the import service and handle results according to CLI arguments.

        Args:
            command_name: The name of the command (e.g., 'journeys', 'oauth')
            service_function: The SDK service function to call
            kwargs: Parameters to pass to the service function
        """
        # Filter out CLI-specific variables from kwargs to avoid unexpected argument errors in SDK
        service_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k not in ["CLIImportHandler", "handler", "kwargs", "self"]
        }
        diff_mode = service_kwargs.get("diff", False)

        try:
            # 1. Execute the SDK standard import logic
            result = service_function(**service_kwargs)

            # 2. Handle Diff Result (if in diff mode)
            if diff_mode:
                if isinstance(result, DiffResult):
                    self.diff_presenter.display_diff_summary(result)

                    # Generate HTML Report if requested (handled in DiffPresenter)
                    if result.current_data and result.new_data:
                        self.diff_presenter.generate_html_report(
                            result, result.current_data, result.new_data
                        )

                    # Log summary of changes for visibility
                    total_changes = (
                        len(result.added_items)
                        + len(result.modified_items)
                        + len(result.removed_items)
                    )

                    if total_changes > 0:
                        warning(f"Import would make {total_changes} changes")
                        info(
                            "Use the import command without --diff to proceed "
                            "with the actual import"
                        )
                    else:
                        info("Configuration is already up to date")

                    return result
                elif result is None:
                    # Some importers might return None if diff fails internally
                    error(f"Diff analysis failed for {command_name}")
                    raise TrxoAbort(code=1)
                else:
                    # If we got a result but it's not a DiffResult (fallback)
                    return result

            # Library handles its own logging during import
            # If we reach here and it wasn't diff mode, assume success
            return result

        except TrxoError as e:
            error(str(e))
            raise TrxoAbort(code=1) from e
        except Exception as e:
            error(f"Import failed for {command_name}: {str(e)}")
            raise TrxoAbort(code=1) from e
