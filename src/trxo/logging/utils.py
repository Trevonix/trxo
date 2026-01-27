"""
Utility functions for TRXO logging.

This module provides helper functions for data sanitization,
log management, and logging-related operations.
"""

import re
import json
from typing import Any, Dict, List, Union, Tuple
from pathlib import Path
from datetime import datetime, timedelta
from trxo.constants import SENSITIVE_KEYS


def sanitize_data(data: Any, sensitive_keys: Tuple[str, ...]) -> Any:
    """
    Recursively sanitize sensitive data from dictionaries, lists, and strings.
    
    Args:
        data: Data to sanitize (dict, list, str, or other)
        sensitive_keys: Tuple of keys/patterns to sanitize
        
    Returns:
        Any: Sanitized data with sensitive values replaced
    """
    if isinstance(data, dict):
        return sanitize_dict(data, sensitive_keys)
    elif isinstance(data, list):
        return sanitize_list(data, sensitive_keys)
    elif isinstance(data, str):
        return sanitize_string(data, sensitive_keys)
    else:
        return data


def sanitize_dict(data: Dict[str, Any], sensitive_keys: Tuple[str, ...]) -> Dict[str, Any]:
    """
    Sanitize sensitive values in a dictionary.
    
    Args:
        data: Dictionary to sanitize
        sensitive_keys: Keys to sanitize
        
    Returns:
        Dict: Sanitized dictionary
    """
    sanitized = {}
    
    for key, value in data.items():
        key_lower = key.lower()
        
        # Check if key matches any sensitive pattern
        is_sensitive = any(
            sensitive_key.lower() in key_lower 
            for sensitive_key in sensitive_keys
        )
        
        if is_sensitive:
            if isinstance(value, str) and value:
                # Show first 4 and last 4 characters for tokens/keys
                if len(value) > 8:
                    sanitized[key] = f"{value[:4]}...{value[-4:]}"
                else:
                    sanitized[key] = "***"
            else:
                sanitized[key] = "***"
        else:
            # Recursively sanitize nested data
            sanitized[key] = sanitize_data(value, sensitive_keys)
    
    return sanitized


def sanitize_list(data: List[Any], sensitive_keys: Tuple[str, ...]) -> List[Any]:
    """
    Sanitize sensitive values in a list.
    
    Args:
        data: List to sanitize
        sensitive_keys: Keys to sanitize
        
    Returns:
        List: Sanitized list
    """
    return [sanitize_data(item, sensitive_keys) for item in data]


def sanitize_string(data: str, sensitive_keys: Tuple[str, ...]) -> str:
    """
    Sanitize sensitive patterns in strings (like URLs with tokens).
    
    Args:
        data: String to sanitize
        sensitive_keys: Patterns to sanitize
        
    Returns:
        str: Sanitized string
    """
    sanitized = data
    
    # Common patterns to sanitize in URLs and strings
    patterns = [
        # Bearer tokens
        (r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer ***'),
        # URL parameters with sensitive names
        (r'([?&](?:token|key|secret|password|jwt)=)[^&\s]+', r'\1***'),
        # JWT tokens (rough pattern)
        (r'eyJ[A-Za-z0-9\-._~+/]+=*\.eyJ[A-Za-z0-9\-._~+/]+=*\.[A-Za-z0-9\-._~+/]+=*', '***JWT***'),
    ]
    
    for pattern, replacement in patterns:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
    
    return sanitized


def format_size(size_bytes: int) -> str:
    """
    Format byte size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        str: Formatted size string
    """
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"


def cleanup_old_logs(log_directory: Path, retention_days: int = 30) -> int:
    """
    Clean up old log files based on retention policy.
    
    Args:
        log_directory: Directory containing log files
        retention_days: Number of days to retain logs
        
    Returns:
        int: Number of files cleaned up
    """
    if not log_directory.exists():
        return 0
    
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    cleaned_count = 0
    
    # Look for rotated log files (trxo.log.1, trxo.log.2, etc.)
    for log_file in log_directory.glob("trxo.log.*"):
        try:
            if log_file.stat().st_mtime < cutoff_date.timestamp():
                log_file.unlink()
                cleaned_count += 1
        except (OSError, ValueError):
            # Skip files we can't process
            continue
    
    return cleaned_count


def get_log_directory() -> Path:
    """
    Get the log directory path (imported from config for convenience).
    
    Returns:
        Path: Log directory path
    """
    from .config import get_log_directory as _get_log_directory
    return _get_log_directory()
