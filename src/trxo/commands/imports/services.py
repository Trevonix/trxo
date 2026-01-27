"""
Services import commands.

Import functionality for PingOne Advanced Identity Cloud services.
Supports both global and realm-based services:
- Global: PUT only (update existing services, no creation)
- Realm: PUT with upsert capability (create or update)

Future-ready with flexible realm selection.
"""

import json
from typing import List, Dict, Any
import typer
from trxo.utils.console import error, info, warning
from .base_importer import BaseImporter
from trxo.constants import DEFAULT_REALM


class ServicesImporter(BaseImporter):
    """Importer for PingOne Advanced Identity Cloud services with scope-aware behavior"""

    def __init__(self, scope: str = "global", realm: str = DEFAULT_REALM):
        super().__init__()
        self.scope = scope.lower()
        self.realm = realm

    def get_required_fields(self) -> List[str]:
        return []  # We need _type object which contains _id

    def get_item_type(self) -> str:
        # Use consistent naming for hash validation
        return "services"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        if self.scope == "global":
            return self._construct_api_url(
                base_url, f"/am/json/global-config/services/{item_id}"
            )
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/"
            f"realm-config/services/{item_id}",
        )

    def _prepare_service_payload(self, item_data: Dict[str, Any]) -> str:
        """Prepare service payload by removing dynamic fields."""
        # Remove dynamic fields that should not be imported
        excluded_fields = {
            "_rev",
            "_lastModified",
            "_lastModifiedBy",
            "_id",
            "_type",
        }

        # Keep all service configuration data except excluded fields
        service_config = {
            k: v for k, v in item_data.items() if k not in excluded_fields
        }

        return json.dumps(service_config, indent=2)

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Update service based on scope (global=update only, realm=upsert)"""
        # Get service ID from _type._id field
        item_id = item_data.get("_id")
        if not item_id:
            type_info = item_data.get("_type", {})
            item_id = type_info.get("_id")
            if not item_id:
                error("Service missing '_type._id'; required for service operations")
                return False

        # Extract nextDescendents before processing existing payload
        next_descendents = item_data.pop("nextDescendents", [])

        payload = self._prepare_service_payload(item_data)

        url = self.get_api_endpoint(item_id, base_url)
        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=2.1,resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, payload)

            if self.scope == "global":
                info(f"Updated global service: {item_id}")
                # Note: Global services can only be updated, not created
            else:
                info(f"Upserted realm service ({self.realm}): {item_id}")

            # Process descendants if any
            if next_descendents:
                info(
                    f"Processing {len(next_descendents)} descendants for "
                    f"service '{item_id}'..."
                )
                for descendant in next_descendents:
                    desc_type = descendant.get("_type", {}).get("_id")
                    desc_id = descendant.get("_id")
                    if desc_type and desc_id:
                        # Construct URL: service_url / type / id
                        desc_url = f"{url}/{desc_type}/{desc_id}"

                        # Prepare payload (remove _rev)
                        desc_payload_data = {
                            k: v for k, v in descendant.items() if k not in ["_rev"]
                        }
                        desc_payload = json.dumps(desc_payload_data, indent=2)

                        # Fetch schema to ensure payload completeness
                        desc_schema_url = f"{url}/{desc_type}?_action=schema"
                        try:
                            desc_schema_response = self.make_http_request(
                                desc_schema_url, "POST", headers
                            )
                            if (
                                desc_schema_response
                                and desc_schema_response.status_code == 200
                            ):
                                desc_schema = desc_schema_response.json()
                                schema_properties = desc_schema.get("properties", {})

                                # Compare and add missing fields
                                for prop, prop_def in schema_properties.items():
                                    if prop not in desc_payload_data:
                                        # Determine default value based on type
                                        prop_type = prop_def.get("type", "string")
                                        default_val = ""

                                        if prop_type == "boolean":
                                            default_val = False
                                        elif (
                                            prop_type == "integer"
                                            or prop_type == "number"
                                        ):
                                            default_val = 0
                                        elif prop_type == "array":
                                            default_val = []
                                        elif prop_type == "object":
                                            default_val = {}

                                        desc_payload_data[prop] = default_val

                                # Update payload with added fields
                                desc_payload = json.dumps(desc_payload_data, indent=2)
                        except Exception as e:
                            # Log warning but proceed with original payload
                            warning(
                                f"Could not validate schema for descendant "
                                f"{desc_id}: {e}"
                            )
                        try:
                            self.make_http_request(
                                desc_url, "PUT", headers, desc_payload
                            )
                        except Exception as de:
                            warning(
                                f"Failed to update descendant {desc_id} for "
                                f"service {item_id}: {de}"
                            )
                    else:
                        warning(
                            f"Skipping descendant without _type._id or _id in "
                            f"service {item_id}"
                        )

            return True
        except Exception as e:
            action = "update" if self.scope == "global" else "upsert"
            error(f"Failed to {action} service '{item_id}': {e}")
            return False


def create_services_import_command():
    """Create the services import command function"""

    def import_services(
        file: str = typer.Option(
            None,
            "--file",
            help="Path to JSON file containing services data (local mode only)",
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
        force_import: bool = typer.Option(
            False, "--force-import", "-f", help="Skip hash validation and force import"
        ),
        diff: bool = typer.Option(
            False, "--diff", help="Show differences before import"
        ),
        branch: str = typer.Option(
            None, "--branch", help="Git branch to import from (Git mode only)"
        ),
        cherry_pick: str = typer.Option(
            None,
            "--cherry-pick",
            help=(
                "Import only specific services with these IDs(_id) "
                "(comma-separated for multiple IDs)"
            ),
        ),
        scope: str = typer.Option(
            "realm",
            "--scope",
            help="Service scope: 'global' (update only) or 'realm' (upsert)",
        ),
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Target realm name (used when scope=realm, default: {DEFAULT_REALM})",
        ),
    ):
        """Import services from JSON file or Git repository."""

        # Validate scope
        if scope.lower() not in ["global", "realm"]:
            error("Invalid scope. Use 'global' or 'realm'")
            raise typer.Exit(1)

        # Show behavior info
        if scope.lower() == "global":
            info("Global scope: Will update existing services only (no creation)")
        else:
            info(f"Realm scope ({realm}): Will create or update services (upsert)")

        importer = ServicesImporter(scope=scope, realm=realm)
        importer.import_from_file(
            file_path=file,
            realm=realm if scope.lower() == "realm" else "global",
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
            cherry_pick=cherry_pick,
        )

    return import_services
