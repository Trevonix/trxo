"""
Services export commands.

This module provides export functionality for PingOne Advanced Identity
Cloud services.
Supports both global and realm-based services with flexible realm selection.
Fetches complete service configurations by individual service ID.
"""

import typer
from trxo.utils.console import warning
from .base_exporter import BaseExporter
from trxo.constants import DEFAULT_REALM


class ServicesExporter(BaseExporter):
    """Custom exporter for services that fetches complete configurations"""

    pass


def create_services_export_command():
    """Create the services export command function"""

    def export_services(
        scope: str = typer.Option(
            "realm",
            "--scope",
            help=(
                "Service scope: 'global' for global services or 'realm' "
                "for realm services"
            ),
        ),
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=(
                f"Target realm name (used when scope=realm, "
                f"default: {DEFAULT_REALM})"
            ),
        ),
        view: bool = typer.Option(
            False,
            "--view",
            help="Display data in table format instead of exporting to file",
        ),
        view_columns: str = typer.Option(
            None,
            "--view-columns",
            help="Comma-separated list of columns to display (e.g., '_id,name,active')",
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
        """Export services configuration with complete data for each service"""
        exporter = ServicesExporter()

        headers = {
            "Accept-API-Version": "protocol=2.1,resource=1.0",
            "Content-Type": "application/json",
        }

        # Determine API endpoints and command name based on scope
        if scope.lower() == "global":
            command_name = "services"  # Consistent naming
            api_endpoint = "/am/json/global-config/services?_queryFilter=true"
        elif scope.lower() == "realm":
            command_name = "services"
            api_endpoint = (
                f"/am/json/realms/root/realms/{realm}/realm-config/"
                "services?_queryFilter=true"
            )
        else:
            from trxo.utils.console import error

            error("Invalid scope. Use 'global' or 'realm'")
            raise typer.Exit(1)

        # Custom response filter to fetch complete service configurations
        def services_response_filter(data):
            """Filter to fetch complete service configurations"""
            if not isinstance(data, dict) or "result" not in data:
                return data

            services_list = data["result"]
            if not services_list:
                return data

            # Get authentication details from exporter
            token, api_base_url = exporter.get_current_auth()
            if not token or not api_base_url:
                warning("Authentication not available for detailed service fetch")
                return data

            complete_services = []
            auth_headers = {**headers, **exporter.build_auth_headers(token)}

            for service_summary in services_list:
                service_id = service_summary.get("_id")
                if not service_id:
                    complete_services.append(service_summary)
                    continue

                # Skip problematic services that cannot be processed
                # DataStoreService is a known service that fails during export
                if service_id == "DataStoreService":
                    # info(f"Skipping service '{service_id}' "
                    #      "(known compatibility issue)")
                    continue

                # Build detail endpoint
                if scope.lower() == "global":
                    detail_url = exporter._construct_api_url(
                        api_base_url, f"/am/json/global-config/services/{service_id}"
                    )
                else:
                    detail_url = exporter._construct_api_url(
                        api_base_url,
                        f"/am/json/realms/root/realms/{realm}/"
                        f"realm-config/services/{service_id}",
                    )

                try:
                    detail_response = exporter.make_http_request(
                        detail_url, "GET", auth_headers
                    )
                    complete_service = detail_response.json()

                    # Fetch nextDescendents
                    try:
                        next_descendents_url = f"{detail_url}?_action=nextdescendents"
                        # Use POST as requested
                        nd_response = exporter.make_http_request(
                            next_descendents_url, "POST", auth_headers
                        )
                        nd_result = nd_response.json()

                        descendants = nd_result.get("result", [])
                        # Clean _rev from descendants
                        cleaned_descendants = []
                        for desc in descendants:
                            # Create a copy to avoid modifying original if it matters,
                            # though here it's new data
                            clean_desc = desc.copy()
                            clean_desc.pop("_rev", None)
                            cleaned_descendants.append(clean_desc)

                        complete_service["nextDescendents"] = cleaned_descendants
                    except Exception:
                        # Log warning but continue with service export
                        complete_service["nextDescendents"] = []

                    complete_services.append(complete_service)
                except Exception as e:
                    warning(
                        f"Failed to fetch complete config for service "
                        f"'{service_id}': {e}"
                    )
                    complete_services.append(service_summary)

            # Return data with complete services
            return {**data, "result": complete_services}

        # Use BaseExporter with custom response filter for complete service data
        exporter.export_data(
            command_name=command_name,
            api_endpoint=api_endpoint,
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
            response_filter=services_response_filter,
            version=version,
            no_version=no_version,
            branch=branch,
            commit_message=commit,
        )

    return export_services
