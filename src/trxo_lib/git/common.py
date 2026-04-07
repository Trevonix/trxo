"""
Common Git utilities.
"""


def extract_branch_name_from_ref(ref_name: str) -> str:
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
