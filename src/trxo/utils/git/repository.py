"""
Git repository management (cloning, initialization, path resolution).
"""

import shutil
from pathlib import Path
from git import Repo, GitCommandError, InvalidGitRepositoryError
from trxo.utils.console import info
from trxo.logging import get_logger

logger = get_logger("trxo.utils.git.repository")


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
    # Don't create the directory here, as it might confuse clone operations logic
    # checking for existence. But the original code created it.
    # Original code: repo_path.mkdir(parents=True, exist_ok=True)
    # But clone_from expects empty dir or non-existent.
    # Let's keep consistent with original if possible, but original code had a check "if local_path.exists() and (local_path / .git).exists()"
    # If the dir exists but is empty, clone works.
    if not repo_path.exists():
        repo_path.parent.mkdir(parents=True, exist_ok=True)
    return repo_path


def init_empty_repo(
    local_path: Path, repo_name: str, secure_url: str, repo_info: dict
) -> Repo:
    """Initialize empty repository with initial commit"""
    local_path.mkdir(parents=True, exist_ok=True)
    repo = Repo.init(str(local_path))

    # Create initial branch
    default_branch = repo_info.get("default_branch", "main")
    try:
        repo.git.checkout("-b", default_branch)
    except GitCommandError:
        repo.git.symbolic_ref("HEAD", f"refs/heads/{default_branch}")

    # Create initial commit
    readme_path = local_path / "README.md"
    readme_path.write_text(
        f"# {repo_name}\n\nPingOne Advanced Identity Cloud configuration repository.\n"
    )
    repo.index.add([str(readme_path)])
    repo.index.commit("Initial commit by PingOne Advanced Identity Cloud CLI")

    # Set up remote and push
    try:
        repo.create_remote("origin", secure_url)
    except Exception:
        if "origin" in [r.name for r in repo.remotes]:
            repo.delete_remote("origin")
        repo.create_remote("origin", secure_url)

    # Push initial branch
    origin = repo.remote("origin")
    origin.push(refspec=f"{default_branch}:{default_branch}")
    logger.info(f"Initialized empty repository with '{default_branch}' branch")

    return repo


def clone_or_init_repo(
    local_path: Path, repo_name: str, secure_url: str, repo_info: dict
) -> Repo:
    """Clone existing repo or initialize empty repo"""
    logger.info(f"Setting up repository: {repo_name}")

    try:
        # Try to clone
        repo = Repo.clone_from(secure_url, str(local_path))
        logger.info(f"Repository cloned to: {local_path}")
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
            repo = init_empty_repo(local_path, repo_name, secure_url, repo_info)
        else:
            raise RuntimeError(f"Failed to clone repository: {e}")

    return repo


def get_or_create_repo(
    local_path: Path, repo_name: str, secure_url: str, repo_info: dict
) -> Repo:
    """Get existing repository or create/clone it (one-time setup)"""
    # Check if repo already exists locally
    if local_path.exists() and (local_path / ".git").exists():
        logger.debug(f"Using existing repository: {local_path}")
        info(f"📂 Using existing repository: {local_path}")
        try:
            repo = Repo(str(local_path))
            # Update origin remote with secure URL (with credentials) for auth
            try:
                origin = repo.remote("origin")
                origin.set_url(secure_url)
                logger.debug(f"Updated origin URL for repository")
            except Exception as e:
                logger.debug(f"Could not update origin URL: {e}")
            return repo
        except InvalidGitRepositoryError:
            logger.warning(
                "Local directory exists but is not a valid Git repository. Re-cloning..."
            )
            shutil.rmtree(local_path)

    # Clone or initialize repository
    return clone_or_init_repo(local_path, repo_name, secure_url, repo_info)
