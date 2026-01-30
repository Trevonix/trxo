"""
Git repository manager for export/import operations.

This module provides optimized Git repository management for export/import operations,
including validation, cloning, branch management, and commit/push operations.
"""

import httpx
from git import Repo, GitCommandError, InvalidGitRepositoryError
from pathlib import Path
from typing import Optional
from trxo.utils.console import info, warning, error, success


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

    def validate_credentials(self) -> dict:
        """Validate GitHub credentials and repository access"""
        info("🔐 Validating GitHub credentials...")

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

        success("Repository access & write permissions validated")
        return repo_json

    def get_or_create_repo(self, repo_info: dict) -> Repo:
        """Get existing repository or create/clone it (one-time setup)"""
        if self._repo_cache:
            return self._repo_cache

        # Check if repo already exists locally
        if self.local_path.exists() and (self.local_path / ".git").exists():
            info(f"📂 Using existing repository: {self.local_path}")
            try:
                repo = Repo(str(self.local_path))
                # Update origin remote with secure URL (with credentials) for auth
                try:
                    origin = repo.remote("origin")
                    origin.set_url(self.secure_url)
                except Exception:
                    pass
                self._repo_cache = repo
                return repo
            except InvalidGitRepositoryError:
                warning(
                    "Local directory exists but is not a valid Git repository. Re-cloning..."
                )
                import shutil

                shutil.rmtree(self.local_path)

        # Clone or initialize repository
        return self._clone_or_init_repo(repo_info)

    def _clone_or_init_repo(self, repo_info: dict) -> Repo:
        """Clone existing repo or initialize empty repo"""
        info(f"⬇️ Setting up repository: {self.repo_name}")

        try:
            # Try to clone
            repo = Repo.clone_from(self.secure_url, str(self.local_path))
            success(f"Repository cloned to: {self.local_path}")
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
                info("📝 Remote repository is empty. Initializing...")
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
        success(f"Initialized empty repository with '{default_branch}' branch")

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
            success(f"Created initial commit on '{default_branch}' branch")
        except Exception as e:
            warning(f"Created local commit but could not push to remote: {e}")

    def ensure_work_branch(self, work_branch: str = "feature/export---") -> Repo:
        """Ensure work branch exists and is checked out (called every time)"""
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

    def ensure_branch(self, branch_name: str, create_from_default: bool = True) -> Repo:
        """Ensure a specific branch exists and is checked out

        Args:
            branch_name: Name of the branch to ensure
            create_from_default: If True, create from default branch; if False,
            create from current branch
        """
        repo = self._repo_cache
        if not repo:
            raise RuntimeError(
                "Repository not initialized. Call get_or_create_repo() first."
            )

        # Fetch latest changes from remote to ensure we have up-to-date branch info
        try:
            origin = repo.remote("origin")
            origin.fetch()
        except Exception as e:
            warning(f"Could not fetch from remote: {e}")

        # Check if branch exists locally
        local_branches = [h.name for h in repo.heads]
        remote_branches = []

        # Get remote branches
        try:
            origin = repo.remote("origin")
            remote_branches = [
                ref.name.split("/")[-1]
                for ref in origin.refs
                if not ref.name.endswith("/HEAD")
            ]
        except Exception:
            pass

        if branch_name in local_branches:
            info(f"🌿 Switching to existing local branch: {branch_name}")
            repo.git.checkout(branch_name)

            # If branch exists on remote, pull latest changes
            if branch_name in remote_branches:
                try:
                    info(f"📥 Pulling latest changes from remote '{branch_name}'")
                    repo.git.pull("origin", branch_name)
                except GitCommandError as e:
                    warning(f"Could not pull from remote branch '{branch_name}': {e}")

        elif branch_name in remote_branches:
            info(f"🌿 Checking out remote branch: {branch_name}")
            try:
                repo.git.checkout("-b", branch_name, f"origin/{branch_name}")
            except GitCommandError as e:
                raise RuntimeError(
                    f"Failed to checkout remote branch '{branch_name}': {e}"
                )

        else:
            # Create new branch
            if create_from_default:
                default_branch = self._get_default_branch(repo)
                info(f"🌿 Creating new branch '{branch_name}' from '{default_branch}'")
                try:
                    repo.git.checkout(default_branch)
                    repo.git.checkout("-b", branch_name)
                except GitCommandError as e:
                    raise RuntimeError(
                        f"Failed to create branch '{branch_name}' from '{default_branch}': {e}"
                    )
            else:
                info(f"🌿 Creating new branch '{branch_name}' from current branch")
                try:
                    repo.git.checkout("-b", branch_name)
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
        self, file_paths: list, commit_message: str, smart_pull: bool = True
    ) -> bool:
        """Commit specific files and push to remote with smart conflict resolution

        Args:
            file_paths: List of file paths to commit
            commit_message: Commit message
            smart_pull: If True, fetch and pull before pushing to handle conflicts
        """
        repo = self._repo_cache
        if not repo:
            raise RuntimeError("Repository not initialized")

        try:
            current_branch = repo.active_branch.name

            # Smart pull: fetch and pull before committing if enabled
            if smart_pull:
                try:
                    # info("📥 Fetching latest changes from remote...")
                    origin = repo.remote("origin")
                    origin.fetch()

                    # Check if remote branch exists
                    remote_branches = [
                        ref.name.split("/")[-1]
                        for ref in origin.refs
                        if not ref.name.endswith("/HEAD")
                    ]
                    if current_branch in remote_branches:
                        # Check if there are remote changes
                        try:
                            local_commit = repo.head.commit.hexsha
                            remote_commit = origin.refs[current_branch].commit.hexsha

                            if local_commit != remote_commit:
                                info(
                                    f"📥 Pulling latest changes from remote '{current_branch}'..."
                                )
                                repo.git.pull("origin", current_branch)
                                info("Successfully merged remote changes")
                        except GitCommandError as e:
                            warning(f"Could not pull from remote: {e}")
                            info("Continuing with local changes only")

                except Exception as e:
                    warning(f"Smart pull failed: {e}")
                    info("Continuing without remote sync")

            # Stage specific files
            repo.index.add(file_paths)

            # Check if there are changes to commit
            if not repo.index.diff("HEAD"):
                info("📝 No changes to commit")
                return False

            # Commit changes
            repo.index.commit(commit_message)

            # Push to remote
            try:
                origin = repo.remote("origin")
                origin.push(refspec=f"{current_branch}:{current_branch}")
                return True
            except GitCommandError as e:
                if "non-fast-forward" in str(e) or "rejected" in str(e):
                    error(
                        f"Push rejected - remote has newer changes. Try pulling first: {e}"
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
                ref.name.split("/")[-1]
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
                    ref.name.split("/")[-1]
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


# Legacy function for backward compatibility
def validate_and_setup_git_repo(
    username: str,
    token: str,
    repo_url: str,
    work_branch: str = "feature/export---",
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
    username: str, token: str, repo_url: str, branch: str = None
) -> GitManager:
    """Optimized setup for export operations - minimal validation

    Args:
        username: Git username
        token: Git token
        repo_url: Repository URL
        branch: Optional branch name. If None, uses default work branch
    """
    git_manager = GitManager(username, token, repo_url)

    # Quick validation (cached if done recently)
    try:
        repo_info = git_manager.validate_credentials()
        git_manager.get_or_create_repo(repo_info)

        if branch:
            git_manager.ensure_branch(branch)
        else:
            git_manager.ensure_work_branch()

        return git_manager
    except Exception as e:
        raise RuntimeError(f"Git setup failed: {e}")


def setup_git_for_import(
    username: str, token: str, repo_url: str, branch: str = None
) -> GitManager:
    """Setup Git for import operations with optional branch selection

    Args:
        username: Git username
        token: Git token
        repo_url: Repository URL
        branch: Optional branch name to import from. If None, uses current/default branch
    """
    git_manager = GitManager(username, token, repo_url)

    try:
        repo_info = git_manager.validate_credentials()
        git_manager.get_or_create_repo(repo_info)

        if branch:
            # For import, we want to switch to the specified branch but
            # not create it if it doesn't exist
            branches = git_manager.branch_exists(branch)
            if branches["local"] or branches["remote"]:
                git_manager.ensure_branch(branch, create_from_default=False)
            else:
                raise RuntimeError(
                    f"Branch '{branch}' does not exist locally or remotely"
                )
        else:
            # Use current branch or default
            current_branch = (
                git_manager.get_current_branch() if git_manager._repo_cache else None
            )
            if not current_branch:
                git_manager.ensure_work_branch()

        return git_manager
    except Exception as e:
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
