"""
SAML export commands.

This module provides export functionality for PingOne Advanced Identity
Cloud SAML configurations.
"""

import base64
import typer
from typing import Any, Dict, List
from trxo.utils.console import warning, info, error
from .base_exporter import BaseExporter
from trxo.constants import DEFAULT_REALM


class SamlExporter(BaseExporter):
    def export_as_dict(
        self,
        realm: str = DEFAULT_REALM,
        jwk_path=None,
        client_id=None,
        sa_id=None,
        base_url=None,
        project_name=None,
        auth_mode=None,
        onprem_username=None,
        onprem_password=None,
        onprem_realm="root",
    ):
        headers = {
            "Accept-API-Version": "protocol=2.1,resource=1.0",
            "Content-Type": "application/json",
        }

        api_endpoint = (
            f"/am/json/realms/root/realms/{realm}/realm-config/saml2?_queryFilter=true"
        )

        captured = {}
        original_save_response = self.save_response

        def capture_save_response(payload, *args, **kwargs):
            # 👇 SAML exporter sends the final structured dict directly
            captured["data"] = payload
            return None

        self.save_response = capture_save_response

        try:
            self.export_data(
                command_name="saml",
                api_endpoint=api_endpoint,
                headers=headers,
                view=False,
                jwk_path=jwk_path,
                client_id=client_id,
                sa_id=sa_id,
                base_url=base_url,
                project_name=project_name,
                auth_mode=auth_mode,
                onprem_username=onprem_username,
                onprem_password=onprem_password,
                onprem_realm=onprem_realm,
                response_filter=process_saml_response(self, realm),
            )
        finally:
            self.save_response = original_save_response

        return captured.get("data") or {}


