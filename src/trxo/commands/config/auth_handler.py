"""
Authentication setup and handling.

This module handles the setup of different authentication modes
including service account and on-premises authentication.
"""

import os
import getpass
from typing import Dict, Optional
from urllib.parse import urlparse
import typer
from trxo.auth.service_account import ServiceAccountAuth
from trxo.utils.console import error, success
from .settings import get_credential_value, process_regions_value
from .validation import (
    validate_jwk_file,
    store_jwk_in_keyring,
    validate_authentication,
    validate_git_setup,
    validate_onprem_authentication
)

# Token endpoint to get access token
TOKEN_ENDPOINT = "/am/oauth2/access_token"


def normalize_base_url(base_url: str, auth_mode: str) -> str:
    """Normalize base URL based on authentication mode"""
    if not base_url:
        return base_url
    base_url = base_url.rstrip("/")
    if auth_mode == "service-account":
        # If user enters https://host/am, strip /am to keep base
        # (SA usually expects root base + /am endpoint)
        if base_url.endswith("/am"):
            base_url = base_url[:-3]
    elif auth_mode == "onprem":
        # For on-prem, if no context is provided (e.g. https://host), default to /am
        # If context is provided (e.g. https://host/custom), keep it.
        parsed = urlparse(base_url)
        if not parsed.path or parsed.path == "/":
            base_url = f"{base_url}/am"
    return base_url


def setup_service_account_auth(
    existing_config: Dict,
    jwk_path: Optional[str],
    client_id: Optional[str],
    sa_id: Optional[str],
    base_url: str,
    regions: Optional[str],
    storage_mode: str,
    git_username: Optional[str],
    git_repo: Optional[str],
    git_token: Optional[str],
    current_project: str
) -> Dict:
    """Setup service account authentication configuration"""
    # Collect SA-only inputs
    jwk_path_value = get_credential_value(
        jwk_path, "jwk_path", existing_config, "\nJWK private key file path"
    )

    # Validate JWK and get content
    jwk_raw, jwk_fingerprint, keyring_available = validate_jwk_file(jwk_path_value)
    jwk_path_expanded = (
        jwk_path_value
        if jwk_path_value.startswith("/")
        else os.path.expanduser(jwk_path_value)
    )
    # Store JWK in keyring if available
    keyring_ok = False
    if keyring_available:
        keyring_ok = store_jwk_in_keyring(current_project, jwk_raw)

    client_id_value = get_credential_value(
        client_id, "client_id", existing_config, "\nClient ID"
    )

    sa_id_value = get_credential_value(
        sa_id, "sa_id", existing_config, "\nService Account ID"
    )

    # Construct token URL from base URL
    token_url = base_url.rstrip("/") + TOKEN_ENDPOINT

    # Handle git setup if needed
    if storage_mode == "git":
        git_username_value = get_credential_value(
            git_username, "git_username", existing_config, "\nGit username"
        )
        git_repo_value = get_credential_value(
            git_repo, "git_repo", existing_config, "\nGit Repository URL "
            "(https://github.com/owner/repo.git)"
        )
        git_token_value = get_credential_value(
            git_token, "git_token", existing_config, "\nPersonal access token"
        )
        validate_git_setup(git_username_value, git_repo_value, git_token_value, current_project)

    # Test SA authentication
    try:
        auth = ServiceAccountAuth(
            jwk_path_expanded, client_id_value, sa_id_value, token_url, jwk_content=jwk_raw
        )
        if validate_authentication(auth):
            success("\nAuthentication successful!")
        else:
            error("\nAuthentication failed")
            raise typer.Exit(1)
    except Exception as e:
        error(f"Authentication failed: {str(e)}")
        raise typer.Exit(1)

    # Build configuration
    config = {
        "auth_mode": "service-account",
        "base_url": base_url,
        "sa_id": sa_id_value,
        "jwk_path": jwk_path_expanded,
        "jwk_keyring": keyring_ok,
        "jwk_fingerprint": jwk_fingerprint,
        "client_id": client_id_value,
        "token_url": token_url,
        "regions": process_regions_value(regions),
        "storage_mode": storage_mode,
    }
    if storage_mode == "git":
        config.update({
            "git_username": git_username_value,
            "git_repo": git_repo_value,
        })
    return config


def setup_onprem_auth(
    existing_config: Dict,
    onprem_username: Optional[str],
    onprem_realm: Optional[str],
    base_url: str,
    storage_mode: str,
    git_username: Optional[str],
    git_repo: Optional[str],
    git_token: Optional[str],
    current_project: str
) -> Dict:
    """Setup on-premises authentication configuration"""

    username_value = get_credential_value(
        onprem_username, "onprem_username", existing_config, "\nOn-Prem username"
    )
    realm_value = get_credential_value(
        onprem_realm, "onprem_realm", existing_config, "On-Prem realm", required=False
    ) or "root"

    # Prompt for password (not stored)
    password_value = getpass.getpass("\nOn-Prem password: ")

    # Handle git setup if needed
    if storage_mode == "git":
        git_username_value = get_credential_value(
            git_username, "git_username", existing_config, "\nGit username"
        )
        git_repo_value = get_credential_value(
            git_repo, "git_repo", existing_config, "\nGit Repository URL "
            "(https://github.com/owner/repo.git)"
        )
        git_token_value = get_credential_value(
            git_token, "git_token", existing_config, "\nPersonal access token"
        )

        validate_git_setup(git_username_value, git_repo_value, git_token_value, current_project)

    # Test On-Prem authentication
    if not validate_onprem_authentication(base_url, realm_value, username_value, password_value):
        raise typer.Exit(1)

    # Build configuration
    config = {
        "auth_mode": "onprem",
        "base_url": base_url,
        "onprem_username": username_value,
        "onprem_realm": realm_value,
        "storage_mode": storage_mode,
    }

    if storage_mode == "git":
        config.update({
            "git_username": git_username_value,
            "git_repo": git_repo_value,
        })

    return config
