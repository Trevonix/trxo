"""
Base command class providing common functionality.

This module provides the base class that contains common functionality
used by both import and export commands.
"""

from trxo_lib.exceptions import (
    TrxoAbort,
    TrxoAuthError,
    TrxoError,
    TrxoIOError,
    TrxoValidationError,
)
import json
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

from trxo_lib.auth.token_manager import TokenManager
from trxo_lib.logging import get_logger, log_api_call
from trxo_lib.config.config_store import ConfigStore
from trxo_lib.core.url import construct_api_url

from trxo_lib.core.auth_manager import AuthManager


class BaseCommand(ABC):
    """Base class for all import and export commands"""

    def __init__(self):
        self.config_store = ConfigStore()
        self.token_manager = TokenManager(self.config_store)
        self.auth_manager = AuthManager(self.config_store, self.token_manager)
        self.successful_updates = 0
        self.failed_updates = 0
        self.auth_mode: str = "service-account"
        self.product: str = "am"  # Default product (overridden by subclasses)

        # IDM credentials (populated during initialize_auth for on-prem IDM)
        self._idm_username: Optional[str] = None
        self._idm_password: Optional[str] = None
        self._idm_base_url: Optional[str] = None

        # Initialize logging
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    def _construct_api_url(self, base_url: str, endpoint: str) -> str:
        """Construct API URL using shared utility"""
        return construct_api_url(base_url, endpoint)

    def initialize_auth(
        self,
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
    ) -> tuple:
        """Initialize authentication and return token/session and base URL.
        Sets self.auth_mode to the active mode ('service-account' or 'onprem').
        """
        # Validate project with argument mode support (including on-prem argument mode)
        current_project = self.auth_manager.validate_project(
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
        # If not in argument mode, update config if arguments provided
        argument_mode = all([jwk_path, sa_id, base_url])
        if not argument_mode:
            self.auth_manager.update_config_if_needed(jwk_path, sa_id, base_url)

        # Determine mode and get token/session
        self.auth_mode = self.auth_manager.get_auth_mode(
            current_project, override=auth_mode
        )
        api_base_url = None
        if self.auth_mode != "onprem" or self.product == "am":
            api_base_url = self.auth_manager.get_base_url(current_project, base_url)

        if self.auth_mode == "onprem":
            token_or_session = None
            if self.product == "am":
                # Get AM session token
                token_or_session = self.auth_manager.get_onprem_session(
                    current_project,
                    username=onprem_username,
                    password=onprem_password,
                    realm=onprem_realm,
                    base_url=am_base_url,
                )

            # Initialize IDM credentials if provided or if product is IDM
            if self.product == "idm" or idm_username or idm_password or idm_base_url:
                # Gather IDM credentials (no prompting here, logic is in auth_manager)
                try:
                    self._idm_username, self._idm_password = (
                        self.auth_manager.get_idm_credentials(
                            current_project,
                            idm_username=idm_username,
                            idm_password=idm_password,
                        )
                    )
                    self._idm_base_url = self.auth_manager.get_idm_base_url(
                        current_project, idm_base_url
                    )
                except (TrxoAuthError, TrxoConfigError):
                    # If IDM is not the primary product, we can tolerate missing credentials
                    # unless they are explicitly provided and failed.
                    if self.product == "idm":
                        raise
        else:
            token_or_session = self.auth_manager.get_token(current_project)

        if self.auth_mode == "onprem" and self.product == "idm":
            api_base_url = self._idm_base_url

        return token_or_session, api_base_url

    def build_auth_headers(
        self, token_or_session: str, product: Optional[str] = None
    ) -> Dict[str, str]:
        """Return auth headers based on current mode and target product.

        Args:
            token_or_session: Bearer token or AM session token.
            product: Target product - 'am' or 'idm'. Defaults to self.product.
        """
        if not product:
            product = self.product

        if self.auth_mode == "onprem":
            if product == "idm":
                if not self._idm_username or not self._idm_password:
                    self.logger.error(
                        "IDM credentials not available for building auth headers"
                    )
                    raise TrxoAuthError(
                        "IDM credentials not available. Configure IDM access or "
                        "provide --idm-username and --idm-password."
                    )
                return {
                    "X-OpenIDM-Username": self._idm_username,
                    "X-OpenIDM-Password": self._idm_password,
                }
            else:
                if not token_or_session:
                    self.logger.error(
                        "AM session token not available for building auth headers"
                    )
                    raise TrxoAuthError(
                        "AM session token not available. Configure AM access or "
                        "provide --onprem-username and --onprem-password."
                    )
                return {"Cookie": f"iPlanetDirectoryPro={token_or_session}"}
        return {"Authorization": f"Bearer {token_or_session}"}

    def cleanup(self):
        """Clean up resources (e.g., temporary projects)"""
        self.auth_manager.cleanup_argument_mode()

    def load_data_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Load and validate data from JSON file"""
        try:
            # Convert to absolute path if relative
            if not os.path.isabs(file_path):
                file_path = os.path.abspath(file_path)

            # Check if file exists
            if not os.path.exists(file_path):
                raise TrxoIOError(
                    f"File not found: {file_path}",
                    hint=f"Check if the file exists at {file_path}. Use --file to specify the correct path.",
                )

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Decode JSON with hint for non-JSON files
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                raise TrxoIOError(
                    f"Invalid JSON format in {os.path.basename(file_path)}: {str(e)}",
                    hint=f"Ensure the file {os.path.basename(file_path)} is a valid JSON.",
                )

            # Validate JSON structure
            if not isinstance(data, dict):
                raise TrxoValidationError(
                    "Invalid JSON structure in export file",
                    hint="The root of the JSON file should be an object.",
                )

            # Check for expected structure
            if "data" not in data:
                raise TrxoValidationError(
                    "Invalid JSON structure: Missing 'data' field",
                    hint="The file does not appear to be a standard TRXO export.",
                )

            # Support both collection (data.result = [...]) and single-object (data = {...}) shapes
            if "result" in data["data"]:
                items = data["data"]["result"]
                if not isinstance(items, list):
                    raise TrxoValidationError(
                        "Invalid JSON structure: 'data.result' should be an array"
                    )
            else:
                # No 'result' array; accept a single object and wrap it
                if isinstance(data["data"], dict):
                    items = [data["data"]]
                else:
                    raise TrxoValidationError(
                        "Invalid JSON structure: 'data' must be an object or contain 'result' array"
                    )

            # Validate each item has required fields
            required_fields = self.get_required_fields()
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    raise TrxoValidationError(
                        f"Invalid item at index {i}: Should be an object"
                    )

                for field in required_fields:
                    if field not in item:
                        raise TrxoValidationError(
                            f"Invalid item at index {i}: Missing required field '{field}'",
                            hint=f"Each item in this command requires the '{field}' field.",
                        )

            return items

        except TrxoError:
            raise
        except Exception as e:
            file_name = os.path.basename(file_path)
            raise TrxoIOError(
                f"Error loading file {file_name}: {str(e)}",
                hint="Verify the file exists, is readable, and is formatted correctly.",
            )

    def make_http_request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        data: Optional[str] = None,
        timeout: float = 30.0,
        suppress_logs: bool = False,
    ) -> httpx.Response:
        """Make HTTP request with common error handling and comprehensive logging"""
        start_time = time.time()
        method_upper = method.upper()
        request_size = len(data.encode("utf-8")) if data else 0

        # Log request start (only if not suppressed)
        if not suppress_logs:
            self.logger.debug(f"Starting {method_upper} request to {url}")
            accept_version = headers.get('Accept-API-Version') if headers else None
            self.logger.debug(f"Header accept version: {accept_version}")

        try:
            with httpx.Client(timeout=timeout) as client:
                if method_upper == "GET":
                    response = client.get(url, headers=headers)
                elif method_upper == "PUT":
                    response = client.put(url, headers=headers, data=data)
                elif method_upper == "POST":
                    response = client.post(url, headers=headers, data=data)
                elif method_upper == "PATCH":
                    response = client.patch(url, headers=headers, data=data)
                elif method_upper == "DELETE":
                    response = client.delete(url, headers=headers)
                else:
                    raise TrxoError(f"Unsupported HTTP method: {method}")

                # Calculate timing and response size
                duration = time.time() - start_time
                response_size = len(response.content) if response.content else 0

                # Log successful API call (only if not suppressed or if it's an actual error)
                if not suppress_logs or response.status_code >= 500:
                    log_api_call(
                        method=method_upper,
                        url=url,
                        status_code=response.status_code,
                        duration=duration,
                        request_size=request_size if request_size > 0 else None,
                        response_size=response_size if response_size > 0 else None,
                        request_headers=headers,
                        response_headers=(
                            dict(response.headers) if response.headers else None
                        ),
                    )

                response.raise_for_status()
                return response

        except httpx.HTTPStatusError as e:
            duration = time.time() - start_time

            # Extract clean error message from response
            error_msg = e.response.text
            try:
                error_data = e.response.json()
                if isinstance(error_data, dict):
                    if "message" in error_data:
                        error_msg = error_data["message"]
                    elif "reason" in error_data:
                        error_msg = error_data["reason"]
                    elif "error_description" in error_data:
                        error_msg = error_data["error_description"]
            except Exception:
                pass

            clean_error = f"{e.response.status_code} - {error_msg}"

            # Log failed API call
            if not suppress_logs or e.response.status_code >= 500:
                log_api_call(
                    method=method_upper,
                    url=url,
                    status_code=e.response.status_code,
                    duration=duration,
                    request_size=request_size if request_size > 0 else None,
                    response_size=len(e.response.content) if e.response.content else None,
                    request_headers=headers,
                    response_headers=(
                        dict(e.response.headers) if e.response.headers else None
                    ),
                    error=clean_error,
                )

                self.logger.error(f"HTTP error: {clean_error}")

            # Raise generic exception with clean message
            # to avoid verbose string representation in callers
            raise TrxoIOError(clean_error) from None
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            # Log failed request
            log_api_call(
                method=method_upper,
                url=url,
                duration=duration,
                request_size=request_size if request_size > 0 else None,
                request_headers=headers,
                error=error_msg,
            )

            self.logger.error(f"Request error: {error_msg}")
            raise

    def get_summary(self) -> dict:
        """Return a structured summary of operations.

        Returns:
            dict with item_type, successful count, and failed count.
        """
        return {
            "item_type": self.get_item_type(),
            "successful": self.successful_updates,
            "failed": self.failed_updates,
        }

    def print_summary(self) -> None:
        """Evaluate operation summary and raise TrxoAbort on failures.

        This is a thin wrapper around get_summary() kept for backward
        compatibility with existing callers. It logs instead of printing.
        """
        summary = self.get_summary()
        item_type = summary["item_type"]

        if summary["successful"] > 0:
            self.logger.info(
                f"Successfully processed {summary['successful']} {item_type}"
            )

        if summary["failed"] > 0:
            self.logger.error(f"Failed to process {summary['failed']} {item_type}")
            raise TrxoAbort(code=1)

        if summary["successful"] == 0:
            self.logger.warning(f"No {item_type} were processed")
            raise TrxoAbort(code=1)

    @abstractmethod
    def get_required_fields(self) -> List[str]:
        """Return list of required fields for validation"""
        return []

    @abstractmethod
    def get_item_type(self) -> str:
        """Return the type of items being processed (for logging)"""
        pass
