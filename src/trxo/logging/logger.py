"""
Main logging module for TRXO CLI.

This module provides the primary logging interface, logger setup,
and integration with the existing console output system with daily rotation.
"""

import logging
import logging.handlers
import sys
from typing import Optional, Dict, Any

from .config import LogConfig, LogLevel, get_log_file_path
from .formatters import TRxOFormatter, APICallFormatter, MultiplexFormatter


# Global logger registry
_loggers: Dict[str, logging.Logger] = {}
_logging_configured = False
_is_configuring = False
_log_config: Optional[LogConfig] = None


def setup_logging(
    config: Optional[LogConfig] = None, force_reconfigure: bool = False
) -> None:
    """
    Set up the TRxO logging system.

    Args:
        config: LogConfig instance, uses default if None
        force_reconfigure: Force reconfiguration even if already set up
    """
    global _logging_configured, _is_configuring, _log_config

    if _logging_configured and not force_reconfigure:
        return

    if _is_configuring:
        return

    _is_configuring = True
    try:
        if config is None:
            config = LogConfig()

            # Default to DEBUG for all logs to ensure we capture everything
            config.default_level = LogLevel.DEBUG

            # Try to read log level from user config as an override
            try:
                from trxo.utils.config_store import ConfigStore
                import json

                config_store = ConfigStore()
                global_settings_file = config_store.base_dir / "settings.json"

                if global_settings_file.exists():
                    with open(global_settings_file, "r", encoding="utf-8") as f:
                        settings = json.load(f)
                        user_level = settings.get("log_level")
                        if user_level and user_level in [lev.value for lev in LogLevel]:
                            config.default_level = LogLevel(user_level)
            except Exception:
                pass

        _log_config = config

        # Get log file path
        log_file_path = get_log_file_path(config)

        # Create root logger for TRXO
        root_logger = logging.getLogger("trxo")
        # Ensure root logger level is at least as low as the lowest target
        root_logger.setLevel(logging.DEBUG)

        # Clear existing handlers
        root_logger.handlers.clear()

        # Create daily rotating file handler
        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=log_file_path,
            when="midnight",
            interval=1,
            backupCount=config.log_retention_days,
            encoding="utf-8",
            utc=False,
        )
        # Always allow DEBUG at the file handler level
        file_handler.setLevel(logging.DEBUG)

        # Set suffix for rotated files (YYYY-MM-DD format)
        file_handler.suffix = "%Y-%m-%d"

        # Create formatters
        standard_formatter = TRxOFormatter(
            include_timestamps=config.include_timestamps,
            include_thread_info=config.include_thread_info,
            include_process_info=config.include_process_info,
            sanitize_sensitive=config.sanitize_sensitive_data,
            sensitive_keys=config.sensitive_keys,
        )

        api_formatter = APICallFormatter(
            sanitize_sensitive=config.sanitize_sensitive_data,
            sensitive_keys=config.sensitive_keys,
        )

        # Use multiplex formatter to handle both types in one file
        multiplex_formatter = MultiplexFormatter(
            default_formatter=standard_formatter, api_formatter=api_formatter
        )
        file_handler.setFormatter(multiplex_formatter)

        # Add file handler to root logger
        root_logger.addHandler(file_handler)

        # Setup console handler
        console_handler = logging.StreamHandler(sys.stderr)
        # Console uses its own level from config (defaults to WARNING)
        console_handler.setLevel(getattr(logging, config.console_level.value))

        console_formatter = TRxOFormatter(
            include_timestamps=False,
            sanitize_sensitive=config.sanitize_sensitive_data,
            sensitive_keys=config.sensitive_keys,
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # Explicitly set API logger to DEBUG
        api_logger = logging.getLogger("trxo.api")
        api_logger.setLevel(logging.DEBUG)
        api_logger.propagate = True

        _logging_configured = True
        _is_configuring = False

        # Log completion
        setup_logger = get_logger("trxo.setup")
        setup_logger.debug(f"Logging initialized - File: {log_file_path}")
        setup_logger.debug(f"Default Level: {config.default_level.value}")

    except Exception:
        _is_configuring = False
        raise


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the specified name."""
    if not _logging_configured:
        setup_logging()

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
    logger_name: str = "trxo.api",
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
    logger_name: str = "trxo.transaction",
) -> None:
    """Log critical transaction data at DEBUG level."""
    logger = get_logger(logger_name)
    extra = {"transaction_operation": operation}

    if details:
        from .utils import sanitize_data
        from trxo.constants import SENSITIVE_KEYS

        sanitized_details = sanitize_data(details, SENSITIVE_KEYS)
        extra["transaction_details"] = sanitized_details

    logger.debug(f"Transaction: {operation}", extra=extra)


def log_application_event(
    event: str,
    level: str = "info",
    details: Optional[Dict[str, Any]] = None,
    logger_name: str = "trxo.app",
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
    logger_name: str = "trxo.auth",
) -> None:
    """Log authentication events with appropriate levels."""
    logger = get_logger(logger_name)
    extra = {"auth_type": auth_type, "auth_success": success}

    if details:
        from .utils import sanitize_data
        from trxo.constants import SENSITIVE_KEYS

        sanitized_details = sanitize_data(details, SENSITIVE_KEYS)
        extra["auth_details"] = sanitized_details

    if success:
        logger.info(f"Authentication successful: {auth_type}", extra=extra)
    else:
        logger.error(f"Authentication failed: {auth_type}", extra=extra)
