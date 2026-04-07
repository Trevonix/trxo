"""
Authentication setup and handling.

This module handles the setup of different authentication modes
including service account and on-premises authentication.
"""

import getpass
import os
from typing import Dict, Optional

import typer

from trxo_lib.auth.service_account import ServiceAccountAuth
from trxo.utils.console import error, info, success
from trxo_lib.auth.handler import (
    normalize_base_url,
    create_service_account_config,
    create_onprem_config,
    TOKEN_ENDPOINT,
)

from .settings import get_credential_value, process_regions_value
from .validation import (
    store_jwk_in_keyring,
    validate_authentication,
    validate_git_setup,
    validate_idm_authentication,
    validate_jwk_file,
    validate_onprem_authentication,
)

# normalize_base_url and TOKEN_ENDPOINT are imported from trxo_lib.auth.handler


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
    force_prompt: bool = False,
) -> Dict:
    """Setup service account authentication configuration"""
    # Collect Base URL
    base_url_value = get_credential_value(
        base_url,
        "base_url",
        existing_config,
        "\nBase URL (example: https://alpha.id.pingidentity.com)",
        force_prompt=force_prompt,
    )
    base_url_value = normalize_base_url(base_url_value, "service-account")

    # Collect SA-only inputs
    jwk_path_value = get_credential_value(
        jwk_path,
        "jwk_path",
        existing_config,
        "\nJWK private key file path",
        force_prompt=force_prompt,
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
        sa_id,
        "sa_id",
        existing_config,
        "\nService Account ID",
        force_prompt=force_prompt,
    )

    # Construct token URL from base URL
    token_url = base_url_value.rstrip("/") + TOKEN_ENDPOINT

    # Handle git setup if needed
    if storage_mode == "git":
        git_username_value = get_credential_value(
            git_username,
            "git_username",
            existing_config,
            "\nGit username",
            force_prompt=force_prompt,
        )
        git_repo_value = get_credential_value(
            git_repo,
            "git_repo",
            existing_config,
            "\nGit Repository URL (https://github.com/owner/repo.git)",
            force_prompt=force_prompt,
        )
        git_token_value = get_credential_value(
            git_token,
            "git_token",
            existing_config,
            "\nPersonal access token",
            force_prompt=force_prompt,
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
            success("Authentication successful!")
        else:
            error("Authentication failed")
            raise typer.Exit(1)
    except Exception as e:
        error(f"Authentication failed: {str(e)}")
        raise typer.Exit(1)

    # Build configuration using library generator
    config = create_service_account_config(
        base_url=base_url_value,
        sa_id=sa_id_value,
        jwk_path_expanded=jwk_path_expanded,
        jwk_fingerprint=jwk_fingerprint,
        keyring_ok=keyring_ok,
        regions=process_regions_value(regions),
        storage_mode=storage_mode,
        git_username=git_username_value if storage_mode == "git" else None,
        git_repo=git_repo_value if storage_mode == "git" else None,
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
    force_prompt: bool = False,
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
        force_prompt=force_prompt,
    )

    if username_value:
        am_base_url_value = get_credential_value(
            am_base_url or base_url,
            "am_base_url",
            existing_config,
            "\nBase AM URL (example: http://localhost:8080/am)",
            required=True,
            force_prompt=force_prompt,
        )
        am_base_url_value = normalize_base_url(am_base_url_value, "onprem")

        realm_value = (
            get_credential_value(
                onprem_realm,
                "onprem_realm",
                existing_config,
                "\nOn-Prem AM realm",
                required=False,
                force_prompt=force_prompt,
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
        force_prompt=force_prompt,
    )

    idm_base_url_value = None
    if idm_username_value:
        idm_base_url_value = get_credential_value(
            idm_base_url,
            "idm_base_url",
            existing_config,
            "\nIDM Base URL (example: http://localhost:8080)",
            required=True,
            force_prompt=force_prompt,
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
            git_username,
            "git_username",
            existing_config,
            "\nGit username",
            force_prompt=force_prompt,
        )
        git_repo_value = get_credential_value(
            git_repo,
            "git_repo",
            existing_config,
            "\nGit Repository URL (https://github.com/owner/repo.git)",
            force_prompt=force_prompt,
        )
        git_token_value = get_credential_value(
            git_token,
            "git_token",
            existing_config,
            "\nPersonal access token",
            force_prompt=force_prompt,
        )

        validate_git_setup(
            git_username_value, git_repo_value, git_token_value, current_project
        )

    # Build configuration using library generator
    config = create_onprem_config(
        products=products,
        storage_mode=storage_mode,
        am_base_url=am_base_url_value if am_configured else None,
        onprem_username=username_value if am_configured else None,
        onprem_realm=realm_value if am_configured else None,
        idm_base_url=effective_idm_url if idm_configured else None,
        idm_username=idm_username_value if idm_configured else None,
        git_username=git_username_value if storage_mode == "git" else None,
        git_repo=git_repo_value if storage_mode == "git" else None,
    )
    return config
