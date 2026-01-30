"""
Rollback manager used by import flows.

This module creates a baseline snapshot (in-memory + optional
Git branch commit) and performs rollback actions (DELETE for
created items, PUT baseline for updated items) when an import
run fails and the user requested automatic rollback.
"""

from typing import Dict, Any, List, Optional
import json
from datetime import datetime
from trxo.utils.console import info, error, warning
from trxo.utils.data_fetcher import DataFetcher, get_command_api_endpoint
from trxo.utils.git import GitManager
from trxo.constants import DEFAULT_REALM


class RollbackManager:
    """Manage baseline snapshots and rollback operations."""

    def __init__(self, command_name: str, realm: Optional[str] = None):
        self.command_name = command_name
        self.realm = realm or DEFAULT_REALM
        self.baseline_snapshot: Dict[str, Any] = {}
        self.imported_items: List[Dict[str, Any]] = []
        self.git_branch: Optional[str] = None
        self.git_manager: Optional[GitManager] = None

    def create_baseline_snapshot(
        self,
        token: str,
        base_url: str,
        git_manager: Optional[GitManager] = None,
    ) -> bool:
        """Fetch current server state and keep it in-memory.

        Optionally persist to a Git branch. Returns True on success.
        """
        try:
            info(
                f"Creating baseline snapshot for {self.command_name} "
                f"(realm={self.realm})..."
            )

            # Get API endpoint for this command
            from trxo.utils.data_fetcher import get_command_api_endpoint

            api_endpoint, _ = get_command_api_endpoint(self.command_name, self.realm)
            if not api_endpoint:
                error(f"Unknown command for baseline snapshot: {self.command_name}")
                return False

            fetcher = DataFetcher()
            data = fetcher.fetch_data(
                command_name=self.command_name,
                api_endpoint=api_endpoint,
                realm=self.realm,
                jwk_path=None,
                client_id=None,
                sa_id=None,
                base_url=None,
                project_name=None,
                auth_mode=None,
            )

            if not data:
                error("Failed to capture baseline snapshot from server")
                return False

            # Normalize to list of items if possible
            items = []
            if (
                isinstance(data, dict)
                and isinstance(data.get("data"), dict)
                and isinstance(data["data"].get("result"), list)
            ):
                items = data["data"]["result"]
            elif isinstance(data, dict) and isinstance(data.get("data"), list):
                items = data["data"]
            elif isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                # single config object -> use as dict keyed by id/name
                items = [data.get("data") or data]

            # Build mapping of id -> item
            mapping = {}
            for itm in items:
                # items may have _id or id or name
                key = None
                if isinstance(itm, dict):
                    key = itm.get("_id") or itm.get("id") or itm.get("name")
                if key:
                    mapping[str(key)] = itm

            self.baseline_snapshot = mapping
            # Keep raw data for full-config restores
            self.raw_baseline_data = data

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
                    file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
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

        # Special-case: managed objects are a single config object
        if self.command_name == "managed":
            try:
                info("Restoring full managed objects configuration from baseline...")
                api_endpoint, _ = get_command_api_endpoint(
                    self.command_name, self.realm
                )
                if not api_endpoint:
                    raise RuntimeError("Unknown API endpoint for managed restore")
                from trxo.utils.url import construct_api_url

                url = construct_api_url(base_url, api_endpoint)
                headers = {
                    "Content-Type": "application/json",
                    "Accept-API-Version": "protocol=2.1,resource=1.0",
                }
                headers = {**headers, **self._build_auth_headers(token)}
                import httpx

                with httpx.Client() as client:
                    payload = json.dumps(getattr(self, "raw_baseline_data", {}))
                    resp = client.put(url, headers=headers, data=payload)
                    if resp.status_code in (200, 201):
                        info("Managed objects restored from baseline")
                        report["rolled_back"].append(
                            {"action": "restored_managed_config"}
                        )
                    else:
                        warning(
                            f"Failed to restore managed baseline: "
                            f"{resp.status_code}"
                        )
                        report["errors"].append({"error": resp.text})
                return report
            except Exception as e:
                warning(f"Managed restore failed: {e}")
                report["errors"].append({"error": str(e)})
                return report

        # Process in reverse order
        for record in reversed(self.imported_items):
            item_id = record.get("id")
            action = record.get("action")
            baseline = record.get("baseline")

            try:
                if action == "created":
                    # Delete the newly created item
                    url = self._build_api_url(item_id, base_url)
                    headers = {
                        "Content-Type": "application/json",
                        "Accept-API-Version": "resource=1.0",
                    }
                    headers = {**headers, **(self._build_auth_headers(token))}
                    # Perform delete using httpx directly
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
                                f"Failed to delete {item_id} during rollback: "
                                f"{resp.status_code}"
                            )
                            report["errors"].append({"id": item_id, "error": resp.text})

                elif action == "updated":
                    # Restore baseline via PUT
                    if not baseline:
                        warning(f"No baseline found for {item_id}; skipping restore")
                        report["errors"].append({"id": item_id, "error": "no_baseline"})
                        continue

                    url = self._build_api_url(item_id, base_url)
                    headers = {
                        "Content-Type": "application/json",
                        "Accept-API-Version": "resource=1.0",
                    }
                    headers = {**headers, **(self._build_auth_headers(token))}
                    import httpx

                    with httpx.Client() as client:
                        payload = json.dumps(baseline)
                        resp = client.put(url, headers=headers, data=payload)
                        if resp.status_code in (200, 201):
                            info(f"Rolled back (restored): {item_id}")
                            report["rolled_back"].append(
                                {"id": item_id, "action": "restored"}
                            )
                        else:
                            warning(
                                f"Failed to restore {item_id} during rollback: "
                                f"{resp.status_code}"
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

            # If endpoint contains a placeholder like .../{item_id}, append
            if api_endpoint.endswith("?_queryFilter=true"):
                # Many endpoints are list endpoints; attempt to append /{id}
                api_endpoint = api_endpoint.replace("?_queryFilter=true", f"/{item_id}")
            elif api_endpoint.endswith("/"):
                api_endpoint = f"{api_endpoint}{item_id}"
            else:
                api_endpoint = f"{api_endpoint}/{item_id}"

            from trxo.utils.url import construct_api_url

            return construct_api_url(base_url, api_endpoint)
        except Exception:
            from trxo.utils.url import construct_api_url

            return construct_api_url(base_url, f"/{item_id}")

    def _build_auth_headers(self, token: str) -> Dict[str, str]:
        """Return headers for given token (simple helper)."""
        # Best-effort: prefer Bearer token
        return {"Authorization": f"Bearer {token}"}
