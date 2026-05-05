"""
Rollback manager used by import flows.

This module creates a baseline snapshot (in-memory + optional
Git branch commit) and performs rollback actions (DELETE for
created items, PUT baseline for updated items) when an import
run fails and the user requested automatic rollback.
"""

import base64
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from trxo_lib.config.api_headers import get_headers
from trxo_lib.config.constants import DEFAULT_REALM
from trxo_lib.config.config_store import ConfigStore
from trxo_lib.core.url import construct_api_url
from trxo_lib.git import GitManager
from trxo_lib.logging import get_logger
from trxo_lib.state.diff.data_fetcher import DataFetcher, get_command_api_endpoint
from trxo_lib.state.rollback.auth import RollbackAuthHelper
from trxo_lib.state.rollback.url_builder import RollbackUrlBuilder

logger = get_logger(__name__)

# Root-level IDM config commands (not realm-scoped)
ROOT_LEVEL_COMMANDS = frozenset(
    [
        "privileges",
        "email_templates",
        "endpoints",
        "managed",
        "managed_objects",
        "mappings",
        "connectors",
        "themes",
    ]
)


class RollbackManager:
    """Manage baseline snapshots and rollback operations."""

    def __init__(self, command_name: str, realm: Optional[str] = None):
        self.command_name = command_name
        self.realm = (
            "root" if command_name in ROOT_LEVEL_COMMANDS else (realm or DEFAULT_REALM)
        )

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

        # Composed helpers (initialised lazily after auth params are known)
        self._auth_helper: Optional[RollbackAuthHelper] = None
        self._url_builder: Optional[RollbackUrlBuilder] = None

    # -----------------------------------------------------------------
    # Composed helpers
    # -----------------------------------------------------------------

    def _get_auth_helper(self) -> RollbackAuthHelper:
        if self._auth_helper is None:
            self._auth_helper = RollbackAuthHelper(
                command_name=self.command_name,
                auth_mode=self.auth_mode,
                idm_username=self._idm_username,
                idm_password=self._idm_password,
            )
        return self._auth_helper

    def _get_url_builder(self) -> RollbackUrlBuilder:
        if self._url_builder is None:
            self._url_builder = RollbackUrlBuilder(
                command_name=self.command_name,
                realm=self.realm,
                baseline_snapshot=self.baseline_snapshot,
            )
        return self._url_builder

    def _build_auth_headers(self, token: str, url: str) -> Dict[str, str]:
        return self._get_auth_helper().build_auth_headers(token, url)

    def _build_api_url(self, item_id: str, base_url: str) -> str:
        return self._get_url_builder().build_api_url(item_id, base_url)

    # -----------------------------------------------------------------
    # BASELINE SNAPSHOT
    # -----------------------------------------------------------------

    def create_baseline_snapshot(
        self,
        token: str,
        base_url: str,
        git_manager: Optional[GitManager] = None,
        **auth_params,
    ) -> bool:
        try:
            logger.info(
                f"Creating baseline snapshot for {self.command_name} "
                f"(realm={self.realm})..."
            )

            self.auth_mode = auth_params.get("auth_mode", "service-account")
            self._idm_username = auth_params.get("idm_username")
            self._idm_password = auth_params.get("idm_password")
            # Reset helpers so they pick up new auth params
            self._auth_helper = None
            self._url_builder = None

            self.auth_headers = self._build_auth_headers(token, base_url)

            api_endpoint, _ = get_command_api_endpoint(self.command_name, self.realm)

            if not api_endpoint:
                logger.error(
                    f"Unknown command for baseline snapshot: {self.command_name}"
                )
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
                logger.error("Failed to capture baseline snapshot from server")
                return False

            # ---------------------------------------------------------
            # OAUTH AND SAML: ABSORB ALREADY FETCHED SCRIPTS AND SCAN FOR MORE
            # ---------------------------------------------------------
            if self.command_name in ("oauth", "saml"):
                # Extract and merge any scripts already fetched by the exporter's filter
                if isinstance(data, dict) and "scripts" in data:
                    if "scripts" not in self.baseline_snapshot:
                        self.baseline_snapshot["scripts"] = {}
                    
                    scripts_batch = data["scripts"]
                    if isinstance(scripts_batch, list):
                        for s in scripts_batch:
                            sid = s.get("_id")
                            if sid:
                                self.baseline_snapshot["scripts"][str(sid)] = s
                    elif isinstance(scripts_batch, dict):
                         self.baseline_snapshot["scripts"].update(scripts_batch)

                self._capture_scripts(data, token, base_url)

            # ---------------------------------------------------------
            # SINGLE-DOCUMENT CONFIGURATIONS (blob data)
            # ---------------------------------------------------------
            if self.command_name in [
                "themes",
                "authn",
                "authentication",
                "managed", 
                "managed_objects"
            ]:
                return self._snapshot_single_document(data, git_manager)

            # ---------------------------------------------------------
            # NODES (bulk collection)
            # ---------------------------------------------------------
            if self.command_name == "nodes":
                return self._snapshot_nodes(data, git_manager)

            # ---------------------------------------------------------
            # SAML ENTITIES
            # ---------------------------------------------------------
            if self.command_name == "saml":
                return self._snapshot_saml(data, git_manager)

            # ---------------------------------------------------------
            # EMAIL TEMPLATES
            # ---------------------------------------------------------
            if self.command_name == "email_templates":
                return self._snapshot_email_templates(
                    data, token, base_url, git_manager
                )

            # ---------------------------------------------------------
            # GENERIC: flatten items and build mapping
            # ---------------------------------------------------------
            return self._snapshot_generic(data, token, base_url, git_manager)

        except Exception as e:
            logger.error(f"Baseline snapshot failed: {e}")
            return False

    # -----------------------------------------------------------------
    # BASELINE: command-specific helpers
    # -----------------------------------------------------------------

    def _capture_scripts(self, data: Any, token: str, base_url: str) -> None:
        """Scan data for script references and fetch their full configs."""
        script_ids: set = set()

        def find_scripts(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if (
                        k.endswith("Script")
                        and isinstance(v, str)
                        and v.strip()
                        and v.strip() != "[Empty]"
                    ):
                        val = v.strip()
                        if len(val) > 10 and ("-" in val or len(val) == 36):
                            script_ids.add(val)
                    elif isinstance(v, (dict, list)):
                        find_scripts(v)
            elif isinstance(obj, list):
                for item in obj:
                    find_scripts(item)

        find_scripts(data)
        if not script_ids:
            return

        logger.info(f"Capturing {len(script_ids)} scripts for rollback")

        for script_id in script_ids:
            try:
                url = construct_api_url(
                    base_url,
                    f"/am/json/realms/root/realms/{self.realm}/scripts/{script_id}",
                )
                headers = get_headers("oauth")
                headers = {**headers, **self._build_auth_headers(token, url)}

                with httpx.Client() as client:
                    resp = client.get(url, headers=headers)

                if resp.status_code == 200:
                    if "scripts" not in self.baseline_snapshot:
                        self.baseline_snapshot["scripts"] = {}
                    self.baseline_snapshot["scripts"][script_id] = resp.json()
                else:
                    logger.warning(f"Failed to capture script {script_id}")
            except Exception as e:
                logger.warning(f"Error fetching script {script_id}: {e}")

    def _snapshot_single_document(
        self, data: Any, git_manager: Optional[GitManager]
    ) -> bool:
        if not isinstance(data, dict):
            logger.error("Unexpected response for single-document baseline snapshot")
            return False

        # Use command-specific IDs for rollback tracking
        default_id = "root"
        if self.command_name == "themes":
            default_id = "ui/themerealm"
        elif self.command_name in ("authn", "authentication"):
            default_id = "authn_settings"
        elif self.command_name in ("managed", "managed_objects"):
            default_id = "managed_objects"
        elif self.command_name == "connectors":
            default_id = "connectors"
        elif self.command_name == "mappings":
            default_id = "mappings"
        elif self.command_name == "endpoints":
            default_id = "endpoints"

        item_id = data.get("_id", default_id)
        mapping = {item_id: data}

        self.baseline_snapshot.update(mapping)
        self.raw_baseline_data = self.baseline_snapshot

        self._persist_baseline(mapping, git_manager)
        return True

    def _snapshot_nodes(self, data: Any, git_manager: Optional[GitManager]) -> bool:
        if not isinstance(data, dict):
            logger.error("Unexpected response for nodes baseline snapshot")
            return False

        mapping = data.get("nodes", {})
        if not mapping:
            logger.warning("No nodes found in baseline snapshot")
            return False

        self.baseline_snapshot.update(mapping)
        self.raw_baseline_data = self.baseline_snapshot

        self._persist_baseline(mapping, git_manager)
        return True

    def _snapshot_saml(self, data: Any, git_manager: Optional[GitManager]) -> bool:
        if not isinstance(data, dict):
            logger.error("Unexpected response for SAML baseline snapshot")
            return False

        mapping = {}
        for location in ("hosted", "remote"):
            for entity in data.get(location, []):
                entity_id = entity.get("_id") or entity.get("entityId")
                if not entity_id:
                    continue
                entity_with_loc = dict(entity)
                entity_with_loc["_saml_location"] = location
                mapping[str(entity_id)] = entity_with_loc
                alt_id = entity.get("entityId")
                if alt_id and str(alt_id) != str(entity_id):
                    mapping[str(alt_id)] = entity_with_loc

        self.baseline_snapshot.update(mapping)
        self.raw_baseline_data = self.baseline_snapshot

        self._persist_baseline(mapping, git_manager)
        return True

    def _snapshot_email_templates(
        self,
        data: Any,
        token: str,
        base_url: str,
        git_manager: Optional[GitManager],
    ) -> bool:
        email_names: List[str] = []

        if isinstance(data, dict):
            et_map = data.get("emailTemplates", {})
            if et_map and isinstance(et_map, dict):
                email_names = list(et_map.keys())
            else:
                for itm in data.get("result", []):
                    if isinstance(itm, dict) and "_id" in itm:
                        full_id = itm["_id"]
                        name = full_id.split("/")[-1] if "/" in full_id else full_id
                        email_names.append(name)

        mapping: Dict[str, Any] = {}
        idm_base = base_url.rstrip("/")
        if idm_base.endswith("/am"):
            idm_base = idm_base[:-3]

        for name in email_names:
            url = f"{idm_base}/openidm/config/emailTemplate/{name}"
            try:
                hdrs = get_headers("email_templates")
                hdrs = {**hdrs, **self._build_auth_headers(token, url)}
                with httpx.Client() as client:
                    resp = client.get(url, headers=hdrs)
                if resp.status_code == 200:
                    mapping[name] = resp.json()
                else:
                    logger.warning(
                        f"Could not fetch email template '{name}': {resp.status_code}"
                    )
            except Exception as e:
                logger.warning(
                    f"Failed baseline fetch for email template '{name}': {e}"
                )

        self.baseline_snapshot.update(mapping)
        self.raw_baseline_data = self.baseline_snapshot

        self._persist_baseline(mapping, git_manager)
        return True

    def _snapshot_generic(
        self,
        data: Any,
        token: str,
        base_url: str,
        git_manager: Optional[GitManager],
    ) -> bool:
        """Generic snapshot for commands that return a list of items."""

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
                    if key in ("metadata", "scripts"):
                        continue
                    if isinstance(value, list):
                        collected.extend(value)
                if collected:
                    return collected
            return []

        if self.command_name == "saml" and isinstance(data, dict):
            if "hosted" in data:
                for item in data["hosted"]:
                    item["_location"] = "hosted"
            if "remote" in data:
                for item in data["remote"]:
                    item["_location"] = "remote"

        if self.command_name == "mappings" and isinstance(data, dict):
            items = data.get("mappings", [])
        else:
            items = flatten_items(data)

        if not items and isinstance(data, dict):
            if "data" in data and isinstance(data["data"], dict):
                if "result" in data["data"]:
                    items = data["data"]["result"]

        mapping: Dict[str, Any] = {}

        for itm in items:
            item_id = (
                itm.get("_id")
                or itm.get("id")
                or itm.get("entityId")
                or itm.get("name")
            )

            if not item_id:
                continue

            if isinstance(item_id, str) and item_id.startswith("script::"):
                continue

            if isinstance(itm, dict):
                non_meta_keys = [
                    k for k in itm.keys() if k not in {"_id", "_rev", "_type"}
                ]

                if any(isinstance(itm[k], (dict, list)) for k in non_meta_keys):
                    is_script = (
                        isinstance(itm, dict)
                        and itm.get("script") is not None
                        and itm.get("context") is not None
                    )

                    if is_script:
                        if "scripts" not in self.baseline_snapshot:
                            self.baseline_snapshot["scripts"] = {}
                        self.baseline_snapshot["scripts"][str(item_id)] = itm
                        continue

                    mapping[str(item_id)] = itm

                    entity_id = itm.get("entityId")
                    if entity_id:
                        mapping[str(entity_id)] = itm

                    continue

            # Fetch full config if not already complete
            try:
                url = self._build_api_url(item_id, base_url)
                headers = get_headers(self.command_name)
                headers = {**headers, **self._build_auth_headers(token, url)}

                with httpx.Client() as client:
                    resp = client.get(url, headers=headers)

                if resp.status_code == 200:
                    mapping[str(item_id)] = resp.json()
                else:
                    continue
            except Exception as e:
                logger.warning(f"Failed baseline fetch for {item_id}: {e}")

        # Preserve script entries captured earlier
        scripts_data = self.baseline_snapshot.get("scripts", {})

        for k, v in mapping.items():
            self.baseline_snapshot[k] = v
        self.baseline_snapshot["scripts"] = scripts_data

        self.raw_baseline_data = self.baseline_snapshot

        self._persist_baseline(mapping, git_manager)
        return True

    def _persist_baseline(
        self, mapping: Dict[str, Any], git_manager: Optional[GitManager] = None
    ) -> None:
        """Persist baseline to Git or local storage and log status."""
        if git_manager:
            self._persist_baseline_to_git(git_manager, mapping)
            logger.info("Baseline snapshot created")
        else:
            path = self._persist_baseline_to_local(mapping)
            if path:
                logger.info(f"Baseline snapshot created (File: {path})")
            else:
                logger.info("Baseline snapshot created")

    def _persist_baseline_to_local(self, mapping: Dict[str, Any]) -> str:
        """Saves baseline mapping to a local JSON file for rollback reference."""
        try:
            config_store = ConfigStore()

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            rollback_dir = config_store.base_dir / "rollback" / self.command_name
            rollback_dir.mkdir(parents=True, exist_ok=True)

            filename = f"baseline_{self.realm or 'root'}_{timestamp}.json"
            file_path = rollback_dir / filename

            if self.command_name == "mappings":
                data_to_save = {"_id": "sync", "mappings": list(mapping.values())}
            else:
                data_to_save = mapping

            baseline_file_data = {
                "metadata": {
                    "command": self.command_name,
                    "realm": self.realm,
                    "timestamp": timestamp,
                    "type": "baseline",
                },
                "data": data_to_save,
            }

            # Include captured scripts if present
            scripts = self.baseline_snapshot.get("scripts")
            if scripts:
                baseline_file_data["scripts"] = scripts

            file_path.write_text(
                json.dumps(baseline_file_data, indent=2), encoding="utf-8"
            )
            return str(file_path)
        except Exception as e:
            logger.warning(f"Failed to persist baseline snapshot locally: {e}")
            return ""

    def _persist_baseline_to_git(
        self, git_manager: Any, mapping: Dict[str, Any]
    ) -> None:
        """Create a git branch and commit the baseline mapping."""
        self.git_manager = git_manager

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        branch_name = f"baseline/{self.command_name}/{timestamp}"

        try:
            logger.info(f"Creating baseline git branch: {branch_name}")
            git_manager.ensure_branch(branch_name)

            repo_path = git_manager.local_path
            component = self.command_name

            if self.command_name == "mappings":
                baseline_file_data = {
                    "data": {"_id": "sync", "mappings": list(mapping.values())}
                }
            else:
                baseline_file_data = {"data": self.baseline_snapshot}

            realm_dir = repo_path / (self.realm or "root")
            comp_dir = realm_dir / component
            comp_dir.mkdir(parents=True, exist_ok=True)

            filename = f"{(self.realm or 'root')}_{component}.json"
            file_path = comp_dir / filename

            file_path.write_text(
                json.dumps(baseline_file_data, indent=2), encoding="utf-8"
            )

            rel = file_path.relative_to(repo_path)
            commit_msg = (
                f"Baseline snapshot for {self.command_name} "
                f"({self.realm}) at {timestamp} ({len(mapping)} items)"
            )
            git_manager.commit_and_push([str(rel)], commit_msg, smart_pull=False)
            self.git_branch = branch_name

        except Exception as e:
            logger.warning(f"Failed to persist baseline snapshot to Git: {e}")

    # -----------------------------------------------------------------
    # IMPORT TRACKING
    # -----------------------------------------------------------------

    def track_import(
        self, item_id: str, action: str, baseline_item: Optional[Dict[str, Any]] = None
    ) -> None:
        """Track imported items so rollback can undo them."""
        self.imported_items.append(
            {"id": item_id, "action": action, "baseline": baseline_item}
        )

    # -----------------------------------------------------------------
    # ROLLBACK EXECUTION
    # -----------------------------------------------------------------

    def execute_rollback(self, token: str, base_url: str) -> Dict[str, Any]:
        """Execute rollback of imported items.

        Returns a report dict with 'rolled_back' and 'errors' lists.
        """
        report: Dict[str, Any] = {"rolled_back": [], "errors": []}

        logger.info("Initiating rollback of imported items...")

        # ------------------------------------------------------------
        # CASE 1: No tracked items → restore full baseline
        # ------------------------------------------------------------
        if not self.imported_items:
            logger.warning(
                "No imported items tracked. Restoring entire baseline snapshot..."
            )
            self._restore_full_baseline(token, base_url, report)
            logger.info("Rollback completed (baseline snapshot restored)")
            return report

        # ------------------------------------------------------------
        # CASE 2: Rollback tracked items
        # ------------------------------------------------------------
        self._rollback_tracked_items(token, base_url, report)
        return report

    def _restore_full_baseline(
        self, token: str, base_url: str, report: Dict[str, Any]
    ) -> None:
        """Restore all items from the baseline snapshot."""
        # Restore data items
        for baseline_id, baseline_item in self.baseline_snapshot.items():
            if baseline_id == "scripts":
                continue
            try:
                url = self._build_api_url(baseline_id, base_url)

                if self.command_name == "saml":
                    loc = baseline_item.get("_location")
                    if loc:
                        url = construct_api_url(
                            base_url,
                            f"/am/json/realms/root/realms/{self.realm}"
                            f"/realm-config/saml2/{loc}/{baseline_id}",
                        )

                headers = get_headers(self.command_name)
                headers = {**headers, **self._build_auth_headers(token, url)}

                restore_data = {}
                for k, v in baseline_item.items():
                    if k in {
                        "_id",
                        "_rev",
                        "_type",
                        "entityId",
                        "name",
                        "id",
                        "_location",
                    }:
                        continue
                    if v is None:
                        continue
                    if isinstance(v, dict):
                        restore_data[k] = v
                    elif isinstance(v, str):
                        v_strip = v.strip()
                        if v_strip.startswith("<") and v_strip.endswith(">"):
                            restore_data[k] = v

                with httpx.Client() as client:
                    resp = client.put(url, headers=headers, json=restore_data)

                if resp.status_code in (200, 201, 204):
                    logger.info(f"Restored baseline item: {baseline_id}")
                    report["rolled_back"].append(
                        {"id": baseline_id, "action": "restored"}
                    )
                else:
                    report["errors"].append(
                        {
                            "id": baseline_id,
                            "error": f"{resp.status_code} - {resp.text}",
                        }
                    )
            except Exception as e:
                report["errors"].append({"id": baseline_id, "error": str(e)})

        # Restore scripts
        for script_id, baseline in self.baseline_snapshot.get("scripts", {}).items():
            try:
                url = self._build_api_url(f"script::{script_id}", base_url)
                headers = get_headers("oauth")
                headers = {**headers, **self._build_auth_headers(token, url)}

                restore_data = {}
                for k, v in baseline.items():
                    if k == "_rev":
                        continue
                    if v is None:
                        continue
                    restore_data[k] = v

                restore_data["name"] = restore_data.get("name", baseline.get("name"))
                restore_data["context"] = restore_data.get(
                    "context", baseline.get("context")
                )
                restore_data["language"] = restore_data.get(
                    "language", baseline.get("language", "JAVASCRIPT")
                )

                if "script" in restore_data:
                    script_val = restore_data["script"]
                    if isinstance(script_val, list):
                        script_val = "\n".join(script_val)
                    restore_data["script"] = base64.b64encode(
                        script_val.encode("utf-8")
                    ).decode("ascii")

                with httpx.Client() as client:
                    resp = client.put(url, headers=headers, json=restore_data)

                if resp.status_code in (200, 201, 204):
                    logger.info(f"Restored script: {script_id}")
                    report["rolled_back"].append(
                        {"id": f"script::{script_id}", "action": "restored"}
                    )
                else:
                    report["errors"].append(
                        {
                            "id": script_id,
                            "error": f"{resp.status_code} - {resp.text}",
                        }
                    )
            except Exception as e:
                report["errors"].append({"id": script_id, "error": str(e)})

    def _rollback_tracked_items(
        self, token: str, base_url: str, report: Dict[str, Any]
    ) -> None:
        """Rollback each tracked item in reverse order."""
        for record in reversed(self.imported_items):
            item_id = record.get("id")
            action = record.get("action")

            if not item_id:
                continue
            if isinstance(item_id, str) and item_id.startswith("http"):
                continue

            lookup_id = str(item_id).split("::")[-1]

            baseline = record.get("baseline")
            item_type = None

            is_script = isinstance(item_id, str) and item_id.startswith("script::")
            if lookup_id in self.baseline_snapshot.get("scripts", {}):
                baseline = self.baseline_snapshot["scripts"][lookup_id]
                item_type = "script"
            elif is_script:
                item_type = "script"
            elif lookup_id in self.baseline_snapshot:
                baseline = self.baseline_snapshot[lookup_id]
                item_type = "data"
            elif baseline:
                item_type = "data"

            if action == "updated" and not baseline:
                continue
            if action == "created" and item_type is None:
                item_type = "data"

            if isinstance(lookup_id, str) and lookup_id.startswith("http"):
                continue

            try:
                if item_type == "script":
                    url = self._build_api_url(f"script::{lookup_id}", base_url)
                    headers = get_headers("oauth")
                else:
                    url = self._build_api_url(lookup_id, base_url)
                    headers = get_headers(self.command_name)

                headers = {**headers, **self._build_auth_headers(token, url)}

                if action == "created":
                    self._rollback_delete(
                        item_id,
                        lookup_id,
                        item_type,
                        url,
                        headers,
                        token,
                        base_url,
                        report,
                    )
                elif action == "updated" and baseline:
                    self._rollback_restore(
                        item_id,
                        lookup_id,
                        item_type,
                        baseline,
                        url,
                        headers,
                        token,
                        base_url,
                        report,
                    )
            except Exception as e:
                report["errors"].append({"id": item_id, "error": str(e)})

    def _rollback_delete(
        self,
        item_id: str,
        lookup_id: str,
        item_type: Optional[str],
        url: str,
        headers: Dict[str, str],
        token: str,
        base_url: str,
        report: Dict[str, Any],
    ) -> None:
        """Delete a created item during rollback."""
        if self.command_name == "saml" and item_type != "script":
            loc = ({}).get("_location")  # no baseline for created items
            # Check record baseline for location info
            for record in self.imported_items:
                if record.get("id") == item_id:
                    loc = (record.get("baseline") or {}).get("_location")
                    break
            if loc:
                url = construct_api_url(
                    base_url,
                    f"/am/json/realms/root/realms/{self.realm}"
                    f"/realm-config/saml2/{loc}/{lookup_id}",
                )
                headers = get_headers(self.command_name)
                headers = {**headers, **self._build_auth_headers(token, url)}

        with httpx.Client() as client:
            resp = client.delete(url, headers=headers)

        if resp.status_code in (200, 204):
            logger.info(f"Deleted created item: {item_id}")
            report["rolled_back"].append({"id": item_id, "action": "deleted"})
        else:
            is_default_script_error = (
                resp.status_code == 403
                and "Default script" in resp.text
                and "cannot be deleted" in resp.text
            )
            if is_default_script_error:
                return

            if self.command_name == "policies" and resp.status_code == 404:
                fallback_url = construct_api_url(
                    base_url,
                    f"/am/json/realms/root/realms/{self.realm}"
                    f"/applications/{lookup_id}",
                )
                fallback_headers = get_headers("policy_sets")
                fallback_headers = {
                    **fallback_headers,
                    **self._build_auth_headers(token, fallback_url),
                }
                with httpx.Client() as client:
                    resp = client.delete(fallback_url, headers=fallback_headers)

                if resp.status_code in (200, 204):
                    logger.info(f"Deleted created policy set: {item_id}")
                    report["rolled_back"].append({"id": item_id, "action": "deleted"})
                    return

            report["errors"].append(
                {"id": item_id, "error": f"{resp.status_code} - {resp.text}"}
            )

    def _rollback_restore(
        self,
        item_id: str,
        lookup_id: str,
        item_type: Optional[str],
        baseline: Dict[str, Any],
        url: str,
        headers: Dict[str, str],
        token: str,
        base_url: str,
        report: Dict[str, Any],
    ) -> None:
        """Restore an updated item to its baseline during rollback."""
        restore_data: Dict[str, Any] = {}

        if item_type == "script":
            headers = get_headers("oauth")
            headers = {**headers, **self._build_auth_headers(token, url)}

            for k, v in baseline.items():
                if k == "_rev":
                    continue
                if v is None:
                    continue
                restore_data[k] = v

            restore_data["name"] = baseline.get("name")
            restore_data["context"] = baseline.get("context")
            restore_data["language"] = baseline.get("language", "JAVASCRIPT")

            if "script" in restore_data:
                script_val = restore_data["script"]
                if isinstance(script_val, list):
                    script_val = "\n".join(script_val)
                restore_data["script"] = base64.b64encode(
                    script_val.encode("utf-8")
                ).decode("ascii")

        elif self.command_name == "saml":
            loc = baseline.get("_location")
            if loc:
                url = construct_api_url(
                    base_url,
                    f"/am/json/realms/root/realms/{self.realm}"
                    f"/realm-config/saml2/{loc}/{lookup_id}",
                )
                headers = get_headers(self.command_name)
                headers = {**headers, **self._build_auth_headers(token, url)}

            restore_data = {
                k: v
                for k, v in baseline.items()
                if k not in {"_rev", "_type", "_location", "_saml_location"}
            }
        else:
            restore_data = {
                k: v
                for k, v in baseline.items()
                if k not in {"_rev", "_type", "_location", "_saml_location"}
            }

        with httpx.Client() as client:
            resp = client.put(url, headers=headers, json=restore_data)

        if resp.status_code in (200, 201, 204):
            logger.info(f"Restored baseline item: {item_id}")
            report["rolled_back"].append({"id": item_id, "action": "restored"})
        else:
            report["errors"].append(
                {"id": item_id, "error": f"{resp.status_code} - {resp.text}"}
            )
