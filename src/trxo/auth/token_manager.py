import time
from trxo.auth.service_account import ServiceAccountAuth
from trxo.utils.config_store import ConfigStore
from trxo.utils.console import error
from trxo.logging import get_logger, setup_logging
from trxo.constants import TOKEN_EXPIRY_BUFFER, DEFAULT_TOKEN_EXPIRES_IN


class TokenManager:
    def __init__(self, config_store: ConfigStore):
        self.config_store = config_store
        setup_logging()
        self.logger = get_logger("trxo.auth.token_manager")

    def get_token(self, project_name: str) -> str:
        """Get a valid access token asynchronously, refreshing if necessary"""
        self.logger.debug(f"Requesting token for project: {project_name}")

        # Check if we have a valid token
        token_data = self.config_store.get_token(project_name)
        current_time = int(time.time())

        if (
            token_data
            and current_time < token_data.get("expires_at", 0) - TOKEN_EXPIRY_BUFFER
        ):  # Buffer time
            expires_in = token_data.get("expires_at", 0) - current_time
            self.logger.debug(f"Using cached token for {project_name}, expires in {expires_in}s")
            return token_data["access_token"]

        # Need to get a new token
        self.logger.info(f"Refreshing token for project: {project_name}")
        config = self.config_store.get_project_config(project_name)
        if not config:
            self.logger.error(f"No configuration found for project '{project_name}'")
            error(f"No configuration found for project '{project_name}'")
            raise ValueError(f"Project '{project_name}' not configured")

        has_core = all(key in config for key in ["client_id", "sa_id", "token_url"])
        has_jwk = ("jwk" in config) or ("jwk_path" in config)
        if not (has_core and has_jwk):
            self.logger.error(f"Missing authentication configuration for project {project_name}")
            error(
                "Missing authentication configuration. "
                "Run 'trxo config setup' first."
            )
            raise ValueError("Missing authentication configuration")

        try:
            # Prefer JWK from keyring; if absent, fall back to file path content
            jwk_content = None
            try:
                import keyring
                jwk_content = keyring.get_password(f"trxo:{project_name}:jwk", "jwk")
                if jwk_content:
                    self.logger.debug(f"Using JWK from keyring for project {project_name}")
                else:
                    self.logger.debug(f"No JWK found in keyring for project {project_name}, using file path")
            except Exception as e:
                self.logger.debug(f"Keyring access failed for project {project_name}: {str(e)}")
                jwk_content = None

            auth = ServiceAccountAuth(
                jwk_path=config.get("jwk_path", ""),
                client_id=config["client_id"],
                sa_id=config["sa_id"],
                token_url=config["token_url"],
                jwk_content=jwk_content,
            )

            self.logger.debug(f"Requesting new access token from {config['token_url']}")
            token_response = auth.get_access_token()
            expires_in = token_response.get("expires_in", DEFAULT_TOKEN_EXPIRES_IN)
            expires_at = current_time + expires_in

            # Save token with expiry info
            token_data = {
                "access_token": token_response["access_token"],
                "expires_in": expires_in,
                "expires_at": expires_at,
                "created_at": current_time,
            }

            self.config_store.save_token(project_name, token_data)
            self.logger.info(f"Successfully refreshed token for project {project_name}, expires in {expires_in}s")

            return token_data["access_token"]

        except Exception as e:
            self.logger.error(f"Failed to get access token for project {project_name}: {str(e)}")
            error(f"Failed to get access token: {str(e)}")
            raise