def process_saml_response(exporter_instance: BaseExporter, realm: str):
    """
    Process SAML response to fetch complete data including hosted/remote
    providers, metadata, and referenced scripts.

    This is a response filter that gets the complete SAML export data with
    all dependencies.

    Args:
        exporter_instance: The BaseExporter instance for making API calls
        realm: The realm name

    Returns:
        Function that processes the initial API response
    """

    def filter_function(response_data: Any, **kwargs) -> Dict[str, Any]:
        """
        Filter function to process SAML response and fetch complete data.

        Args:
            response_data: Initial API response with SAML providers list

        Returns:
            Complete SAML export data with hosted, remote, metadata, and scripts
        """
        # Get authentication details from the exporter instance
        token, api_base_url = exporter_instance.get_current_auth()

        headers = {
            "Accept-API-Version": "protocol=2.1,resource=1.0",
            "Content-Type": "application/json",
            **exporter_instance.build_auth_headers(token),
        }

        # Initialize result structure
        result = {"hosted": [], "remote": [], "metadata": [], "scripts": []}

        # Track entity IDs for metadata fetching
        entity_ids_list = []

        # Step 1: Get SAML providers list
        providers_endpoint = (
            f"/am/json/realms/root/realms/{realm}/realm-config/saml2"
            "?_queryFilter=true"
        )

        providers_url = exporter_instance._construct_api_url(
            api_base_url, providers_endpoint
        )

        try:
            # info("Fetching SAML providers list...")
            providers_response = exporter_instance.make_http_request(
                providers_url, "GET", headers
            )
            providers_data = providers_response.json()

            if isinstance(providers_data, dict) and "result" in providers_data:
                providers_list = providers_data["result"]
                # info(f"Found {len(providers_list)} SAML provider(s)")

                # Step 2: Fetch complete data for each provider
                for provider in providers_list:
                    provider_id = provider.get("_id")
                    location = provider.get("location")  # 'hosted' or 'remote'
                    entity_id = provider.get("entityId")

                    if not provider_id or not location:
                        warning(
                            f"Skipping provider with missing _id or location: {provider}"
                        )
                        continue

                    # info(f"Fetching {location} provider: {entity_id or provider_id}")

                    # Get complete provider data
                    provider_endpoint = (
                        f"/am/json/realms/root/realms/{realm}"
                        f"/realm-config/saml2/{location}/{provider_id}"
                    )

                    provider_url = exporter_instance._construct_api_url(
                        api_base_url, provider_endpoint
                    )

                    try:
                        provider_detail_response = exporter_instance.make_http_request(
                            provider_url, "GET", headers
                        )
                        provider_detail = provider_detail_response.json()

                        # Step 3: Extract and fetch scripts referenced in the provider data
                        script_ids = extract_script_ids(provider_detail)
                        if script_ids:
                            fetch_scripts(
                                exporter_instance,
                                realm,
                                script_ids,
                                result["scripts"],
                                token,
                                api_base_url,
                            )

                        # Store provider data in appropriate array
                        if location == "hosted":
                            result["hosted"].append(provider_detail)
                        elif location == "remote":
                            result["remote"].append(provider_detail)

                        # Track entity ID for metadata fetching
                        if entity_id and entity_id not in entity_ids_list:
                            entity_ids_list.append(entity_id)

                    except Exception as e:
                        error(f"Failed to fetch provider {provider_id}: {str(e)}")
                        continue

            else:
                warning("No SAML providers found in the response")

        except Exception as e:
            error(f"Failed to fetch SAML providers list: {str(e)}")

        # Step 4: Get SAML metadata for each provider individually
        if entity_ids_list:
            # info(f"Fetching SAML metadata for {len(entity_ids_list)} provider(s)...")

            for entity_id in entity_ids_list:
                try:
                    # Use the JSP endpoint to export metadata for each entity
                    metadata_endpoint = f"/am/saml2/jsp/exportmetadata.jsp?entityid={entity_id}&realm={realm}"

                    metadata_url = exporter_instance._construct_api_url(
                        api_base_url, metadata_endpoint
                    )

                    # info(f"Fetching metadata for entity: {entity_id}")
                    metadata_response = exporter_instance.make_http_request(
                        metadata_url, "GET", headers
                    )

                    # The JSP endpoint returns XML metadata as text
                    metadata_xml = metadata_response.text

                    # Store metadata as object in array
                    result["metadata"].append(
                        {"entityId": entity_id, "xml": metadata_xml}
                    )

                except Exception as e:
                    warning(
                        f"Failed to fetch metadata for entity '{entity_id}': "
                        f"{str(e)}"
                    )
        else:
            info("No SAML providers found, skipping metadata export")

        return result

    return filter_function


def extract_script_ids(data: Any, script_ids: List[str] = None) -> List[str]:
    """
    Recursively extract script IDs from keys ending with 'Script' in the data structure.

    Args:
        data: The data structure to search (dict, list, or primitive)
        script_ids: Accumulator for script IDs (used in recursion)

    Returns:
        List of unique script IDs found
    """
    if script_ids is None:
        script_ids = []

    if isinstance(data, dict):
        for key, value in data.items():
            # Check if key ends with 'Script' and value looks like a UUID/script ID
            if key.endswith("Script") and isinstance(value, str) and value:
                # Check if it looks like a UUID pattern (loose check)
                if len(value) > 10 and ("-" in value or len(value) == 36):
                    if value not in script_ids:
                        script_ids.append(value)
            # Recurse into nested structures
            elif isinstance(value, (dict, list)):
                extract_script_ids(value, script_ids)

    elif isinstance(data, list):
        for item in data:
            extract_script_ids(item, script_ids)

    return script_ids


