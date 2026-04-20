"""
Journey import commands.

This module provides import functionality for
PingOne Advanced Identity Cloud journeys.

It handles two export formats:

1. **Enriched format** (new) — produced by the updated journey exporter.
   The ``data`` dict contains ``trees``, ``nodes``, ``innerNodes``,
   ``scripts``, ``emailTemplates``, ``themes``, ``saml2Entities``,
   ``saml2CirclesOfTrust``, ``socialIdentityProviders``.
   Dependencies are imported in order before the journeys themselves.

2. **Legacy flat format** (backward-compatible) — a raw list of tree
   objects, or the old trxo-wrapped ``{"metadata": ..., "data": [...]}``
   structure.  Handled by the original ``BaseImporter`` processing chain.
"""

from trxo_lib.exceptions import TrxoAbort
import base64
import json
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

from trxo_lib.config.api_headers import get_headers
from trxo_lib.config.constants import DEFAULT_REALM
from trxo_lib.logging import error, info, success, warning

from trxo_lib.imports.processor import BaseImporter


# Lazy-imported to avoid circular-dependency at module load time
# (saml.py and themes.py both pull in base_importer which pulls in journeys
# through the CLI registry).  We import inside methods that need them.
def _saml_importer(realm: str):
    from .saml import SamlImporter  # noqa: PLC0415

    return SamlImporter(realm=realm)


def _themes_importer():
    from .themes import ThemesImporter  # noqa: PLC0415

    return ThemesImporter()


# ---------------------------------------------------------------------------
# JourneyImporter
# ---------------------------------------------------------------------------


