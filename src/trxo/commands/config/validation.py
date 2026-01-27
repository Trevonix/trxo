"""
Configuration and authentication validation.

This module handles validation of authentication credentials, JWK files,
and git setup.
"""

import os
import json
import hashlib
from typing import Tuple, Optional
import typer
from trxo.auth.service_account import ServiceAccountAuth
from trxo.auth.on_premise import OnPremAuth
from trxo.utils.console import error, success, info
from trxo.utils.git_manager import validate_and_setup_git_repo
from trxo.utils.config_store import ConfigStore


def validate_authentication(auth: ServiceAccountAuth) -> bool:
    """Validate service account authentication by token retrieval"""
    try:
        auth.get_access_token()
        return True
    except Exception:
        return False


def validate_jwk_file(jwk_path: str) -> Tuple[str, Optional[str], bool]:
    """
    Validate JWK file and extract metadata.
    
    Returns:
        Tuple of (jwk_content, jwk_fingerprint, keyring_success)
    """
    jwk_path_expanded = os.path.expanduser(jwk_path)
    if not os.path.exists(jwk_path_expanded):
        error(f"JWK file not found at {jwk_path_expanded}")
        raise typer.Exit(1)
    
    try:
        with open(jwk_path_expanded, "r", encoding="utf-8") as f:
            jwk_raw = f.read()
    except Exception as e:
        error(f"Failed to read JWK file: {e}")
        raise typer.Exit(1)

    # Derive fingerprint
    jwk_fingerprint = None
    try:
        jwk_obj = json.loads(jwk_raw)
        normalized = json.dumps(jwk_obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
        jwk_fingerprint = "sha256:" + hashlib.sha256(normalized).hexdigest()
    except Exception:
        pass

    # Store in keyring (best effort)
    keyring_ok = False
    try:
        import keyring
        # We'll get the current project from the caller
        # For now, we'll return the keyring status and let the caller handle storage
        keyring_ok = True
    except Exception:
        keyring_ok = False

    return jwk_raw, jwk_fingerprint, keyring_ok


def store_jwk_in_keyring(project_name: str, jwk_content: str) -> bool:
    """Store JWK content in keyring for secure storage"""
    try:
        import keyring
        keyring.set_password(f"trxo:{project_name}:jwk", "jwk", jwk_content)
        return True
    except Exception:
        return False


def validate_git_setup(git_username: str, git_repo: str, git_token: str, current_project: str) -> None:
    """Validate git credentials and setup repository"""
    try:
        validate_and_setup_git_repo(git_username, git_token, git_repo)
        config_store = ConfigStore()
        config_store.store_git_credentials(current_project, git_username, git_repo, git_token)
    except Exception as e:
        error(f"Git credentials validation failed: {str(e)}")
        raise typer.Exit(1)


def validate_onprem_authentication(base_url: str, realm: str, username: str, password: str) -> bool:
    """Validate on-premises authentication"""
    try:
        info("\nValidating On-Prem authentication (password will NOT be stored)")
        client = OnPremAuth(base_url=base_url, realm=realm)
        data = client.authenticate(username=username, password=password)
        if data.get("tokenId"):
            success("On-Prem authentication successful!")
            return True
        else:
            error("On-Prem authentication failed")
            return False
    except Exception as e:
        error(f"On-Prem authentication failed: {str(e)}")
        return False
