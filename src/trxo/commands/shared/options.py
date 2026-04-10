"""
Shared Typer CLI options for TRXO commands.
"""

from typing import Annotated, Optional

import typer

from trxo.constants import DEFAULT_REALM

# Core Options
RealmOpt = Annotated[
    str,
    typer.Option(
        ...,
        "--realm",
        help=f"Target realm where you want to import (default: {DEFAULT_REALM})",
    ),
]

SrcRealmOpt = Annotated[
    Optional[str],
    typer.Option(
        ...,
        "--src-realm",
        help="The realm path in the directory to select for the import as src (git mode only). Defaults to target realm.",
    ),
]

InputFileOpt = Annotated[
    Optional[str],
    typer.Option(..., "--file", help="Path to JSON file containing items"),
]

# View Options
ViewOpt = Annotated[
    bool,
    typer.Option(
        ...,
        "--view",
        help="Display data in table format instead of exporting to file",
    ),
]

ViewColumnsOpt = Annotated[
    Optional[str],
    typer.Option(
        ...,
        "--view-columns",
        help="Comma-separated list of columns to display (e.g., '_id,name,active')",
    ),
]

# Versioning & Git Options
VersionOpt = Annotated[
    Optional[str],
    typer.Option(..., "--version", help="Custom version name (default: auto)"),
]

NoVersionOpt = Annotated[
    bool,
    typer.Option(
        ...,
        "--no-version",
        help="Disable auto versioning for legacy filenames",
    ),
]

BranchOpt = Annotated[
    Optional[str],
    typer.Option(
        ...,
        "--branch",
        help="Git branch to use (Git mode only)",
    ),
]

CommitMessageOpt = Annotated[
    Optional[str],
    typer.Option(..., "--commit", help="Custom commit message (Git mode only)"),
]

# Import-Specific Options
ForceImportOpt = Annotated[
    bool,
    typer.Option(
        ...,
        "--force-import",
        "-f",
        help="Skip hash validation and force import",
    ),
]

DiffOpt = Annotated[
    bool,
    typer.Option(
        ...,
        "--diff",
        help="Show differences before import",
    ),
]

DryRunOpt = Annotated[
    bool,
    typer.Option(
        ...,
        "--dry-run",
        help=(
            "Validate input and print a medium summary of what a real import "
            "would do; no import API calls. Ignored when --diff is set (diff uses "
            "the API to compare)."
        ),
    ),
]

RollbackOpt = Annotated[
    bool,
    typer.Option(
        ...,
        "--rollback",
        help="Automatically rollback imported items on first failure (requires git storage)",
    ),
]

ContinueOnErrorOpt = Annotated[
    bool,
    typer.Option(
        ...,
        "--continue-on-error/--stop-on-error",
        help="Stop on first error by default; use --continue-on-error to process all items",
    ),
]

WithDepsOpt = Annotated[
    bool,
    typer.Option(
        ...,
        "--with-deps",
        help=(
            "Include AM OAuth2 clients (ssoEntities.oidcId) and their script dependencies "
            "in export/import (applications only)"
        ),
    ),
]

SyncOpt = Annotated[
    bool,
    typer.Option(
        ...,
        "--sync",
        help="Synchronize items (create new, update existing, delete missing)",
    ),
]

CherryPickOpt = Annotated[
    Optional[str],
    typer.Option(
        ...,
        "--cherry-pick",
        help="Comma-separated IDs of specific items to import",
    ),
]

GlobalOpt = Annotated[
    bool,
    typer.Option(
        ...,
        "--global-policy",
        help="Include IDM policies in addition to AM policies",
    ),
]

# Auth & Connection Options
JwkPathOpt = Annotated[
    Optional[str],
    typer.Option(..., "--jwk-path", help="Path to JWK private key file"),
]

SaIdOpt = Annotated[
    Optional[str],
    typer.Option(..., "--sa-id", help="Service Account ID"),
]

BaseUrlOpt = Annotated[
    Optional[str],
    typer.Option(
        ...,
        "--base-url",
        help="Base URL for PingOne Advanced Identity Cloud instance",
    ),
]

ProjectNameOpt = Annotated[
    Optional[str],
    typer.Option(
        ...,
        "--project-name",
        help="Project name for argument mode (optional)",
    ),
]

# Output Options
OutputDirOpt = Annotated[
    Optional[str],
    typer.Option(..., "--dir", help="Output directory for JSON files"),
]

OutputFileOpt = Annotated[
    Optional[str],
    typer.Option(..., "--file", help="Output filename (without .json extension)"),
]

# Auth Mode Overrides
AuthModeOpt = Annotated[
    Optional[str],
    typer.Option(
        ...,
        "--auth-mode",
        help="Auth mode override: service-account|onprem",
    ),
]

# On-Prem Options
OnPremUsernameOpt = Annotated[
    Optional[str],
    typer.Option(..., "--onprem-username", help="On-Prem username"),
]

OnPremPasswordOpt = Annotated[
    Optional[str],
    typer.Option(..., "--onprem-password", help="On-Prem password", hide_input=True),
]

OnPremRealmOpt = Annotated[
    str,
    typer.Option(..., "--onprem-realm", help="On-Prem realm"),
]

AmBaseUrlOpt = Annotated[
    Optional[str],
    typer.Option(..., "--am-base-url", help="On-Prem AM base URL"),
]

IdmBaseUrlOpt = Annotated[
    Optional[str],
    typer.Option(..., "--idm-base-url", help="On-Prem IDM base URL"),
]

IdmUsernameOpt = Annotated[
    Optional[str],
    typer.Option(..., "--idm-username", help="On-Prem IDM username"),
]

IdmPasswordOpt = Annotated[
    Optional[str],
    typer.Option(..., "--idm-password", help="On-Prem IDM password", hide_input=True),
]
