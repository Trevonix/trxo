"""
Global constants for the TRXO CLI.
"""

# Default realm name
DEFAULT_REALM = "alpha"

# Authentication constants
TOKEN_EXPIRY_BUFFER = 60  # Buffer time in seconds before token expiry
DEFAULT_TOKEN_EXPIRES_IN = (
    899  # Default expiration time in seconds if not provided by server
)

# API constants
DEFAULT_PAGE_SIZE = 200

# Script ignore lists
IGNORED_SCRIPT_NAMES = {
    "PingOne Advanced Identity Cloud Internal: OIDC Claims Script",
    (
        "PingOne Advanced Identity Cloud Internal: OAuth2 "
        "Access Token Modification Script"
    ),
}
IGNORED_SCRIPT_IDS = {
    "1f389a3d-21cf-417c-a6d3-42ea620071f0",
    "c234ba0b-58a1-4cfd-9567-09edde980745",
}

# HTTP Headers
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Accept-API-Version": "resource=1.0",
}

# Logging constants
LOG_APP_NAME = "TRXO"
LOG_FILE_NAME = "trxo"
LOG_RETENTION_DAYS = 7
LOG_LINES_TO_SHOW = 20

# Sensitive data keys for sanitization
SENSITIVE_KEYS = (
    "password", "token", "access_token", "refresh_token", "jwk", "key", "secret",
    "client_secret", "private_key", "authorization", "x-api-key", "api_key",
    "bearer", "oauth", "session", "cookie", "csrf", "xsrf"
)
