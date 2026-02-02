"""
Git manager (main entry point).
"""

from typing import Optional
from pathlib import Path
from git import Repo

from trxo.utils.console import info, warning, error
from trxo.logging import get_logger
from trxo.constants import DEFAULT_EXPORT_BRANCH

from trxo.utils.git.credentials import validate_credentials, build_secure_url
from trxo.utils.git.repository import get_repo_path, get_or_create_repo
from trxo.utils.git.branches import (
    ensure_branch,
    list_branches,
    branch_exists,
    check_branch_sync_status,
    validate_branch_sync_for_operation,
    get_default_branch,
)
from trxo.utils.git.operations import (
    commit_and_push,
    get_diff,
    is_working_tree_clean,
    get_working_tree_status,
    validate_clean_state_for_operation,
)
from trxo.utils.git.common import extract_branch_name_from_ref

logger = get_logger("trxo.utils.git.manager")


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
        return build_secure_url(self.repo_url, self.username, self.token)

    @staticmethod
    def _extract_branch_name_from_ref(ref_name: str) -> str:
        return extract_branch_name_from_ref(ref_name)

    def validate_credentials(self) -> dict:
        return validate_credentials(self.token, self.repo_url)

    def get_or_create_repo(self, repo_info: dict) -> Repo:
        if self._repo_cache:
            return self._repo_cache

        repo = get_or_create_repo(
            self.local_path, self.repo_name, self.secure_url, repo_info
        )
        self._repo_cache = repo
        return repo

    def ensure_work_branch(
        self, work_branch: str = DEFAULT_EXPORT_BRANCH, validate: bool = False
    ) -> Repo:
        """Ensure work branch exists and is checked out (Legacy support)"""
        repo = self._repo_cache
        if not repo:
            raise RuntimeError("Repository not initialized")

        # Check commits
        try:
            repo.head.commit
            has_commits = True
        except (ValueError, Exception):
            has_commits = False

        if not has_commits:
            info("📝 Repository has no commits. Creating initial structure...")
            self._create_initial_commit(repo)

        if validate:
            repo = ensure_branch(
                repo,
                work_branch,
                create_from_default=True,
                validate_clean=True,
                validate_sync=True,
                operation="work branch setup",
            )
            self._repo_cache = repo
            return repo

        warning(
            "Using ensure_work_branch without validation is deprecated. "
            "Consider using ensure_branch() with validation."
        )

        # Fetch
        try:
            repo.remote("origin").fetch()
        except:
            pass

        default_branch = self._get_default_branch(repo)

        if work_branch in [h.name for h in repo.heads]:
            info(f"🌿 Switching to existing work branch: {work_branch}")
            repo.git.checkout(work_branch)
        else:
            info(f"🌿 Creating work branch '{work_branch}' from '{default_branch}'")
            try:
                repo.git.checkout(default_branch)
                repo.git.checkout("-b", work_branch)
            except Exception as e:
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
        self._repo_cache = ensure_branch(
            self._repo_cache,
            branch_name,
            create_from_default,
            validate_clean,
            validate_sync,
            operation,
        )
        return self._repo_cache

    def _get_default_branch(self, repo: Repo) -> str:
        return get_default_branch(repo)

    def commit_and_push(
        self, file_paths: list, commit_message: str, smart_pull: bool = False
    ) -> bool:
        if smart_pull:
            warning("smart_pull parameter is deprecated.")
        return commit_and_push(self._repo_cache, file_paths, commit_message)

    def get_current_branch(self) -> str:
        if not self._repo_cache:
            raise RuntimeError("Repository not initialized")
        return self._repo_cache.active_branch.name

    def list_branches(self) -> dict:
        return list_branches(self._repo_cache)

    def branch_exists(self, branch_name: str, check_remote: bool = True) -> dict:
        return branch_exists(self._repo_cache, branch_name, check_remote)

    def get_diff(self, file_path: str) -> str:
        return get_diff(self._repo_cache, file_path)

    def is_working_tree_clean(self) -> bool:
        return is_working_tree_clean(self._repo_cache)

    def get_working_tree_status(self) -> dict:
        return get_working_tree_status(self._repo_cache)

    def check_branch_sync_status(self, branch_name: str) -> dict:
        return check_branch_sync_status(self._repo_cache, branch_name)

    def validate_clean_state_for_operation(self, operation: str = "operation") -> None:
        validate_clean_state_for_operation(self._repo_cache, operation)

    def validate_branch_sync_for_operation(
        self, branch_name: str, operation: str = "operation"
    ) -> None:
        validate_branch_sync_for_operation(self._repo_cache, branch_name, operation)

    def _repo_has_commits(self, repo: Repo) -> bool:
        try:
            repo.head.commit
            return True
        except (ValueError, Exception):
            return False

    def _create_initial_commit(self, repo: Repo) -> None:
        default_branch = "main"
        try:
            origin = repo.remote("origin")
            origin.fetch()
            for ref in origin.refs:
                if ref.name.endswith("/HEAD"):
                    if hasattr(ref, "ref"):
                        default_branch = ref.ref.path.split("/")[-1]
                    break
        except:
            pass

        try:
            repo.git.checkout("-b", default_branch)
        except:
            try:
                repo.git.symbolic_ref("HEAD", f"refs/heads/{default_branch}")
            except:
                pass

        readme_path = self.local_path / "README.md"
        readme_path.write_text(
            f"# {self.repo_name}\n\nPingOne Advanced Identity Cloud configuration repository.\n"
        )

        repo.index.add([str(readme_path)])
        repo.index.commit("Initial commit by TRXO CLI")

        try:
            origin = repo.remote("origin")
            origin.push(refspec=f"{default_branch}:{default_branch}")
            logger.info(f"Created initial commit on '{default_branch}' branch")
        except Exception as e:
            logger.warning(f"Created local commit but could not push to remote: {e}")

    def _init_empty_repo(self, repo_info: dict) -> Repo:
        # No-op as repository.py handles this in get_or_create_repo -> clone_or_init_repo -> init_empty_repo
        return self.get_or_create_repo(repo_info)


