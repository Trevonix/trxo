"""
Git repository manager for export/import operations.

This module provides optimized Git repository management for export/import operations,
including validation, cloning, branch management, and commit/push operations.
"""

import httpx
from git import Repo, GitCommandError, InvalidGitRepositoryError
from pathlib import Path
from typing import Optional
from trxo.utils.console import info, warning
from trxo.logging import get_logger
from trxo.constants import DEFAULT_EXPORT_BRANCH

# Initialize logger for this module
logger = get_logger("trxo.utils.git_manager")


class GitManager:
    """Optimized Git repository manager with separate concerns"""

    def __init__(self, username: str, token: str, repo_url: str):
        self.username = username
        self.token = token
        self.repo_url = repo_url
        self.repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        self.local_path = get_repo_path(self.repo_name)
        self.secure_url = self._build_secure_url()
        self._repo_cache: Optional[Repo] = None

    def _build_secure_url(self) -> str:
        """Build secure HTTPS URL with credentials"""
        if self.repo_url.startswith("https://"):
            return self.repo_url.replace(
                "https://", f"https://{self.username}:{self.token}@"
            )
        return self.repo_url

    @staticmethod
    def _extract_branch_name_from_ref(ref_name: str) -> str:
        """
        Extract branch name from Git ref name.

        Handles branch names with slashes (e.g., 'feature/export').
        Converts 'refs/remotes/origin/scripts/export' to 'scripts/export'.

        Args:
            ref_name: Full Git ref name

        Returns:
            Branch name without remote prefix
        """
        branch_name = ref_name
        if branch_name.startswith("refs/remotes/origin/"):
            branch_name = branch_name.replace("refs/remotes/origin/", "", 1)
        elif "/" in branch_name:
            # Fallback: remove everything up to 'origin/'
            parts = branch_name.split("origin/", 1)
            if len(parts) > 1:
                branch_name = parts[1]
        return branch_name

    def validate_credentials(self) -> dict:
        """Validate GitHub credentials and repository access"""

        # Extract API path
        if "github.com/" not in self.repo_url:
            raise ValueError(
                "Unsupported repo URL. Use https://github.com/owner/repo(.git)"
            )

        api_repo_path = (
            self.repo_url.split("github.com/")[1].rstrip("/").replace(".git", "")
        )
        api_url = f"https://api.github.com/repos/{api_repo_path}"
        headers = {"Authorization": f"token {self.token}"}

        try:
            with httpx.Client() as client:
                resp = client.get(api_url, headers=headers, timeout=15)
        except httpx.RequestError as e:
            raise RuntimeError(f"Network error during validation: {e}")

        if resp.status_code == 404:
            raise PermissionError(
                "Repository not found or token does not grant access (404)."
            )
        if resp.status_code == 401:
            raise PermissionError("Invalid or expired token (401).")
        if resp.status_code != 200:
            raise RuntimeError(f"Unexpected GitHub API response: {resp.status_code}")

        repo_json = resp.json()
        perms = repo_json.get("permissions", {}) or {}
        if not perms.get("push", False):
            raise PermissionError(
                "Token does not have push/write permission to this repository."
            )

        logger.info("Repository access & write permissions validated")
        return repo_json

    def get_or_create_repo(self, repo_info: dict) -> Repo:
        """Get existing repository or create/clone it (one-time setup)"""
        if self._repo_cache:
            return self._repo_cache

        # Check if repo already exists locally
        if self.local_path.exists() and (self.local_path / ".git").exists():
            logger.debug(f"Using existing repository: {self.local_path}")
            info(f"📂 Using existing repository: {self.local_path}")
            try:
                repo = Repo(str(self.local_path))
                # Update origin remote with secure URL (with credentials) for auth
                try:
                    origin = repo.remote("origin")
                    origin.set_url(self.secure_url)
                    logger.debug(f"Updated origin URL for repository")
                except Exception as e:
                    logger.debug(f"Could not update origin URL: {e}")
                self._repo_cache = repo
                return repo
            except InvalidGitRepositoryError:
                logger.warning(
                    "Local directory exists but is not a valid Git repository. Re-cloning..."
                )
                import shutil

                shutil.rmtree(self.local_path)

        # Clone or initialize repository
        return self._clone_or_init_repo(repo_info)

    def _clone_or_init_repo(self, repo_info: dict) -> Repo:
        """Clone existing repo or initialize empty repo"""
        logger.info(f"Setting up repository: {self.repo_name}")

        try:
            # Try to clone
            repo = Repo.clone_from(self.secure_url, str(self.local_path))
            logger.info(f"Repository cloned to: {self.local_path}")
        except GitCommandError as e:
            # Handle empty repository
            if any(
                phrase in str(e)
                for phrase in [
                    "remote HEAD refers to nonexistent ref",
                    "does not match any file(s) known to git",
                    "Couldn't find remote ref",
                ]
            ):
                logger.info("Remote repository is empty. Initializing...")
                repo = self._init_empty_repo(repo_info)
            else:
                raise RuntimeError(f"Failed to clone repository: {e}")

        self._repo_cache = repo
        return repo

    def _init_empty_repo(self, repo_info: dict) -> Repo:
        """Initialize empty repository with initial commit"""
        self.local_path.mkdir(parents=True, exist_ok=True)
        repo = Repo.init(str(self.local_path))

        # Create initial branch
        default_branch = repo_info.get("default_branch", "main")
        try:
            repo.git.checkout("-b", default_branch)
        except GitCommandError:
            repo.git.symbolic_ref("HEAD", f"refs/heads/{default_branch}")

        # Create initial commit
        readme_path = self.local_path / "README.md"
        readme_path.write_text(
            f"# {self.repo_name}\n\nPingOne Advanced Identity Cloud configuration repository.\n"
        )
        repo.index.add([str(readme_path)])
        repo.index.commit("Initial commit by PingOne Advanced Identity Cloud CLI")

        # Set up remote and push
        try:
            repo.create_remote("origin", self.secure_url)
        except Exception:
            if "origin" in [r.name for r in repo.remotes]:
                repo.delete_remote("origin")
            repo.create_remote("origin", self.secure_url)

        # Push initial branch
        origin = repo.remote("origin")
        origin.push(refspec=f"{default_branch}:{default_branch}")
        logger.info(f"Initialized empty repository with '{default_branch}' branch")

        return repo

    def _repo_has_commits(self, repo: Repo) -> bool:
        """Check if repository has any commits"""
        try:
            repo.head.commit
            return True
        except (ValueError, GitCommandError):
            return False

    def _create_initial_commit(self, repo: Repo) -> None:
        """Create initial commit in an empty repository"""
        # Determine default branch name
        default_branch = "main"
        try:
            # Try to get from remote
            origin = repo.remote("origin")
            origin.fetch()
            for ref in origin.refs:
                if ref.name.endswith("/HEAD"):
                    if hasattr(ref, "ref"):
                        default_branch = ref.ref.path.split("/")[-1]
                    break
        except Exception:
            pass  # Use default 'main'

        # Create initial branch and commit
        try:
            repo.git.checkout("-b", default_branch)
        except GitCommandError:
            try:
                repo.git.symbolic_ref("HEAD", f"refs/heads/{default_branch}")
            except Exception:
                pass  # Branch might already be set

        # Create README
        readme_path = self.local_path / "README.md"
        readme_path.write_text(
            f"# {self.repo_name}\n\n"
            "PingOne Advanced Identity Cloud configuration repository.\n"
        )

        # Add and commit
        repo.index.add([str(readme_path)])
        repo.index.commit("Initial commit by TRXO CLI")

        # Push to remote
        try:
            origin = repo.remote("origin")
            origin.push(refspec=f"{default_branch}:{default_branch}")
            logger.info(f"Created initial commit on '{default_branch}' branch")
        except Exception as e:
            logger.warning(f"Created local commit but could not push to remote: {e}")

    def ensure_work_branch(
        self, work_branch: str = DEFAULT_EXPORT_BRANCH, validate: bool = False
    ) -> Repo:
        """Ensure work branch exists and is checked out

        DEPRECATED: This method is kept for backward compatibility.
        New code should use ensure_branch() with proper validation.

        Args:
            work_branch: Name of the work branch
            validate: If True, perform clean state and sync validation

        Raises:
            RuntimeError: If branch operations fail
        """
        repo = self._repo_cache
        if not repo:
            raise RuntimeError(
                "Repository not initialized. Call get_or_create_repo() first."
            )

        # Check if repo has any commits
        has_commits = self._repo_has_commits(repo)

        # If no commits, create initial commit first
        if not has_commits:
            info("📝 Repository has no commits. Creating initial structure...")
            self._create_initial_commit(repo)

        # If validation is requested, use the new ensure_branch method
        if validate:
            return self.ensure_branch(
                work_branch,
                create_from_default=True,
                validate_clean=True,
                validate_sync=True,
                operation="work branch setup",
            )

        # Legacy behavior (no validation) - for backward compatibility
        warning(
            "Using ensure_work_branch without validation is deprecated. "
            "Consider using ensure_branch() with validation."
        )

        # Fetch latest changes from remote
        try:
            origin = repo.remote("origin")
            origin.fetch()
        except Exception as e:
            warning(f"Could not fetch from remote: {e}")

        # Get default branch
        default_branch = self._get_default_branch(repo)

        # Check if work branch exists
        if work_branch in [h.name for h in repo.heads]:
            info(f"🌿 Switching to existing work branch: {work_branch}")
            repo.git.checkout(work_branch)
        else:
            info(f"🌿 Creating work branch '{work_branch}' from '{default_branch}'")
            try:
                repo.git.checkout(default_branch)
                repo.git.checkout("-b", work_branch)
            except GitCommandError as e:
                raise RuntimeError(f"Failed to create work branch '{work_branch}': {e}")

        return repo

    def ensure_branch(
        self,
        branch_name: str,
        create_from_default: bool = True,
        validate_clean: bool = True,
        validate_sync: bool = True,
        operation: str = "operation",
    ) -> Repo:
        """Ensure a specific branch exists and is checked out with proper validation

        Args:
            branch_name: Name of the branch to ensure
            create_from_default: If True, create from default branch; if False, create from current branch
            validate_clean: If True, validate working tree is clean before switching
            validate_sync: If True, validate branch sync status with remote
            operation: Name of the operation (for error messages)

        Raises:
            RuntimeError: If validation fails or branch operations fail
        """
        repo = self._repo_cache
        if not repo:
            raise RuntimeError(
                "Repository not initialized. Call get_or_create_repo() first."
            )

        # Step 1: Validate working tree is clean (if requested)
        if validate_clean:
            logger.debug("Validating working tree is clean...")
            self.validate_clean_state_for_operation(operation)
            logger.debug("Working tree is clean")

        # Step 2: Fetch latest changes from remote (suppress stderr output)
        logger.debug("Fetching latest changes from remote...")
        try:
            import os
            from contextlib import redirect_stderr

            origin = repo.remote("origin")
            # Suppress stderr to avoid "Error lines received while fetching" messages
            with open(os.devnull, "w") as devnull:
                with redirect_stderr(devnull):
                    origin.fetch()
            logger.debug("Fetch completed successfully")
        except Exception as e:
            logger.warning(f"Could not fetch from remote: {e}")

        # Step 3: Check branch existence
        local_branches = [h.name for h in repo.heads]
        remote_branches = []

        try:
            origin = repo.remote("origin")
            remote_branches = [
                self._extract_branch_name_from_ref(ref.name)
                for ref in origin.refs
                if not ref.name.endswith("/HEAD")
            ]
        except Exception:
            pass

        # Step 4: Handle branch checkout/creation based on existence
        if branch_name in local_branches:
            # Branch exists locally
            logger.debug(f"Switching to existing local branch: {branch_name}")
            repo.git.checkout(branch_name)

            # Validate sync status if branch exists on remote
            if branch_name in remote_branches and validate_sync:
                logger.debug("Validating branch sync status...")
                self.validate_branch_sync_for_operation(branch_name, operation)

                # If validation passed and we're behind, fast-forward pull
                sync_status = self.check_branch_sync_status(branch_name)
                if sync_status["behind"] > 0 and sync_status["ahead"] == 0:
                    logger.info(f"Fast-forward pulling from remote '{branch_name}'...")
                    info("📥 Pulling latest changes from remote")
                    # Suppress stderr to avoid git messages
                    import os
                    from contextlib import redirect_stderr

                    with open(os.devnull, "w") as devnull:
                        with redirect_stderr(devnull):
                            repo.git.pull("origin", branch_name, "--ff-only")
                elif sync_status["in_sync"]:
                    logger.debug("Branch is in sync with remote")

        elif branch_name in remote_branches:
            # Branch exists only on remote
            logger.debug(f"Checking out remote branch: {branch_name}")
            try:
                repo.git.checkout("-b", branch_name, f"origin/{branch_name}")
                logger.info(f"Checked out remote branch '{branch_name}'")
            except GitCommandError as e:
                raise RuntimeError(
                    f"Failed to checkout remote branch '{branch_name}': {e}"
                )

        else:
            # Branch doesn't exist - create it
            if create_from_default:
                default_branch = self._get_default_branch(repo)
                info(f"🌿 Creating new branch '{branch_name}' from '{default_branch}'")
                try:
                    # Ensure default branch is up to date first
                    current_branch = repo.active_branch.name
                    repo.git.checkout(default_branch)

                    # Update default branch if it exists on remote
                    if default_branch in remote_branches and validate_sync:
                        sync_status = self.check_branch_sync_status(default_branch)
                        if sync_status["behind"] > 0 and sync_status["ahead"] == 0:
                            info(f"📥 Updating '{default_branch}' from remote...")
                            repo.git.pull("origin", default_branch, "--ff-only")

                    # Create new branch
                    repo.git.checkout("-b", branch_name)
                    logger.info(f"Created new branch '{branch_name}'")
                except GitCommandError as e:
                    raise RuntimeError(
                        f"Failed to create branch '{branch_name}' from '{default_branch}': {e}"
                    )
            else:
                info(f"🌿 Creating new branch '{branch_name}' from current branch")
                try:
                    repo.git.checkout("-b", branch_name)
                    logger.info(f"Created new branch '{branch_name}'")
                except GitCommandError as e:
                    raise RuntimeError(f"Failed to create branch '{branch_name}': {e}")

        return repo

    def _get_default_branch(self, repo: Repo) -> str:
        """Determine the default branch"""
        # Try to get from remote origin
        try:
            if "origin" in [r.name for r in repo.remotes]:
                origin = repo.remote("origin")
                origin.fetch()
                # Look for remote HEAD
                for ref in origin.refs:
                    if ref.name.endswith("/HEAD"):
                        target_branch = (
                            ref.ref.path.split("/")[-1] if hasattr(ref, "ref") else None
                        )
                        if target_branch and target_branch in [
                            h.name for h in repo.heads
                        ]:
                            return target_branch
        except Exception:
            pass

        # Fallback strategies
        for branch_name in ["main", "master"]:
            if branch_name in [h.name for h in repo.heads]:
                return branch_name

        # Use first available branch
        if repo.heads:
            return repo.heads[0].name

        return "main"  # ultimate fallback

    def commit_and_push(
        self, file_paths: list, commit_message: str, smart_pull: bool = False
    ) -> bool:
        """Commit specific files and push to remote

        Note: smart_pull is deprecated and should not be used. Branch sync validation
        should be done before calling this method using validate_branch_sync_for_operation().

        Args:
            file_paths: List of file paths to commit
            commit_message: Commit message
            smart_pull: DEPRECATED - kept for backward compatibility, defaults to False

        Raises:
            RuntimeError: If commit or push fails
        """
        repo = self._repo_cache
        if not repo:
            raise RuntimeError("Repository not initialized")

        try:
            current_branch = repo.active_branch.name

            # Warn if smart_pull is being used
            if smart_pull:
                warning(
                    "smart_pull parameter is deprecated. "
                    "Use validate_branch_sync_for_operation() before commit_and_push()."
                )

            # Stage specific files
            repo.index.add(file_paths)

            # Check if there are changes to commit
            if not repo.index.diff("HEAD"):
                logger.debug("No changes to commit")
                return False

            # Commit changes
            repo.index.commit(commit_message)
            logger.info(f"Committed changes: {commit_message}")

            # Push to remote (suppress stderr to avoid git messages)
            try:
                import os
                from contextlib import redirect_stderr

                origin = repo.remote("origin")
                with open(os.devnull, "w") as devnull:
                    with redirect_stderr(devnull):
                        origin.push(refspec=f"{current_branch}:{current_branch}")
                logger.info(f"Pushed changes to remote branch '{current_branch}'")
                return True
            except GitCommandError as e:
                if "non-fast-forward" in str(e) or "rejected" in str(e):
                    logger.error(
                        f"Push rejected - remote has newer changes. "
                        f"This should not happen if branch sync was validated before commit. "
                        f"Error: {e}"
                    )
                    raise RuntimeError(f"Push rejected due to conflicts: {e}")
                else:
                    raise RuntimeError(f"Failed to push: {e}")

        except Exception as e:
            raise RuntimeError(f"Failed to commit and push: {e}")

    def get_current_branch(self) -> str:
        """Get the name of the currently active branch"""
        repo = self._repo_cache
        if not repo:
            raise RuntimeError("Repository not initialized")
        return repo.active_branch.name

    def list_branches(self) -> dict:
        """List all local and remote branches

        Returns:
            dict: {'local': [branch_names], 'remote': [branch_names]}
        """
        repo = self._repo_cache
        if not repo:
            raise RuntimeError("Repository not initialized")

        local_branches = [h.name for h in repo.heads]
        remote_branches = []

        try:
            origin = repo.remote("origin")
            origin.fetch()
            remote_branches = [
                self._extract_branch_name_from_ref(ref.name)
                for ref in origin.refs
                if not ref.name.endswith("/HEAD")
            ]
        except Exception:
            pass

        return {"local": local_branches, "remote": remote_branches}

    def branch_exists(self, branch_name: str, check_remote: bool = True) -> dict:
        """Check if a branch exists locally and/or remotely

        Args:
            branch_name: Name of the branch to check
            check_remote: Whether to check remote branches

        Returns:
            dict: {'local': bool, 'remote': bool}
        """
        repo = self._repo_cache
        if not repo:
            raise RuntimeError("Repository not initialized")

        local_exists = branch_name in [h.name for h in repo.heads]
        remote_exists = False

        if check_remote:
            try:
                origin = repo.remote("origin")
                origin.fetch()
                remote_branches = [
                    self._extract_branch_name_from_ref(ref.name)
                    for ref in origin.refs
                    if not ref.name.endswith("/HEAD")
                ]
                remote_exists = branch_name in remote_branches
            except Exception:
                pass

        return {"local": local_exists, "remote": remote_exists}

    def get_diff(self, file_path: str) -> str:
        """Get diff for a specific file"""
        repo = self._repo_cache
        if not repo:
            return ""

        try:
            return repo.git.diff("HEAD", file_path)
        except Exception:
            return ""

    def is_working_tree_clean(self) -> bool:
        """Check if working tree is clean (no uncommitted or untracked changes)

        Returns:
            True if working tree is clean, False otherwise
        """
        repo = self._repo_cache
        if not repo:
            raise RuntimeError("Repository not initialized")

        try:
            # Check for uncommitted changes (staged and unstaged)
            if repo.is_dirty(untracked_files=False):
                return False

            # Check for untracked files
            if repo.untracked_files:
                return False

            return True
        except Exception:
            return False

    def get_working_tree_status(self) -> dict:
        """Get detailed working tree status

        Returns:
            dict with keys: 'clean', 'uncommitted_changes', 'untracked_files'
        """
        repo = self._repo_cache
        if not repo:
            raise RuntimeError("Repository not initialized")

        try:
            uncommitted = []
            untracked = list(repo.untracked_files)

            # Get modified files (staged and unstaged)
            if repo.is_dirty(untracked_files=False):
                # Get changed files
                changed_files = [item.a_path for item in repo.index.diff(None)]
                staged_files = [item.a_path for item in repo.index.diff("HEAD")]
                uncommitted = list(set(changed_files + staged_files))

            is_clean = len(uncommitted) == 0 and len(untracked) == 0

            return {
                "clean": is_clean,
                "uncommitted_changes": uncommitted,
                "untracked_files": untracked,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to get working tree status: {e}")

    def check_branch_sync_status(self, branch_name: str) -> dict:
        """Check if local branch is in sync with remote

        Args:
            branch_name: Name of the branch to check

        Returns:
            dict with keys:
                - 'exists_local': bool
                - 'exists_remote': bool
                - 'behind': int (commits behind remote)
                - 'ahead': int (commits ahead of remote)
                - 'diverged': bool (local and remote have diverged)
                - 'in_sync': bool (local and remote are identical)
        """
        repo = self._repo_cache
        if not repo:
            raise RuntimeError("Repository not initialized")

        result = {
            "exists_local": False,
            "exists_remote": False,
            "behind": 0,
            "ahead": 0,
            "diverged": False,
            "in_sync": False,
        }

        try:
            # Check local existence
            result["exists_local"] = branch_name in [h.name for h in repo.heads]

            # Fetch to get latest remote info
            origin = repo.remote("origin")
            origin.fetch()

            # Check remote existence
            remote_branches = [
                self._extract_branch_name_from_ref(ref.name)
                for ref in origin.refs
                if not ref.name.endswith("/HEAD")
            ]
            result["exists_remote"] = branch_name in remote_branches

            # If both exist, check sync status
            if result["exists_local"] and result["exists_remote"]:
                local_commit = repo.heads[branch_name].commit
                remote_commit = origin.refs[branch_name].commit

                if local_commit == remote_commit:
                    result["in_sync"] = True
                else:
                    # Count commits behind and ahead
                    try:
                        # Commits in remote but not in local (behind)
                        behind_commits = list(
                            repo.iter_commits(f"{branch_name}..origin/{branch_name}")
                        )
                        result["behind"] = len(behind_commits)

                        # Commits in local but not in remote (ahead)
                        ahead_commits = list(
                            repo.iter_commits(f"origin/{branch_name}..{branch_name}")
                        )
                        result["ahead"] = len(ahead_commits)

                        # Diverged if both behind and ahead
                        result["diverged"] = (
                            result["behind"] > 0 and result["ahead"] > 0
                        )
                    except Exception:
                        # If we can't determine, assume diverged for safety
                        result["diverged"] = True

            return result

        except Exception as e:
            raise RuntimeError(f"Failed to check branch sync status: {e}")

    def validate_clean_state_for_operation(self, operation: str = "operation") -> None:
        """Validate that working tree is clean before performing Git operations

        Args:
            operation: Name of the operation (for error messages)

        Raises:
            RuntimeError: If working tree is not clean
        """
        status = self.get_working_tree_status()

        if not status["clean"]:
            error_msg = f"Cannot proceed with {operation}: working tree has uncommitted changes.\n"

            if status["uncommitted_changes"]:
                error_msg += f"\nUncommitted changes:\n"
                for file in status["uncommitted_changes"]:
                    error_msg += f"  - {file}\n"

            if status["untracked_files"]:
                error_msg += f"\nUntracked files:\n"
                for file in status["untracked_files"]:
                    error_msg += f"  - {file}\n"

            error_msg += "\nPlease commit or stash your changes before proceeding."
            raise RuntimeError(error_msg)

    def validate_branch_sync_for_operation(
        self, branch_name: str, operation: str = "operation"
    ) -> None:
        """Validate that branch is properly synced with remote before
        operations

        Args:
            branch_name: Name of the branch to validate
            operation: Name of the operation (for error messages)

        Raises:
            RuntimeError: If branch is not properly synced
        """
        sync_status = self.check_branch_sync_status(branch_name)

        # If branch doesn't exist remotely yet, that's okay (new branch)
        if not sync_status["exists_remote"]:
            return

        # If local is behind remote, require pull
        if sync_status["behind"] > 0 and sync_status["ahead"] == 0:
            try:
                # pull first
                repo = self._repo_cache
                repo.git.fetch("origin", branch_name)
                repo.git.pull("origin", branch_name)
                info(f"📥 Pulled latest changes from remote '{branch_name}'")
            except Exception as e:
                raise RuntimeError(f"Failed to pull latest changes: {e}")

        # If branches have diverged, require manual resolution
        if sync_status["diverged"]:
            raise RuntimeError(
                f"Cannot proceed with {operation}: local and remote branches have diverged.\n"
                f"Local is {sync_status['ahead']} commit(s) ahead and "
                f"{sync_status['behind']} commit(s) behind remote.\n"
                f"Please resolve the divergence manually before proceeding."
            )


# Legacy function for backward compatibility
def validate_and_setup_git_repo(
    username: str,
    token: str,
    repo_url: str,
    work_branch: str = DEFAULT_EXPORT_BRANCH,
    preferred_default: str = "main",
):
    """
    Legacy function - uses new GitManager internally
    Returns Repo object on success or raises an exception on failure.
    """
    git_manager = GitManager(username, token, repo_url)

    # Validate credentials and get repo info
    repo_info = git_manager.validate_credentials()

    # Get or create repository (one-time setup)
    repo = git_manager.get_or_create_repo(repo_info)

    # Ensure work branch exists and is checked out
    repo = git_manager.ensure_work_branch(work_branch)

    info(f"✅ Repository ready: {git_manager.local_path}")
    info(f"🌿 Active branch: {repo.active_branch.name}")

    return repo


# Optimized functions for export operations
def get_git_manager(username: str, token: str, repo_url: str) -> GitManager:
    """Get GitManager instance for export operations"""
    return GitManager(username, token, repo_url)


def setup_git_for_export(
    username: str, token: str, repo_url: str, branch: Optional[str] = None
) -> GitManager:
    """Setup Git for export operations with strict validation

    Export Flow Rules:
    1. Working tree must be clean (no uncommitted or untracked changes)
    2. If local branch is behind remote, fetch and fast-forward pull first
    3. If local and remote have diverged, abort and require manual resolution
    4. Never modify Git state implicitly (no auto-stash, auto-commit, auto-merge)

    Args:
        username: Git username
        token: Git token
        repo_url: Repository URL
        branch: Optional branch name. If None, uses default work branch

    Raises:
        RuntimeError: If validation fails or Git operations fail
    """
    git_manager = GitManager(username, token, repo_url)

    try:
        # Validate credentials and setup repository
        repo_info = git_manager.validate_credentials()
        git_manager.get_or_create_repo(repo_info)

        # Ensure branch with full validation for export
        if branch:
            git_manager.ensure_branch(
                branch,
                create_from_default=True,
                validate_clean=True,
                validate_sync=True,
                operation="export",
            )
            info(
                f"🌿 Using branch: {branch}, to change branch use --branch <branch_name>"
            )
        else:
            # Use legacy ensure_work_branch for backward compatibility
            # git_manager.ensure_work_branch()
            info(f"🌿 Using default branch for export: {DEFAULT_EXPORT_BRANCH}")
            git_manager.ensure_branch(
                DEFAULT_EXPORT_BRANCH,
                create_from_default=True,
                validate_clean=True,
                validate_sync=True,
                operation="export",
            )

        return git_manager
    except Exception as e:
        # Log the error but don't print to console (will be handled by caller)
        logger.error(f"Git setup for export failed: {e}")
        raise RuntimeError(f"Git setup failed: {e}")


def setup_git_for_import(
    username: str, token: str, repo_url: str, branch: Optional[str] = None
) -> GitManager:
    """Setup Git for import operations with strict validation

    Import Flow Rules:
    1. Working tree must be clean (no uncommitted or untracked changes)
    2. Source branch must be up to date with remote before importing
    3. If local and remote have diverged, abort and require manual resolution
    4. Import data strictly from the current branch state
    5. Never modify Git state implicitly (no auto-stash, auto-commit, auto-merge)

    Args:
        username: Git username
        token: Git token
        repo_url: Repository URL
        branch: Optional branch name to import from. If None, uses current/default branch

    Raises:
        RuntimeError: If validation fails or Git operations fail
    """
    git_manager = GitManager(username, token, repo_url)

    try:
        # Validate credentials and setup repository
        logger.debug("Validating Git credentials...")
        repo_info = git_manager.validate_credentials()
        git_manager.get_or_create_repo(repo_info)

        if branch:
            # For import, ensure the specified branch exists
            logger.debug(f"Setting up branch '{branch}' for import...")
            branches = git_manager.branch_exists(branch)
            if not (branches["local"] or branches["remote"]):
                raise RuntimeError(
                    f"Branch '{branch}' does not exist locally or remotely. "
                    f"Cannot import from non-existent branch."
                )

            # Ensure branch with full validation for import
            git_manager.ensure_branch(
                branch,
                create_from_default=False,
                validate_clean=True,
                validate_sync=True,
                operation="import",
            )
            info(
                f"🌿 Using branch: {branch}, to change branch use --branch <branch_name>"
            )
        else:
            # Use current branch with validation
            current_branch = (
                git_manager.get_current_branch() if git_manager._repo_cache else None
            )
            if current_branch:
                logger.debug(f"Using current branch '{current_branch}' for import...")
                # Validate current branch
                git_manager.ensure_branch(
                    current_branch,
                    create_from_default=False,
                    validate_clean=True,
                    validate_sync=True,
                    operation="import",
                )
                info(
                    f"🌿 Using branch: {current_branch}, to change branch use --branch <branch_name>"
                )
            else:
                # Fallback to work branch
                git_manager.ensure_work_branch()

        return git_manager
    except Exception as e:
        # Log the error but don't print to console (will be handled by caller)
        logger.error(f"Git setup for import failed: {e}")
        raise RuntimeError(f"Git setup for import failed: {e}")


def get_repo_base_path() -> Path:
    """
    Returns a user-visible, OS-safe base directory for storing repos.
    Example:
        Linux/Mac: /home/user/trxo_repos/
        Windows:   C:\\Users\\user\\trxo_repos\\
    """
    home_dir = Path.home()
    base_dir = home_dir / "trxo_repos"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def get_repo_path(repo_name: str) -> Path:
    """
    Returns the full path for a specific repo.
    """
    base_path = get_repo_base_path()
    repo_path = base_path / repo_name
    repo_path.mkdir(parents=True, exist_ok=True)
    return repo_path
