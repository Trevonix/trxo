"""
Batch import command for multiple configurations.

Allows importing multiple configuration types in a single command.
Supports both local storage mode (file-based) and Git storage mode.
"""

import typer
from typing import List, Optional, Dict
from pathlib import Path
import json
import re
from trxo.utils.console import info, success, error, warning
from ..imports.manager import app as import_app
from trxo.utils.config_store import ConfigStore
from trxo.constants import DEFAULT_REALM


def create_batch_import_command():
    """Create the batch import command function"""

    def batch_import(
        commands: List[str] = typer.Argument(
            None,
            help=(
                "List of import commands (e.g., scripts services themes "
                "agent.gateway agent.java esv.secrets esv.variables). "
                "Can also specify command:file pairs like 'realms:my_realms.json' "
                "for local mode"
            ),
        ),
        dir: str = typer.Option(
            None,
            "--dir",
            help=(
                "Directory to scan for export files (local mode only, "
                "default: current directory)"
            ),
        ),
        config_file: str = typer.Option(
            None,
            "--config-file",
            help=(
                "JSON config file specifying commands and their files "
                "(legacy local mode)"
            ),
        ),
        scope: str = typer.Option(
            "realm",
            "--scope",
            help="Default scope for applicable commands (global/realm)",
        ),
        realm: str = typer.Option(
            DEFAULT_REALM, "--realm", help="Default realm for applicable commands"
        ),
        branch: str = typer.Option(
            None, "--branch", help="Git branch to import from (Git mode only)"
        ),
        jwk_path: str = typer.Option(
            None, "--jwk-path", help="Path to JWK private key file"
        ),
        sa_id: str = typer.Option(None, "--sa-id", help="Service Account ID"),
        base_url: str = typer.Option(
            None,
            "--base-url",
            help="Base URL for PingOne Advanced Identity Cloud instance",
        ),
        project_name: str = typer.Option(None, "--project-name", help="Project name"),
        auth_mode: str = typer.Option(
            None,
            "--auth-mode",
            help="Auth mode override: service-account|onprem",
        ),
        onprem_username: str = typer.Option(
            None, "--onprem-username", help="On-Prem username"
        ),
        onprem_password: str = typer.Option(
            None, "--onprem-password", help="On-Prem password", hide_input=True
        ),
        onprem_realm: str = typer.Option(
            "root", "--onprem-realm", help="On-Prem realm"
        ),
        idm_base_url: str = typer.Option(
            None, "--idm-base-url", help="On-Prem IDM base URL"
        ),
        idm_username: str = typer.Option(
            None, "--idm-username", help="On-Prem IDM username"
        ),
        idm_password: str = typer.Option(
            None, "--idm-password", help="On-Prem IDM password", hide_input=True
        ),
        continue_on_error: bool = typer.Option(
            True,
            "--continue-on-error/--stop-on-error",
            help="Continue if one command fails",
        ),
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            help="Show what would be imported without actually importing",
        ),
        force_import: bool = typer.Option(
            False,
            "--force-import",
            "-f",
            help="Skip hash validation and force import for all commands",
        ),
        diff: bool = typer.Option(
            False, "--diff", help="Show differences before import for all commands"
        ),
    ):
        """Import multiple configurations in batch

        Supports both Git storage mode and local storage mode:

        Git Mode (automatic when project uses Git storage):
        1. Import from Git: trxo batch import realms themes journeys
        2. Import specific commands: trxo batch import scripts services esv.secrets

        Local Mode (when project uses local storage or files specified):
        1. Auto-discover files: trxo batch import realms themes journeys --dir exports/
        2. Specify files: trxo batch import realms:my_realms.json themes:my_themes.json
        3. Legacy config: trxo batch import --config-file batch_config.json

        Config file format (legacy local mode):
        {
            "imports": [
                {"command": "realms", "file": "realms_export.json"},
                {"command": "agent.gateway", "file": "agents_gateway_export.json"}
            ]
        }
        """

        # Get available commands including sub-commands
        available_commands = typer.main.get_command(import_app).commands
        available_list = set(available_commands.keys())

        # Add sub-commands with dot notation
        esv = available_commands.get("esv")
        if esv:
            available_list |= {f"esv.{k}" for k in esv.commands.keys()}

        agent = available_commands.get("agent")
        if agent:
            available_list |= {f"agent.{k}" for k in agent.commands.keys()}

        # Remove the agent and esv main commands (only sub-commands are valid)
        available_list -= {"agent", "esv"}

        # Determine storage mode
        config_store = ConfigStore()
        storage_mode = _get_storage_mode(config_store)
        info(f"Storage mode: {storage_mode}")

        # Determine working directory (only needed for local mode)
        work_dir = None
        if storage_mode == "local" or dir or config_file:
            work_dir = Path(dir) if dir else Path.cwd()
            info(f"Working directory: {work_dir}")
            if not work_dir.exists():
                error(f"Directory not found: {work_dir}")
                raise typer.Exit(1)

        # Handle different input modes
        if config_file:
            # Legacy mode: use config file (local mode only)
            if storage_mode != "local":
                error("Config file mode only supported in local storage mode")
                raise typer.Exit(1)
            imports = _load_config_file_imports(config_file)
        elif commands:
            # New mode: command-based import (supports both Git and local modes)
            imports = _build_command_imports(
                commands, work_dir, available_list, storage_mode
            )
        else:
            error("No commands specified. Provide commands or use --config-file.")
            raise typer.Exit(1)

        info(f"Starting batch import of {len(imports)} configurations...")
        if storage_mode == "git":
            info("Using Git storage mode - importing from Git repository")
        else:
            info(f"Using local storage mode - working directory: {work_dir}")

        if dry_run:
            info("🔍 DRY RUN MODE - No actual imports will be performed")

        success_count = 0
        failed_commands = []

        for i, import_config in enumerate(imports, 1):
            command = import_config.get("command")
            file_path = import_config.get("file")

            # Validate command
            if not command:
                error(f"Import {i}: Missing 'command' in config")
                failed_commands.append(f"import-{i}")
                continue

            if command not in available_list:
                error(
                    f"Import {i}: Invalid command '{command}'. "
                    f"Available: {', '.join(sorted(available_list))}"
                )
                failed_commands.append(command)
                continue

            # Validate file_path (only required for local mode)
            if storage_mode == "local" and not file_path:
                error(f"Import {i}: Missing 'file' in config for local mode")
                failed_commands.append(f"import-{i}")
                continue

                error(
                    f"Import {i}: Invalid command '{command}'. "
                    f"Available: {', '.join(sorted(available_list))}"
                )
                failed_commands.append(command)
                continue

            # For Git mode, file_path will be None
            if storage_mode == "local":
                file_path = Path(file_path)
                if not file_path.exists():
                    error(f"Import {i}: File not found: {file_path}")
                    failed_commands.append(command)
                    continue
            else:
                # Git mode - file_path should be None
                file_path = None

            print()
            if storage_mode == "git":
                info(
                    f"[{i}/{len(imports)}] Importing {command} from Git "
                    "repository..."
                )
            else:
                info(
                    f"[{i}/{len(imports)}] Importing {command} from " f"{file_path}..."
                )

            if dry_run:
                if storage_mode == "git":
                    info(f"  Would import {command} from Git repository")
                else:
                    info(f"  Would import {command} from {file_path}")
                success_count += 1
                continue

            try:
                # Get command-specific parameters
                cmd_scope = import_config.get("scope", scope)
                cmd_realm = import_config.get("realm", realm)

                # Build parameters for the import command
                import_params = {
                    "file": str(file_path) if file_path else None,  # None for Git mode
                    "branch": branch,  # Git branch to import from
                    "jwk_path": jwk_path,
                    "sa_id": sa_id,
                    "base_url": base_url,
                    "project_name": project_name,
                    "auth_mode": auth_mode,
                    "onprem_username": onprem_username,
                    "onprem_password": onprem_password,
                    "onprem_realm": onprem_realm,
                    "force_import": force_import,
                    "diff": diff,
                }

                # Add scope and realm for applicable commands
                if command in {"services"}:
                    import_params["scope"] = cmd_scope
                    if cmd_scope == "realm":
                        import_params["realm"] = cmd_realm

                # if command in {"themes", "scripts", "services", "journeys",
                #  "webhooks", "endpoints", "privileges"}:
                #     import_params["realm"] = cmd_realm

                # Execute the import command (handle sub-commands with dot notation)
                if "." in command:
                    group, sub = command.split(".", 1)
                    import_command = (
                        typer.main.get_command(import_app).commands[group].commands[sub]
                    )
                else:
                    import_command = typer.main.get_command(import_app).commands[
                        command
                    ]
                import_command.callback(**import_params)

                success(f"{command} imported successfully")
                success_count += 1

            except Exception as e:
                error(f"Failed to import {command}: {e}")
                failed_commands.append(command)

                if not continue_on_error:
                    error("Stopping batch import due to error")
                    raise typer.Exit(1)

        # Summary
        info("\nBatch Import Summary:")
        info(f"Successful: {success_count}/{len(imports)}")
        if failed_commands:
            info(f"Failed: {', '.join(failed_commands)}")

        if success_count == len(imports):
            success("All imports completed successfully!")
        elif success_count > 0:
            warning(
                f"Partial success: {success_count}/{len(imports)} imports completed"
            )
        else:
            error("All imports failed!")
            raise typer.Exit(1)

    return batch_import


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
        raise typer.Exit(1)

    if "imports" not in config:
        error("Config file must contain 'imports' array")
        raise typer.Exit(1)

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
    except (ValueError, typer.Abort):
        return None


def _extract_version_number(filename: str) -> int:
    """Extract version number from filename"""
    match = re.search(r"_v(\d+)_", filename)
    return int(match.group(1)) if match else 0
