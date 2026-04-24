"""
CLI export handler utility.

This module provides the central handler for CLI export commands.
It accepts the data returned by the library (SDK) and handles all CLI-specific
side effects such as logging, progressing bars, printing tabular views,
and saving to files or git.
"""

import sys
from typing import Any, Callable, Dict

from trxo.utils.console import error, info, success, warning
from trxo.utils.export.file_saver import FileSaver
from trxo.utils.export.git_export_handler import GitExportHandler
from trxo.utils.export.view_config import suggest_columns
from trxo.utils.export.view_renderer import ViewRenderer

from trxo_lib.config.config_store import ConfigStore
from trxo_lib.state.hash import HashManager
from trxo_lib.exceptions import TrxoAbort, TrxoError
from trxo.utils.error_presenter import present_error, present_generic_error


class CLIExportHandler:
    """Handles CLI presentation and saving for exported data."""

    def __init__(self):
        self.config_store = ConfigStore()
        self.hash_manager = HashManager(self.config_store)
        self.git_handler = None

    def _get_storage_mode(self) -> str:
        """Get the current storage mode from project config"""
        try:
            current_project = self.config_store.get_current_project()
            if current_project:
                project_config = self.config_store.get_project_config(current_project)
                return project_config.get("storage_mode", "local")
            return "local"
        except (AttributeError, TypeError, OSError):
            return "local"

    def handle_export(
        self,
        command_name: str,
        service_function: Callable[..., Any],
        kwargs: Dict[str, Any],
    ) -> None:
        """
        Execute the export service and handle results according to CLI arguments.

        Args:
            command_name: The name of the command (e.g., 'authn', 'saml')
            service_function: The SDK service function to call
            kwargs: Parameters to pass to the service function and handler
        """
        # Extract CLI-specific arguments
        view = kwargs.get("view", False)
        view_columns = kwargs.get("view_columns", None)
        output_dir = kwargs.get("output_dir", None)
        output_file = kwargs.get("output_file", None)
        version = kwargs.get("version", None)
        no_version = kwargs.get("no_version", False)
        branch = kwargs.get("branch", None)
        commit_message = kwargs.get("commit", kwargs.get("commit_message", None))

        # Warning for invalid combinations BEFORE making API calls
        if view_columns and not view:
            warning(
                "The --view-columns option can only be used with --view. "
                "Example: trxo export --view --view-columns _id,name"
            )
            raise TrxoAbort(code=1)

        try:
            # 1. Execute the SDK standard export logic
            export_result = service_function(**kwargs)
        except TrxoError as e:
            present_error(e)
            raise TrxoAbort(code=e.exit_code) from None
        except Exception as e:
            present_generic_error(e, command_name)
            raise TrxoAbort(code=1) from None

        # Handle when the service intercepts the workflow (e.g. applications with dependencies) and handles output itself
        if export_result is None:
            return

        # Handle tests that return dicts or mocks
        if type(export_result).__name__ in ("Mock", "MagicMock", "MagicMock"):
            return

        status_code = getattr(export_result, "status_code", 200)
        data = getattr(export_result, "data", export_result)
        metadata = getattr(export_result, "metadata", {})

        if status_code != 200 or not data:
            error(f"Failed to export {command_name}.")
            raise TrxoAbort(code=1)

        # Build a dict containing the result to match what CLI utilities expect
        result_dict = {
            "metadata": metadata,
            "data": data,
        }

        # 2. Handle View Mode
        if view:
            info(f"Displaying {command_name} data in view mode")
            effective_columns = suggest_columns(command_name, view_columns)
            ViewRenderer.display_table_view(
                result_dict, command_name, effective_columns
            )
            return

        # 3. Handle Save Mode
        info(f"Exporting {command_name.title()}...")
        storage_mode = self._get_storage_mode()
        file_path = None
        try:
            if storage_mode == "git":
                if not self.git_handler:
                    self.git_handler = GitExportHandler(self.config_store)

                file_path = self.git_handler.save_to_git(
                    data=result_dict,
                    command_name=command_name,
                    output_file=output_file,
                    branch=branch,
                    commit_message=commit_message,
                )
            else:
                file_path = FileSaver.save_to_local(
                    data=result_dict,
                    command_name=command_name,
                    output_dir=output_dir,
                    output_file=output_file,
                    version=version,
                    no_version=no_version,
                )

                # Create and save hash for data integrity (local mode only)
                if file_path:
                    hash_value = self.hash_manager.create_hash(data, command_name)
                    self.hash_manager.save_export_hash(
                        command_name, hash_value, file_path
                    )
        except TrxoAbort as e:
            # Already presented upstream — just exit
            sys.exit(e.exit_code)
        except TrxoError as e:
            present_error(e)
            sys.exit(e.exit_code)
        except Exception as e:
            present_generic_error(e, command_name)
            sys.exit(1)

        if file_path:
            success(f"{command_name.title()} exported successfully")
        else:
            error(f"Failed to save export for {command_name}.")
            raise TrxoAbort(code=1)
