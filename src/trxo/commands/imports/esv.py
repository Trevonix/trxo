"""
ESV (Environment Secrets & Variables) import commands.

This module provides import functionality for PingOne Advanced Identity Cloud Environment
Secrets and Variables.
"""

import json
import base64
from typing import List, Dict, Any
import typer
from trxo.utils.console import console, error, info, warning
from .base_importer import BaseImporter


class EsvVariablesImporter(BaseImporter):
    """Importer for PingOne Advanced Identity Cloud Environment Variables"""

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "Environment_Variables"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/environment/variables/{item_id}"

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Update a single Environment Variable via API"""
        item_id = item_data.get("_id")

        if not item_id:
            error(f"Environment Variable '{item_id}' missing _id field, skipping")
            return False

        # Construct URL with Environment Variable ID
        url = self.get_api_endpoint(item_id, base_url)

        if "valueBase64" not in item_data:
            warning(f"Variable '{item_id}' is missing 'valueBase64'. Add it with:")
            warning('  "valueBase64": "<your_base64_encoded_value>"')
            return False

        try:
            # Attempt to decode the Base64 value
            base64.b64decode(item_data["valueBase64"], validate=True)

            payload = json.dumps(item_data)

            headers = {
                "Content-Type": "application/json",
                "Accept-API-Version": "resource=1.0",
            }
            headers = {**headers, **self.build_auth_headers(token)}

            response = self.make_http_request(url, "PUT", headers, payload)
            info(f"Successfully updated Environment Variable: (ID: {item_id})")
            return True

        except Exception as e:
            error(f"Error updating Environment Variable '{item_id}': {str(e)}")
            return False


class EsvSecretsImporter(BaseImporter):
    """Importer for PingOne Advanced Identity Cloud Environment Secrets"""

    VALID_ENCODINGS = {"generic", "pem", "base64hmac", "base64aes"}

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "Environment_Secrets"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/environment/secrets/{item_id}"

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Update a single Environment Secret via API"""
        item_id = item_data.get("_id")
        if not item_id:
            error("Secret missing _id field, skipping")
            return False

        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "resource=2.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        base_endpoint = self.get_api_endpoint(item_id, base_url)

        try:
            # Check if secret exists
            get_resp = self.make_http_request(base_endpoint, "GET", headers)

            if get_resp.status_code == 404:
                # Create secret with first version
                if "valueBase64" not in item_data:
                    warning(
                        f"Secret '{item_id}' does not exist and no 'valueBase64' provided. Add it to create the secret."
                    )
                    return False

                # Validate encoding
                encoding = item_data.get("encoding", "generic")
                if encoding not in self.VALID_ENCODINGS:
                    warning(
                        f"Secret '{item_id}' has invalid or missing 'encoding'. Set one of {sorted(self.VALID_ENCODINGS)}."
                    )
                    return False

                # Validate base64 value
                try:
                    base64.b64decode(item_data["valueBase64"], validate=True)
                except Exception:
                    warning(
                        f"Secret '{item_id}' has invalid Base64. Add it with: 'valueBase64': '<your_base64_encoded_value>'"
                    )
                    return False

                payload = json.dumps(
                    {
                        "description": item_data.get("description", ""),
                        "encoding": encoding,
                        "useInPlaceholders": item_data.get("useInPlaceholders", True),
                        "valueBase64": item_data["valueBase64"],
                    }
                )

                put_resp = self.make_http_request(
                    base_endpoint, "PUT", headers, payload
                )
                info(f"Created secret '{item_id}' with initial version")
                return True

            elif get_resp.status_code == 200:
                # Secret exists
                did_any = False

                # If value provided, create a new version
                if "valueBase64" in item_data:
                    try:
                        base64.b64decode(item_data["valueBase64"], validate=True)
                    except Exception:
                        warning(
                            f"Secret '{item_id}' has invalid Base64. Add it with: 'valueBase64': '<your_base64_encoded_value>'"
                        )
                        return False

                    versions_endpoint = f"{base_endpoint}/versions?_action=create"
                    payload = json.dumps({"valueBase64": item_data["valueBase64"]})

                    post_resp = self.make_http_request(
                        versions_endpoint, "POST", headers, payload
                    )
                    info(f"Created new version for secret '{item_id}'")
                    did_any = True
                else:
                    info(f"Secret '{item_id}' exists. No value update provided.")

                # If description provided, update it
                if "description" in item_data:
                    desc_payload = json.dumps({"description": item_data["description"]})
                    desc_resp = self.make_http_request(
                        f"{base_endpoint}?_action=setDescription",
                        "POST",
                        headers,
                        desc_payload,
                    )
                    info(f"Updated description for secret '{item_id}'")
                    did_any = True

                if did_any:
                    return True
                else:
                    warning(
                        "No actionable fields provided. Provide 'valueBase64' to create a new version or 'description' to update description."
                    )
                    return False

            else:
                error(
                    f"Failed to read secret '{item_id}': {get_resp.status_code} - {get_resp.text}"
                )
                return False

        except Exception as e:
            error(f"Error processing secret '{item_id}': {str(e)}")
            return False


