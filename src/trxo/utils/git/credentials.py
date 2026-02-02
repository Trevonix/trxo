"""
Git credentials management and validation.
"""

import httpx
from trxo.logging import get_logger

logger = get_logger("trxo.utils.git.credentials")


def build_secure_url(repo_url: str, username: str, token: str) -> str:
    """Build secure HTTPS URL with credentials"""
    if repo_url.startswith("https://"):
        return repo_url.replace("https://", f"https://{username}:{token}@")
    return repo_url


def validate_credentials(token: str, repo_url: str) -> dict:
    """
    Validate GitHub credentials and repository access.

    Args:
        token: Git token
        repo_url: Repository URL

    Returns:
        dict: Repository information from GitHub API

    Raises:
        ValueError: If URL is unsupported
        RuntimeError: If network error or unexpected response
        PermissionError: If access denied
    """
    # Extract API path
    if "github.com/" not in repo_url:
        raise ValueError(
            "Unsupported repo URL. Use https://github.com/owner/repo(.git)"
        )

    api_repo_path = repo_url.split("github.com/")[1].rstrip("/").replace(".git", "")
    api_url = f"https://api.github.com/repos/{api_repo_path}"
    headers = {"Authorization": f"token {token}"}

    try:
        with httpx.Client() as client:
            resp = client.get(api_url, headers=headers, timeout=15)
    except httpx.RequestError as e:
        raise RuntimeError(f"Network error during validation: {e}")

    if resp.status_code == 404:
        raise PermissionError(
            "Repository not found or token does not grant access (404)."
        )
    if resp.status_code == 401:
        raise PermissionError("Invalid or expired token (401).")
    if resp.status_code != 200:
        raise RuntimeError(f"Unexpected GitHub API response: {resp.status_code}")

    repo_json = resp.json()
    perms = repo_json.get("permissions", {}) or {}
    if not perms.get("push", False):
        raise PermissionError(
            "Token does not have push/write permission to this repository."
        )

    logger.info("Repository access & write permissions validated")
    return repo_json
