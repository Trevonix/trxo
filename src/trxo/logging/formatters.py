"""
Custom formatters for TRXO logging.

This module provides specialized formatters for different types of log entries,
including API calls, authentication events, and general application logs.
"""

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
        sensitive_keys: tuple = None,
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
        fmt_parts.extend(["%(levelname)s", "[%(name)s]", "%(message)s"])
        if include_thread_info:
            fmt_parts.insert(-1, "[Thread:%(thread)d]")
        if include_process_info:
            fmt_parts.insert(-1, "[PID:%(process)d]")
        fmt_string = " ".join(fmt_parts)
        super().__init__(fmt=fmt_string, datefmt="%Y-%m-%d %H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record with optional sanitization.
        Args:
            record: The log record to format
        Returns:
            str: Formatted log message
        """
        # Sanitize sensitive data if enabled
        if self.sanitize_sensitive and hasattr(record, "msg"):
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
        Format an API call log record in a human-readable text format.
        """
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        method = getattr(record, "api_method", "UNKNOWN")
        url = getattr(record, "api_url", "")
        status = getattr(record, "api_status", "---")
        duration = round(getattr(record, "api_duration", 0) * 1000, 2)

        # Base line matching standard log format
        # Example: 2026-02-02 17:27:34 DEBUG [trxo.api] GET /am/json/... -> 200 (120ms)
        log_msg = (
            f"{timestamp} {record.levelname} [{record.name}] "
            f"{method} {url} -> {status} ({duration}ms)"
        )

        lines = [log_msg]

        # Add error info if present
        if hasattr(record, "api_error") and record.api_error:
            lines.append(f"    Error: {record.api_error}")

        # Add request/response headers only if in DEBUG/Trace mode and enabled
        # For now, we keep it clean as requested, but if you want headers back,
        # we can toggle them here. Since the user requested "clean", we skip headers
        # unless there is an error or specific need.

        return "\n".join(lines)


class MultiplexFormatter(logging.Formatter):
    """
    Formatter that delegates to different formatters based on the log record.

    Uses APICallFormatter for API logs and TRxOFormatter for everything else.
    """

    def __init__(
        self, default_formatter: logging.Formatter, api_formatter: logging.Formatter
    ):
        """
        Initialize the multiplex formatter.

        Args:
            default_formatter: Formatter for standard logs
            api_formatter: Formatter for API logs
        """
        self.default_formatter = default_formatter
        self.api_formatter = api_formatter
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        """
        Delegate formatting to the appropriate formatter.

        Args:
            record: The log record to format

        Returns:
            str: Formatted log message
        """
        # specialized formatting for API logger or records with API metadata
        if record.name == "trxo.api" or hasattr(record, "api_method"):
            return self.api_formatter.format(record)
        return self.default_formatter.format(record)
