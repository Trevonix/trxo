"""
Configuration management commands.

This module contains the main typer commands for configuration management.
"""

import json
from typing import Optional

import typer

from trxo_lib.logging import LogLevel, get_logger, setup_logging
from trxo_lib.utils.config_store import ConfigStore
from trxo.utils.console import error, info, success, warning

from .auth_handler import (
    setup_onprem_auth,
    setup_service_account_auth,
)
from .settings import display_config, get_credential_value

app = typer.Typer(help="Manage project configuration")
config_store = ConfigStore()


@app.command()
def setup(
    auth_mode: Optional[str] = typer.Option(
        None,
        "--auth-mode",
        help="Authentication mode: service-account or onprem",
        case_sensitive=False,
    ),
    base_url: Optional[str] = typer.Option(
        None, "--base-url", help="Base URL for PingOne Advanced Identity Cloud instance"
    ),
    am_base_url: Optional[str] = typer.Option(
        None, "--am-base-url", help="On-Prem AM base URL"
    ),
    jwk_path: Optional[str] = typer.Option(
        None, "--jwk-path", help="Path to JWK private key file"
    ),
    sa_id: Optional[str] = typer.Option(None, "--sa-id", help="Service Account ID"),
    onprem_username: Optional[str] = typer.Option(
        None, "--onprem-username", help="On-Prem AM username"
    ),
    onprem_realm: Optional[str] = typer.Option(
        "root", "--onprem-realm", help="On-Prem AM realm (default: root)"
    ),
    idm_base_url: Optional[str] = typer.Option(
        None, "--idm-base-url", help="On-Prem IDM base URL (if different from AM)"
    ),
    idm_username: Optional[str] = typer.Option(
        None, "--idm-username", help="On-Prem IDM username"
    ),
    regions: Optional[str] = typer.Option(None, "--regions", help="Regions"),
    storage_mode: Optional[str] = typer.Option(
        None, "--storage-mode", help="Storage mode: git (default) or local"
    ),
    git_username: Optional[str] = typer.Option(
        None, "--git-username", help="Git username"
    ),
    git_repo: Optional[str] = typer.Option(
        None, "--git-repo", help="Git repository name"
    ),
    git_token: Optional[str] = typer.Option(None, "--git-token", help="Git token"),
):
    """Configure authentication for current project"""
    current_project = config_store.get_current_project()

    if not current_project:
        error("No active project. Run 'trxo project create <name>' first")
        raise typer.Exit(1)

    # Get existing config
    existing_config = config_store.get_project_config(current_project) or {}
    has_existing_config = bool(
        existing_config.get("base_url") or existing_config.get("am_base_url")
    )

    provided_args = {
        "auth_mode": auth_mode,
        "base_url": base_url,
        "am_base_url": am_base_url,
        "jwk_path": jwk_path,
        "sa_id": sa_id,
        "onprem_username": onprem_username,
        "onprem_realm": onprem_realm,
        "idm_base_url": idm_base_url,
        "idm_username": idm_username,
        "regions": regions,
        "storage_mode": storage_mode,
        "git_username": git_username,
        "git_repo": git_repo,
        "git_token": git_token,
    }

    # check if user passed ANY override
    has_any_override = any(v is not None for v in provided_args.values())

    force_interactive = False
    if has_existing_config and not has_any_override:
        info(f"Found existing configuration for project '{current_project}'")
        if typer.confirm(
            "Do you want to update configuration interactively?", default=False
        ):
            force_interactive = True
        else:
            info("Use flags to override specific values, e.g. --git-token <token>")
            raise typer.Exit(0)

    # Resolve auth_mode_value (prefer argument, then existing, then default)
    auth_mode_value = (
        (auth_mode or existing_config.get("auth_mode", "service-account"))
        .lower()
        .strip()
    )

    # If git token not provided, try retrieving from keyring
    if not git_token and (
        storage_mode == "git" or existing_config.get("storage_mode") == "git"
    ):
        creds = config_store.get_git_credentials(current_project)
        if creds:
            git_token = creds.get("token")

    info(f"Configuring project: [bold]{current_project}[/bold]\n")

    if (
        not any(
            [
                jwk_path,
                sa_id,
                base_url,
                onprem_username,
                idm_username,
                am_base_url,
                idm_base_url,
            ]
        )
        and not has_existing_config
    ):
        # Explain what we're doing
        warning("No saved configuration found or arguments provided.")
        info("Please enter your configuration details.")

    # Optional fields (Storage mode can be prompted early)
    storage_mode_value = get_credential_value(
        storage_mode,
        "storage_mode",
        existing_config,
        "\nStorage mode (git|local)",
        required=False,
        force_prompt=force_interactive,
    )

    regions_value = get_credential_value(
        regions,
        "regions",
        existing_config,
        "\nRegions (comma-separated)",
        required=False,
        force_prompt=force_interactive,
    )

    if auth_mode_value == "service-account":
        config = setup_service_account_auth(
            existing_config=existing_config,
            jwk_path=jwk_path,
            sa_id=sa_id,
            base_url=base_url,
            regions=regions_value,
            storage_mode=storage_mode_value,
            git_username=git_username,
            git_repo=git_repo,
            git_token=git_token,
            current_project=current_project,
            force_prompt=force_interactive,
        )

    elif auth_mode_value == "onprem":
        config = setup_onprem_auth(
            existing_config=existing_config,
            onprem_username=onprem_username,
            onprem_realm=onprem_realm,
            base_url=base_url,
            storage_mode=storage_mode_value,
            git_username=git_username,
            git_repo=git_repo,
            git_token=git_token,
            current_project=current_project,
            idm_base_url=idm_base_url,
            idm_username=idm_username,
            am_base_url=am_base_url,
            force_prompt=force_interactive,
        )
    else:
        error("Invalid --auth-mode. Use 'service-account' or 'onprem'")
        raise typer.Exit(1)

    # Update project config
    existing_config.update(config)
    config_store.save_project(current_project, existing_config)

    success(f"Configuration saved for project '{current_project}'")


