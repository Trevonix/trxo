"""
Authentication helper for rollback operations.

Builds the correct auth headers for AM and IDM endpoints
based on the current authentication mode.
"""

from typing import Dict, Optional

from trxo_lib.config.api_headers import get_headers


class RollbackAuthHelper:
    """Builds authentication headers for rollback API calls."""

    def __init__(
        self,
        command_name: str,
        auth_mode: str = "service-account",
        idm_username: Optional[str] = None,
        idm_password: Optional[str] = None,
    ):
        self.command_name = command_name
        self.auth_mode = auth_mode
        self._idm_username = idm_username
        self._idm_password = idm_password

    def build_auth_headers(self, token: str, url: str) -> Dict[str, str]:
        """Build authentication headers for the given URL.

        IDM endpoints use username/password or Bearer token.
        AM endpoints use Bearer token or Cookie-based auth.
        """
        if "/openidm/" in url:
            if self._idm_username and self._idm_password:
                headers = get_headers(self.command_name)
                return {
                    "X-OpenIDM-Username": self._idm_username,
                    "X-OpenIDM-Password": self._idm_password,
                    "Accept-API-Version": headers.get(
                        "Accept-API-Version", "protocol=2.1,resource=1.0"
                    ),
                }
            # AIC/SaaS mode for IDM requires Bearer token
            return {"Authorization": f"Bearer {token}"}

        # For AM endpoints: service account (cloud) uses Bearer token,
        # on-premise uses Cookie-based auth
        if self.auth_mode == "service-account":
            return {"Authorization": f"Bearer {token}"}

        return {"Cookie": f"iPlanetDirectoryPro={token}"}
