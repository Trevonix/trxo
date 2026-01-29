"""
On-prem (AM) authentication helper.

Provides a simple way to obtain an AM session token (iPlanetDirectoryPro)
by calling the JSON authentication endpoint. This token is NOT persisted.
"""

from typing import Dict
import httpx
from trxo.logging import get_logger, setup_logging


class OnPremAuth:
    def __init__(self, base_url: str, realm: str = "root"):
        self.base_url = base_url.rstrip("/")
        self.realm = realm.strip("/") or "root"
        setup_logging()
        self.logger = get_logger("trxo.auth.on_premise")

    @property
    def auth_url(self) -> str:
        from trxo.utils.url import construct_api_url
        endpoint = f"/am/json/realms/{self.realm}/authenticate"
        return construct_api_url(self.base_url, endpoint)

    def authenticate(self, username: str, password: str) -> Dict[str, str]:
        self.logger.debug(f"Authenticating user {username} against realm {self.realm}")
        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "resource=2.0, protocol=1.0",
            "X-OpenAM-Username": username,
            "X-OpenAM-Password": password,
        }
        try:
            self.logger.debug(f"Sending authentication request to {self.auth_url}")
            with httpx.Client() as client:
                resp = client.post(self.auth_url, headers=headers, json={})
                resp.raise_for_status()
                data = resp.json()
                token_id = data.get("tokenId")
                if not token_id:
                    self.logger.error("No tokenId returned from AM authenticate "
                                      f"endpoint for user {username}")
                    raise ValueError("No tokenId returned from AM authenticate endpoint")

                self.logger.info("Successfully authenticated user"
                                 f" {username} in realm {self.realm}")
                return {
                    "tokenId": token_id,
                    "successUrl": data.get("successUrl", ""),
                    "realm": data.get("realm", "/"),
                }
        except Exception as e:
            self.logger.error(f"OnPrem authentication failed for user {username}: {str(e)}")
            raise Exception(f"OnPrem authentication failed: {e}")
