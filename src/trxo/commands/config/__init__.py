"""
Configuration management module.

This module provides structured configuration management functionality
split into logical components:

- config_manager: Primary typer commands for configuration management
- settings: User settings and credential management
- validation: Configuration and authentication validation
- auth_handler: Authentication setup and handling

Usage:
    from trxo.commands.config import app
    # or
    from trxo.commands.config.config_manager import app
"""

# Import the main typer app from config_manager.py
from .config_manager import app

# Import commonly used functions for external access
from .settings import get_credential_value, display_config
from .validation import validate_authentication, validate_jwk_file, validate_git_setup
from .auth_handler import setup_service_account_auth, setup_onprem_auth, normalize_base_url

# Define what gets exported when using "from config import *"
__all__ = [
    'app',  # Main typer application
    'get_credential_value',
    'display_config',
    'validate_authentication',
    'validate_jwk_file',
    'validate_git_setup',
    'setup_service_account_auth',
    'setup_onprem_auth',
    'normalize_base_url'
]
