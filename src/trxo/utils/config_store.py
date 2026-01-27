import os
import json
import platform
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import keyring

SERVICE_NAME = "trxo_git_credentials"


class ConfigStore:
    def __init__(self):
        self.base_dir = self._get_config_dir()
        self.projects_file = self.base_dir / "projects.json"
        self.current_project_file = self.base_dir / "current_project"
        self._ensure_config_dir()

    def _get_config_dir(self) -> Path:
        """Get platform-specific config directory"""
        system = platform.system()
        if system == "Windows":
            base_dir = os.environ.get("APPDATA", "")
            return Path(base_dir) / "trxo"
        elif system == "Darwin":  # macOS
            return Path.home() / "Library" / "Application Support" / "trxo"
        else:  # Linux and others
            xdg_config = os.environ.get("XDG_CONFIG_HOME", "")
            if xdg_config:
                return Path(xdg_config) / "trxo"
            return Path.home() / ".trxo"

    def _ensure_config_dir(self):
        """Ensure config directory exists"""
        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.base_dir / "projects", exist_ok=True)

    def get_project_dir(self, project_name: str) -> Path:
        """Get project-specific directory"""
        project_dir = self.base_dir / "projects" / project_name
        os.makedirs(project_dir, exist_ok=True)
        return project_dir

    def save_project(self, project_name: str, config: Dict) -> None:
        """Save project configuration"""
        projects = self.get_projects()
        projects[project_name] = {
            "name": project_name,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            **config,
        }

        with open(self.projects_file, "w", encoding="utf-8") as f:
            json.dump(projects, f, indent=2)

        # Save detailed config in project directory
        project_dir = self.get_project_dir(project_name)
        config_file = project_dir / "config.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    def get_projects(self) -> Dict:
        """Get all projects"""
        if not self.projects_file.exists():
            return {}
        try:
            with open(self.projects_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def get_project_config(self, project_name: str) -> Optional[Dict]:
        """Get project configuration"""
        project_dir = self.get_project_dir(project_name)
        config_file = project_dir / "config.json"
        if not config_file.exists():
            return None
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def set_current_project(self, project_name: str) -> None:
        """Set current active project"""
        with open(self.current_project_file, "w", encoding="utf-8") as f:
            f.write(project_name)

    def get_current_project(self) -> Optional[str]:
        """Get current active project"""
        if not self.current_project_file.exists():
            return None
        try:
            with open(self.current_project_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except IOError:
            return None

    def delete_project(self, project_name: str) -> None:
        """Delete a project"""
        projects = self.get_projects()
        if project_name in projects:
            del projects[project_name]
            with open(self.projects_file, "w", encoding="utf-8") as f:
                json.dump(projects, f, indent=2)

        # Delete project directory
        project_dir = self.get_project_dir(project_name)
        if project_dir.exists():
            for file in project_dir.iterdir():
                file.unlink()
            project_dir.rmdir()

    def save_token(self, project_name: str, token_data: Dict) -> None:
        """Save access token for project"""
        project_dir = self.get_project_dir(project_name)
        token_file = project_dir / "token.json"

        with open(token_file, "w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=2)

    def get_token(self, project_name: str) -> Optional[Dict]:
        """Get access token for project"""
        project_dir = self.get_project_dir(project_name)
        token_file = project_dir / "token.json"
        if not token_file.exists():
            return None
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def save_hashes(self, command_name: str, hash_value: str):
        """Deprecated: Use HashManager.save_export_hash() instead"""
        from trxo.utils.hash_manager import HashManager

        hash_manager = HashManager(self)
        hash_manager.save_export_hash(command_name, hash_value)

    def get_hash(self, command_name: str) -> Optional[str]:
        """Deprecated: Use HashManager.get_hash_info() instead"""
        from trxo.utils.hash_manager import HashManager

        hash_manager = HashManager(self)
        metadata = hash_manager.get_hash_info(command_name)
        return metadata.get("hash") if metadata else None

    def store_git_credentials(
        self, project_name: str, username: str, repo_url: str, token: str
    ):
        """
        Stores git token securely in system keyring (scoped to project).
        Username and Repo URL are stored in project config.json by the caller.
        """
        # Store token with project scope
        keyring.set_password(f"trxo:{project_name}:git_token", "token", token)

        # Determine service name based on project (legacy fallback support)
        # We also update global for tools that might rely on it, strictly for backward compat
        # but the primary source of truth is now project-scoped.
        keyring.set_password(SERVICE_NAME, "token", token)

    def get_git_credentials(self, project_name: str = None) -> Optional[Dict[str, str]]:
        """
        Retrieves git credentials.
        Repo URL & Username -> from project config.json
        Token -> from keyring (scoped -> global fallback)
        """
        if not project_name:
            project_name = self.get_current_project()

        if not project_name:
            return None

        # 1. Get non-sensitive data from Project Config
        config = self.get_project_config(project_name)
        if not config:
            return None

        repo_url = config.get("git_repo")
        username = config.get("git_username")

        if not repo_url or not username:
            # If not in config (old project?), try legacy global keyring
            # This ensures we don't break existing setups completely
            username = keyring.get_password(SERVICE_NAME, "username")
            repo_url = keyring.get_password(SERVICE_NAME, "repo_url")

        # 2. Get sensitive Token from Keyring
        # Try scoped first
        token = keyring.get_password(f"trxo:{project_name}:git_token", "token")

        # Fallback to global if scoped not found
        if not token:
            token = keyring.get_password(SERVICE_NAME, "token")

        if not all([username, repo_url, token]):
            return None

        return {"username": username, "repo_url": repo_url, "token": token}
