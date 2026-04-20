"""
Passive logging module for TRXO Library (trxo_lib).

This module provides the primary logging interface for the library.
Following best practices, it does NOT configure file output or formatting.
It defines the `get_logger` interface and adds a `NullHandler` to the base logger so it
fails silently if the consumer (the CLI) doesn't configure handlers.
"""

import logging
from typing import Any, Dict, Optional

# Base namespace for the library
_ROOT_LOGGER_NAME = "trxo_lib"

# Setup NullHandler as per library best practices
_base_logger = logging.getLogger(_ROOT_LOGGER_NAME)
_base_logger.addHandler(logging.NullHandler())

# Global logger registry
_loggers: Dict[str, logging.Logger] = {}


def info(msg: str, *args, **kwargs):
    """Log an info message to the base library logger."""
    get_logger(_ROOT_LOGGER_NAME).info(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    """Log an error message to the base library logger."""
    get_logger(_ROOT_LOGGER_NAME).error(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    """Log a warning message to the base library logger."""
    get_logger(_ROOT_LOGGER_NAME).warning(msg, *args, **kwargs)


def success(msg: str, *args, **kwargs):
    """Log a success message (as info) to the base library logger."""
    get_logger(_ROOT_LOGGER_NAME).info(f"✔ {msg}", *args, **kwargs)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance within the trxo_lib namespace.

    If the name does not start with 'trxo_lib.', it will be prefixed.
    """
    if name.startswith("trxo."):
        # Normalize trxo.* to trxo_lib.* for library components
        name = name.replace("trxo.", f"{_ROOT_LOGGER_NAME}.", 1)

    if not name.startswith(_ROOT_LOGGER_NAME):
        name = f"{_ROOT_LOGGER_NAME}.{name}"

    if name not in _loggers:
        logger = logging.getLogger(name)
        _loggers[name] = logger

    return _loggers[name]


def log_api_call(
    method: str,
    url: str,
    status_code: Optional[int] = None,
    duration: Optional[float] = None,
    request_size: Optional[int] = None,
    response_size: Optional[int] = None,
    request_headers: Optional[Dict[str, str]] = None,
    response_headers: Optional[Dict[str, str]] = None,
    error: Optional[str] = None,
    logger_name: str = "trxo_lib.api",
) -> None:
    """Log an API call with structured information."""
    logger = get_logger(logger_name)

    extra = {
        "api_method": method,
        "api_url": url,
        "api_status": status_code,
        "api_duration": duration or 0,
    }

    if request_size is not None:
        extra["api_request_size"] = request_size
    if response_size is not None:
        extra["api_response_size"] = response_size
    if request_headers:
        extra["api_request_headers"] = request_headers
    if response_headers:
        extra["api_response_headers"] = response_headers
    if error:
        extra["api_error"] = error

    # Log at appropriate level
    if error or (status_code and status_code >= 500):
        logger.error("API call failed", extra=extra)
    elif status_code and 400 <= status_code < 500:
        logger.warning("API call client error", extra=extra)
    else:
        logger.debug("API call completed", extra=extra)


def log_transaction(
    operation: str,
    details: Optional[Dict[str, Any]] = None,
    logger_name: str = "trxo_lib.transaction",
) -> None:
    """Log critical transaction data at DEBUG level."""
    logger = get_logger(logger_name)
    extra = {"transaction_operation": operation}

    if details:
        # Avoid circular imports for utils
        from trxo_lib.config.constants import SENSITIVE_KEYS
        from .utils import sanitize_dict

        sanitized_details = sanitize_dict(details, SENSITIVE_KEYS)
        extra["transaction_details"] = sanitized_details

    logger.debug(f"Transaction: {operation}", extra=extra)


def log_application_event(
    event: str,
    level: str = "info",
    details: Optional[Dict[str, Any]] = None,
    logger_name: str = "trxo_lib.app",
) -> None:
    """Log application-level events at appropriate levels."""
    logger = get_logger(logger_name)
    extra = {"app_event": event}

    if details:
        extra["app_details"] = details

    log_method = getattr(logger, level.lower(), logger.info)
    log_method(f"Application: {event}", extra=extra)


def log_authentication_event(
    auth_type: str,
    success: bool,
    details: Optional[Dict[str, Any]] = None,
    logger_name: str = "trxo_lib.auth",
) -> None:
    """Log authentication events with appropriate levels."""
    logger = get_logger(logger_name)
    extra = {"auth_type": auth_type, "auth_success": success}

    if details:
        from trxo_lib.config.constants import SENSITIVE_KEYS
        from .utils import sanitize_dict

        sanitized_details = sanitize_dict(details, SENSITIVE_KEYS)
        extra["auth_details"] = sanitized_details

    if success:
        logger.info(f"Authentication successful: {auth_type}", extra=extra)
    else:
        logger.error(f"Authentication failed: {auth_type}", extra=extra)