def create_esv_commands():
    """Create ESV import command functions"""

    def import_esv_variables(
        file: str = typer.Option(
            None,
            "--file",
            help="Path to JSON file containing Environment Variables data",
        ),
        force_import: bool = typer.Option(
            False, "--force-import", "-f", help="Skip hash validation and force import"
        ),
        diff: bool = typer.Option(
            False, "--diff", help="Show differences before import"
        ),
        branch: str = typer.Option(
            None, "--branch", help="Git branch to import from (Git mode only)"
        ),
        rollback: bool = typer.Option(
            False,
            "--rollback",
            help="Automatically rollback imported items on first failure (requires git storage)",
        ),
        jwk_path: str = typer.Option(
            None, "--jwk-path", help="Path to JWK private key file"
        ),
        client_id: str = typer.Option(None, "--client-id", help="Client ID"),
        sa_id: str = typer.Option(None, "--sa-id", help="Service Account ID"),
        base_url: str = typer.Option(
            None,
            "--base-url",
            help="Base URL for PingOne Advanced Identity Cloud instance",
        ),
        project_name: str = typer.Option(
            None, "--project-name", help="Project name for argument mode (optional)"
        ),
        auth_mode: str = typer.Option(
            None, "--auth-mode", help="Auth mode override: service-account|onprem"
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
    ):
        """Import Environment Variables configuration from JSON file"""
        importer = EsvVariablesImporter()
        importer.import_from_file(
            file_path=file,
            realm=None,  # Root-level config
            jwk_path=jwk_path,
            client_id=client_id,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            force_import=force_import,
            branch=branch,
            diff=diff,
            rollback=rollback,
        )

    def import_esv_secrets(
        file: str = typer.Option(
            None, "--file", help="Path to JSON file containing Environment Secrets data"
        ),
        force_import: bool = typer.Option(
            False, "--force-import", "-f", help="Skip hash validation and force import"
        ),
        diff: bool = typer.Option(
            False, "--diff", help="Show differences before import"
        ),
        branch: str = typer.Option(
            None, "--branch", help="Git branch to import from (Git mode only)"
        ),
        rollback: bool = typer.Option(
            False,
            "--rollback",
            help="Automatically rollback imported items on first failure (requires git storage)",
        ),
        jwk_path: str = typer.Option(
            None, "--jwk-path", help="Path to JWK private key file"
        ),
        client_id: str = typer.Option(None, "--client-id", help="Client ID"),
        sa_id: str = typer.Option(None, "--sa-id", help="Service Account ID"),
        base_url: str = typer.Option(
            None,
            "--base-url",
            help="Base URL for PingOne Advanced Identity Cloud instance",
        ),
        project_name: str = typer.Option(
            None, "--project-name", help="Project name for argument mode (optional)"
        ),
        auth_mode: str = typer.Option(
            None, "--auth-mode", help="Auth mode override: service-account|onprem"
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
    ):
        """Import Environment Secrets configuration from JSON file"""
        importer = EsvSecretsImporter()
        importer.import_from_file(
            file_path=file,
            realm=None,  # Root-level config
            jwk_path=jwk_path,
            client_id=client_id,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            force_import=force_import,
            branch=branch,
            diff=diff,
            rollback=rollback,
        )

    return import_esv_variables, import_esv_secrets


def create_esv_callback():
    """Create ESV callback function"""

    def esv_callback(ctx: typer.Context):
        """Top-level ESV command.

        If run without a subcommand, prints a short guide to help the user.
        """
        if ctx.invoked_subcommand is None:
            console.print()
            warning("No ESV subcommand selected.")
            info("ESV has two subcommands:")
            info("  • secrets")
            info("  • variables")
            console.print()
            info("Run one of:")
            info("  trxo import esv secrets --help")
            info("  trxo import esv variables --help")
            console.print()
            info("Tip: use --help on any command to see options.")
            console.print()
            raise typer.Exit(code=0)

    return esv_callback
