"""
Base exporter class for export commands.

This module provides the base class for all export operations with
common functionality like API calls, file saving, and progress tracking.

Refactored to use focused utility modules for better maintainability.
"""

from typing import Optional, Dict, Any, Callable
import typer
from trxo.utils.console import success, error, info, warning
from trxo.utils.hash_manager import HashManager
from ..shared.base_command import BaseCommand
from trxo.utils.export import (
    PaginationHandler,
    MetadataBuilder,
    FileSaver,
    GitExportHandler,
    ViewRenderer,
)


class BaseExporter(BaseCommand):
    """Base class for all export operations"""

    def __init__(self):
        super().__init__()
        self.hash_manager = HashManager(self.config_store)
        self.git_handler = GitExportHandler(self.config_store)
        self._current_token = None
        self._current_api_base_url = None

    def export_data(
        self,
        command_name: str,
        api_endpoint: str,
        headers: Dict[str, str],
        view: bool = False,
        view_columns: Optional[str] = None,
        jwk_path: Optional[str] = None,
        sa_id: Optional[str] = None,
        base_url: Optional[str] = None,
        project_name: Optional[str] = None,
        output_dir: Optional[str] = None,
        output_file: Optional[str] = None,
        auth_mode: Optional[str] = None,
        onprem_username: Optional[str] = None,
        onprem_password: Optional[str] = None,
        onprem_realm: Optional[str] = None,
        idm_base_url: Optional[str] = None,
        idm_username: Optional[str] = None,
        idm_password: Optional[str] = None,
        am_base_url: Optional[str] = None,
        response_filter: Optional[Callable[[Any], Any]] = None,
        version: Optional[str] = None,
        no_version: bool = False,
        branch: Optional[str] = None,
        commit_message: Optional[str] = None,
    ) -> None:
        """Export data with authentication and save to file

        Args:
            command_name: Name of the command
            api_endpoint: API endpoint to call
            headers: HTTP headers
            view: Whether to display data
            view_columns: Columns to display
            jwk_path: Path to JWK file
            sa_id: Service account ID
            base_url: Base URL
            project_name: Project name
            output_dir: Output directory
            output_file: Output file name
            auth_mode: Authentication mode
            onprem_username: On-premise AM username
            onprem_password: On-premise AM password
            onprem_realm: On-premise AM realm
            idm_base_url: On-premise IDM base URL
            idm_username: On-premise IDM username
            idm_password: On-premise IDM password
            am_base_url: On-premise AM base URL
            response_filter: Response filter function
            version: Version string
            no_version: Skip versioning
            branch: Git branch to use (Git mode)
            commit_message: Custom commit message (Git mode)
        """
        self.logger.info(f"Starting export operation: {command_name}")
        try:
            # Determine product type from endpoint for auth context and headers
            product = "idm" if "/openidm/" in api_endpoint else "am"
            self.product = product

            # Initialize authentication
            token, api_base_url = self.initialize_auth(
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
            )
            self.logger.debug(
                f"Authentication initialized for {command_name}, "
                f"auth_mode: {self.auth_mode}, product: {product}"
            )

            # Store current auth details for response filters
            self._current_token = token
            self._current_api_base_url = api_base_url

            # Determine product type from endpoint for auth headers (already set above)
            product = self.product

            # For IDM endpoints in on-prem mode, use IDM base URL if available
            if product == "idm" and self.auth_mode == "onprem" and self._idm_base_url:
                api_base_url = self._idm_base_url

            # Prepare headers with authentication
            if headers is None:
                headers = {
                    "Content-Type": "application/json",
                    "Accept-API-Version": "resource=1.0",
                }
            headers = {**headers, **self.build_auth_headers(token, product=product)}

            # Make API call
            url = self._construct_api_url(api_base_url, api_endpoint)
            response = self.make_http_request(url, "GET", headers)
            raw_data = response.json()

            # Handle pagination automatically
            aggregated_data = self._handle_pagination(
                raw_data, api_endpoint, headers, api_base_url
            )

            # Apply response filter if provided
            filtered_data = (
                response_filter(aggregated_data) if response_filter else aggregated_data
            )

            # Remove _rev fields from all data
            filtered_data = self.remove_rev_fields(filtered_data)

            # Build metadata using MetadataBuilder
            metadata = MetadataBuilder.build_metadata(
                command_name=command_name,
                api_endpoint=api_endpoint,
                data=filtered_data,
                version=None,  # Will be filled during save
            )

            # Prepare result structure
            result = {
                "metadata": metadata,
                "data": filtered_data,
            }

            # Handle view mode or save mode
            if view:
                self.logger.debug(f"Displaying {command_name} data in view mode")
                self._handle_view_mode(result, command_name, view_columns)
            elif view_columns:
                warning(
                    "The --view-columns option can only be used with --view.\n"
                    "Example: trxo export --view --view-columns _id,name"
                )
                return
            else:
                self.logger.debug(f"Saving {command_name} data to file")
                self._handle_save_mode(
                    result,
                    command_name,
                    filtered_data,
                    response,
                    output_dir,
                    output_file,
                    version,
                    no_version,
                    branch,
                    commit_message,
                )
                self.logger.info(
                    f"Export operation completed successfully: {command_name}"
                )

        except Exception as e:
            self.logger.error(f"Export failed for {command_name}: {str(e)}")
            error(f"Export failed: {str(e)}")
            raise typer.Exit(1)
        finally:
            self.cleanup()

    def _handle_pagination(
        self,
        raw_data: Any,
        api_endpoint: str,
        headers: Dict[str, str],
        api_base_url: str,
    ) -> Any:
        """Handle pagination if response is paginated"""
        if PaginationHandler.is_paginated(raw_data):
            try:
                return PaginationHandler.fetch_all_pages(
                    raw_data, api_endpoint, self, headers, api_base_url
                )
            except Exception:
                # Fallback to first page if pagination fails
                return raw_data
        return raw_data

    def _handle_view_mode(
        self, result: Dict[str, Any], command_name: str, view_columns: Optional[str]
    ):
        """Handle view mode display"""
        # from .view_config import suggest_columns
        from trxo.utils.export.view_config import suggest_columns

        effective_columns = suggest_columns(command_name, view_columns)
        ViewRenderer.display_table_view(result, command_name, effective_columns)

    def _handle_save_mode(
        self,
        result: Dict[str, Any],
        command_name: str,
        filtered_data: Any,
        response,
        output_dir: Optional[str],
        output_file: Optional[str],
        version: Optional[str],
        no_version: bool,
        branch: Optional[str],
        commit_message: Optional[str],
    ):
        """Handle save mode with hash management"""
        info(f"Exporting {command_name.title()}...")
        print()

        # Save response to file
        file_path = self.save_response(
            result,
            command_name,
            output_dir,
            output_file,
            version=version,
            no_version=no_version,
            branch=branch,
            commit_message=commit_message,
        )

        # Create and save hash for data integrity (local mode only)
        storage_mode = self._get_storage_mode()
        if storage_mode == "local" and file_path:
            hash_value = self.hash_manager.create_hash(filtered_data, command_name)
            self.hash_manager.save_export_hash(command_name, hash_value, file_path)

        print()
        if response.status_code == 200:
            success(f"{command_name.title()} exported successfully")
        else:
            error(f"Failed to export {command_name}: {response.text}")

    def get_current_auth(self):
        """Get current authentication details for response filters"""
        return self._current_token, self._current_api_base_url

    def _get_storage_mode(self) -> str:
        """Get the current storage mode from project config"""
        try:
            current_project = self.config_store.get_current_project()
            if current_project:
                project_config = self.config_store.get_project_config(current_project)
                return project_config.get("storage_mode", "local")
            return "local"
        except Exception:
            return "local"

    def save_response(
        self,
        data: Dict[Any, Any],
        command_name: str,
        output_dir: Optional[str] = None,
        output_file: Optional[str] = None,
        *,
        version: Optional[str] = None,
        no_version: bool = False,
        branch: Optional[str] = None,
        commit_message: Optional[str] = None,
    ) -> Optional[str]:
        """Save API response to JSON file with versioned filename

        Args:
            data: Data to save
            command_name: Name of the command
            output_dir: Output directory (local mode)
            output_file: Output file name (local mode)
            version: Version string (local mode)
            no_version: Skip versioning (local mode)
            branch: Git branch to use (git mode)
            commit_message: Custom commit message (git mode)

        Returns:
            Path to saved file or None if failed
        """
        storage_mode = self._get_storage_mode()

        if storage_mode == "git":
            return self.git_handler.save_to_git(
                data=data,
                command_name=command_name,
                output_file=output_file,
                branch=branch,
                commit_message=commit_message,
            )
        else:
            return FileSaver.save_to_local(
                data=data,
                command_name=command_name,
                output_dir=output_dir,
                output_file=output_file,
                version=version,
                no_version=no_version,
            )

    def get_required_fields(self):
        """Export commands don't typically need required fields validation"""
        return []

    def get_item_type(self) -> str:
        """Return the type of items being exported (for logging)"""
        return "items"

    def remove_rev_fields(self, data):
        """Recursively remove _rev fields from all data structures"""
        if isinstance(data, dict):
            cleaned = {}
            for key, value in data.items():
                if key != "_rev":
                    cleaned[key] = self.remove_rev_fields(value)
            return cleaned
        elif isinstance(data, list):
            return [self.remove_rev_fields(item) for item in data]
        else:
            return data
