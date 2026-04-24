from typing import Any, List

from trxo_lib.config.api_headers import get_headers
from trxo_lib.config.constants import DEFAULT_REALM
from trxo_lib.logging import error, warning, info

from trxo_lib.exports.processor import BaseExporter


def fetch_global_policies(exporter_instance: BaseExporter) -> List[Any]:
    """
    Fetch global IDM policies including fieldPolicies and the main policy config.
    """
    global_policies = []
    token, api_base_url = exporter_instance.get_current_auth()

    # Use standard IDM headers (important for Cloud/AIC)
    from trxo_lib.config.api_headers import get_headers
    headers = get_headers("managed")
    headers.update(exporter_instance.build_auth_headers(token, product="idm"))

    # IDM base URL handling
    idm_base_url = api_base_url
    if (
        exporter_instance.auth_mode == "onprem"
        and hasattr(exporter_instance, "_idm_base_url")
        and exporter_instance._idm_base_url
    ):
        idm_base_url = exporter_instance._idm_base_url

    info(f"Fetching global IDM policies from {idm_base_url}...")

    try:
        # 1. Get the list of all configs to find fieldPolicies
        list_url = exporter_instance._construct_api_url(idm_base_url, "/openidm/config")
        response = exporter_instance.make_http_request(list_url, "GET", headers)
        configs_data = response.json()

        config_ids = []
        # Support various IDM response formats for /config
        if isinstance(configs_data, dict):
            # Try common keys like 'configs', 'result', 'items'
            for key in ["configs", "result", "items"]:
                if key in configs_data and isinstance(configs_data[key], list):
                    for c in configs_data[key]:
                        if isinstance(c, dict):
                            config_ids.append(c.get("_id") or c.get("id"))
                        elif isinstance(c, str):
                            config_ids.append(c)
                    break
        elif isinstance(configs_data, list):
            for c in configs_data:
                if isinstance(c, dict):
                    config_ids.append(c.get("_id") or c.get("id"))
                elif isinstance(c, str):
                    config_ids.append(c)

        target_ids = [
            cid
            for cid in config_ids
            if cid and (cid.startswith("fieldPolicy/") or cid == "policy")
        ]

        # 2. ForgeRock Cloud (AIC) often hides fieldPolicy/* from the main list.
        #    Try to discover them via managed objects.
        try:
            managed_url = exporter_instance._construct_api_url(idm_base_url, "/openidm/config/managed")
            managed_resp = exporter_instance.make_http_request(managed_url, "GET", headers)
            if managed_resp.status_code == 200:
                managed_json = managed_resp.json()
                for obj in managed_json.get("objects", []):
                    obj_name = obj.get("name")
                    if obj_name:
                        fid = f"fieldPolicy/{obj_name}"
                        if fid not in target_ids:
                            target_ids.append(fid)
        except Exception:
            # Fallback discovery failing is not critical
            pass

        # Always ensure 'policy' is checked even if not in the list
        if "policy" not in target_ids:
            target_ids.append("policy")

        info(f"Discovered {len(target_ids)} potential global policy configurations")

        for cid in target_ids:
            try:
                config_url = exporter_instance._construct_api_url(
                    idm_base_url, f"/openidm/config/{cid}"
                )
                config_resp = exporter_instance.make_http_request(
                    config_url, "GET", headers, suppress_logs=True
                )
                if config_resp.status_code == 200:
                    config_json = config_resp.json()
                    # Ensure _id is present
                    if "_id" not in config_json:
                        config_json["_id"] = cid
                    global_policies.append(config_json)
            except Exception as e:
                # Silently skip items that don't exist (frequent for fieldPolicy fallbacks)
                pass

    except Exception as e:
        warning(f"Failed to fetch IDM config list from {idm_base_url}: {str(e)}")

    return global_policies


def process_policies_response(
    exporter_instance: BaseExporter, realm: str, global_policies: bool = False
):
    """
    Process policies response to fetch and merge policy sets, and optionally global policies.

    Args:
        exporter_instance: The BaseExporter instance for making API calls
        realm: The realm name
        global_policies: Whether to fetch global IDM policies

    Returns:
        Function that processes the initial API response
    """

    def filter_function(data: Any) -> Any:
        # Get authentication details from the exporter instance
        token, api_base_url = exporter_instance.get_current_auth()

        # AM Section: Policy Sets + Policies
        am_policies = []
        if isinstance(data, dict) and isinstance(data.get("result"), list):
            am_policies = data.get("result", [])

        # Fetch AM policy sets (applications)
        url = exporter_instance._construct_api_url(
            api_base_url,
            f"/am/json/realms/root/realms/{realm}/applications?_queryFilter=true",
        )
        headers = get_headers("policy_sets")
        headers = {**headers, **exporter_instance.build_auth_headers(token)}

        policy_sets = []
        try:
            response = exporter_instance.make_http_request(url, "GET", headers)
            policy_sets_data = response.json()
            policy_sets = policy_sets_data.get("result", [])
        except Exception as e:
            error(f"Failed to fetch policy sets: {str(e)}")

        am_section = policy_sets + am_policies

        # Global Section
        global_section = []
        if global_policies:
            global_section = fetch_global_policies(exporter_instance)

        # Return the new restructured format as requested by user
        return {"am": am_section, "global": global_section}

    return filter_function


class PoliciesExporter(BaseExporter):
    """Custom exporter to fetch policy sets and merge them with policies."""

    def __init__(self, realm: str):
        super().__init__()
        self.realm = realm


class PoliciesExportService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self) -> Any:
        realm = self.kwargs.get("realm", DEFAULT_REALM)
        global_policies = self.kwargs.get("global_policies", False)
        exporter = PoliciesExporter(realm=realm)
        headers = get_headers("policies")

        safe_kwargs = self.kwargs.copy()
        if "commit" in safe_kwargs:
            safe_kwargs["commit_message"] = safe_kwargs.pop("commit")

        return exporter.export_data(
            command_name="policies",
            api_endpoint=f"/am/json/realms/root/realms/{realm}/policies?_queryFilter=true",
            headers=headers,
            response_filter=process_policies_response(exporter, realm, global_policies),
            **safe_kwargs,
        )
