"""
Scripts export service execution class.

Decouples export functionality from CLI.
"""

import base64
import logging
from typing import Any, Dict

from trxo_lib.config.api_headers import get_headers
from trxo_lib.constants import DEFAULT_REALM
from trxo_lib.exports.processor import BaseExporter

logger = logging.getLogger(__name__)


def decode_script_response(response_data: Any) -> Any:
    """
    Decode base64-encoded script fields in the response data.
    """

    def decode_script_field(script_obj: Dict[str, Any]) -> None:
        if not isinstance(script_obj, dict):
            return

        script_field = script_obj.get("script")
        if not script_field or not isinstance(script_field, str):
            return

        try:
            decoded_bytes = base64.b64decode(script_field, validate=True)
            decoded_text = decoded_bytes.decode("utf-8")
            script_lines = decoded_text.splitlines()
            script_obj["script"] = script_lines
        except Exception as e:
            script_name = script_obj.get("name", script_obj.get("_id", "Unknown"))
            logger.warning(
                f"Failed to decode script field for '{script_name}': {str(e)}"
            )

    if isinstance(response_data, dict):
        if "result" in response_data and isinstance(response_data["result"], list):
            for script_obj in response_data["result"]:
                decode_script_field(script_obj)
        else:
            decode_script_field(response_data)
    elif isinstance(response_data, list):
        for script_obj in response_data:
            decode_script_field(script_obj)

    return response_data


class ScriptsExportService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        exporter = BaseExporter()
        headers = get_headers("scripts")
        realm = self.kwargs.get("realm", DEFAULT_REALM)

        api_endpoint = f"/am/json/realms/root/realms/{realm}/scripts?_queryFilter=true"

        return exporter.export_data(
            command_name="scripts",
            api_endpoint=api_endpoint,
            headers=headers,
            response_filter=decode_script_response,
            **self.kwargs,
        )
