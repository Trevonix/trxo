"""
URL builder for rollback operations.

Constructs the correct API URL for each command type so that
rollback can DELETE created items or PUT baseline data back.
"""

from typing import Any, Dict, Optional
from urllib.parse import quote

from trxo_lib.core.url import construct_api_url
from trxo_lib.logging import get_logger
from trxo_lib.state.diff.data_fetcher import get_command_api_endpoint

logger = get_logger(__name__)


class RollbackUrlBuilder:
    """Builds API URLs for rollback restore/delete operations."""

    def __init__(
        self,
        command_name: str,
        realm: Optional[str],
        baseline_snapshot: Dict[str, Any],
    ):
        self.command_name = command_name
        self.realm = realm
        self.baseline_snapshot = baseline_snapshot

    def build_api_url(self, item_id: str, base_url: str) -> str:
        """Build the API URL for a given item ID and base URL.

        Handles special cases for scripts, themes, managed objects,
        nodes, email templates, SAML, policies, and standard endpoints.
        """
        try:
            # Handle OAuth scripts
            if isinstance(item_id, str) and item_id.startswith("script::"):
                script_id = item_id.replace("script::", "")
                return construct_api_url(
                    base_url,
                    f"/am/json/realms/root/realms/{self.realm}/scripts/{script_id}",
                )

            # Root-level IDM paths represent the full resource path
            # so we shouldn't append the item_id to them
            if self.command_name in ["themes", "managed", "managed_objects"]:
                api_endpoint, _ = get_command_api_endpoint(
                    self.command_name, self.realm
                )
                if api_endpoint:
                    api_endpoint = api_endpoint.split("?")[0]
                    return construct_api_url(base_url, api_endpoint)

            # Special handling for nodes - extract node type from baseline
            if self.command_name == "nodes":
                return self._build_nodes_url(item_id, base_url)

            # Special handling for email_templates
            if self.command_name == "email_templates":
                return self._build_email_templates_url(item_id, base_url)

            # Special handling for SAML entities
            if self.command_name == "saml":
                return self._build_saml_url(item_id, base_url)

            # Special handling for policies vs policy sets
            if self.command_name == "policies":
                return self._build_policies_url(item_id, base_url)

            # Standard endpoint handling
            return self._build_standard_url(item_id, base_url)

        except Exception as e:
            logger.warning(
                f"Failed to build API URL for {self.command_name}/{item_id}: {e}"
            )
            return construct_api_url(base_url, f"/{item_id}")

    # -----------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------

    def _build_nodes_url(self, item_id: str, base_url: str) -> str:
        baseline = self.baseline_snapshot.get(str(item_id))

        if not baseline or not isinstance(baseline, dict):
            logger.warning(
                f"Node '{item_id}' not found in baseline, " "cannot determine node type"
            )
            return construct_api_url(
                base_url,
                f"/am/json/realms/root/realms/{self.realm}"
                f"/realm-config/authentication/authenticationtrees"
                f"/nodes/unknown/{quote(str(item_id), safe='')}",
            )

        node_type = (baseline.get("_type") or {}).get("_id", "unknown")
        logger.info(f"Building API URL for node '{item_id}' of type '{node_type}'")

        return construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}"
            f"/realm-config/authentication/authenticationtrees"
            f"/nodes/{quote(str(node_type), safe='')}"
            f"/{quote(str(item_id), safe='')}",
        )

    def _build_email_templates_url(self, item_id: str, base_url: str) -> str:
        idm_base = base_url.rstrip("/")
        if idm_base.endswith("/am"):
            idm_base = idm_base[:-3]

        baseline = self.baseline_snapshot.get(str(item_id))
        if baseline:
            logger.info(f"Email template '{item_id}' exists in baseline - will restore")
        else:
            logger.warning(
                f"Email template '{item_id}' NOT in baseline "
                "- marking as newly created"
            )

        return (
            f"{idm_base}/openidm/config/emailTemplate"
            f"/{quote(str(item_id), safe='')}"
        )

    def _build_saml_url(self, item_id: str, base_url: str) -> str:
        baseline = self.baseline_snapshot.get(str(item_id))
        location = "hosted"  # default
        url_id = str(item_id)

        if baseline and isinstance(baseline, dict):
            if "_saml_location" in baseline:
                location = baseline["_saml_location"]
            elif "location" in baseline:
                location = baseline["location"]

            if baseline.get("_id"):
                url_id = str(baseline["_id"])

            logger.info(f"SAML entity '{item_id}' → {location}/{url_id}")
        else:
            logger.warning(
                f"SAML entity '{item_id}' NOT found in baseline, "
                "using default location 'hosted'"
            )

        return construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}"
            f"/realm-config/saml2/{location}/{url_id}",
        )

    def _build_policies_url(self, item_id: str, base_url: str) -> str:
        baseline = self.baseline_snapshot.get(str(item_id))
        if baseline and isinstance(baseline, dict):
            is_policy_set = "applicationName" not in baseline
            if is_policy_set:
                return construct_api_url(
                    base_url,
                    f"/am/json/realms/root/realms/{self.realm}"
                    f"/applications/{quote(str(item_id), safe='')}",
                )

        return construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}"
            f"/policies/{quote(str(item_id), safe='')}",
        )

    def _build_standard_url(self, item_id: str, base_url: str) -> str:
        api_endpoint, _ = get_command_api_endpoint(self.command_name, self.realm)

        if not api_endpoint:
            raise RuntimeError("Unknown command API endpoint")

        api_endpoint = api_endpoint.split("?")[0]

        if not api_endpoint.endswith("/"):
            api_endpoint += "/"

        encoded_id = quote(str(item_id), safe="")
        api_endpoint = f"{api_endpoint}{encoded_id}"

        return construct_api_url(base_url, api_endpoint)
