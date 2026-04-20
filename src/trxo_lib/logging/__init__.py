"""
TRXO Library Logging Module

This module provides logging for the library. It acts as a passive emitter
and adds a NullHandler, expecting the consumer (like the TRXO CLI) to configure
the log outputs (files, formatters, etc.).
"""

from .logger import (
    error,
    get_logger,
    info,
    log_api_call,
    log_application_event,
    log_authentication_event,
    log_transaction,
    success,
    warning,
)
from .utils import sanitize_dict as sanitize_data

__all__ = [
    "get_logger",
    "log_api_call",
    "log_transaction",
    "log_application_event",
    "log_authentication_event",
    "sanitize_data",
    "info",
    "error",
    "warning",
    "success",
]

# Version info
__version__ = "1.0.0"
