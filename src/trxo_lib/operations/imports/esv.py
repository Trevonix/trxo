"""
ESV (Environment Secrets & Variables) import services.
"""

import base64
import json
from typing import Any, Dict, List

from trxo_lib.config.api_headers import get_headers
from trxo.utils.console import error, info, warning
from trxo_lib.operations.imports.base_importer import BaseImporter


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

            headers = get_headers("esv")
            headers = {**headers, **self.build_auth_headers(token)}

            self.make_http_request(url, "PUT", headers, payload)
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

        headers = get_headers("esv")
        headers = {**headers, **self.build_auth_headers(token)}

        base_endpoint = self.get_api_endpoint(item_id, base_url)

        try:
            # Check if secret exists
            get_resp = self.make_http_request(base_endpoint, "GET", headers)

            if get_resp.status_code == 404:
                # Create secret with first version
                if "valueBase64" not in item_data:
                    warning(
                        f"Secret '{item_id}' does not exist and no 'valueBase64' provided. "
                        "Add it to create the secret."
                    )
                    return False

                # Validate encoding
                encoding = item_data.get("encoding", "generic")
                if encoding not in self.VALID_ENCODINGS:
                    warning(
                        f"Secret '{item_id}' has invalid or missing 'encoding'. "
                        f"Set one of {sorted(self.VALID_ENCODINGS)}."
                    )
                    return False

                # Validate base64 value
                try:
                    base64.b64decode(item_data["valueBase64"], validate=True)
                except Exception:
                    warning(
                        f"Secret '{item_id}' has invalid Base64. Add it with: 'valueBase64': "
                        "'<your_base64_encoded_value>'"
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

                self.make_http_request(base_endpoint, "PUT", headers, payload)
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
                            f"Secret '{item_id}' has invalid Base64. Add it with: 'valueBase64': "
                            "'<your_base64_encoded_value>'"
                        )
                        return False

                    versions_endpoint = f"{base_endpoint}/versions?_action=create"
                    payload = json.dumps({"valueBase64": item_data["valueBase64"]})

                    self.make_http_request(versions_endpoint, "POST", headers, payload)
                    info(f"Created new version for secret '{item_id}'")
                    did_any = True
                else:
                    info(f"Secret '{item_id}' exists. No value update provided.")

                # If description provided, update it
                if "description" in item_data:
                    desc_payload = json.dumps({"description": item_data["description"]})
                    self.make_http_request(
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
                        "No actionable fields provided. Provide 'valueBase64' to "
                        "create a new version or 'description' to update description."
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


class EsvImportService:
    """Service wrapper for ESV import operations."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute_variables(self) -> Any:
        importer = EsvVariablesImporter()
        if "file" in self.kwargs:
            self.kwargs["file_path"] = self.kwargs.pop("file")
        self.kwargs["realm"] = None  # Root-level config
        return importer.import_from_file(**self.kwargs)

    def execute_secrets(self) -> Any:
        importer = EsvSecretsImporter()
        if "file" in self.kwargs:
            self.kwargs["file_path"] = self.kwargs.pop("file")
        self.kwargs["realm"] = None  # Root-level config
        return importer.import_from_file(**self.kwargs)