@app.command("show")
def show():
    """Show current project configuration"""
    current_project = config_store.get_current_project()

    if not current_project:
        error("No active project")
        raise typer.Exit(1)

    config = config_store.get_project_config(current_project)
    display_config(current_project, config)


@app.command("set-log-level")
def set_log_level(
    level: str = typer.Argument(..., help="Log level (DEBUG, INFO, WARNING, ERROR)")
) -> None:
    """Set the logging level for TRXO"""
    setup_logging()
    logger = get_logger("trxo.config.log_level")

    try:
        # Validate log level
        level_upper = level.upper()
        valid_levels = [lev.value for lev in LogLevel]

        if level_upper not in valid_levels:
            error(
                f"Invalid log level '{level}'. Valid levels: {', '.join(valid_levels)}"
            )
            raise typer.Exit(1)

        # Store log level in global settings file
        global_settings_file = config_store.base_dir / "settings.json"
        settings = {}
        if global_settings_file.exists():
            try:
                with open(global_settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except (json.JSONDecodeError, IOError):
                settings = {}

        settings["log_level"] = level_upper

        with open(global_settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)

        success(f"Log level set to {level_upper}")
        info("The new log level will take effect on the next TRXO command execution.")
        logger.info(f"Log level changed to {level_upper}")

    except Exception as e:
        logger.error(f"Failed to set log level: {str(e)}")
        error(f"Failed to set log level: {str(e)}")
        raise typer.Exit(1)


@app.command("get-log-level")
def get_log_level() -> None:
    """Get the current logging level for TRxO"""
    setup_logging()
    logger = get_logger("trxo.config.log_level")

    try:
        # Get log level from global settings file
        global_settings_file = config_store.base_dir / "settings.json"
        current_level = "INFO"  # default

        if global_settings_file.exists():
            try:
                with open(global_settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    current_level = settings.get("log_level", "INFO")
            except (json.JSONDecodeError, IOError):
                current_level = "INFO"

        info(f"Current log level: {current_level}")
        logger.debug(f"Retrieved current log level: {current_level}")

    except Exception as e:
        logger.error(f"Failed to get log level: {str(e)}")
        error(f"Failed to get log level: {str(e)}")
        raise typer.Exit(1)
