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
from xmlrpc import client

from trxo.constants import DEFAULT_REALM
from trxo.utils.console import error, info, warning
from trxo.utils.diff.data_fetcher import DataFetcher, get_command_api_endpoint
from trxo.utils.git import GitManager


class RollbackManager:
    """Manage baseline snapshots and rollback operations."""

    def __init__(self, command_name: str, realm: Optional[str] = None):
        self.command_name = command_name
        self.realm = realm or DEFAULT_REALM
        self.baseline_snapshot: Dict[str, Any] = {}
        self.imported_items: List[Dict[str, Any]] = []
        self.git_branch: Optional[str] = None
        self.git_manager: Optional[GitManager] = None
        self.raw_baseline_data: Dict[str, Any] = {}
        self.auth_headers: Dict[str, str] = {}
        # Auth context for rollback
        self.auth_mode: str = "service-account"
        self._idm_username: Optional[str] = None
        self._idm_password: Optional[str] = None

    def create_baseline_snapshot(
        self,
        token: str,
        base_url: str,
        git_manager: Optional[GitManager] = None,
        **auth_params,
    ) -> bool:
        """Fetch current server state and keep it in-memory.

        Optionally persist to a Git branch. Returns True on success.
        """
        try:
            info(
                f"Creating baseline snapshot for {self.command_name} "
                f"(realm={self.realm})..."
            )

            # Store auth context for later rollback execution
            self.auth_mode = auth_params.get("auth_mode", "service-account")
            self._idm_username = auth_params.get("idm_username")
            self._idm_password = auth_params.get("idm_password")
            self.auth_headers = self._build_auth_headers(token, base_url)
            # Get API endpoint for this command
            api_endpoint, _ = get_command_api_endpoint(self.command_name, self.realm)
            if not api_endpoint:
                error(f"Unknown command for baseline snapshot: {self.command_name}")
                return False

            fetcher = DataFetcher()
            # Pass all auth params to fetcher
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

            # Normalize to list of items if possible
            # Normalize fetched data into a list of items
            items = []

            def flatten_items(obj):
                """Recursively extract list items from export structures."""
                if isinstance(obj, list):
                    return obj

                if isinstance(obj, dict):
                    # Standard APIs returning result arrays
                    if "result" in obj and isinstance(obj["result"], list):
                        return obj["result"]

                    # Export wrapper pattern
                    if "data" in obj:
                        return flatten_items(obj["data"])

                    # Handle nested component exports (e.g. saml hosted/remote)
                    collected = []
                    for value in obj.values():
                        if isinstance(value, list):
                            collected.extend(value)

                    if collected:
                        return collected

                return []

            items = flatten_items(data)
            # Build mapping of id -> item
            # Build mapping directly from export data (already full config)

            mapping = {}

            # Handle single-document configuration endpoints like authn
            if self.command_name == "authn":
                if isinstance(data, dict) and "data" in data:
                    mapping["authn_settings"] = data["data"]
                    self.raw_baseline_data = data["data"]
                else:
                    mapping["authn_settings"] = data
                    self.raw_baseline_data = data

            else:
                for itm in items:

                    # Support multiple identifier types across components
                    item_id = (
                        itm.get("_id")
                        or itm.get("id")
                        or itm.get("entityId")
                        or itm.get("name")
                    )

                    if not item_id:
                        continue

                    # If collection already returned full config → use it
                    if isinstance(itm, dict) and len(itm.keys()) > 2:
                        mapping[str(item_id)] = itm

                        entity_id = itm.get("entityId")
                        if entity_id:
                            mapping[str(entity_id)] = itm
                        continue

                    # Otherwise fetch full config by ID
                    try:
                        url = self._build_api_url(item_id, base_url)

                        headers = {
                            "Content-Type": "application/json",
                            "Accept-API-Version": "protocol=2.0,resource=1.0",
                        }

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
            # Keep raw data for full-config restores
            # Store baseline snapshot for rollback usage
            # Save baseline snapshot used for rollback
            # Store baseline snapshot used for rollback
            self.baseline_snapshot = mapping

            # If export structure has "data", flatten it for rollback usage
            if (
                isinstance(self.raw_baseline_data, dict)
                and "data" in self.raw_baseline_data
            ):
                flattened = {}

                data_section = self.raw_baseline_data["data"]

                if isinstance(data_section, dict):
                    for section in data_section.values():
                        if isinstance(section, list):
                            for item in section:
                                item_id = (
                                    item.get("_id")
                                    or item.get("id")
                                    or item.get("entityId")
                                    or item.get("name")
                                )
                                if item_id:
                                    flattened[str(item_id)] = item

                if flattened:
                    self.baseline_snapshot.update(flattened)
            elif self.command_name == "authn":
                self.raw_baseline_data = mapping.get("authn_settings", mapping)

            else:
                self.raw_baseline_data = mapping
            info("===== BASELINE SNAPSHOT (FULL CONFIG PER ID) =====")
            for k, v in mapping.items():
                info(f"\nID: {k}")
                info(json.dumps(v, indent=2))
            info("===== END BASELINE SNAPSHOT =====")
            # Keep raw data for full-config restores

            # Persist the snapshot to a branch for auditability if git_manager
            if git_manager:
                self.git_manager = git_manager
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                branch_name = f"baseline/{self.command_name}/{timestamp}"
                try:
                    info(f"Creating baseline git branch: {branch_name}")
                    git_manager.ensure_branch(branch_name)
                    # Write a file under <repo>/<realm>/<component>.json
                    repo_path = git_manager.local_path
                    component = self.command_name
                    realm_dir = repo_path / (self.realm or "root")
                    comp_dir = realm_dir / component
                    comp_dir.mkdir(parents=True, exist_ok=True)
                    filename = f"{(self.realm or 'root')}_{component}.json"
                    file_path = comp_dir / filename
                    if self.command_name == "saml":
                        baseline_file_data = self.raw_baseline_data
                    else:
                        baseline_file_data = {"data": mapping}

                    file_path.write_text(
                        json.dumps(baseline_file_data, indent=2), encoding="utf-8"
                    )
                    # Commit and push
                    rel = file_path.relative_to(repo_path)
                    commit_msg = (
                        f"Baseline snapshot for {self.command_name} "
                        f"({self.realm}) at {timestamp}"
                    )
                    # Branch sync validation is done in setup_git_for_import
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
        """Record an imported item for potential rollback.

        action: 'created' or 'updated'
        baseline_item: baseline data (if any) to use for restore
        """
        self.imported_items.append(
            {
                "id": item_id,
                "action": action,
                "baseline": baseline_item,
            }
        )

    def execute_rollback(self, token: str, base_url: str) -> Dict[str, Any]:
        """Rollback imported items in reverse order. Returns a report dict."""
        report = {"rolled_back": [], "errors": []}
        info("Initiating rollback of imported items...")

        # If nothing was tracked but baseline exists → restore full configuration
        if not self.imported_items and getattr(self, "raw_baseline_data", None):
            try:
                info(
                    "No tracked items found - restoring full baseline configuration..."
                )

                api_endpoint, _ = get_command_api_endpoint(
                    self.command_name, self.realm
                )

                from trxo.utils.url import construct_api_url

                url = construct_api_url(base_url, api_endpoint)

                headers = {
                    "Content-Type": "application/json",
                    "Accept-API-Version": "protocol=2.0,resource=1.0",
                }

                headers = {**headers, **self._build_auth_headers(token, url)}

                import httpx

                with httpx.Client() as client:

                    baseline_data = self.raw_baseline_data

                    if isinstance(baseline_data, dict) and len(baseline_data) == 1:
                        baseline_data = list(baseline_data.values())[0]

                    if isinstance(baseline_data, dict):
                        baseline_data = {
                            k: v
                            for k, v in baseline_data.items()
                            if k not in {"_id", "_rev", "_type"}
                        }
                    payload = json.dumps(baseline_data)

                    resp = client.put(url, headers=headers, data=payload)
                info(f"Rollback response status: {resp.status_code}")

                try:
                    info(f"Rollback response body: {resp.text}")
                except Exception:
                    pass

                if resp.status_code in (200, 201):
                    info("Full configuration restored from baseline")
                    report["rolled_back"].append({"action": "restored_full_config"})
                else:
                    warning(f"Failed to restore baseline: {resp.status_code}")
                    report["errors"].append({"error": resp.text})

                return report

            except Exception as e:
                warning(f"Rollback restore failed: {e}")
                report["errors"].append({"error": str(e)})
                return report

        # Process tracked items in reverse order
        for record in reversed(self.imported_items):

            item_id = record.get("id")
            action = record.get("action")

            baseline = self.baseline_snapshot.get(str(item_id))

            if baseline:
                info("Baseline item found for restore")
            else:
                warning(f"No baseline found for {item_id}")

            try:

                # ---------------------------
                # DELETE newly created item
                # ---------------------------
                if action == "created":

                    url = self._build_api_url(item_id, base_url)
                    info(f"Rollback restore URL: {url}")

                    headers = {
                        "Content-Type": "application/json",
                        "Accept-API-Version": "protocol=2.0,resource=1.0",
                    }

                    headers = {**headers, **self._build_auth_headers(token, url)}

                    import httpx

                    with httpx.Client() as client:
                        resp = client.delete(url, headers=headers)

                    if resp.status_code in (200, 204):
                        info(f"Rolled back (deleted): {item_id}")
                        report["rolled_back"].append(
                            {"id": item_id, "action": "deleted"}
                        )
                    else:
                        warning(
                            f"Failed to delete {item_id} during rollback: {resp.status_code}"
                        )
                        report["errors"].append({"id": item_id, "error": resp.text})

                # ---------------------------
                # RESTORE updated item
                # ---------------------------
                elif action == "updated":

                    if not baseline:
                        warning(f"No baseline found for {item_id}; skipping restore")
                        report["errors"].append({"id": item_id, "error": "no_baseline"})
                        continue

                    url = self._build_api_url(item_id, base_url)
                    info(f"Rollback restore URL: {url}")

                    headers = {
                        "Content-Type": "application/json",
                        "Accept-API-Version": "protocol=2.0,resource=1.0",
                    }

                    headers = {**headers, **self._build_auth_headers(token, url)}

                    restore_data = {
                        k: v for k, v in baseline.items() if k not in {"_rev", "_type"}
                    }
                    payload = json.dumps(restore_data)

                    import httpx

                    with httpx.Client() as client:

                        # Special restore logic for SAML
                        if self.command_name == "saml":

                            # Restore entity configuration directly
                            resp = client.put(url, headers=headers, data=payload)

                        else:

                            resp = client.put(url, headers=headers, data=payload)

                    if resp.status_code in (200, 201):
                        info(f"Rolled back (restored): {item_id}")
                        report["rolled_back"].append(
                            {"id": item_id, "action": "restored"}
                        )
                    else:
                        warning(
                            f"Failed to restore {item_id} during rollback: {resp.status_code}"
                        )
                        report["errors"].append({"id": item_id, "error": resp.text})

                else:
                    warning(f"Unknown action '{action}' for {item_id}; skipping")

            except Exception as e:
                warning(f"Rollback error for {item_id}: {e}")
                report["errors"].append({"id": item_id, "error": str(e)})

        info("Rollback completed")
        return report

    def _build_api_url(self, item_id: str, base_url: str) -> str:
        """Helper to construct API endpoint for a given item identifier."""
        try:
            api_endpoint, _ = get_command_api_endpoint(self.command_name, self.realm)

            if not api_endpoint:
                raise RuntimeError("Unknown command API endpoint")

            from trxo.utils.url import construct_api_url

            # Special handling for SAML entities
            if self.command_name == "saml":

                api_endpoint = f"/am/json/realms/root/realms/{self.realm}/realm-config/saml2/hosted/{item_id}"

                return construct_api_url(base_url, api_endpoint)

            # Generic handling for other components
            if api_endpoint.endswith("?_queryFilter=true"):
                # Many endpoints are list endpoints; append /{id}
                api_endpoint = api_endpoint.replace("?_queryFilter=true", f"/{item_id}")
            elif api_endpoint.endswith("/"):
                api_endpoint = f"{api_endpoint}{item_id}"
            else:
                api_endpoint = f"{api_endpoint}/{item_id}"

            return construct_api_url(base_url, api_endpoint)

        except Exception:
            from trxo.utils.url import construct_api_url

            return construct_api_url(base_url, f"/{item_id}")

    def _build_auth_headers(self, token: str, url: str) -> Dict[str, str]:

        # IDM endpoints
        if "/openidm/" in url:
            if self._idm_username and self._idm_password:
                return {
                    "X-OpenIDM-Username": self._idm_username,
                    "X-OpenIDM-Password": self._idm_password,
                }
            return {}

        # AM endpoints ALWAYS require session cookie
        return {"Cookie": f"iPlanetDirectoryPro={token}"}
