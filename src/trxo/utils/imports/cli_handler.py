"""
CLI import handler utility.

This module provides the central handler for CLI import commands.
It executes the library (SDK) import services and handles all CLI-specific
side effects such as logging, diff presentation, and confirmation logic.
"""

import sys
from typing import Any, Callable, Dict

from rich.console import Console

from trxo.utils.console import error, info, warning
from trxo.utils.error_presenter import present_error, present_generic_error
from trxo.utils.diff_presenter import DiffPresenter
from trxo.utils.imports.import_progress_handler import ImportProgressHandler
from trxo_lib.state.diff.diff_engine import DiffResult
from trxo_lib.exceptions import TrxoAbort, TrxoError

# Shared console instance
_console = Console()


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
        # Filter out CLI-specific variables from kwargs
        service_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k not in ["CLIImportHandler", "handler", "kwargs", "self"]
        }
        diff_mode = service_kwargs.get("diff", False)

        # ── DIFF MODE ─────────────────────────────────────────────────────────
        if diff_mode:
            return self._handle_diff(command_name, service_function, service_kwargs)

        # ── IMPORT MODE (with live progress) ──────────────────────────────────
        return self._handle_import_with_progress(
            command_name, service_function, service_kwargs
        )

    # ─────────────────────────────────────────────────────────────────────────

    def _handle_diff(
        self,
        command_name: str,
        service_function: Callable[..., Any],
        service_kwargs: Dict[str, Any],
    ) -> Any:
        """Run diff mode — no progress handler, DiffPresenter owns the output."""
        try:
            result = service_function(**service_kwargs)

            if isinstance(result, DiffResult):
                self.diff_presenter.display_diff_summary(result)

                if result.current_data and result.new_data:
                    self.diff_presenter.generate_html_report(
                        result, result.current_data, result.new_data
                    )

                total_changes = (
                    len(result.added_items)
                    + len(result.modified_items)
                    + len(result.removed_items)
                )
                if total_changes > 0:
                    warning(f"Import would make {total_changes} changes")
                    info("Run the import command without --diff to apply the changes")
                else:
                    info("Configuration is already up to date")

                return result
            elif result is None:
                error(f"Diff analysis failed for {command_name}")
                sys.exit(1)
            else:
                return result

        except TrxoAbort as e:
            # Already presented upstream — just exit cleanly
            sys.exit(e.exit_code)
        except TrxoError as e:
            present_error(e)
            sys.exit(e.exit_code)
        except Exception as e:
            present_generic_error(e, command_name)
            sys.exit(1)

    def _handle_import_with_progress(
        self,
        command_name: str,
        service_function: Callable[..., Any],
        service_kwargs: Dict[str, Any],
    ) -> Any:
        """
        Run the actual import wrapped in a Rich live-progress session.

        The ImportProgressHandler is installed on the trxo_lib logger for the
        duration of this call. It intercepts every INFO/WARNING/ERROR record and
        renders it to the console in real-time. On completion it prints a
        summary panel.
        """
        progress_handler = ImportProgressHandler(command_name, console=_console)
        progress_handler.attach()

        try:
            result = service_function(**service_kwargs)
            return result

        except TrxoAbort as e:
            # Already presented — just clean up and exit
            progress_handler.detach()
            sys.exit(e.exit_code)
        except TrxoError as e:
            progress_handler.detach()
            present_error(e)
            sys.exit(e.exit_code)
        except Exception as e:
            progress_handler.detach()
            present_generic_error(e, command_name)
            sys.exit(1)
        finally:
            progress_handler.detach()
            progress_handler.print_summary()
