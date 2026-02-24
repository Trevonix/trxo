"""
Authentication and project management utilities.

This module provides common authentication and project management
functionality used by both import and export commands.
"""

import uuid
from typing import Optional
import typer
from trxo.utils.config_store import ConfigStore
from trxo.auth.token_manager import TokenManager
from trxo.utils.console import console, success, error, info, warning
from trxo.auth.on_premise import OnPremAuth


class AuthManager:
    """Handles authentication and project management for commands"""

    def __init__(self, config_store: ConfigStore, token_manager: TokenManager):
        self.config_store = config_store
        self.token_manager = token_manager
        self._temp_project = None
        self._original_project = None

    def validate_project(
        self,
        jwk_path: Optional[str] = None,
        sa_id: Optional[str] = None,
        base_url: Optional[str] = None,
        project_name: Optional[str] = None,
        auth_mode: Optional[str] = None,
        onprem_username: Optional[str] = None,
        onprem_password: Optional[str] = None,
        onprem_realm: Optional[str] = None,
        idm_base_url: Optional[str] = None,
        idm_username: Optional[str] = None,
        idm_password: Optional[str] = None,
    ) -> str:
        """Validate that a project is active or initialize argument mode"""
        current_project = self.config_store.get_current_project()

        # Check if we're in argument mode (all credentials provided)
        sa_arg_mode = all([jwk_path, sa_id, base_url])
        onprem_arg_mode = (
            (auth_mode or "").lower() == "onprem"
            and base_url
            and (
                (onprem_username and onprem_password) or (idm_username and idm_password)
            )
        )
        argument_mode = sa_arg_mode or onprem_arg_mode

        if not current_project and not argument_mode:
            error("No active project found!")
            console.print()
            info("📋 You have two options:")
            info("   1️⃣  Create and configure a project:")
            info("      • trxo project create <project-name>")
            info("      • trxo project switch <project-name>")
            info("      • trxo config setup")
            console.print()
            info("   2️⃣  Use pipeline mode with all credentials:")
            info("      • --jwk-path <path-to-jwk-file>")
            info("      • --sa-id <your-service-account-id>")
            info("      • --base-url <your-ping-aic-url>")
            console.print()
            raise typer.Exit(1)

        if argument_mode:
            # argument mode: create temporary project configuration
            info("Running in argument mode with provided credentials...")
            if onprem_arg_mode:
                return self._initialize_argument_mode_onprem(
                    base_url=base_url,
                    username=onprem_username,
                    realm=onprem_realm,
                    project_name=project_name,
                    idm_base_url=idm_base_url,
                    idm_username=idm_username,
                )
            return self._initialize_argument_mode(
                jwk_path, sa_id, base_url, project_name
            )
        else:
            return current_project

    def _initialize_argument_mode(self, jwk_path, sa_id, base_url, project_name=None):
        """Initialize in argument mode with provided credentials"""
        # Create temporary project name for this session
        if project_name:
            temp_project_name = f"temp_{project_name}"
        else:
            temp_project_name = f"temp_{uuid.uuid4().hex[:8]}"

        # Store for cleanup
        self._temp_project = temp_project_name
        self._original_project = self.config_store.get_current_project()

        # Generate token URL from base URL
        token_url = f"{base_url}/am/oauth2/access_token"

        # Create temporary configuration
        temp_config = {
            "jwk_path": jwk_path,
            "sa_id": sa_id,
            "base_url": base_url,
            "token_url": token_url,
            "description": "Temporary project configuration",
        }

        # Save temporary project configuration
        self.config_store.save_project(temp_project_name, temp_config)

        # Store JWK content in keyring for argument mode too (best effort)
        try:
            import os
            import keyring

            jwk_path_expanded = os.path.expanduser(jwk_path)
            with open(jwk_path_expanded, "r", encoding="utf-8") as f:
                jwk_raw = f.read()
            keyring.set_password(f"trxo:{temp_project_name}:jwk", "jwk", jwk_raw)
        except Exception:
            pass

    def _initialize_argument_mode_onprem(
        self,
        base_url: str,
        username: Optional[str] = None,
        realm: Optional[str] = None,
        project_name: Optional[str] = None,
        idm_base_url: Optional[str] = None,
        idm_username: Optional[str] = None,
    ) -> str:
        """Initialize in argument mode for on-prem with provided credentials "
        "(no password stored)."""
        # Create temporary project name for this session
        temp_project_name = (
            f"temp_{project_name}" if project_name else f"temp_{uuid.uuid4().hex[:8]}"
        )

        self._temp_project = temp_project_name
        self._original_project = self.config_store.get_current_project()

        # Determine which products are configured
        products = []
        if username:
            products.append("am")
        if idm_username:
            products.append("idm")

        temp_config = {
            "auth_mode": "onprem",
            "base_url": base_url,
            "onprem_products": products,
            "description": "Temporary on-prem project configuration",
        }

        if username:
            temp_config["onprem_username"] = username
            temp_config["onprem_realm"] = (realm or "root").strip("/")

        if idm_username:
            temp_config["idm_username"] = idm_username
            if idm_base_url:
                temp_config["idm_base_url"] = idm_base_url

        self.config_store.save_project(temp_project_name, temp_config)
        self.config_store.set_current_project(temp_project_name)

        try:
            success("✅ argument mode (onprem) initialized successfully")
            return temp_project_name
        except Exception as e:
            if self._original_project:
                self.config_store.set_current_project(self._original_project)
            error(f"Failed to initialize argument mode (onprem): {str(e)}")
            raise typer.Exit(1)

    def cleanup_argument_mode(self):
        """Clean up temporary project created in argument mode"""
        if self._temp_project:
            try:
                # Restore original project
                if self._original_project:
                    self.config_store.set_current_project(self._original_project)
                else:
                    # Remove current project file if no original project
                    if self.config_store.current_project_file.exists():
                        self.config_store.current_project_file.unlink()

                info(f"Cleaned up temporary project: {self._temp_project}")
            except Exception as e:
                warning(f"Failed to cleanup temporary project: {str(e)}")
            finally:
                self._temp_project = None
                self._original_project = None

    def update_config_if_needed(
        self,
        jwk_path: Optional[str],
        sa_id: Optional[str],
        base_url: Optional[str],
    ) -> None:
        """Update configuration if any arguments are provided"""
        if any([jwk_path, sa_id, base_url]):
            info("Updating configuration with provided arguments...")
            try:
                current_project = self.config_store.get_current_project()
                if not current_project:
                    warning("No current project set, skipping config update")
                    return

                # Get existing config
                current_config = (
                    self.config_store.get_project_config(current_project) or {}
                )

                # Update only the provided fields
                if jwk_path:
                    current_config["jwk_path"] = jwk_path
                if sa_id:
                    current_config["sa_id"] = sa_id
                if base_url:
                    current_config["base_url"] = base_url
                    # Also update token_url if base_url is provided
                    current_config["token_url"] = f"{base_url}/am/oauth2/access_token"

                # Save updated config
                self.config_store.save_project(current_project, current_config)

            except Exception as e:
                error(f"Failed to update configuration: {str(e)}")
                raise typer.Exit(1)

    def get_auth_mode(self, project_name: str, override: Optional[str] = None) -> str:
        """Get the auth mode: 'service-account' (default) or 'onprem'"""
        if override:
            return override
        config = self.config_store.get_project_config(project_name) or {}
        return config.get("auth_mode", "service-account")

    def get_onprem_products(self, project_name: str) -> list:
        """Get list of configured on-prem products: ['am'], ['idm'], or ['am', 'idm']"""
        config = self.config_store.get_project_config(project_name) or {}
        return config.get("onprem_products", ["am"])

    def get_token(self, project_name: str) -> str:
        """Get authentication token for the project (service-account mode)"""
        try:
            return self.token_manager.get_token(project_name)
        except Exception as e:
            error(f"Failed to get token: {str(e)}")
            raise typer.Exit(1)

    def get_onprem_session(
        self,
        project_name: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        realm: Optional[str] = None,
    ) -> str:
        """Obtain on-prem AM session token (SSO token). Not persisted."""
        config = self.config_store.get_project_config(project_name) or {}
        base_url = config.get("base_url")
        if not base_url:
            error(
                "Base URL not configured. Run 'trxo config setup' first or provide --base-url"
            )
            raise typer.Exit(1)

        # Defaults from config
        username = username or config.get("onprem_username")
        realm = (realm or config.get("onprem_realm") or "root").strip("/")

        # Prompt if missing
        if not username:
            username = typer.prompt("On-Prem AM username", default="amAdmin")
        if not password:
            password = typer.prompt("On-Prem AM password", hide_input=True)

        try:
            client = OnPremAuth(base_url=base_url, realm=realm)
            data = client.authenticate(username=username, password=password)
            return data["tokenId"]
        except Exception as e:
            error(f"On-Prem AM authentication failed: {e}")
            raise typer.Exit(1)

    def get_idm_credentials(
        self,
        project_name: str,
        idm_username: Optional[str] = None,
        idm_password: Optional[str] = None,
    ) -> tuple:
        """Get IDM credentials (username, password). Password is prompted if not provided."""
        config = self.config_store.get_project_config(project_name) or {}

        # Check if IDM is configured
        products = config.get("onprem_products", [])
        if "idm" not in products and not idm_username:
            error(
                "IDM credentials not configured for this project.\n"
                "💡 Run 'trxo config setup --auth-mode onprem' to add IDM access,\n"
                "   or provide --idm-username and --idm-password."
            )
            raise typer.Exit(1)

        username = idm_username or config.get("idm_username")
        if not username:
            username = typer.prompt("On-Prem IDM username", default="openidm-admin")
        if not idm_password:
            idm_password = typer.prompt("On-Prem IDM password", hide_input=True)

        return username, idm_password

    def get_idm_base_url(
        self, project_name: str, idm_base_url_override: Optional[str] = None
    ) -> str:
        """Get IDM base URL. Falls back to AM base_url if idm_base_url not set."""
        if idm_base_url_override:
            return idm_base_url_override

        config = self.config_store.get_project_config(project_name) or {}
        idm_url = config.get("idm_base_url")
        if idm_url:
            return idm_url

        # Fallback to base_url (same host)
        return config.get("base_url", "")

    def get_base_url(
        self, project_name: str, base_url_override: Optional[str] = None
    ) -> str:
        """Get base URL from config or override"""
        if base_url_override:
            return base_url_override

        config = self.config_store.get_project_config(project_name)
        api_base_url = config.get("base_url") if config else None

        if not api_base_url:
            error(
                "Base URL not configured. Run 'trxo config setup' first or provide --base-url"
            )
            raise typer.Exit(1)

        return api_base_url
