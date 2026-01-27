"""
User settings and credential management.

This module handles user input, credential collection, and configuration display.
"""

from typing import Optional, Dict
from pathlib import Path
from rich.prompt import Prompt
from trxo.utils.console import display_panel, warning


def get_credential_value(
    arg_value: Optional[str],
    config_key: str,
    existing_config: dict,
    prompt_text: str,
    required: bool = True,
) -> Optional[str]:
    """Get credential value with priority: argument > config file > prompt"""
    if arg_value:
        return arg_value

    if existing_config and config_key in existing_config:
        return existing_config[config_key]

    if required:
        return Prompt.ask(prompt_text)
    else:
        return Prompt.ask(prompt_text, default="")


def display_config(current_project: str, config: Dict) -> None:
    """Display current project configuration with sensitive data masked"""
    if not config:
        warning(f"No configuration found for project '{current_project}'")
        return

    # Hide sensitive information
    safe_config = config.copy()

    if "jwk_path" in safe_config:
        safe_config["jwk_path"] = Path(safe_config["jwk_path"]).name

    # Never show JWK content; show only keyring status, kid, fingerprint
    if "jwk" in safe_config:
        del safe_config["jwk"]
    if "jwk_keyring" in safe_config:
        safe_config["jwk_keyring"] = bool(safe_config["jwk_keyring"])
    if "jwk_kid" in safe_config and safe_config["jwk_kid"]:
        # mask kid partially
        kid = str(safe_config["jwk_kid"])
        if len(kid) > 6:
            safe_config["jwk_kid"] = kid[:3] + "*" * (len(kid) - 6) + kid[-3:]

    config_text = "\n".join([f"{key}: {value}" for key, value in safe_config.items()])
    display_panel(config_text, f"Configuration for '{current_project}'", "blue")


def process_regions_value(regions_value: Optional[str]) -> list:
    """Process regions value into a list format"""
    if not regions_value:
        return []
    
    if isinstance(regions_value, list):
        return regions_value
    
    return [r.strip() for r in regions_value.split(",") if r.strip()]
