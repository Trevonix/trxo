"""
Batch import command for multiple configurations.

Allows importing multiple configuration types in a single command.
Supports both local storage mode (file-based) and Git storage mode.
"""

from trxo_lib.exceptions import TrxoAbort
import json
import re
from pathlib import Path
from typing import Dict, List, Optional


from trxo_lib.constants import DEFAULT_REALM
from trxo_lib.config.config_store import ConfigStore
from trxo.utils.console import error, info, success, warning

from ..imports.manager import app as import_app


def _get_storage_mode(config_store: ConfigStore) -> str:
    """Get storage mode from project configuration"""
    try:
        current_project = config_store.get_current_project()
        if current_project:
            project_config = config_store.get_project_config(current_project)
            return project_config.get("storage_mode", "local")
        return "local"
    except Exception:
        return "local"


def _load_config_file_imports(config_file: str) -> List[Dict]:
    """Load imports from config file (legacy mode)"""
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
    except Exception as e:
        error(f"Failed to load config file '{config_file}': {e}")
        raise TrxoAbort(code=1)

    if "imports" not in config:
        error("Config file must contain 'imports' array")
        raise TrxoAbort(code=1)

    return config["imports"]


def _build_command_imports(
    commands: List[str],
    work_dir: Optional[Path],
    available_list: set,
    storage_mode: str,
) -> List[Dict]:
    """Build imports from command list (supports both Git and local modes)"""
    imports = []

    for command_spec in commands:
        # Parse command:file or just command
        if ":" in command_spec:
            # Explicit file specification (local mode only)
            if storage_mode != "local":
                error(
                    f"File specification '{command_spec}' only supported in local storage mode"
                )
                continue

            command, specified_file = command_spec.split(":", 1)
            file_path = work_dir / specified_file
            if not file_path.exists():
                error(f"Specified file not found: {file_path}")
                continue
            imports.append({"command": command, "file": str(file_path)})
        else:
            command = command_spec

            if storage_mode == "git":
                # Git mode - no file needed, command will load from Git repository
                imports.append({"command": command, "file": None})
            else:
                # Local mode - auto-discover file for this command
                if not work_dir:
                    error("Working directory required for local storage mode")
                    continue

                file_path = _find_file_for_command(command, work_dir)
                if file_path:
                    imports.append({"command": command, "file": str(file_path)})
                else:
                    error(
                        f"No suitable file found for command '{command}' in {work_dir}"
                    )
                    continue

    return imports


def _find_file_for_command(command: str, work_dir: Path) -> Optional[Path]:
    """Find the best matching file for a command in the directory (local mode only)"""
    # Get all JSON files in the directory
    json_files = list(work_dir.glob("*.json"))

    if not json_files:
        return None

    # Create search patterns for the command
    search_patterns = _get_search_patterns(command)

    # Find files matching any pattern
    matching_files = []
    for pattern in search_patterns:
        for file in json_files:
            if re.search(pattern, file.name, re.IGNORECASE):
                matching_files.append(file)

    if not matching_files:
        return None

    # If multiple files found, let user choose
    if len(matching_files) > 1:
        return _prompt_user_file_choice(command, matching_files)

    return matching_files[0]


def _get_search_patterns(command: str) -> List[str]:
    """Get regex patterns to search for files matching the command"""
    patterns = []

    # Handle sub-commands (e.g., agent.gateway -> agents_gateway)
    if "." in command:
        group, sub = command.split(".", 1)
        # Pattern: group_sub or groups_sub (more flexible matching)
        patterns.extend(
            [
                rf"{group}_{sub}",
                rf"{group}s_{sub}",  # plural
                rf"{sub}_{group}",  # reversed
            ]
        )
    else:
        # Pattern: exact match or plural (more flexible matching)
        patterns.extend(
            [
                rf"{command}",
                rf"{command}s",  # plural
            ]
        )

    return patterns


def _prompt_user_file_choice(command: str, files: List[Path]) -> Optional[Path]:
    """Prompt user to choose from multiple matching files"""
    info(f"Multiple files found for command '{command}':")

    # Group files by version if possible
    versioned_files = []
    other_files = []

    for file in files:
        # Check if file has version pattern
        if re.search(r"_v\d+_", file.name):
            versioned_files.append(file)
        else:
            other_files.append(file)

    # Sort versioned files by version number (highest first)
    if versioned_files:
        versioned_files.sort(
            key=lambda f: _extract_version_number(f.name), reverse=True
        )

    # Combine lists (versioned first, then others)
    sorted_files = versioned_files + other_files

    for i, file in enumerate(sorted_files, 1):
        version_info = ""
        if re.search(r"_v\d+_", file.name):
            version = _extract_version_number(file.name)
            version_info = f" (v{version})"
        info(f"  {i}. {file.name}{version_info}")

    try:
        choice = typer.prompt(
            f"Select file for '{command}' (1-{len(sorted_files)}, or 's' to skip)"
        )
        if choice.lower() == "s":
            return None

        index = int(choice) - 1
        if 0 <= index < len(sorted_files):
            return sorted_files[index]
        else:
            error("Invalid choice")
            return None
    except (ValueError, TrxoAbort):
        return None


def _extract_version_number(filename: str) -> int:
    """Extract version number from filename"""
    match = re.search(r"_v(\d+)_", filename)
    return int(match.group(1)) if match else 0
