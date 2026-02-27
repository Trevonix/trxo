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
from trxo.utils.console import error, success, info
from .settings import get_credential_value, process_regions_value
from .validation import (
    validate_jwk_file,
    store_jwk_in_keyring,
    validate_authentication,
    validate_git_setup,
    validate_onprem_authentication,
    validate_idm_authentication,
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
    sa_id: Optional[str],
    base_url: Optional[str],
    regions: Optional[str],
    storage_mode: str,
    git_username: Optional[str],
    git_repo: Optional[str],
    git_token: Optional[str],
    current_project: str,
) -> Dict:
    """Setup service account authentication configuration"""
    # Collect Base URL
    base_url_value = get_credential_value(
        base_url,
        "base_url",
        existing_config,
        "\nBase URL for PingOne Advanced Identity Cloud instance",
    )
    base_url_value = normalize_base_url(base_url_value, "service-account")

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

    sa_id_value = get_credential_value(
        sa_id, "sa_id", existing_config, "\nService Account ID"
    )

    # Construct token URL from base URL
    token_url = base_url_value.rstrip("/") + TOKEN_ENDPOINT

    # Handle git setup if needed
    if storage_mode == "git":
        git_username_value = get_credential_value(
            git_username, "git_username", existing_config, "\nGit username"
        )
        git_repo_value = get_credential_value(
            git_repo,
            "git_repo",
            existing_config,
            "\nGit Repository URL " "(https://github.com/owner/repo.git)",
        )
        git_token_value = get_credential_value(
            git_token, "git_token", existing_config, "\nPersonal access token"
        )
        validate_git_setup(
            git_username_value, git_repo_value, git_token_value, current_project
        )

    # Test SA authentication
    try:
        auth = ServiceAccountAuth(
            jwk_path_expanded, sa_id_value, token_url, jwk_content=jwk_raw
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
        "base_url": base_url_value,
        "sa_id": sa_id_value,
        "jwk_path": jwk_path_expanded,
        "jwk_keyring": keyring_ok,
        "jwk_fingerprint": jwk_fingerprint,
        "token_url": token_url,
        "regions": process_regions_value(regions),
        "storage_mode": storage_mode,
    }
    if storage_mode == "git":
        config.update(
            {
                "git_username": git_username_value,
                "git_repo": git_repo_value,
            }
        )
    return config


def setup_onprem_auth(
    existing_config: Dict,
    onprem_username: Optional[str],
    onprem_realm: Optional[str],
    base_url: Optional[str],
    storage_mode: str,
    git_username: Optional[str],
    git_repo: Optional[str],
    git_token: Optional[str],
    current_project: str,
    idm_base_url: Optional[str] = None,
    idm_username: Optional[str] = None,
    am_base_url: Optional[str] = None,
) -> Dict:
    """Setup on-premises authentication configuration.

    Collects AM and/or IDM credentials independently.
    """

    products = []
    am_configured = False
    idm_configured = False
    am_base_url_value = None
    effective_idm_url = None

    # ── AM Credentials (optional) ──
    info("\n── AM Configuration ──")
    username_value = get_credential_value(
        onprem_username,
        "onprem_username",
        existing_config,
        "\nOn-Prem AM username (leave empty to skip AM)",
        required=False,
    )

    if username_value:
        am_base_url_value = get_credential_value(
            am_base_url or base_url,
            "am_base_url",
            existing_config,
            "\nBase AM URL (example: http://localhost:8080/am)",
            required=True,
        )
        am_base_url_value = normalize_base_url(am_base_url_value, "onprem")

        realm_value = (
            get_credential_value(
                onprem_realm,
                "onprem_realm",
                existing_config,
                "On-Prem AM realm",
                required=False,
            )
            or "root"
        )

        # Prompt for AM password (not stored)
        password_value = getpass.getpass("\nOn-Prem AM password: ")

        # Test AM authentication
        if validate_onprem_authentication(
            am_base_url_value, realm_value, username_value, password_value
        ):
            am_configured = True
            products.append("am")
        else:
            error("AM authentication failed. Skipping AM configuration.")
    else:
        info("Skipping AM configuration.")
        realm_value = "root"

    # ── IDM Credentials (optional) ──
    info("\n── IDM Configuration ──")
    idm_username_value = get_credential_value(
        idm_username,
        "idm_username",
        existing_config,
        "\nOn-Prem IDM username (leave empty to skip IDM)",
        required=False,
    )

    idm_base_url_value = None
    if idm_username_value:
        idm_base_url_value = get_credential_value(
            idm_base_url,
            "idm_base_url",
            existing_config,
            "\nIDM Base URL (example: http://localhost:8080)",
            required=True,
        )
        effective_idm_url = idm_base_url_value

        # Prompt for IDM password (not stored)
        idm_password_value = getpass.getpass("\nOn-Prem IDM password: ")

        # Test IDM authentication
        if validate_idm_authentication(
            effective_idm_url, idm_username_value, idm_password_value
        ):
            idm_configured = True
            products.append("idm")
        else:
            error("IDM authentication failed. Skipping IDM configuration.")
    else:
        info("Skipping IDM configuration.")

    # At least one product must be configured
    if not am_configured and not idm_configured:
        error(
            "\nAt least one product (AM or IDM) must be configured. "
            "Please provide valid credentials for AM, IDM, or both."
        )
        raise typer.Exit(1)

    # Handle git setup if needed
    if storage_mode == "git":
        git_username_value = get_credential_value(
            git_username, "git_username", existing_config, "\nGit username"
        )
        git_repo_value = get_credential_value(
            git_repo,
            "git_repo",
            existing_config,
            "\nGit Repository URL " "(https://github.com/owner/repo.git)",
        )
        git_token_value = get_credential_value(
            git_token, "git_token", existing_config, "\nPersonal access token"
        )

        validate_git_setup(
            git_username_value, git_repo_value, git_token_value, current_project
        )

    # Build configuration
    config = {
        "auth_mode": "onprem",
        "am_base_url": am_base_url_value if am_configured else None,
        "idm_base_url": effective_idm_url if idm_configured else None,
        # Keep base_url as primary for the project (prefer AM, fallback to IDM)
        "base_url": am_base_url_value or effective_idm_url,
        "onprem_products": products,
        "storage_mode": storage_mode,
    }

    if am_configured:
        config["onprem_username"] = username_value
        config["onprem_realm"] = realm_value

    if idm_configured:
        config["idm_username"] = idm_username_value

    if storage_mode == "git":
        config.update(
            {
                "git_username": git_username_value,
                "git_repo": git_repo_value,
            }
        )

    return config
