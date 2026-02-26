"""
Base command class providing common functionality.

This module provides the base class that contains common functionality
used by both import and export commands.
"""

import json
import os
import time
from abc import ABC, abstractmethod
import typer
from typing import Optional, List, Dict, Any
import httpx
from trxo.utils.config_store import ConfigStore
from trxo.auth.token_manager import TokenManager
from trxo.utils.console import success, error, warning
from .auth_manager import AuthManager
from trxo.utils.url import construct_api_url
from trxo.logging import get_logger, log_api_call


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
            f"trxo.{self.__class__.__module__}.{self.__class__.__name__}"
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

            # Explicitly check for IDM if that's the target product
            if self.product == "idm":
                # Gather IDM credentials (prompt for password if needed)
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

            # Note: We don't initialize both unless strictly necessary.
            # Most commands target one product (AM or IDM).
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
                    error(
                        "IDM credentials not available. Configure IDM access or "
                        "provide --idm-username and --idm-password."
                    )
                    raise typer.Exit(1)
                return {
                    "X-OpenIDM-Username": self._idm_username,
                    "X-OpenIDM-Password": self._idm_password,
                }
            else:
                if not token_or_session:
                    error(
                        "AM session token not available. Configure AM access or "
                        "provide --onprem-username and --onprem-password."
                    )
                    raise typer.Exit(1)
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
                raise FileNotFoundError(f"File not found: {file_path}")

            # Read and parse JSON file
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validate JSON structure
            if not isinstance(data, dict):
                raise ValueError("Invalid JSON structure: Root should be an object")

            # Check for expected structure
            if "data" not in data:
                raise ValueError("Invalid JSON structure: Missing 'data' field")

            # Support both collection (data.result = [...]) and single-object (data = {...}) shapes
            if "result" in data["data"]:
                items = data["data"]["result"]
                if not isinstance(items, list):
                    raise ValueError(
                        "Invalid JSON structure: 'data.result' should be an array"
                    )
            else:
                # No 'result' array; accept a single object and wrap it
                if isinstance(data["data"], dict):
                    items = [data["data"]]
                else:
                    raise ValueError(
                        "Invalid JSON structure: 'data' must be an object or contain 'result' array"
                    )

            # Validate each item has required fields
            required_fields = self.get_required_fields()
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    raise ValueError(f"Invalid item at index {i}: Should be an object")

                for field in required_fields:
                    if field not in item:
                        raise ValueError(
                            f"Invalid item at index {i}: Missing required field '{field}'"
                        )

            return items

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")
        except Exception as e:
            raise Exception(f"Error loading file: {str(e)}")

    def make_http_request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        data: Optional[str] = None,
        timeout: float = 30.0,
    ) -> httpx.Response:
        """Make HTTP request with common error handling and comprehensive logging"""
        start_time = time.time()
        method_upper = method.upper()
        request_size = len(data.encode("utf-8")) if data else 0

        # Log request start
        self.logger.debug(f"Starting {method_upper} request to {url}")

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
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # Calculate timing and response size
                duration = time.time() - start_time
                response_size = len(response.content) if response.content else 0

                # Log successful API call
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

            error(f"HTTP error: {clean_error}")

            # Raise generic exception with clean message
            # to avoid verbose string representation in callers
            raise Exception(clean_error) from e
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

            error(f"Request error: {error_msg}")
            raise

    def print_summary(self) -> None:
        """Print summary of operations and exit with appropriate code"""
        item_type = self.get_item_type()

        if self.successful_updates > 0:
            success(f"Successfully processed {self.successful_updates} {item_type}")

        if self.failed_updates > 0:
            error(f"Failed to process {self.failed_updates} {item_type}")
            raise typer.Exit(1)

        if self.successful_updates == 0:
            warning(f"No {item_type} were processed")
            raise typer.Exit(1)

    @abstractmethod
    def get_required_fields(self) -> List[str]:
        """Return list of required fields for validation"""
        pass

    @abstractmethod
    def get_item_type(self) -> str:
        """Return the type of items being processed (for logging)"""
        pass