def fetch_scripts(
    exporter_instance: BaseExporter,
    realm: str,
    script_ids: List[str],
    scripts_list: List[Dict[str, Any]],
    token: str,
    api_base_url: str,
):
    """
    Fetch script details for the given script IDs and decode them.

    Args:
        exporter_instance: The BaseExporter instance for making API calls
        realm: The realm name
        script_ids: List of script IDs to fetch
        scripts_list: List to store the fetched scripts (array-based)
        token: Authentication token
        api_base_url: Base URL for API calls
    """
    headers = {
        "Accept-API-Version": "protocol=2.1,resource=1.0",
        "Content-Type": "application/json",
        **exporter_instance.build_auth_headers(token),
    }

    # Track already fetched script IDs to prevent duplicates
    existing_script_ids = {script["_id"] for script in scripts_list if "_id" in script}

    for script_id in script_ids:
        if script_id in existing_script_ids:
            # Already fetched this script
            continue

        try:
            # info(f"Fetching script: {script_id}")
            script_endpoint = f"/am/json/realms/root/realms/{realm}/scripts/{script_id}"
            script_url = exporter_instance._construct_api_url(
                api_base_url, script_endpoint
            )

            script_response = exporter_instance.make_http_request(
                script_url, "GET", headers
            )
            script_data = script_response.json()

            # Decode the script field if present (similar to scripts.py)
            if isinstance(script_data, dict) and "script" in script_data:
                script_field = script_data.get("script")
                if isinstance(script_field, str):
                    try:
                        # Decode base64 to bytes, then to UTF-8 string
                        decoded_bytes = base64.b64decode(script_field, validate=True)
                        decoded_text = decoded_bytes.decode("utf-8")

                        # Split into lines for readability
                        script_lines = decoded_text.splitlines()
                        script_data["script"] = script_lines
                    except Exception as e:
                        script_name = script_data.get("name", script_id)
                        warning(f"Failed to decode script '{script_name}': {str(e)}")

            # Append script to array
            scripts_list.append(script_data)
            existing_script_ids.add(script_id)

        except Exception as e:
            warning(f"Failed to fetch script {script_id}: {str(e)}")


def create_saml_export_command():
    """Create the SAML export command function"""

    def export_saml(
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Target realm name (default: {DEFAULT_REALM})",
        ),
        view: bool = typer.Option(
            False,
            "--view",
            help="Display data in table format instead of exporting to file",
        ),
        view_columns: str = typer.Option(
            None,
            "--view-columns",
            help=(
                "Comma-separated list of columns to display "
                "(e.g., '_id,name,active')"
            ),
        ),
        version: str = typer.Option(
            None, "--version", help="Custom version name (default: auto)"
        ),
        no_version: bool = typer.Option(
            False,
            "--no-version",
            help="Disable auto versioning for legacy filenames",
        ),
        branch: str = typer.Option(
            None,
            "--branch",
            help="Git branch to use for export (Git mode only)",
        ),
        commit: str = typer.Option(
            None, "--commit", help="Custom commit message (Git mode only)"
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
        project_name: str = typer.Option(
            None,
            "--project-name",
            help="Project name for argument mode (optional)",
        ),
        output_dir: str = typer.Option(
            None, "--dir", help="Output directory for JSON files"
        ),
        output_file: str = typer.Option(
            None, "--file", help="Output filename (without .json extension)"
        ),
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
        am_base_url: str = typer.Option(
            None, "--am-base-url", help="On-Prem AM base URL"
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
    ):
        """
        Export SAML configuration with complete data including hosted/remote
        providers, metadata, and scripts
        """
        exporter = BaseExporter()

        headers = {
            "Accept-API-Version": "protocol=2.1,resource=1.0",
            "Content-Type": "application/json",
        }

        # Note: The initial API call is just to trigger the export flow.
        # The actual data fetching happens in the response_filter
        exporter.export_data(
            command_name="saml",
            api_endpoint=(
                f"/am/json/realms/root/realms/{realm}/realm-config/saml2"
                "?_queryFilter=true"
            ),
            headers=headers,
            view=view,
            view_columns=view_columns,
            jwk_path=jwk_path,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            output_dir=output_dir,
            output_file=output_file,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            idm_base_url=idm_base_url,
            idm_username=idm_username,
            idm_password=idm_password,
            am_base_url=am_base_url,
            version=version,
            no_version=no_version,
            branch=branch,
            commit_message=commit,
            response_filter=process_saml_response(exporter, realm),
        )

    return export_saml
