"""
Common CLI options for import and export commands.

This module provides standardized CLI options that are used across
multiple command types to ensure consistency.
"""

import typer


class CommonOptions:
    """Common CLI options for import and export commands"""

    @staticmethod
    def auth_options():
        """Return authentication-related CLI options"""
        return {
            "jwk_path": typer.Option(
                None, "--jwk-path", help="Path to JWK private key file"
            ),
            "sa_id": typer.Option(None, "--sa-id", help="Service Account ID"),
            "base_url": typer.Option(
                None,
                "--base-url",
                help="Base URL for PingOne Advanced Identity Cloud instance",
            ),
            "am_base_url": typer.Option(
                None, "--am-base-url", help="On-Prem AM base URL"
            ),
            "project_name": typer.Option(
                None,
                "--project-name",
                help="Project name for argument mode (optional)",
            ),
        }

    @staticmethod
    def import_options():
        """Return import-specific CLI options"""
        options = CommonOptions.auth_options()
        options.update(
            {
                "file": typer.Option(
                    ...,
                    "--file",
                    help="Path to JSON file containing data to import",
                ),
            }
        )
        return options

    @staticmethod
    def export_options():
        """Return export-specific CLI options"""
        options = CommonOptions.auth_options()
        options.update(
            {
                "output_dir": typer.Option(
                    None, "--dir", help="Output directory for JSON files"
                ),
                "output_file": typer.Option(
                    None,
                    "--file",
                    help="Output filename (without .json extension)",
                ),
            }
        )
        return options


def create_auth_params():
    """Create authentication parameter definitions for typer commands"""
    return [
        typer.Option(None, "--jwk-path", help="Path to JWK private key file"),
        typer.Option(None, "--sa-id", help="Service Account ID"),
        typer.Option(
            None,
            "--base-url",
            help="Base URL for PingOne Advanced Identity Cloud instance",
        ),
        typer.Option(None, "--am-base-url", help="On-Prem AM base URL"),
        typer.Option(
            None,
            "--project-name",
            help="Project name for argument mode (optional)",
        ),
    ]


def create_import_params():
    """Create import parameter definitions for typer commands"""
    params = create_auth_params()
    params.insert(
        0,
        typer.Option(..., "--file", help="Path to JSON file containing data to import"),
    )
    return params


def create_export_params():
    """Create export parameter definitions for typer commands"""
    params = create_auth_params()
    params.extend(
        [
            typer.Option(None, "--dir", help="Output directory for JSON files"),
            typer.Option(
                None, "--file", help="Output filename (without .json extension)"
            ),
        ]
    )
    return params
