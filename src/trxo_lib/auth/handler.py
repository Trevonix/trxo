"""
Authentication handling and configuration generation core logic.

This module provides pure logical functions for parsing, structuring
and generating config blocks for different authentication strategies.
No Typer/CLI interactive features occur here.
"""

from typing import Dict, List, Optional
from urllib.parse import urlparse

TOKEN_ENDPOINT = "/am/oauth2/access_token"


def normalize_base_url(base_url: str, auth_mode: str) -> str:
    """Normalize base URL based on authentication mode"""
    if not base_url:
        return base_url
    base_url = base_url.rstrip("/")
    if auth_mode == "service-account":
        if base_url.endswith("/am"):
            base_url = base_url[:-3]
    elif auth_mode == "onprem":
        parsed = urlparse(base_url)
        if not parsed.path or parsed.path == "/":
            base_url = f"{base_url}/am"
    return base_url


def create_service_account_config(
    base_url: str,
    sa_id: str,
    jwk_path_expanded: str,
    jwk_fingerprint: str,
    keyring_ok: bool,
    regions: Optional[Dict] = None,
    storage_mode: str = "local",
    git_username: Optional[str] = None,
    git_repo: Optional[str] = None,
) -> Dict:
    """Build configuration dict for service account."""
    token_url = base_url.rstrip("/") + TOKEN_ENDPOINT
    config = {
        "auth_mode": "service-account",
        "base_url": base_url,
        "sa_id": sa_id,
        "jwk_path": jwk_path_expanded,
        "jwk_keyring": keyring_ok,
        "jwk_fingerprint": jwk_fingerprint,
        "token_url": token_url,
        "regions": regions,
        "storage_mode": storage_mode,
        "am_base_url": None,
        "idm_base_url": None,
        "onprem_username": None,
        "onprem_realm": None,
        "onprem_products": None,
        "idm_username": None,
    }

    if storage_mode == "git":
        config.update(
            {
                "git_username": git_username,
                "git_repo": git_repo,
            }
        )

    return config


def create_onprem_config(
    products: List[str],
    storage_mode: str = "local",
    am_base_url: Optional[str] = None,
    onprem_username: Optional[str] = None,
    onprem_realm: Optional[str] = None,
    idm_base_url: Optional[str] = None,
    idm_username: Optional[str] = None,
    git_username: Optional[str] = None,
    git_repo: Optional[str] = None,
) -> Dict:
    """Build configuration dict for on-premise authentication."""
    config = {
        "auth_mode": "onprem",
        "am_base_url": am_base_url,
        "idm_base_url": idm_base_url,
        "base_url": None,
        "onprem_products": products,
        "storage_mode": storage_mode,
        "sa_id": None,
        "jwk_path": None,
        "jwk_keyring": None,
        "jwk_fingerprint": None,
        "token_url": None,
    }

    if "am" in products:
        config["onprem_username"] = onprem_username
        config["onprem_realm"] = onprem_realm

    if "idm" in products:
        config["idm_username"] = idm_username

    if storage_mode == "git":
        config.update(
            {
                "git_username": git_username,
                "git_repo": git_repo,
            }
        )

    return config
