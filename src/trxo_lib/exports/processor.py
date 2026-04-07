"""
Base exporter class for export commands.

This module provides the base class for all export operations with
common functionality like API calls, file saving, and progress tracking.

Refactored to use focused utility modules for better maintainability.
"""

from dataclasses import dataclass, field
from trxo_lib.exceptions import TrxoAbort
from typing import Any, Callable, Dict, Optional


from trxo_lib.config.api_headers import get_headers
from trxo_lib.exports.helpers.metadata_builder import MetadataBuilder
from trxo_lib.exports.helpers.pagination_handler import PaginationHandler
from trxo_lib.state.hash import HashManager

from trxo_lib.core.base_command import BaseCommand


@dataclass
class ExportResult:
    """Structured result returned by export_data().

    Attributes:
        data: The filtered data payload.
        metadata: Export metadata (command name, timestamp, etc.).
        file_path: Path to saved file, or None if view mode / not saved.
        status_code: HTTP status code from the API response.
    """

    data: Any = None
    metadata: dict = field(default_factory=dict)
    file_path: Optional[str] = None
    status_code: int = 0


class BaseExporter(BaseCommand):
    """Base class for all export operations"""

    def __init__(self):
        super().__init__()
        self.hash_manager = HashManager(self.config_store)
        self._current_token = None
        self._current_api_base_url = None

    def export_data(
        self,
        command_name: str,
        api_endpoint: str,
        headers: Dict[str, str],
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
        response_filter: Optional[Callable[[Any], Any]] = None,
        **kwargs,
    ) -> ExportResult:
        """Export data fetching logic without UI side effects.

        Returns:
            ExportResult with data, metadata, file_path, and status_code.
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
                headers = get_headers("protocol_1_0")
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
            export_result = ExportResult(
                data=filtered_data,
                metadata=metadata,
                status_code=response.status_code,
            )

            return export_result

        except Exception as e:
            self.logger.error(f"Export failed for {command_name}: {str(e)}")
            raise
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
