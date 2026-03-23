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
            "connectors",
            "themes",
        ]:
            self.realm = realm if realm else "root"
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
            # OAUTH AND SAML: ALSO CAPTURE SCRIPTS
            # ---------------------------------------------------------
            if self.command_name in ("oauth", "saml"):

                script_ids = set()

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
                if script_ids:

                    info(f"Capturing {len(script_ids)} scripts for rollback")

                    import httpx
                    from trxo.utils.url import construct_api_url

                    for script_id in script_ids:

                        try:

                            url = construct_api_url(
                                base_url,
                                f"/am/json/realms/root/realms/{self.realm}/scripts/{script_id}",
                            )

                            headers = get_headers("oauth")
                            headers = {
                                **headers,
                                **self._build_auth_headers(token, url),
                            }

                            with httpx.Client() as client:
                                resp = client.get(url, headers=headers)

                            if resp.status_code == 200:
                                if "scripts" not in self.baseline_snapshot:
                                    self.baseline_snapshot["scripts"] = {}

                                self.baseline_snapshot["scripts"][
                                    script_id
                                ] = resp.json()

                            else:
                                warning(f"Failed to capture script {script_id}")

                        except Exception as e:
                            warning(f"Error fetching script {script_id}: {e}")
            # ---------------------------------------------------------
            # THEMES SPECIAL HANDLING (ui/themerealm)
            # ---------------------------------------------------------
            if self.command_name == "themes":

                if not isinstance(data, dict):
                    error("Unexpected response for ui/themerealm baseline snapshot")
                    return False

                item_id = data.get("_id", "ui/themerealm")

                # Filter only the requested realm
                filtered_doc = dict(data)

                if "realm" in filtered_doc and isinstance(filtered_doc["realm"], dict):
                    if self.realm in filtered_doc["realm"]:
                        filtered_doc["realm"] = {
                            self.realm: filtered_doc["realm"][self.realm]
                        }
                    else:
                        warning(f"Realm '{self.realm}' not found in ui/themerealm")
                        filtered_doc["realm"] = {}

                mapping = {item_id: filtered_doc}

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

                    for value in obj.values():
                        if isinstance(value, list):
                            collected.extend(value)

                    if collected:
                        return collected

                return []

            if self.command_name == "saml" and isinstance(data, dict):
                # Annotate SAML entities so we know where to restore them
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

                # Skip script items already captured
                if isinstance(item_id, str) and item_id.startswith("script::"):
                    continue

                # Already full config
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
                        continue

                except Exception as e:
                    warning(f"Failed baseline fetch for {item_id}: {e}")

            # Preserve script entries captured earlier
            scripts_data = self.baseline_snapshot.get("scripts", {})

            self.baseline_snapshot = {
                "data": mapping,
                "scripts": scripts_data,
            }
            self.raw_baseline_data = self.baseline_snapshot
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
                        baseline_file_data = {"data": self.baseline_snapshot}

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

        import httpx
        import base64

        # ------------------------------------------------------------
        # CASE 1: No tracked items → restore full baseline
        # ------------------------------------------------------------
        if not self.imported_items:
            warning("No imported items tracked. Restoring entire baseline snapshot...")

            # ----------- RESTORE DATA (SAML etc) -----------
            for baseline_id, baseline_item in self.baseline_snapshot.get(
                "data", {}
            ).items():
                try:
                    url = self._build_api_url(baseline_id, base_url)

                    if self.command_name == "saml":
                        loc = baseline_item.get("_location")
                        if loc:
                            from trxo.utils.url import construct_api_url

                            url = construct_api_url(
                                base_url,
                                f"/am/json/realms/root/realms/{self.realm}/realm-config/saml2/{loc}/{baseline_id}",
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

                        # ✅ ONLY VALID SAML BLOCKS
                        if isinstance(v, dict):
                            restore_data[k] = v

                        elif isinstance(v, str):
                            v_strip = v.strip()
                            if v_strip.startswith("<") and v_strip.endswith(">"):
                                restore_data[k] = v

                    with httpx.Client() as client:
                        resp = client.put(url, headers=headers, json=restore_data)

                    if resp.status_code in (200, 201, 204):
                        info(f"Restored baseline item: {baseline_id}")
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

            # ----------- RESTORE SCRIPTS -----------
            for script_id, baseline in self.baseline_snapshot.get(
                "scripts", {}
            ).items():
                try:
                    url = self._build_api_url(f"script::{script_id}", base_url)

                    headers = get_headers("oauth")  # ✅ IMPORTANT
                    headers = {**headers, **self._build_auth_headers(token, url)}

                    restore_data = {}

                    for k, v in baseline.items():
                        if k == "_rev":
                            continue
                        if v is None:
                            continue
                        restore_data[k] = v

                    # ✅ ADD THIS (minimal fix, no logic change)
                    restore_data["name"] = restore_data.get(
                        "name", baseline.get("name")
                    )
                    restore_data["context"] = restore_data.get(
                        "context", baseline.get("context")
                    )
                    restore_data["language"] = restore_data.get(
                        "language", baseline.get("language", "JAVASCRIPT")
                    )

                    # ✅ encode script properly
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
                        info(f"Restored script: {script_id}")
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

            info("Rollback completed (baseline snapshot restored)")
            return report

        # ------------------------------------------------------------
        # CASE 2: Rollback tracked items
        # ------------------------------------------------------------
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

            if lookup_id in self.baseline_snapshot.get("scripts", {}):
                baseline = self.baseline_snapshot["scripts"][lookup_id]
                item_type = "script"

            elif lookup_id in self.baseline_snapshot.get("data", {}):
                baseline = self.baseline_snapshot["data"][lookup_id]
                item_type = "data"

            elif baseline:
                # Baseline was stored at tracking time (e.g. SAML entities)
                item_type = "data"

            # Skip updated items that have no baseline data to restore from
            if action == "updated" and not baseline:
                continue

            # For created items with no baseline – we delete them (no skip)
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

                # -------- DELETE --------
                if action == "created":
                    if self.command_name == "saml":
                        loc = (record.get("baseline") or {}).get("_location")
                        if loc:
                            from trxo.utils.url import construct_api_url

                            url = construct_api_url(
                                base_url,
                                f"/am/json/realms/root/realms/{self.realm}"
                                f"/realm-config/saml2/{loc}/{lookup_id}",
                            )
                            headers = get_headers(self.command_name)
                            headers = {
                                **headers,
                                **self._build_auth_headers(token, url),
                            }

                    with httpx.Client() as client:
                        resp = client.delete(url, headers=headers)

                    if resp.status_code in (200, 204):
                        info(f"Deleted created item: {item_id}")
                        report["rolled_back"].append(
                            {"id": item_id, "action": "deleted"}
                        )
                    else:
                        is_default_script_error = (
                            resp.status_code == 403
                            and "Default script" in resp.text
                            and "cannot be deleted" in resp.text
                        )
                        if is_default_script_error:
                            continue
                        else:
                            report["errors"].append(
                                {
                                    "id": item_id,
                                    "error": f"{resp.status_code} - {resp.text}",
                                }
                            )

                # -------- RESTORE --------
                elif action == "updated" and baseline:

                    restore_data = {}

                    # ---------------- SCRIPT ----------------
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
                        restore_data["language"] = baseline.get(
                            "language", "JAVASCRIPT"
                        )

                        if "script" in restore_data:
                            script_val = restore_data["script"]
                            if isinstance(script_val, list):
                                script_val = "\n".join(script_val)

                            restore_data["script"] = base64.b64encode(
                                script_val.encode("utf-8")
                            ).decode("ascii")

                    # ---------------- SAML ----------------
                    elif self.command_name == "saml":

                        loc = baseline.get("_location")
                        if loc:
                            from trxo.utils.url import construct_api_url

                            url = construct_api_url(
                                base_url,
                                f"/am/json/realms/root/realms/{self.realm}"
                                f"/realm-config/saml2/{loc}/{lookup_id}",
                            )
                            headers = get_headers(self.command_name)
                            headers = {
                                **headers,
                                **self._build_auth_headers(token, url),
                            }

                        restore_data = {
                            k: v
                            for k, v in baseline.items()
                            if k not in {"_rev", "_type", "_location"}
                        }

                    # ---------------- DEFAULT ----------------
                    else:
                        restore_data = {
                            k: v
                            for k, v in baseline.items()
                            if k not in {"_rev", "_type"}
                        }

                    with httpx.Client() as client:
                        resp = client.put(url, headers=headers, json=restore_data)

                    if resp.status_code in (200, 201, 204):
                        info(f"Restored baseline item: {item_id}")
                        report["rolled_back"].append(
                            {"id": item_id, "action": "restored"}
                        )
                    else:
                        report["errors"].append(
                            {
                                "id": item_id,
                                "error": f"{resp.status_code} - {resp.text}",
                            }
                        )

            except Exception as e:
                report["errors"].append({"id": item_id, "error": str(e)})

        return report

    # ---------------------------------------------------------------------
    # URL BUILDER (FIXED)
    # ---------------------------------------------------------------------

    def _build_api_url(self, item_id: str, base_url: str) -> str:

        try:

            from trxo.utils.url import construct_api_url

            # Handle OAuth scripts
            if isinstance(item_id, str) and item_id.startswith("script::"):

                script_id = item_id.replace("script::", "")

                return construct_api_url(
                    base_url,
                    f"/am/json/realms/root/realms/{self.realm}/scripts/{script_id}",
                )

            api_endpoint, _ = get_command_api_endpoint(self.command_name, self.realm)

            if not api_endpoint:
                raise RuntimeError("Unknown command API endpoint")

            api_endpoint = api_endpoint.split("?")[0]

            if not api_endpoint.endswith("/"):
                api_endpoint += "/"

            api_endpoint = f"{api_endpoint}{item_id}"

            return construct_api_url(base_url, api_endpoint)

        except Exception:

            from trxo.utils.url import construct_api_url

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

            return {}

        return {"Cookie": f"iPlanetDirectoryPro={token}"}
