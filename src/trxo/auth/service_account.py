import json
import time
import uuid
from typing import Dict
import jwt
from jwcrypto import jwk
import httpx
from trxo.logging import get_logger


class ServiceAccountAuth:
    def __init__(
        self,
        jwk_path: str,
        sa_id: str,
        token_url: str,
        *,
        jwk_content: str | None = None,
    ) -> None:
        self.jwk_path = jwk_path
        self.jwk_content = jwk_content
        self.sa_id = sa_id
        self.token_url = token_url
        self.logger = get_logger("trxo.auth.service_account")

    def get_private_key(self) -> bytes:
        """Load JWK and convert to PEM format"""
        if self.jwk_content:
            jwk_data = json.loads(self.jwk_content)
        else:
            with open(self.jwk_path, "r", encoding="utf-8") as f:
                jwk_data = json.load(f)

        key = jwk.JWK(**jwk_data)
        return key.export_to_pem(private_key=True, password=None)

    def create_jwt(self) -> str:
        """Create signed JWT for authentication"""
        now = int(time.time())
        jwt_payload = {
            "iss": self.sa_id,
            "sub": self.sa_id,
            "aud": self.token_url,
            "exp": now + 899,
            "jti": str(uuid.uuid4()),
        }

        private_key_pem = self.get_private_key()
        return jwt.encode(jwt_payload, private_key_pem, algorithm="RS256")

    def get_access_token(self) -> Dict:
        """Get access token using JWT assertion"""
        self.logger.debug(f"Creating JWT assertion for service account {self.sa_id}")
        signed_jwt = self.create_jwt()

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "client_id": "service-account",
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": signed_jwt,
            "scope": ("fr:am:* " "fr:idm:* " "fr:idc:esv:* "),
        }

        self.logger.debug(f"Requesting access token from {self.token_url}")
        try:
            with httpx.Client() as client:
                response = client.post(self.token_url, headers=headers, data=data)
                response.raise_for_status()
                token_data = response.json()
                self.logger.info(
                    "Successfully obtained access token "
                    f"for service account {self.sa_id}"
                )
                return token_data
        except Exception as e:
            error_msg = (
                f"Failed to get access token for service account {self.sa_id}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise Exception(error_msg)
