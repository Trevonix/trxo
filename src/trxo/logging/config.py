"""
Logging configuration for TRXO CLI.

This module handles cross-platform log directory detection,
log file configuration, and logging setup parameters.
"""

import os
import platform
from pathlib import Path
from enum import Enum
from typing import Optional
from dataclasses import dataclass
from trxo.constants import (
    LOG_FILE_NAME,
    LOG_RETENTION_DAYS,
    SENSITIVE_KEYS
)


class LogLevel(Enum):
    """Log levels for TRXO logging"""
    DEBUG = "DEBUG"
    INFO = "INFO" 
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class LogConfig:
    """Configuration class for TRXO logging"""

    # Log file settings
    log_filename: str = f"{LOG_FILE_NAME}.log"
    log_retention_days: int = LOG_RETENTION_DAYS
    
    # Log levels
    default_level: LogLevel = LogLevel.INFO
    console_level: LogLevel = LogLevel.WARNING
    
    # Log format settings
    include_timestamps: bool = True
    include_thread_info: bool = False
    include_process_info: bool = False
    
    # API logging settings
    log_api_requests: bool = True
    log_api_responses: bool = True
    log_request_headers: bool = True
    log_response_headers: bool = False
    max_payload_size: int = 1024  # Max chars to log for request/response bodies
    
    # Sanitization settings
    sanitize_sensitive_data: bool = True
    sensitive_keys: tuple = SENSITIVE_KEYS


def get_log_directory() -> Path:
    """
    Get the appropriate log directory for the current operating system.
    
    Returns:
        Path: Platform-specific log directory
        
    Raises:
        OSError: If unable to create log directory
    """
    system = platform.system().lower()
    
    if system == "windows":
        # Windows: %APPDATA%/TRXO/logs/
        base_dir = Path(os.environ.get("APPDATA", ""))
        if not base_dir.exists():
            # Fallback to user profile
            base_dir = Path.home()
        log_dir = base_dir / LOG_FILE_NAME / "logs"

    elif system == "darwin":
        # macOS: ~/Library/Logs/TRXO/
        log_dir = Path.home() / "Library" / "Logs" / LOG_FILE_NAME
        
    else:
        # Linux and other Unix-like: ~/.local/share/TRXO/logs/
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if xdg_data_home:
            base_dir = Path(xdg_data_home)
        else:
            base_dir = Path.home() / ".local" / "share"
        log_dir = base_dir / LOG_FILE_NAME / "logs"
    
    # Create directory if it doesn't exist
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir
    except (OSError, PermissionError) as e:
        # Fallback to current directory if we can't create the log directory
        fallback_dir = Path.cwd() / "logs"
        fallback_dir.mkdir(exist_ok=True)
        return fallback_dir


def get_log_file_path(config: Optional[LogConfig] = None) -> Path:
    """
    Get the full path to the log file.
    
    Args:
        config: LogConfig instance, uses default if None
        
    Returns:
        Path: Full path to the log file
    """
    if config is None:
        config = LogConfig()
    
    log_dir = get_log_directory()
    return log_dir / config.log_filename
