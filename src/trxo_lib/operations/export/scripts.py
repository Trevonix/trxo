"""
Scripts export commands.

This module provides export functionality for
PingOne Advanced Identity Cloud scripts.
"""

import base64
from typing import Any, Dict


from trxo_lib.config.api_headers import get_headers
from trxo_lib.constants import DEFAULT_REALM
from trxo_lib.utils.console import warning

from trxo_lib.operations.export.base_exporter import BaseExporter


def decode_script_response(response_data: Any) -> Any:
    """
    Decode base64-encoded script fields in the response data.

    This filter processes the API response before saving to make scripts
    human-readable in exported JSON files.

    Args:
        response_data: The API response data (dict with 'result' or list)

    Returns:
        Modified response data with decoded script fields
    """

    def decode_script_field(script_obj: Dict[str, Any]) -> None:
        """Decode the 'script' field in a script object if present."""
        if not isinstance(script_obj, dict):
            return

        script_field = script_obj.get("script")
        if not script_field or not isinstance(script_field, str):
            return

        try:
            # Decode base64 to bytes, then to UTF-8 string
            decoded_bytes = base64.b64decode(script_field, validate=True)
            decoded_text = decoded_bytes.decode("utf-8")

            # Split into array of lines for better readability (Frodo format)
            script_lines = decoded_text.splitlines()
            script_obj["script"] = script_lines
        except Exception as e:
            # If decoding fails, keep original value and log a warning
            script_name = script_obj.get("name", script_obj.get("_id", "Unknown"))
            warning(f"Failed to decode script field for '{script_name}': {str(e)}")

    # Handle different response structures
    if isinstance(response_data, dict):
        # Standard AM API response: {"result": [...], ...}
        if "result" in response_data and isinstance(response_data["result"], list):
            for script_obj in response_data["result"]:
                decode_script_field(script_obj)
        # Single script object
        else:
            decode_script_field(response_data)
    elif isinstance(response_data, list):
        # Direct list of scripts
        for script_obj in response_data:
            decode_script_field(script_obj)

    return response_data

