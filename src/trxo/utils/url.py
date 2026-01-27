"""
URL construction utilities.

This module provides common functionality for constructing API URLs,
handling base URL contexts and preventing path duplication.
"""

from urllib.parse import urlparse


def construct_api_url(base_url: str, endpoint: str) -> str:
    """
    Construct API URL handling base URL context and endpoint prefixes.

    If endpoint starts with /am/ and base_url has a path component (context),
    it assumes base_url context replaces the default /am context in endpoint.

    Args:
        base_url: The base URL (e.g. https://host or https://host/am)
        endpoint: The API endpoint (e.g. /am/json/...)

    Returns:
        Full API URL
    """
    base_url = base_url.rstrip("/")
    endpoint = endpoint or ""

    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    # Logic for /am endpoints
    if endpoint.startswith("/am/"):
        parsed = urlparse(base_url)
        # Check if there is a path component (e.g. /custom or /am)
        # We check parsed.path.strip("/") to ignore root path "/"
        if parsed.path and parsed.path.strip("/"):
            # Strip default context (/am) from endpoint
            # endpoint is /am/something...
            endpoint = endpoint[3:]  # Remove /am

    return f"{base_url}{endpoint}"
