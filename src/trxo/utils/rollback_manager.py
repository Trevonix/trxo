"""
Rollback manager used by import flows.

This module creates a baseline snapshot (in-memory + optional
Git branch commit) and performs rollback actions (DELETE for
created items, PUT baseline for updated items) when an import
run fails and the user requested automatic rollback.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from trxo.config.api_headers import get_headers
from trxo.constants import DEFAULT_REALM
from trxo.utils.console import error, info, warning
from trxo.utils.diff.data_fetcher import DataFetcher, get_command_api_endpoint
from trxo.utils.git import GitManager


class RollbackManager:
    """Manage baseline snapshots and rollback operations."""

    def __init__(self, command_name: str, realm: Optional[str] = None):
        self.command_name = command_name

        # Root-level IDM configs
        if command_name in [
            "privileges",
            "email_templates",
            "endpoints",
            "managed",
            "managed_objects",
            "mappings",
            "connectors",
            "themes",
        ]:
            self.realm = "root"
        else:
            self.realm = realm or DEFAULT_REALM

        self.baseline_snapshot: Dict[str, Any] = {}
        self.imported_items: List[Dict[str, Any]] = []
        self.git_branch: Optional[str] = None
        self.git_manager: Optional[GitManager] = None
        self.raw_baseline_data: Dict[str, Any] = {}
        self.auth_headers: Dict[str, str] = {}

        # Auth context
        self.auth_mode: str = "service-account"
        self._idm_username: Optional[str] = None
        self._idm_password: Optional[str] = None

    # ---------------------------------------------------------------------
    # BASELINE SNAPSHOT
    # ---------------------------------------------------------------------

    def create_baseline_snapshot(
        self,
        token: str,
        base_url: str,
        git_manager: Optional[GitManager] = None,
        **auth_params,
    ) -> bool:

        try:

            info(
                f"Creating baseline snapshot for {self.command_name} "
                f"(realm={self.realm})..."
            )

            self.auth_mode = auth_params.get("auth_mode", "service-account")
            self._idm_username = auth_params.get("idm_username")
            self._idm_password = auth_params.get("idm_password")
            self.auth_headers = self._build_auth_headers(token, base_url)

            api_endpoint, _ = get_command_api_endpoint(self.command_name, self.realm)

            if not api_endpoint:
                error(f"Unknown command for baseline snapshot: {self.command_name}")
                return False

            fetcher = DataFetcher()

            data = fetcher.fetch_data(
                command_name=self.command_name,
                api_endpoint=api_endpoint,
                realm=self.realm,
                base_url=base_url,
                **auth_params,
            )

            if not data:
                error("Failed to capture baseline snapshot from server")
                return False

            # ---------------------------------------------------------
            # ROOT LEVEL IDM CONFIGS (ONE BIG DOCUMENT)
            # ---------------------------------------------------------
            if self.command_name in [
                "themes",
                "managed",
                "managed_objects",
            ]:

                if not isinstance(data, dict):
                    error("Unexpected response for ui/themerealm baseline snapshot")
                    return False

                item_id = data.get("_id", "ui/themerealm")

                mapping = {item_id: data}

                self.baseline_snapshot = mapping
                self.raw_baseline_data = mapping

                # ------------------- Git baseline -------------------
                if git_manager:

                    self.git_manager = git_manager

                    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                    branch_name = f"baseline/{self.command_name}/{timestamp}"

                    info(f"Creating baseline git branch: {branch_name}")
                    git_manager.ensure_branch(branch_name)

                    repo_path = git_manager.local_path
                    component = self.command_name

                    realm_dir = repo_path / (self.realm or "root")
                    comp_dir = realm_dir / component
                    comp_dir.mkdir(parents=True, exist_ok=True)

                    filename = f"{(self.realm or 'root')}_{component}.json"
                    file_path = comp_dir / filename

                    baseline_file_data = {"data": mapping}

                    file_path.write_text(
                        json.dumps(baseline_file_data, indent=2),
                        encoding="utf-8",
                    )

                    rel = file_path.relative_to(repo_path)

                    commit_msg = (
                        f"Baseline snapshot for {self.command_name} "
                        f"({self.realm}) at {timestamp}"
                    )

                    git_manager.commit_and_push(
                        [str(rel)], commit_msg, smart_pull=False
                    )

                    self.git_branch = branch_name

                info("Baseline snapshot created")
                return True

            # ---------------------------------------------------------
            # NODES - BULK FETCHED COLLECTION (ALREADY FULL CONFIGS)
            # ---------------------------------------------------------
            if self.command_name == "nodes":

                if not isinstance(data, dict):
                    error("Unexpected response for nodes baseline snapshot")
                    return False

                # data is {"nodes": {node_id: node_config, ...}}
                # Extract the nodes mapping
                mapping = data.get("nodes", {})

                if not mapping:
                    warning(f"No nodes found in baseline snapshot")
                    return False

                self.baseline_snapshot = mapping
                self.raw_baseline_data = mapping

                # ------------------- Git baseline -------------------
                if git_manager:

                    self.git_manager = git_manager

                    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                    branch_name = f"baseline/{self.command_name}/{timestamp}"

                    info(f"Creating baseline git branch: {branch_name}")
                    git_manager.ensure_branch(branch_name)

                    repo_path = git_manager.local_path
                    component = self.command_name

                    realm_dir = repo_path / (self.realm or "root")
                    comp_dir = realm_dir / component
                    comp_dir.mkdir(parents=True, exist_ok=True)

                    filename = f"{(self.realm or 'root')}_{component}.json"
                    file_path = comp_dir / filename

                    baseline_file_data = {"data": mapping}

                    file_path.write_text(
                        json.dumps(baseline_file_data, indent=2),
                        encoding="utf-8",
                    )

                    rel = file_path.relative_to(repo_path)

                    commit_msg = (
                        f"Baseline snapshot for {self.command_name} "
                        f"({self.realm}) at {timestamp} ({len(mapping)} items)"
                    )

                    git_manager.commit_and_push(
                        [str(rel)], commit_msg, smart_pull=False
                    )

                    self.git_branch = branch_name

                info(f"Baseline snapshot created with {len(mapping)} nodes")
                return True
            items = []

            def flatten_items(obj):

                if isinstance(obj, list):
                    return obj

                if isinstance(obj, dict):

                    if "result" in obj and isinstance(obj["result"], list):
                        return obj["result"]

                    if "data" in obj:
                        return flatten_items(obj["data"])

                    if "mappings" in obj and isinstance(obj["mappings"], list):
                        return obj["mappings"]

                    collected = []

                    for key, value in obj.items():
                        # Skip metadata and scripts from SAML response as they're
                        # not individual fetch-able resources
                        if key in ("metadata", "scripts"):
                            continue
                        if isinstance(value, list):
                            collected.extend(value)

                    if collected:
                        return collected

                return []

            if self.command_name == "mappings" and isinstance(data, dict):
                items = data.get("mappings", [])
            else:
                items = flatten_items(data)

            if not items and isinstance(data, dict):
                if "data" in data and isinstance(data["data"], dict):
                    if "result" in data["data"]:
                        items = data["data"]["result"]

            mapping = {}

            for itm in items:

                item_id = (
                    itm.get("_id")
                    or itm.get("id")
                    or itm.get("entityId")
                    or itm.get("name")
                )

                if not item_id:
                    continue

                # Already full config
                if isinstance(itm, dict):

                    non_meta_keys = [
                        k for k in itm.keys() if k not in {"_id", "_rev", "_type"}
                    ]

                    if any(isinstance(itm[k], (dict, list)) for k in non_meta_keys):

                        mapping[str(item_id)] = itm

                        entity_id = itm.get("entityId")
                        if entity_id:
                            mapping[str(entity_id)] = itm

                        continue

                # Otherwise fetch full config
                try:

                    url = self._build_api_url(item_id, base_url)

                    headers = get_headers(self.command_name)

                    headers = {**headers, **self._build_auth_headers(token, url)}

                    import httpx

                    with httpx.Client() as client:
                        resp = client.get(url, headers=headers)

                    if resp.status_code == 200:
                        mapping[str(item_id)] = resp.json()
                    else:
                        warning(
                            f"Could not fetch full config for {item_id}: {resp.status_code}"
                        )

                except Exception as e:
                    warning(f"Failed baseline fetch for {item_id}: {e}")

            self.baseline_snapshot = mapping
            self.raw_baseline_data = mapping

            # -----------------------------------------------------------------
            # GIT BASELINE
            # -----------------------------------------------------------------

            if git_manager:

                self.git_manager = git_manager

                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                branch_name = f"baseline/{self.command_name}/{timestamp}"

                try:

                    info(f"Creating baseline git branch: {branch_name}")

                    git_manager.ensure_branch(branch_name)

                    repo_path = git_manager.local_path
                    component = self.command_name

                    realm_dir = repo_path / (self.realm or "root")
                    comp_dir = realm_dir / component
                    comp_dir.mkdir(parents=True, exist_ok=True)

                    filename = f"{(self.realm or 'root')}_{component}.json"
                    file_path = comp_dir / filename

                    if self.command_name == "mappings":
                        baseline_file_data = {
                            "data": {"_id": "sync", "mappings": list(mapping.values())}
                        }
                    else:
                        baseline_file_data = {"data": mapping}

                    file_path.write_text(
                        json.dumps(baseline_file_data, indent=2),
                        encoding="utf-8",
                    )

                    rel = file_path.relative_to(repo_path)

                    commit_msg = (
                        f"Baseline snapshot for {self.command_name} "
                        f"({self.realm}) at {timestamp}"
                    )

                    git_manager.commit_and_push(
                        [str(rel)], commit_msg, smart_pull=False
                    )

                    self.git_branch = branch_name

                except Exception as e:
                    warning(f"Failed to persist baseline snapshot to Git: {e}")

            info("Baseline snapshot created")
            return True

        except Exception as e:

            error(f"Baseline snapshot failed: {e}")
            return False

    def track_import(
        self, item_id: str, action: str, baseline_item: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track imported items so rollback can undo them.
        """

        self.imported_items.append(
            {
                "id": item_id,
                "action": action,
                "baseline": baseline_item,
            }
        )

    # ---------------------------------------------------------------------
    # ROLLBACK EXECUTION
    # ---------------------------------------------------------------------

    def execute_rollback(self, token: str, base_url: str) -> Dict[str, Any]:

        report = {"rolled_back": [], "errors": []}

        info("Initiating rollback of imported items...")

        # If rollback triggered before any valid item ID was tracked
        if not self.imported_items:
            warning("No imported items tracked. Restoring entire baseline snapshot...")

            for baseline_id, baseline_item in self.baseline_snapshot.items():
                try:
                    url = self._build_api_url(baseline_id, base_url)

                    headers = get_headers(self.command_name)

                    headers = {**headers, **self._build_auth_headers(token, url)}

                    restore_data = {
                        k: v
                        for k, v in baseline_item.items()
                        if k not in {"_rev", "_type"}
                    }

                    import httpx

                    with httpx.Client() as client:
                        resp = client.put(url, headers=headers, json=restore_data)

                    if resp.status_code in (200, 201, 204):
                        info(f"Restored baseline item: {baseline_id}")
                        report["rolled_back"].append(
                            {"id": baseline_id, "action": "restored"}
                        )
                    else:
                        report["errors"].append({"id": baseline_id, "error": resp.text})

                except Exception as e:
                    report["errors"].append({"id": baseline_id, "error": str(e)})

            info("Rollback completed (baseline snapshot restored)")
            return report

        # Rollback previously imported items
        for record in reversed(self.imported_items):

            item_id = record.get("id")
            action = record.get("action")

            if not item_id:
                continue

            baseline = self.baseline_snapshot.get(str(item_id))

            try:
                url = self._build_api_url(item_id, base_url)

                headers = get_headers(self.command_name)

                headers = {**headers, **self._build_auth_headers(token, url)}

                import httpx

                # If item was newly created → delete it
                if action == "created":
                    with httpx.Client() as client:
                        resp = client.delete(url, headers=headers)

                    if resp.status_code in (200, 204):
                        info(f"Deleted created item: {item_id}")
                        report["rolled_back"].append(
                            {"id": item_id, "action": "deleted"}
                        )
                    else:
                        report["errors"].append({"id": item_id, "error": resp.text})

                # If item existed before → restore baseline
                elif action == "updated" and baseline:

                    restore_data = {
                        k: v for k, v in baseline.items() if k not in {"_rev", "_type"}
                    }

                    with httpx.Client() as client:
                        resp = client.put(url, headers=headers, json=restore_data)

                    if resp.status_code in (200, 201, 204):
                        info(f"Restored baseline item: {item_id}")
                        report["rolled_back"].append(
                            {"id": item_id, "action": "restored"}
                        )
                    else:
                        report["errors"].append({"id": item_id, "error": resp.text})

            except Exception as e:
                report["errors"].append({"id": item_id, "error": str(e)})

        return report

    # ---------------------------------------------------------------------
    # URL BUILDER (FIXED)
    # ---------------------------------------------------------------------

    def _build_api_url(self, item_id: str, base_url: str) -> str:

        try:

            from trxo.utils.url import construct_api_url
            from urllib.parse import quote

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
                baseline = self.baseline_snapshot.get(str(item_id))

                if not baseline or not isinstance(baseline, dict):
                    warning(
                        f"Node '{item_id}' not found in baseline, cannot determine node type"
                    )
                    return construct_api_url(
                        base_url,
                        f"/am/json/realms/root/realms/{self.realm}"
                        f"/realm-config/authentication/authenticationtrees/nodes/unknown/{quote(str(item_id), safe='')}",
                    )

                # Extract node type from _type._id field
                node_type = (baseline.get("_type") or {}).get("_id", "unknown")
                info(f"Building delete URL for node '{item_id}' of type '{node_type}'")

                return construct_api_url(
                    base_url,
                    f"/am/json/realms/root/realms/{self.realm}"
                    f"/realm-config/authentication/authenticationtrees"
                    f"/nodes/{quote(str(node_type), safe='')}/{quote(str(item_id), safe='')}",
                )

            # Special handling for email_templates (use resource endpoint, not query endpoint)
            if self.command_name == "email_templates":
                # IDM base URL (strip /am if needed)
                idm_base = base_url.rstrip("/")
                if idm_base.endswith("/am"):
                    idm_base = idm_base[:-3]

                # item_id is the template name like "resetPassword"
                baseline = self.baseline_snapshot.get(str(item_id))
                if baseline:
                    info(
                        f"Email template '{item_id}' exists in baseline - will restore"
                    )
                else:
                    warning(
                        f"Email template '{item_id}' NOT in baseline - marking as newly created"
                    )

                return f"{idm_base}/openidm/config/emailTemplate/{quote(str(item_id), safe='')}"

            # Special handling for SAML entities - determine location from baseline data
            if self.command_name == "saml":
                baseline = self.baseline_snapshot.get(str(item_id))
                location = "hosted"  # default

                if baseline and isinstance(baseline, dict):
                    # Baseline structure: {"hosted": {...}} or {"remote": {...}}
                    if "hosted" in baseline:
                        location = "hosted"
                        info(f"SAML entity '{item_id}' found in baseline as 'hosted'")
                    elif "remote" in baseline:
                        location = "remote"
                        info(f"SAML entity '{item_id}' found in baseline as 'remote'")
                else:
                    warning(
                        f"SAML entity '{item_id}' NOT found in baseline, using default location 'hosted'"
                    )

                return construct_api_url(
                    base_url,
                    f"/am/json/realms/root/realms/{self.realm}"
                    f"/realm-config/federation/entityproviders/saml2/{location}/{quote(str(item_id), safe='')}",
                )

            # Standard endpoint handling for other commands
            api_endpoint, _ = get_command_api_endpoint(self.command_name, self.realm)

            if not api_endpoint:
                raise RuntimeError("Unknown command API endpoint")

            # remove query parameters like ?_queryFilter
            api_endpoint = api_endpoint.split("?")[0]

            if not api_endpoint.endswith("/"):
                api_endpoint += "/"

            # URL-encode item_id to handle special characters (e.g., nodes with special IDs)
            encoded_id = quote(str(item_id), safe="")
            api_endpoint = f"{api_endpoint}{encoded_id}"

            return construct_api_url(base_url, api_endpoint)

        except Exception as e:

            from trxo.utils.url import construct_api_url

            warning(f"Failed to build API URL for {self.command_name}/{item_id}: {e}")
            return construct_api_url(base_url, f"/{item_id}")

    # ---------------------------------------------------------------------
    # AUTH
    # ---------------------------------------------------------------------

    def _build_auth_headers(self, token: str, url: str) -> Dict[str, str]:

        if "/openidm/" in url:

            if self._idm_username and self._idm_password:

                headers = get_headers(self.command_name)
                return {
                    "X-OpenIDM-Username": self._idm_username,
                    "X-OpenIDM-Password": self._idm_password,
                    "Accept-API-Version": headers.get(
                        "Accept-API-Version", "protocol=2.1,resource=1.0"
                    ),
                }

            # AIC/SaaS mode for IDM requires Bearer token
            return {"Authorization": f"Bearer {token}"}

        # For AM endpoints: service account (cloud) uses Bearer token,
        # on-premise uses Cookie-based auth
        if self.auth_mode == "service-account":
            return {"Authorization": f"Bearer {token}"}

        return {"Cookie": f"iPlanetDirectoryPro={token}"}
