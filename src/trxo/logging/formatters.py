"""
Custom formatters for TRXO logging.

This module provides specialized formatters for different types of log entries,
including API calls, authentication events, and general application logs.
"""

import json
import logging
from datetime import datetime
from .utils import sanitize_data
from trxo.constants import SENSITIVE_KEYS


class TRxOFormatter(logging.Formatter):
    """
    Custom formatter for TRXO log entries.

    Provides structured formatting with optional components and
    automatic sanitization of sensitive data.
    """
    def __init__(
        self,
        include_timestamps: bool = True,
        include_thread_info: bool = False,
        include_process_info: bool = False,
        sanitize_sensitive: bool = True,
        sensitive_keys: tuple = None
    ):
        self.include_timestamps = include_timestamps
        self.include_thread_info = include_thread_info
        self.include_process_info = include_process_info
        self.sanitize_sensitive = sanitize_sensitive
        self.sensitive_keys = sensitive_keys or SENSITIVE_KEYS
        # Build format string
        fmt_parts = []
        if include_timestamps:
            fmt_parts.append("%(asctime)s")
        fmt_parts.extend([
            "%(levelname)s",
            "[%(name)s]",
            "%(message)s"
        ])
        if include_thread_info:
            fmt_parts.insert(-1, "[Thread:%(thread)d]")
        if include_process_info:
            fmt_parts.insert(-1, "[PID:%(process)d]")
        fmt_string = " ".join(fmt_parts)
        super().__init__(
            fmt=fmt_string,
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record with optional sanitization.
        Args:
            record: The log record to format
        Returns:
            str: Formatted log message
        """
        # Sanitize sensitive data if enabled
        if self.sanitize_sensitive and hasattr(record, 'msg'):
            if isinstance(record.msg, (dict, list)):
                record.msg = sanitize_data(record.msg, self.sensitive_keys)
            elif isinstance(record.args, (tuple, list)):
                sanitized_args = []
                for arg in record.args:
                    if isinstance(arg, (dict, list)):
                        sanitized_args.append(sanitize_data(arg, self.sensitive_keys))
                    else:
                        sanitized_args.append(arg)
                record.args = tuple(sanitized_args)

        return super().format(record)


class APICallFormatter(logging.Formatter):
    """
    Specialized formatter for API call logging.

    Creates structured log entries for HTTP requests and responses
    with timing information and sanitized headers/payloads.
    """

    def __init__(self, sanitize_sensitive: bool = True, sensitive_keys: tuple = None):
        self.sanitize_sensitive = sanitize_sensitive
        self.sensitive_keys = sensitive_keys or SENSITIVE_KEYS
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        """
        Format an API call log record.

        Expected record attributes:
        - api_method: HTTP method (GET, POST, etc.)
        - api_url: Request URL
        - api_status: Response status code
        - api_duration: Request duration in seconds
        - api_request_size: Request payload size (optional)
        - api_response_size: Response payload size (optional)
        - api_error: Error message (optional)
        """
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        # Build base API log entry
        api_info = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "method": getattr(record, "api_method", "UNKNOWN"),
            "url": getattr(record, "api_url", ""),
            "status": getattr(record, "api_status", None),
            "duration_ms": round(getattr(record, "api_duration", 0) * 1000, 2)
        }

        # Add optional fields
        if hasattr(record, "api_request_size"):
            api_info["request_size"] = record.api_request_size

        if hasattr(record, "api_response_size"):
            api_info["response_size"] = record.api_response_size

        if hasattr(record, "api_error"):
            api_info["error"] = record.api_error

        # Add request/response details if present
        if hasattr(record, "api_request_headers"):
            headers = record.api_request_headers
            if self.sanitize_sensitive:
                headers = sanitize_data(headers, self.sensitive_keys)
            api_info["request_headers"] = headers

        if hasattr(record, "api_response_headers"):
            headers = record.api_response_headers
            if self.sanitize_sensitive:
                headers = sanitize_data(headers, self.sensitive_keys)
            api_info["response_headers"] = headers

        # Format as JSON for structured logging
        try:
            return json.dumps(api_info, ensure_ascii=False, separators=(',', ':'))
        except (TypeError, ValueError):
            # Fallback to simple string format
            return (
                f"{timestamp} {record.levelname} [API] "
                f"{api_info['method']} {api_info['url']} -> "
                f"{api_info['status']} ({api_info['duration_ms']}ms)"
            )
