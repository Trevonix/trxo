"""
TRXO Logging Module

This module provides comprehensive logging functionality for the TRXO CLI tool.
It includes structured logging, API call tracking, cross-platform log storage,
and automatic sanitization of sensitive information.

Key Features:
- Single log file with daily rotation
- Cross-platform log directory detection
- API call logging with request/response details
- Transaction and authentication logging
- Automatic sanitization of sensitive data
- Configurable log levels and formatting
- Integration with existing console output
"""

from .config import LogConfig
from .logger import (
    LogLevel,
    get_logger,
    log_api_call,
    log_application_event,
    log_authentication_event,
)
from .utils import get_log_directory, sanitize_data

__all__ = [
    "get_logger",
    "setup_logging",
    "log_api_call",
    "log_transaction",
    "log_application_event",
    "log_authentication_event",
    "LogLevel",
    "LogConfig",
    "sanitize_data",
    "get_log_directory",
]

# Version info
__version__ = "1.0.0"
