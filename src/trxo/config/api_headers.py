"""
Central configuration for API HTTP headers used across the application.
"""

from typing import Dict

BASE_HEADERS = {
    "Content-Type": "application/json",
}

# The dictionary maps API component configurations (like "journeys", "saml")
# to their required HTTP Headers.
API_HEADERS = {
    # Default fallback
    "default": {
        **BASE_HEADERS,
        "Accept-API-Version": "resource=1.0",
    },
    # ----------------------------------------------------
    # Export and Import Command Component Mappings
    # ----------------------------------------------------
    "agents": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.1,resource=1.0",
    },
    "am_scripts": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.1,resource=1.0",
    },
    "applications": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.1,resource=1.0",
    },
    "authn": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.0,resource=1.0",
    },
    "circle_of_trust": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.0,resource=1.0",
    },
    "connectors": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.1,resource=1.0",
    },
    "email_templates": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.1,resource=1.0",
    },
    "endpoints": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.1,resource=1.0",
    },
    "esv": {
        **BASE_HEADERS,
        "Accept-API-Version": "resource=2.0",
        # NOTE: some ESV calls use resource=1.0 but standard is 2.0. Handled via specific helper if needed.
    },
    "journeys": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.1,resource=1.0",
    },
    "managed": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.1,resource=1.0",
        # Note: Managed creates (POST) sometimes need resource=2.0 or 1.0 depending on exact endpoint
    },
    "mappings": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.1,resource=1.0",
    },
    "oauth": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.0,resource=1.0",
    },
    "policies": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.1,resource=1.0",
    },
    "privileges": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.1,resource=1.0",
    },
    "realms": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.1,resource=1.0",
    },
    "saml": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.1,resource=1.0",
    },
    "saml_metadata": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.1,resource=1.0",
    },
    "saml_metadata_check": {
        "Accept-API-Version": "protocol=2.1,resource=1.0",
    },
    "scripts": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=1.0,resource=1.0",
    },
    "services": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=1.0,resource=1.0",
    },
    "services_delete": {
        "Accept-API-Version": "resource=1.0",
    },
    "themes": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.1,resource=1.0",
    },
    "webhooks": {
        **BASE_HEADERS,
        "Accept-API-Version": "protocol=2.0,resource=1.0",
    },
}


def get_headers(config_name: str = "default") -> Dict[str, str]:
    """Retrieve the standard HTTP headers for a given configuration/component."""
    return API_HEADERS.get(config_name, API_HEADERS["default"]).copy()
