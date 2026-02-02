"""
Git export handler for Git storage mode.

Handles exporting data to Git repositories with proper structure and commits.
"""

import time
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from tqdm import tqdm
from trxo.utils.console import info, error
from trxo.utils.git import setup_git_for_export


class GitExportHandler:
    """Handles Git-specific export operations"""

    def __init__(self, config_store):
        """
        Initialize Git export handler.

        Args:
            config_store: Configuration store instance
        """
        self.config_store = config_store

    def setup_git_repo(self, branch: Optional[str] = None):
        """
        Setup Git repository for export.

        Args:
            branch: Optional branch name

        Returns:
            GitManager instance
        """
<<<<<<< HEAD
        current_project = self.config_store.get_current_project()
        git_credentials = self.config_store.get_git_credentials(current_project)
        if not git_credentials or not all(git_credentials.values()):
            raise ValueError(
                "Git credentials not found. Run 'trxo config' to set up Git integration."
            )

        username, repo_url, token = git_credentials.values()
        return setup_git_for_export(username, token, repo_url, branch)
=======
        try:
            current_project = self.config_store.get_current_project()
            git_credentials = self.config_store.get_git_credentials(current_project)
            if not git_credentials or not all(git_credentials.values()):
                error("Git credentials not found. Run 'trxo config' to set up Git integration.")
                raise ValueError("Missing Git credentials")

            username, repo_url, token = git_credentials.values()
            return setup_git_for_export(username, token, repo_url, branch)
        except Exception as e:
            error(f"Failed to setup Git repository: {e}")
            raise
>>>>>>> origin/fix/linters

    @staticmethod
    def extract_realm_and_component(
        data: Dict[str, Any], command_name: str
    ) -> tuple[str, str]:
        """
        Extract realm and component from data and command name.

        Args:
            data: Export data
            command_name: Command name

        Returns:
            Tuple of (realm, component)
        """
        realm = "root"
        component = command_name

        # Extract from metadata if available
        if isinstance(data, dict) and isinstance(data.get("metadata"), dict):
            metadata_realm = data["metadata"].get("realm")
            if metadata_realm:
                realm = metadata_realm

        # Normalize component name
        if command_name.startswith("services_realm_"):
            component = "services"
            if not metadata_realm:
                realm = command_name.split("services_realm_")[-1]
        elif command_name == "services_global":
            component = "services"
            realm = "global"

        return realm, component

    @staticmethod
    def create_commit_message(
        realm: str, component: str, file_path: Path, data: Dict[str, Any]
    ) -> str:
        """
        Create a descriptive commit message.

        Args:
            realm: Realm name
            component: Component name
            file_path: File path
            data: Export data

        Returns:
            Commit message string
        """
        # Count items
        item_count = 0
        if isinstance(data, dict) and "data" in data:
            if isinstance(data["data"], dict) and "result" in data["data"]:
                result = data["data"]["result"]
                item_count = len(result) if isinstance(result, list) else 1
            elif isinstance(data["data"], list):
                item_count = len(data["data"])
            else:
                item_count = 1

        # Get API version
        api_version = "2.1"
        if isinstance(data, dict) and "metadata" in data:
            api_version = data["metadata"].get("api_version", "2.1")

        # Build message
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        subject = f"Export: {file_path}"
        body = f"""
Realm: {realm}
Component: {component}
Items: {item_count}
API Version: {api_version}
Timestamp: {timestamp}
"""
        return f"{subject}\n{body.strip()}"

    def save_to_git(
        self,
        data: Dict[Any, Any],
        command_name: str,
        output_file: Optional[str] = None,
        branch: Optional[str] = None,
        commit_message: Optional[str] = None,
    ) -> Optional[str]:
        """
        Save data to Git repository.

        Args:
            data: Data to save
            command_name: Command name
            output_file: Optional custom filename
            branch: Optional branch name
            commit_message: Optional custom commit message

        Returns:
            Path to saved file or None if failed
        """
        try:
            # Setup Git repository
            git_manager = self.setup_git_repo(branch)
            repo_path = git_manager.local_path

            # Extract realm and component
            realm, component = self.extract_realm_and_component(data, command_name)

            # Create directory structure: <repo>/<realm>/<component>/
            realm_dir = repo_path / realm
            component_dir = realm_dir / component
            component_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename
            if output_file:
                filename = f"{output_file}.json"
            else:
                filename = f"{realm}_{component}.json"

            file_path = component_dir / filename

            # Update metadata for Git mode
            if isinstance(data, dict):
                meta = data.setdefault("metadata", {})
                meta["storage_mode"] = "git"
                meta["realm"] = realm
                meta["component"] = component
                meta.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
                meta.pop("hash", None)  # Git provides integrity

            # Save with progress bar
            with tqdm(
                total=100,
                desc=f"🔄 Git Export {filename}",
                bar_format="{l_bar}{bar:40}{r_bar}{bar:-40b}",
                colour="blue",
                ncols=100,
                leave=True,
            ) as pbar:
                pbar.set_description("📁 Creating directories")
                pbar.update(20)
                time.sleep(0.1)

                pbar.set_description("✍️  Writing file")
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                pbar.update(30)
                time.sleep(0.1)

                pbar.set_description("📋 Staging changes")
                pbar.update(20)
                time.sleep(0.1)

                pbar.set_description("💾 Committing")
                relative_path = file_path.relative_to(repo_path)

                if not commit_message:
                    commit_message = self.create_commit_message(
                        realm, component, relative_path, data
                    )

<<<<<<< HEAD
                # Branch sync validation is already done in setup_git_for_export
=======
>>>>>>> origin/fix/linters
                success = git_manager.commit_and_push(
                    [str(relative_path)], commit_message, smart_pull=False
                )

                if success:
                    pbar.update(30)
                    pbar.set_description("✅ Git export complete")
                else:
                    pbar.update(30)
                    pbar.set_description("✅ No changes to commit")

            print()
            info(f"✅ Exported to Git: {relative_path}")
            info(f"📂 Repository: {repo_path}")

            # Display branch info
            try:
                current_branch = git_manager.get_current_branch()
                info(f"🌿 Branch: {current_branch}")
            except Exception:
                pass

            return str(file_path)

        except Exception as e:
            # Only print error if it's not already a RuntimeError from setup
            if not isinstance(e, RuntimeError) or "Git setup failed" not in str(e):
                error(f"Failed to save to Git: {str(e)}")
            else:
                # This is a setup error, just print it once
                error(str(e).replace("Git setup failed: ", ""))
            return None
