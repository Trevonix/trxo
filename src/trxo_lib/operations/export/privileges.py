"""
Privileges export service.
"""

from typing import Any, Dict
from trxo_lib.config.api_headers import get_headers
from trxo_lib.operations.export.base_exporter import BaseExporter


def privileges_response_filter(raw: Dict[str, Any], realm: str) -> Dict[str, Any]:
    realm_clean = realm.strip()
    wanted_ids = {f"{realm_clean}OrgPrivileges", "privilegeAssignments"}
    if isinstance(raw, dict) and isinstance(raw.get("result"), list):
        filtered = [
            item
            for item in raw["result"]
            if isinstance(item, dict) and item.get("_id") in wanted_ids
        ]
        return {**raw, "result": filtered}
    return raw


class PrivilegesExportService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        realm = self.kwargs.get("realm")
        exporter = BaseExporter()
        headers = get_headers("privileges")

        response_filter = None
        if realm:
            response_filter = lambda data: privileges_response_filter(data, realm)

        safe_kwargs = self.kwargs.copy()
        if "commit" in safe_kwargs:
            safe_kwargs["commit_message"] = safe_kwargs.pop("commit")

        return exporter.export_data(
            command_name="privileges",
            api_endpoint='/openidm/config?_queryFilter=_id co "privilege"',
            headers=headers,
            response_filter=response_filter,
            **safe_kwargs,
        )
