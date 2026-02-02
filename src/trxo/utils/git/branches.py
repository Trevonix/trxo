"""
Git branch management (ensure branch, sync check).
"""

import os
from contextlib import redirect_stderr
from git import Repo, GitCommandError
from trxo.utils.console import info
from trxo.logging import get_logger
from trxo.utils.git.common import extract_branch_name_from_ref
from trxo.utils.git.operations import validate_clean_state_for_operation

logger = get_logger("trxo.utils.git.branches")


def get_default_branch(repo: Repo) -> str:
    """Determine the default branch"""
    # Try to get from remote origin
    try:
        if "origin" in [r.name for r in repo.remotes]:
            origin = repo.remote("origin")
            origin.fetch()
            # Look for remote HEAD
            for ref in origin.refs:
                if ref.name.endswith("/HEAD"):
                    if hasattr(ref, "ref"):
                        target_branch = ref.ref.path.split("/")[-1]
                    else:
                        continue
                    if target_branch and target_branch in [h.name for h in repo.heads]:
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


def check_branch_sync_status(repo: Repo, branch_name: str) -> dict:
    """
    Check if local branch is in sync with remote.

    Returns:
        dict with keys: exists_local, exists_remote, behind, ahead, diverged, in_sync
    """
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
            extract_branch_name_from_ref(ref.name)
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
                    result["diverged"] = result["behind"] > 0 and result["ahead"] > 0
                except Exception:
                    # If we can't determine, assume diverged for safety
                    result["diverged"] = True

        return result

    except Exception as e:
        raise RuntimeError(f"Failed to check branch sync status: {e}")


def validate_branch_sync_for_operation(
    repo: Repo, branch_name: str, operation: str = "operation"
) -> None:
    """Validate that branch is properly synced with remote"""
    sync_status = check_branch_sync_status(repo, branch_name)

    # If branch doesn't exist remotely yet, that's okay (new branch)
    if not sync_status["exists_remote"]:
        return

    # If local is behind remote, require pull
    if sync_status["behind"] > 0 and sync_status["ahead"] == 0:
        try:
            # pull first
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


def ensure_branch(
    repo: Repo,
    branch_name: str,
    create_from_default: bool = True,
    validate_clean: bool = True,
    validate_sync: bool = True,
    operation: str = "operation",
) -> Repo:
    """Ensure a specific branch exists and is checked out with proper validation"""
    if not repo:
        raise RuntimeError("Repository not initialized.")

    # Step 1: Validate working tree is clean (if requested)
    if validate_clean:
        logger.debug("Validating working tree is clean...")
        validate_clean_state_for_operation(repo, operation)
        logger.debug("Working tree is clean")

    # Step 2: Fetch latest changes from remote (suppress stderr output)
    logger.debug("Fetching latest changes from remote...")
    try:
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
            extract_branch_name_from_ref(ref.name)
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
            validate_branch_sync_for_operation(repo, branch_name, operation)

            # If validation passed and we're behind, fast-forward pull
            sync_status = check_branch_sync_status(repo, branch_name)
            if sync_status["behind"] > 0 and sync_status["ahead"] == 0:
                logger.info(f"Fast-forward pulling from remote '{branch_name}'...")
                info("📥 Pulling latest changes from remote")
                # Suppress stderr to avoid git messages
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
            raise RuntimeError(f"Failed to checkout remote branch '{branch_name}': {e}")

    else:
        # Branch doesn't exist - create it
        if create_from_default:
            default_branch = get_default_branch(repo)
            info(f"🌿 Creating new branch '{branch_name}' from '{default_branch}'")
            try:
                # Ensure default branch is up to date first
                repo.git.checkout(default_branch)

                # Update default branch if it exists on remote
                if default_branch in remote_branches and validate_sync:
                    sync_status = check_branch_sync_status(repo, default_branch)
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


def list_branches(repo: Repo) -> dict:
    """List all local and remote branches"""
    if not repo:
        raise RuntimeError("Repository not initialized")

    local_branches = [h.name for h in repo.heads]
    remote_branches = []

    try:
        origin = repo.remote("origin")
        origin.fetch()
        remote_branches = [
            extract_branch_name_from_ref(ref.name)
            for ref in origin.refs
            if not ref.name.endswith("/HEAD")
        ]
    except Exception:
        pass

    return {"local": local_branches, "remote": remote_branches}


def branch_exists(repo: Repo, branch_name: str, check_remote: bool = True) -> dict:
    """Check if a branch exists locally and/or remotely"""
    if not repo:
        raise RuntimeError("Repository not initialized")

    local_exists = branch_name in [h.name for h in repo.heads]
    remote_exists = False

    if check_remote:
        try:
            origin = repo.remote("origin")
            origin.fetch()
            remote_branches = [
                extract_branch_name_from_ref(ref.name)
                for ref in origin.refs
                if not ref.name.endswith("/HEAD")
            ]
            remote_exists = branch_name in remote_branches
        except Exception:
            pass

    return {"local": local_exists, "remote": remote_exists}
