"""
Git operations (commit, push, status, diff).
"""

import os
from contextlib import redirect_stderr
from git import Repo, GitCommandError
from trxo.logging import get_logger

logger = get_logger("trxo.utils.git.operations")


def get_diff(repo: Repo, file_path: str) -> str:
    """Get diff for a specific file"""
    if not repo:
        return ""
    try:
        return repo.git.diff("HEAD", file_path)
    except Exception:
        return ""


def is_working_tree_clean(repo: Repo) -> bool:
    """Check if working tree is clean (no uncommitted or untracked changes)"""
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


def get_working_tree_status(repo: Repo) -> dict:
    """
    Get detailed working tree status

    Returns:
        dict with keys: 'clean', 'uncommitted_changes', 'untracked_files'
    """
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


def validate_clean_state_for_operation(
    repo: Repo, operation: str = "operation"
) -> None:
    """Validate that working tree is clean before performing Git operations"""
    status = get_working_tree_status(repo)

    if not status["clean"]:
        error_msg = (
            f"Cannot proceed with {operation}: working tree has uncommitted changes.\n"
        )

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


def commit_and_push(repo: Repo, file_paths: list, commit_message: str) -> bool:
    """Commit specific files and push to remote"""
    if not repo:
        raise RuntimeError("Repository not initialized")

    try:
        current_branch = repo.active_branch.name

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