class JourneyImporter(BaseImporter):
    """Importer for PingOne Advanced Identity Cloud journeys."""

    def __init__(self, realm: str = DEFAULT_REALM):
        super().__init__()
        self.realm = realm

    # ── BaseImporter contract ───────────────────────────────────────────

    def get_required_fields(self) -> List[str]:
        return ["_id"]

    def get_item_type(self) -> str:
        return "journeys"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/realm-config/"
            f"authentication/authenticationtrees/trees/{item_id}",
        )

    # ── override import_from_file so we can detect enriched format ──────

    def load_data_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Custom normaliser used by BaseImporter._import_from_local().

        Reads the raw JSON directly (bypassing FileLoader's strict schema
        validation) so it can handle:
         - Enriched format: ``{"data": {"trees": {...}, ...}}``
           → returns list of tree dicts
         - Legacy trxo flat format: ``{"data": [...]}``
           → returns the list
         - Legacy trxo result format: ``{"data": {"result": [...]}}``
           → returns the result list
        """
        import os

        fp = file_path if os.path.isabs(file_path) else os.path.abspath(file_path)
        with open(fp, "r", encoding="utf-8") as fh:
            file_json = json.load(fh)

        # Unwrap trxo metadata wrapper
        if isinstance(file_json, dict) and "data" in file_json:
            payload = file_json["data"]
        else:
            payload = file_json

        # Enriched format: data section is a dict with a "trees" key
        if isinstance(payload, dict) and "trees" in payload:
            return list(payload["trees"].values())

        # Legacy format with result array
        if isinstance(payload, dict) and "result" in payload:
            return payload["result"]

        # Flat list
        if isinstance(payload, list):
            return payload

        # Single journey object
        if isinstance(payload, dict):
            return [payload]

        return []

    def import_from_file(
        self,
        file_path=None,
        realm=None,
        src_realm=None,
        jwk_path=None,
        sa_id=None,
        base_url=None,
        project_name=None,
        auth_mode=None,
        onprem_username=None,
        onprem_password=None,
        onprem_realm=None,
        idm_base_url=None,
        idm_username=None,
        idm_password=None,
        am_base_url=None,
        force_import=False,
        branch=None,
        diff=False,
        rollback=False,
        sync=False,
        cherry_pick=None,
    ):
        """
        Override: detect enriched vs legacy format and branch accordingly.

        Enriched format (has ``trees`` key in ``data``) uses
        ``import_journey_data()`` with ordered dependency import.

        Legacy flat list falls through to the standard BaseImporter flow.
        """
        # ── Git mode: load file from git, then probe for enriched format ──
        storage_mode = self._get_storage_mode()
        if storage_mode == "git":
            # Ask the base-class machinery to resolve the git file path/content
            # so we can probe it for the enriched format before deciding how to route.
            from pathlib import Path as _Path

            from trxo_lib.imports.helpers.file_loader import FileLoader

            git_manager = self._setup_git_manager(branch)
            effective_realm = self._determine_effective_realm(
                realm, self.get_item_type(), branch
            )
            repo_path = _Path(git_manager.local_path)
            discovered = FileLoader.discover_git_files(
                repo_path, self.get_item_type(), effective_realm
            )

            if not discovered:
                self._handle_no_git_files_found(
                    self.get_item_type(), effective_realm, realm
                )
                return

            # Use the first discovered file (same logic as base _import_from_git)
            git_file_path = discovered[0]
            info(f"Found: {git_file_path.relative_to(repo_path)}")
            info(f"Loading from: {git_file_path.relative_to(repo_path)}")

            import json as _json

            with open(git_file_path, "r", encoding="utf-8") as _fh:
                raw_file = _json.load(_fh)

            # Unwrap trxo metadata wrapper
            if isinstance(raw_file, dict) and "data" in raw_file:
                payload = raw_file["data"]
            else:
                payload = raw_file

            is_enriched = isinstance(payload, dict) and "trees" in payload

            if not is_enriched:
                # Legacy format — let BaseImporter handle everything via super()
                return super().import_from_file(
                    file_path=str(git_file_path),
                    realm=realm,
                    src_realm=src_realm,
                    jwk_path=jwk_path,
                    sa_id=sa_id,
                    base_url=base_url,
                    project_name=project_name,
                    auth_mode=auth_mode,
                    onprem_username=onprem_username,
                    onprem_password=onprem_password,
                    onprem_realm=onprem_realm,
                    idm_base_url=idm_base_url,
                    idm_username=idm_username,
                    idm_password=idm_password,
                    am_base_url=am_base_url,
                    force_import=force_import,
                    branch=branch,
                    diff=diff,
                    rollback=rollback,
                    sync=sync,
                    cherry_pick=cherry_pick,
                )

            # ── Enriched git file → same path as local enriched ───────────
            info("Detected enriched journey export (with dependency graph)")

            token, api_base_url = self.initialize_auth(
                jwk_path=jwk_path,
                sa_id=sa_id,
                base_url=base_url,
                project_name=project_name,
                auth_mode=auth_mode,
                onprem_username=onprem_username,
                onprem_password=onprem_password,
                onprem_realm=onprem_realm,
                idm_base_url=idm_base_url,
                idm_username=idm_username,
                idm_password=idm_password,
                am_base_url=am_base_url,
            )

            try:
                # Git mode does not perform local hash validation

                if diff:
                    self._perform_enriched_journey_diff(
                        payload=payload,
                        realm=realm,
                        jwk_path=jwk_path,
                        sa_id=sa_id,
                        base_url=base_url,
                        project_name=project_name,
                        auth_mode=auth_mode,
                        onprem_username=onprem_username,
                        onprem_password=onprem_password,
                        onprem_realm=onprem_realm,
                        idm_base_url=idm_base_url,
                        idm_username=idm_username,
                        idm_password=idm_password,
                        am_base_url=am_base_url,
                        file_path=str(git_file_path),
                    )
                    return

                ok = self.import_journey_data(
                    data=payload,
                    token=token,
                    base_url=api_base_url,
                    cherry_pick_ids=cherry_pick,
                    rollback_managers=self._setup_enriched_rollback_managers(
                        rollback=rollback,
                        branch=branch,
                        token=token,
                        base_url=api_base_url,
                    ),
                )
                if not ok:
                    if rollback:
                        self._execute_enriched_rollback(token, api_base_url)
                    raise TrxoAbort(code=1)
            finally:
                self.cleanup()
            return

        # ── Local mode: probe the file for enriched format ───────────────
        if not file_path:
            error("File path is required for local storage mode")
            raise TrxoAbort(code=1)

        import os

        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        with open(file_path, "r", encoding="utf-8") as fh:
            raw_file = json.load(fh)

        # Unwrap trxo metadata wrapper
        if isinstance(raw_file, dict) and "data" in raw_file:
            payload = raw_file["data"]
        else:
            payload = raw_file

        is_enriched = isinstance(payload, dict) and "trees" in payload

        if not is_enriched:
            # Legacy path — let BaseImporter handle everything
            return super().import_from_file(
                file_path=file_path,
                realm=realm,
                src_realm=src_realm,
                jwk_path=jwk_path,
                sa_id=sa_id,
                base_url=base_url,
                project_name=project_name,
                auth_mode=auth_mode,
                onprem_username=onprem_username,
                onprem_password=onprem_password,
                onprem_realm=onprem_realm,
                idm_base_url=idm_base_url,
                idm_username=idm_username,
                idm_password=idm_password,
                am_base_url=am_base_url,
                force_import=force_import,
                branch=branch,
                diff=diff,
                rollback=rollback,
                sync=sync,
                cherry_pick=cherry_pick,
            )

        # ── Enriched format ───────────────────────────────────────────────
        info("Detected enriched journey export (with dependency graph)")

        token, api_base_url = self.initialize_auth(
            jwk_path=jwk_path,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            idm_base_url=idm_base_url,
            idm_username=idm_username,
            idm_password=idm_password,
            am_base_url=am_base_url,
        )

        try:
            if not self.validate_import_hash(raw_file, force_import):
                error("Import validation failed: hash mismatch with exported data")
                raise TrxoAbort(code=1)

            # ── Diff mode: show changes without importing ─────────────────
            if diff:
                self._perform_enriched_journey_diff(
                    payload=payload,
                    realm=realm,
                    jwk_path=jwk_path,
                    sa_id=sa_id,
                    base_url=base_url,
                    project_name=project_name,
                    auth_mode=auth_mode,
                    onprem_username=onprem_username,
                    onprem_password=onprem_password,
                    onprem_realm=onprem_realm,
                    idm_base_url=idm_base_url,
                    idm_username=idm_username,
                    idm_password=idm_password,
                    am_base_url=am_base_url,
                    file_path=file_path,
                )
                return

            ok = self.import_journey_data(
                data=payload,
                token=token,
                base_url=api_base_url,
                cherry_pick_ids=cherry_pick,
                rollback_managers=self._setup_enriched_rollback_managers(
                    rollback=rollback,
                    branch=branch,
                    token=token,
                    base_url=api_base_url,
                ),
            )
            if not ok:
                if rollback:
                    self._execute_enriched_rollback(token, api_base_url)
                raise TrxoAbort(code=1)
        finally:
            self.cleanup()

    def _setup_enriched_rollback_managers(
        self,
        rollback: bool,
        branch: Optional[str],
        token: str,
        base_url: str,
    ) -> Dict[str, Any]:
        """Create rollback managers for journey enriched imports (journeys + deps)."""
        self._enriched_rollback_managers = {}
        if not rollback:
            return self._enriched_rollback_managers

        from trxo_lib.state.rollback import RollbackManager

        storage_mode = self._get_storage_mode()
        git_mgr = self._setup_git_manager(branch) if storage_mode == "git" else None

        specs = {
            "scripts": "scripts",
            "emailTemplates": "email_templates",
            "saml2Entities": "saml",
            "themes": "themes",
            "nodes": "nodes",
            "trees": "journeys",
        }

        for section, command_name in specs.items():
            manager = RollbackManager(command_name, self.realm)
            created = manager.create_baseline_snapshot(
                token,
                base_url,
                git_manager=git_mgr,
                auth_mode=self.auth_mode,
                idm_username=self._idm_username,
                idm_password=self._idm_password,
                idm_base_url=self._idm_base_url,
            )
            if created:
                self._enriched_rollback_managers[section] = manager
            else:
                warning(
                    f"Rollback baseline unavailable for {section}; "
                    "rollback for that section will be skipped"
                )

        return self._enriched_rollback_managers

    def _track_enriched_rollback(self, section: str, item_id: str, **kwargs) -> None:
        manager = getattr(self, "_enriched_rollback_managers", {}).get(section)
        if not manager or not item_id:
            return

        baseline_item = manager.baseline_snapshot.get(str(item_id))
        action = "updated" if baseline_item is not None else "created"

        # For SAML entities, ensure location is stored in baseline
        # so rollback URL builder knows the correct endpoint path
        saml_location = kwargs.get("saml_location")
        saml_entity_id = kwargs.get("saml_entity_id")
        if section == "saml2Entities" and saml_location:
            if baseline_item is None:
                # Newly created — store minimal entry with location
                # and the AM _id so rollback can build the correct URL
                entry = {"_saml_location": saml_location}
                if saml_entity_id:
                    entry["_id"] = saml_entity_id
                manager.baseline_snapshot[str(item_id)] = entry
            elif isinstance(baseline_item, dict):
                baseline_item.setdefault("_saml_location", saml_location)

        # For Nodes, store node_type if it's newly created
        node_type = kwargs.get("node_type")
        if section == "nodes" and node_type:
            if baseline_item is None:
                manager.baseline_snapshot[str(item_id)] = {"_type": {"_id": node_type}}

        manager.track_import(str(item_id), action, baseline_item)

    def _execute_enriched_rollback(self, token: str, base_url: str) -> None:
        """Rollback enriched journey imports in reverse dependency order."""
        managers = getattr(self, "_enriched_rollback_managers", {})
        for section in [
            "trees",
            "themes",
            "nodes",
            "saml2Entities",
            "emailTemplates",
            "scripts",
        ]:
            manager = managers.get(section)
            if not manager:
                continue
            info(f"Running rollback for journey section: {section}")
            report = manager.execute_rollback(token, base_url)
            self._print_rollback_report(report)

    # ── Diff helper (enriched format) ─────────────────────────────────────

    def _perform_enriched_journey_diff(
        self,
        payload: dict,
        realm: str,
        file_path: str,
        jwk_path=None,
        sa_id=None,
        base_url=None,
        project_name=None,
        auth_mode=None,
        onprem_username=None,
        onprem_password=None,
        onprem_realm=None,
        idm_base_url=None,
        idm_username=None,
        idm_password=None,
        am_base_url=None,
    ) -> None:
        """
        Show diff for enriched journey exports.

        - Journeys (trees): full DiffEngine diff against live AM data
          (fetched via DataFetcher so auth is reused), rendered via
          DiffReporter with HTML report generation.
        - All other deps (nodes, scripts, etc.): counts-only table with
          file vs server columns.  Server count is fetched for journeys
          as a by-product of the tree diff — no extra round-trips needed.
        """
        from pathlib import Path

        from trxo_lib.state.diff.data_fetcher import (
            DataFetcher,
            get_command_api_endpoint,
        )
        from trxo_lib.state.diff.diff_engine import DiffEngine
        from trxo_lib.state.diff.diff_reporter import DiffReporter

        info("Diff mode: comparing journey trees against live environment...")

        # ── Step 1: Fetch live tree list from AM ──────────────────────────
        fetcher = DataFetcher()
        api_endpoint, response_filter = get_command_api_endpoint(
            "journeys", realm or "alpha"
        )
        current_data = fetcher.fetch_data(
            command_name="journeys",
            api_endpoint=api_endpoint,
            response_filter=response_filter,
            realm=realm,
            jwk_path=jwk_path,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            idm_base_url=idm_base_url,
            idm_username=idm_username,
            idm_password=idm_password,
            am_base_url=am_base_url,
        )

        # ── Step 2: Convert local trees dict → result list ────────────────
        # The enriched export stores trees as {treeId: {_id, nodes, ...}}.
        # DiffEngine._extract_items expects {"result": [{_id, ...}, ...]}
        # (or raw list).  We convert once here so no engine changes needed.
        local_trees: dict = payload.get("trees", {})
        local_trees_list = list(local_trees.values())
        new_data = {"result": local_trees_list}

        diff_result = None

        if current_data is None:
            from trxo_lib.logging import warning as _warning

            _warning("Could not fetch live data — showing file counts only")
        else:
            # current_data already comes back as {"result": [...]} from
            # DataFetcher (it unwraps the AM response wrapper for us).
            if isinstance(current_data, dict) and "result" in current_data:
                pass
            elif isinstance(current_data, list):
                current_data = {"result": current_data}

            # ── Step 3: Run diff engine ───────────────────────────────────
            engine = DiffEngine()
            diff_result = engine.compare_data(
                current_data=current_data,
                new_data=new_data,
                command_name="journeys",
                realm=realm,
            )

            # ── Step 4: Display rich diff report ──────────────────────────
            reporter = DiffReporter()
            reporter.display_summary(diff_result)

            html_path = reporter.generate_html_diff(
                diff_result=diff_result,
                current_data=current_data,
                new_data=new_data,
            )
            if html_path:
                html_uri = Path(html_path).absolute().as_uri()
                info(f"Open HTML report: {html_uri}")

            total = (
                len(diff_result.added_items)
                + len(diff_result.modified_items)
                + len(diff_result.removed_items)
            )
            if total > 0:
                from trxo_lib.logging import warning as _warning

                _warning(
                    f"Journey diff: {total} change(s) found — "
                    "run without --diff to import"
                )
            else:
                from trxo_lib.logging import success as _success

                _success("Journey diff: no changes — journeys are already up to date")

        # ── Step 5: Dep counts table (file counts only) ───────────────────
        dep_sections = [
            ("Trees (journeys)", "trees"),
            ("Root nodes", "nodes"),
            ("Inner nodes", "innerNodes"),
            ("Scripts", "scripts"),
            ("Email templates", "emailTemplates"),
            ("SAML2 entities", "saml2Entities"),
            ("Circles of trust", "saml2CirclesOfTrust"),
            ("Themes", "themes"),
            ("Social providers", "socialIdentityProviders"),
        ]

        rows = [
            (label, len(payload.get(key, {})))
            for label, key in dep_sections
            if len(payload.get(key, {})) > 0
        ]

        if rows:
            print()
            col_w = max(len(label) for label, _ in rows) + 2
            separator = "+" + "-" * (col_w + 2) + "+" + "-" * 9 + "+"
            print(separator)
            print(f"| {'Dependency':<{col_w}} | {'In file':>7} |")
            print(separator)
            for label, count in rows:
                print(f"| {label:<{col_w}} | {count:>7} |")
            print(separator)
            info("(Dep counts are from the export file — use import to apply them)")

    # ── Enriched import orchestrator ─────────────────────────────────────

    def import_journey_data(
        self,
        data: Dict[str, Any],
        token: str,
        base_url: str,
        cherry_pick_ids: Optional[str] = None,
        rollback_managers: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Import an enriched journey export in dependency order:

        1.  Scripts
        2.  Email templates
        3.  SAML2 entities (metadata first, then hosted/remote upsert)
        4.  SAML2 circles of trust
        5.  Inner nodes (page-node children first)
        6.  Root nodes
        7.  Themes (merged into the living themerealm document)
        8.  Journeys (trees)

        Args:
            data: Enriched export payload (the ``data`` section, not the
                  full file wrapper).
            token: Authentication bearer token.
            base_url: AM API base URL.
            cherry_pick_ids: Optional comma-separated journey IDs (_id) to
                             import selectively.

        Returns:
            True if all steps succeeded (or had nothing to do), False on error.
        """
        if not data:
            warning("No journey data to import")
            return True

        selected_tree_ids: Optional[List[str]] = None
        cherry_pick_scope: Optional[Dict[str, set]] = None
        if cherry_pick_ids:
            selected_tree_ids = [
                i.strip() for i in cherry_pick_ids.split(",") if i.strip()
            ]
            info(f"Cherry-pick mode: importing journeys {selected_tree_ids}")
            # Single O(n) pass over the local JSON — no network calls.
            cherry_pick_scope = _resolve_deps_for_trees(data, selected_tree_ids)
            info(
                f"  Resolved deps: "
                f"{len(cherry_pick_scope['root_nodes'])} root node(s), "
                f"{len(cherry_pick_scope['inner_nodes'])} inner node(s), "
                f"{len(cherry_pick_scope['scripts'])} script(s), "
                f"{len(cherry_pick_scope['email_templates'])} email template(s), "
                f"{len(cherry_pick_scope['saml2_entities'])} SAML2 entity(ies), "
                f"{len(cherry_pick_scope['cots'])} CoT(s), "
                f"{len(cherry_pick_scope['themes'])} theme(s)"
            )

        error_count = 0
        fail_fast = bool(rollback_managers)

        # -- 1. Scripts -------------------------------------------------------
        scripts: Dict[str, Any] = data.get("scripts", {})
        if scripts:
            needed = (
                _scripts_needed_by_trees(data, selected_tree_ids)
                if selected_tree_ids
                else set(scripts.keys())
            )
            to_import = {sid: cfg for sid, cfg in scripts.items() if sid in needed}
            if to_import:
                info(f"Importing {len(to_import)} script(s)")
            for script_id, script_cfg in to_import.items():
                if not self._import_single_script(script_cfg, token, base_url):
                    error_count += 1
                    if fail_fast:
                        return False
                else:
                    self._track_enriched_rollback("scripts", script_id)

        # -- 2. Email templates -----------------------------------------------
        email_templates: Dict[str, Any] = data.get("emailTemplates", {})
        if email_templates:
            if cherry_pick_scope is not None:
                email_templates = {
                    k: v
                    for k, v in email_templates.items()
                    if k in cherry_pick_scope["email_templates"]
                }
            if email_templates:
                info(f"Importing {len(email_templates)} email template(s)")
            for name, tmpl_cfg in email_templates.items():
                if not self._import_email_template(name, tmpl_cfg, token, base_url):
                    error_count += 1
                    if fail_fast:
                        return False
                else:
                    self._track_enriched_rollback("emailTemplates", name)

        # -- 3. SAML2 entities ------------------------------------------------
        saml2_entities: Dict[str, Any] = data.get("saml2Entities", {})
        if saml2_entities:
            if cherry_pick_scope is not None:
                saml2_entities = {
                    k: v
                    for k, v in saml2_entities.items()
                    if k in cherry_pick_scope["saml2_entities"]
                }
            if saml2_entities:
                info(f"Importing {len(saml2_entities)} SAML2 entity(ies)")
                saml_imp = _saml_importer(self.realm)
                saml_imp.token = token
                for entity_id, entity_entry in saml2_entities.items():
                    if not self._import_saml_entity(
                        entity_id, entity_entry, saml_imp, token, base_url
                    ):
                        error_count += 1
                        if fail_fast:
                            return False
                    else:
                        # Determine location and AM _id for rollback URL
                        saml_loc = "hosted" if "hosted" in entity_entry else "remote"
                        # Extract the AM _id from entity config
                        provider_cfg = (
                            entity_entry.get("hosted")
                            or entity_entry.get("remote")
                            or {}
                        )
                        saml_am_id = provider_cfg.get("_id")
                        self._track_enriched_rollback(
                            "saml2Entities",
                            entity_id,
                            saml_location=saml_loc,
                            saml_entity_id=saml_am_id,
                        )

        # -- 4. Circles of trust ----------------------------------------------
        cots: Dict[str, Any] = data.get("saml2CirclesOfTrust", {})
        if cots:
            if cherry_pick_scope is not None:
                cots = {k: v for k, v in cots.items() if k in cherry_pick_scope["cots"]}
            if cots:
                info(f"Importing {len(cots)} circle(s) of trust")
            for cot_id, cot_cfg in cots.items():
                if not self._import_circle_of_trust(cot_id, cot_cfg, token, base_url):
                    error_count += 1
                    if fail_fast:
                        return False

        # -- 5. Inner nodes ---------------------------------------------------
        inner_nodes: Dict[str, Any] = data.get("innerNodes", {})
        if inner_nodes:
            if cherry_pick_scope is not None:
                inner_nodes = {
                    k: v
                    for k, v in inner_nodes.items()
                    if k in cherry_pick_scope["inner_nodes"]
                }
            if inner_nodes:
                info(f"Importing {len(inner_nodes)} inner node(s)")
            for node_id, node_cfg in inner_nodes.items():
                if not self._import_node(node_id, node_cfg, token, base_url):
                    error_count += 1
                    if fail_fast:
                        return False
                else:
                    n_type = (node_cfg.get("_type") or {}).get("_id")
                    self._track_enriched_rollback("nodes", node_id, node_type=n_type)

        # -- 6. Root nodes ----------------------------------------------------
        nodes: Dict[str, Any] = data.get("nodes", {})
        if nodes:
            if cherry_pick_scope is not None:
                nodes = {
                    k: v
                    for k, v in nodes.items()
                    if k in cherry_pick_scope["root_nodes"]
                }
            if nodes:
                info(f"Importing {len(nodes)} root node(s)")
            for node_id, node_cfg in nodes.items():
                if not self._import_node(node_id, node_cfg, token, base_url):
                    error_count += 1
                    if fail_fast:
                        return False
                else:
                    n_type = (node_cfg.get("_type") or {}).get("_id")
                    self._track_enriched_rollback("nodes", node_id, node_type=n_type)

        # -- 7. Themes --------------------------------------------------------
        themes: Dict[str, Any] = data.get("themes", {})
        if themes:
            if cherry_pick_scope is not None:
                themes = {
                    k: v for k, v in themes.items() if k in cherry_pick_scope["themes"]
                }
            if themes:
                info(f"Importing {len(themes)} theme(s)")
                if not self._import_themes(themes, token, base_url):
                    error_count += 1
                    if fail_fast:
                        return False
                else:
                    self._track_enriched_rollback("themes", "ui/themerealm")

        # -- 8. Journeys (trees) ----------------------------------------------
        trees: Dict[str, Any] = data.get("trees", {})
        if selected_tree_ids:
            trees = {k: v for k, v in trees.items() if k in selected_tree_ids}

        if trees:
            info(f"Importing {len(trees)} journey(s)")
            for tree_id, tree_cfg in trees.items():
                if not self.update_item(tree_cfg, token, base_url):
                    error_count += 1
                    if fail_fast:
                        return False
                else:
                    self._track_enriched_rollback("trees", tree_id)
        else:
            warning("No journeys found in export data")

        if error_count == 0:
            success(
                f"Journey import completed successfully — "
                f"{len(trees)} journey(s), "
                f"{len(nodes)} root node(s), "
                f"{len(inner_nodes)} inner node(s), "
                f"{len(scripts)} script(s), "
                f"{len(email_templates)} email template(s), "
                f"{len(saml2_entities)} SAML2 entity(ies), "
                f"{len(cots)} circle(s) of trust, "
                f"{len(themes)} theme(s)"
            )
        else:
            warning(f"Journey import completed with {error_count} error(s)")

        return error_count == 0

    # ── update_item (single journey PUT — used by both paths) ───────────

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Update a single journey tree via PUT."""
        item_id = item_data.get("_id")

        if not item_id:
            error("Journey missing _id field, skipping")
            return False

        url = self.get_api_endpoint(item_id, base_url)
        filtered_data = {k: v for k, v in item_data.items() if k not in ("_id", "_rev")}
        payload = json.dumps(filtered_data)

        headers = get_headers("journeys")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, payload)
            self.logger.debug(f"Imported journey: {item_id}")
            return True
        except Exception as exc:
            error(f"Error importing journey '{item_id}': {exc}")
            return False

    # ── Dependency import helpers ─────────────────────────────────────────

    def _import_single_script(
        self, script_data: Dict[str, Any], token: str, base_url: str
    ) -> bool:
        """Import one script, encoding the script field to base64 as required."""
        script_id = script_data.get("_id")
        script_name = script_data.get("name", script_id or "unknown")

        if not script_id:
            error(f"Script '{script_name}' missing _id field, skipping")
            return False

        payload_data = {k: v for k, v in script_data.items() if k != "_rev"}

        # Encode script field (stored as list of lines in enriched export)
        script_field = payload_data.get("script")
        if script_field is not None:
            if isinstance(script_field, list):
                script_text = "\n".join(script_field)
            elif isinstance(script_field, str):
                script_text = script_field
            else:
                error(
                    f"Script '{script_name}' has unexpected type: {type(script_field)}"
                )
                return False

            if script_text:
                try:
                    encoded = base64.b64encode(script_text.encode("utf-8")).decode(
                        "ascii"
                    )
                    payload_data["script"] = encoded
                except Exception as exc:
                    error(f"Failed to encode script '{script_name}': {exc}")
                    return False

        url = self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/scripts/{quote(script_id)}",
        )
        headers = get_headers("journeys")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            # First try updating (PUT) using httpx directly to avoid noisy 404 logs
            # from make_http_request since a 404 here just means "needs creation"
            with httpx.Client(timeout=30.0) as client:
                response = client.put(url, headers=headers, json=payload_data)

                if response.status_code == 404:
                    # Switch to create logic
                    create_url = self._construct_api_url(
                        base_url,
                        f"/am/json/realms/root/realms/{self.realm}/scripts?_action=create",
                    )
                    self.make_http_request(
                        create_url, "POST", headers, json.dumps(payload_data)
                    )
                    self.logger.debug(f"Created script: {script_name} ({script_id})")
                    return True

                # Otherwise, raise if not successful
                response.raise_for_status()

            self.logger.debug(f"Imported script: {script_name} ({script_id})")
            return True

        except Exception as exc:
            error(f"Failed to import/create script '{script_name}': {exc}")
            return False

    def _import_email_template(
        self, name: str, tmpl_data: Dict[str, Any], token: str, base_url: str
    ) -> bool:
        """Import one email template via PUT to the IDM endpoint."""
        # IDM base URL (strip /am if needed)
        idm_base = getattr(self, "_idm_base_url", None) or base_url
        idm_base = idm_base.rstrip("/")
        if idm_base.endswith("/am"):
            idm_base = idm_base[:-3]

        url = f"{idm_base}/openidm/config/emailTemplate/{quote(name)}"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        payload_data = {k: v for k, v in tmpl_data.items() if k != "_rev"}

        try:
            self.make_http_request(url, "PUT", headers, json.dumps(payload_data))
            self.logger.debug(f"Imported email template: {name}")
            return True
        except Exception as exc:
            error(f"Failed to import email template '{name}': {exc}")
            return False

    def _import_node(
        self, node_id: str, node_data: Dict[str, Any], token: str, base_url: str
    ) -> bool:
        """Import one AM node via PUT to nodes/{type}/{id}."""
        node_type = (node_data.get("_type") or {}).get("_id")
        if not node_type:
            error(f"Node '{node_id}' missing _type._id, skipping")
            return False

        url = self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}"
            f"/realm-config/authentication/authenticationtrees"
            f"/nodes/{quote(node_type)}/{quote(node_id)}",
        )

        payload_data = {k: v for k, v in node_data.items() if k not in ("_id", "_rev")}

        headers = get_headers("journeys")
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, json.dumps(payload_data))
            self.logger.debug(f"Imported node: {node_id} [{node_type}]")
            return True
        except Exception as exc:
            error(f"Failed to import node '{node_id}' [{node_type}]: {exc}")
            return False

    def _post_saml_metadata(
        self, entity_id: str, metadata_xml: str, token: str, base_url: str
    ) -> bool:
        """POST metadata ignoring 500/409 conflict errors which indicate it exists."""
        url = self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}/realm-config/"
            "saml2/remote/?_action=importEntity",
        )
        try:
            encoded = base64.urlsafe_b64encode(metadata_xml.encode("utf-8")).decode(
                "ascii"
            )
        except Exception as e:
            error(f"Failed to encode metadata for '{entity_id}': {e}")
            return False

        payload = {"standardMetadata": encoded}
        headers = get_headers("saml_metadata")
        headers = {
            **headers,
            **self.build_auth_headers(token),
        }

        # We explicitly use httpx here instead of self.make_http_request
        # to avoid printing loud ERROR messages to the console for the
        # expected 409/500 "metadata already exists" responses.
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, headers=headers, json=payload)

                # If it's a 409 or 500, we treat it as "already exists" and skip
                if response.status_code in (409, 500):
                    self.logger.debug(
                        f"Metadata for '{entity_id}' likely already exists "
                        f"(status {response.status_code}), skipping POST."
                    )
                    return True

                # Otherwise, raise if not successful
                response.raise_for_status()
                self.logger.debug(f"Imported metadata for: {entity_id}")
                return True

        except Exception as e:
            error(f"Failed to import metadata for '{entity_id}': {e}")
            return False

    def _import_saml_entity(
        self,
        entity_id: str,
        entity_entry: Dict[str, Any],
        saml_imp: Any,
        token: str,
        base_url: str,
    ) -> bool:
        """
        Import one SAML2 entity from the enriched export format.

        The entry format is:
          { "hosted|remote": <provider_detail>, "metadata": "<xml>" }

        For remote entities the metadata XML is posted first (importEntity
        action), then the provider config is upserted.  For hosted entities
        only the provider config upsert is needed.
        """
        ok = True
        metadata_xml: str = entity_entry.get("metadata", "")

        for location in ("hosted", "remote"):
            provider_cfg = entity_entry.get(location)
            if not provider_cfg:
                continue

            # Remote entities: POST metadata first so the entity exists,
            # then upsert the config.
            if location == "remote" and metadata_xml:
                if not self._post_saml_metadata(
                    entity_id, metadata_xml, token, base_url
                ):
                    self.logger.debug(
                        f"Metadata POST failed for '{entity_id}'; "
                        "will still attempt provider config upsert"
                    )
                    ok = False

            if not saml_imp._upsert_entity(provider_cfg, location, token, base_url):
                ok = False

        return ok

    def _import_circle_of_trust(
        self, cot_id: str, cot_cfg: Dict[str, Any], token: str, base_url: str
    ) -> bool:
        """Import one SAML2 circle of trust via PUT."""
        url = self._construct_api_url(
            base_url,
            f"/am/json/realms/root/realms/{self.realm}"
            f"/realm-config/federation/circlesoftrust/{quote(cot_id)}",
        )
        payload_data = {k: v for k, v in cot_cfg.items() if k not in {"_rev", "_type"}}
        headers = get_headers("circle_of_trust")
        headers = {
            **headers,
            **self.build_auth_headers(token),
        }

        # Use httpx instead of make_http_request to bypass loud console error logs
        # for a known, very common AM "false-positive" 500 Server Error where AM
        # successfully writes the CoT but throws an exception because the SAML entity
        # we submitted milliseconds ago hasn't fully registered in the AM server cache.
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.put(url, headers=headers, json=payload_data)

                # AM bug: "Unable to update entity provider's circle of trust"
                if (
                    response.status_code == 500
                    and "Unable to update entity provider" in response.text
                ):
                    self.logger.debug(
                        f"Caught known CoT creation 500 caching bug on '{cot_id}'. "
                        "Waiting 1s and retrying..."
                    )
                    import time

                    time.sleep(1)

                    # 99% of the time, the second, identical PUT succeeds purely
                    # because AM had 1 extra second to cache the newly created entity
                    # internally. If it still fails, the CoT was still created anyway.
                    retry_response = client.put(url, headers=headers, json=payload_data)

                    if retry_response.status_code >= 400:
                        self.logger.debug(
                            f"Retry failed for CoT '{cot_id}', but AM normally "
                            "creates it anyway. Proceeding."
                        )
                    else:
                        self.logger.debug(
                            f"Imported circle of trust (after retry): {cot_id}"
                        )

                    return True

                response.raise_for_status()

            self.logger.debug(f"Imported circle of trust: {cot_id}")
            return True

        except Exception as exc:
            error_msg = str(exc)
            error(f"Failed to import circle of trust '{cot_id}': {error_msg}")
            return False

    def _import_themes(self, themes: Dict[str, Any], token: str, base_url: str) -> bool:
        """
        Merge exported themes into the live themerealm document.

        Delegates to ThemesImporter.update_item which does:
          GET current themerealm → merge by _id → PUT back with If-Match.

        The ``themes`` dict from the enriched export is keyed by themeId.
        We convert it to the themerealm ``realm`` structure the ThemesImporter
        expects: ``{"realm": {realm: [theme1, theme2, ...]}}``.
        """
        themes_imp = _themes_importer()
        # Wire auth so ThemesImporter can call make_http_request
        themes_imp.token = token

        # IDM base (strip /am if present — same logic used for email templates)
        idm_base = getattr(self, "_idm_base_url", None) or base_url
        idm_base = idm_base.rstrip("/")
        if idm_base.endswith("/am"):
            idm_base = idm_base[:-3]

        theme_list = list(themes.values())
        payload = {"realm": {self.realm: theme_list}}

        return themes_imp.update_item(payload, token, idm_base)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_deps_for_trees(
    data: Dict[str, Any], selected_tree_ids: List[str]
) -> Dict[str, set]:
    """
    Single O(n) in-memory pass over the local export JSON.

    Returns a dict of sets keyed by dep type:
      root_nodes, inner_nodes, scripts, email_templates,
      saml2_entities, cots, themes

    Algorithm:
    1.  Walk the selected tree definitions to collect their direct node IDs
        (root_nodes).  Also harvest the theme ID if the tree references one.
    2.  For every root node, inspect its inner-node children (pageNode pattern)
        → inner_nodes.
    3.  Scan all required nodes for known script-reference fields → scripts.
    4.  Scan all required nodes for known email-template fields → email_templates.
    5.  Scan all required nodes for SAML entity references → saml2_entities;
        look up each entity's CoT membership → cots.

    This keeps cherry-pick imports to the minimum possible network requests.
    """
    trees: Dict[str, Any] = data.get("trees", {})
    all_nodes: Dict[str, Any] = {**data.get("nodes", {}), **data.get("innerNodes", {})}
    all_saml: Dict[str, Any] = data.get("saml2Entities", {})
    all_cots: Dict[str, Any] = data.get("saml2CirclesOfTrust", {})
    all_themes: Dict[str, Any] = data.get("themes", {})

    root_nodes: set = set()
    inner_nodes: set = set()
    scripts: set = set()
    email_templates: set = set()
    saml2_entities: set = set()
    cots: set = set()
    themes: set = set()

    # ── Step 1: root nodes + theme from tree definition ─────────────────────
    for tid in selected_tree_ids:
        tree = trees.get(tid, {})
        # Tree-level node references live under "nodes": {nodeId: {nodeType}}
        root_nodes.update(tree.get("nodes", {}).keys())
        # Some tree definitions carry a "uiThemeId" or "themeId" reference
        for theme_field in ("uiThemeId", "themeId"):
            theme_id = tree.get(theme_field)
            if theme_id and theme_id in all_themes:
                themes.add(theme_id)

    # ── Step 2 & 3 & 4: walk nodes for inner-nodes, scripts, email templates,
    #    SAML entity refs — we need a closure over all reachable node IDs, so
    #    we expand page-node children into root_nodes first (one extra pass).
    #
    #    Page nodes store children in node.nodes list → those are inner nodes.
    to_scan = set(root_nodes)  # Start with what the tree explicitly references
    visited: set = set()

    _SCRIPT_FIELDS = (
        "script",
        "transformationScript",
        "validationScript",
        "filterScript",
    )
    _EMAIL_FIELDS = ("emailTemplateName", "emailTemplate")
    _SAML_FIELDS = ("saml2EntityName", "entityId", "idpEntityId", "spEntityId")

    while to_scan:
        nid = to_scan.pop()
        if nid in visited:
            continue
        visited.add(nid)

        node = all_nodes.get(nid)
        if node is None:
            continue

        # Inner-node children (page node pattern: node.nodes is a list of IDs)
        for child_id in node.get("nodes", []):
            if isinstance(child_id, str) and child_id not in visited:
                inner_nodes.add(child_id)
                to_scan.add(child_id)
        # Also handle dict-form {nodeId: {nodeType}} used by some node types
        for child_id in (
            node.get("nodes", {}).keys() if isinstance(node.get("nodes"), dict) else []
        ):
            if child_id not in visited:
                inner_nodes.add(child_id)
                to_scan.add(child_id)

        # Scripts
        for field in _SCRIPT_FIELDS:
            val = node.get(field)
            if val and isinstance(val, str):
                scripts.add(val)

        # Email templates
        for field in _EMAIL_FIELDS:
            val = node.get(field)
            if val and isinstance(val, str):
                email_templates.add(val)

        # SAML entities referenced by specific node types
        for field in _SAML_FIELDS:
            val = node.get(field)
            if val and isinstance(val, str) and val in all_saml:
                saml2_entities.add(val)

    # ── Step 5: CoTs — pull in any CoT whose trustedProviders list overlaps
    #   with the entities we already need.
    for cot_id, cot_cfg in all_cots.items():
        trusted: list = cot_cfg.get("trustedProviders", [])
        # trustedProviders entries look like "entityId|saml2"
        trusted_entity_ids = {p.split("|")[0] for p in trusted if "|" in p}
        if trusted_entity_ids & saml2_entities:  # intersection
            cots.add(cot_id)

    return {
        "root_nodes": root_nodes,
        "inner_nodes": inner_nodes,
        "scripts": scripts,
        "email_templates": email_templates,
        "saml2_entities": saml2_entities,
        "cots": cots,
        "themes": themes,
    }


def _scripts_needed_by_trees(data: Dict[str, Any], selected_tree_ids: List[str]) -> set:
    """Thin shim kept for backward-compatibility; delegates to _resolve_deps_for_trees."""
    return _resolve_deps_for_trees(data, selected_tree_ids)["scripts"]


class JourneyImportService:
    """Service to handle journey import logic"""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self):
        realm = self.kwargs.get("realm", DEFAULT_REALM)
        importer = JourneyImporter(realm=realm)

        # Typer passes 'file' which maps to 'file_path' in BaseImporter
        if "file" in self.kwargs:
            self.kwargs["file_path"] = self.kwargs.pop("file")

        return importer.import_from_file(**self.kwargs)


# ---------------------------------------------------------------------------
# CLI command factory
# ---------------------------------------------------------------------------