def setup_git_for_export(
    username: str, token: str, repo_url: str, branch: Optional[str] = None
) -> GitManager:
    git_manager = GitManager(username, token, repo_url)
    try:
        repo_info = git_manager.validate_credentials()
        git_manager.get_or_create_repo(repo_info)

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
        logger.error(f"Git setup for export failed: {e}")
        raise RuntimeError(f"Git setup failed: {e}")


def setup_git_for_import(
    username: str, token: str, repo_url: str, branch: Optional[str] = None
) -> GitManager:
    git_manager = GitManager(username, token, repo_url)
    try:
        logger.debug("Validating Git credentials...")
        repo_info = git_manager.validate_credentials()
        git_manager.get_or_create_repo(repo_info)

        if branch:
            logger.debug(f"Setting up branch '{branch}' for import...")
            branches = git_manager.branch_exists(branch)
            if not (branches["local"] or branches["remote"]):
                raise RuntimeError(
                    f"Branch '{branch}' does not exist locally or remotely."
                )

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
            current_branch = (
                git_manager.get_current_branch() if git_manager._repo_cache else None
            )
            if current_branch:
                logger.debug(f"Using current branch '{current_branch}' for import...")
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
                git_manager.ensure_work_branch()

        return git_manager
    except Exception as e:
        logger.error(f"Git setup for import failed: {e}")
        raise RuntimeError(f"Git setup for import failed: {e}")


# Legacy support
def get_git_manager(username: str, token: str, repo_url: str) -> GitManager:
    return GitManager(username, token, repo_url)


def validate_and_setup_git_repo(
    username: str,
    token: str,
    repo_url: str,
    work_branch: str = DEFAULT_EXPORT_BRANCH,
    preferred_default: str = "main",
) -> Repo:
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
