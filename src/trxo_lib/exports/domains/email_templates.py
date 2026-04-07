"""
email templates export command.

This module provides export functionality for PingOne Advanced Identity Cloud email templates.
Filters /openidm/config?_queryFilter=true to only include items with _id starting with
"emailTemplate".
"""

from typing import Any
from trxo_lib.config.api_headers import get_headers
from trxo_lib.exports.processor import BaseExporter


class EmailTemplatesExportService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        exporter = BaseExporter()
        headers = get_headers("email_templates")

        safe_kwargs = self.kwargs.copy()
        if "commit" in safe_kwargs:
            safe_kwargs["commit_message"] = safe_kwargs.pop("commit")

        return exporter.export_data(
            command_name="email_templates",
            api_endpoint='/openidm/config?_queryFilter=_id sw "emailTemplate"',
            headers=headers,
            **safe_kwargs,
        )
