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

import base64
import json
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import typer

from trxo.constants import DEFAULT_REALM
from trxo.utils.console import error, info, success, warning

from .base_importer import BaseImporter


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
        # ── Git mode: delegate entirely to the base class ────────────────
        storage_mode = self._get_storage_mode()
        if storage_mode == "git":
            return super().import_from_file(
                file_path=file_path,
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
                force_import=force_import,
                branch=branch,
                diff=diff,
                rollback=rollback,
                sync=sync,
                cherry_pick=cherry_pick,
            )

        # ── Local mode: probe the file for enriched format ───────────────
        if not file_path:
            error("File path is required for local storage mode")
            raise typer.Exit(1)

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
                raise typer.Exit(1)

            ok = self.import_journey_data(
                data=payload,
                token=token,
                base_url=api_base_url,
                cherry_pick_ids=cherry_pick,
            )
            if not ok:
                raise typer.Exit(1)
        finally:
            self.cleanup()

    # ── Enriched import orchestrator ─────────────────────────────────────

    def import_journey_data(
        self,
        data: Dict[str, Any],
        token: str,
        base_url: str,
        cherry_pick_ids: Optional[str] = None,
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
        if cherry_pick_ids:
            selected_tree_ids = [
                i.strip() for i in cherry_pick_ids.split(",") if i.strip()
            ]
            info(f"Cherry-pick mode: importing journeys {selected_tree_ids}")

        error_count = 0

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

        # -- 2. Email templates -----------------------------------------------
        email_templates: Dict[str, Any] = data.get("emailTemplates", {})
        if email_templates:
            info(f"Importing {len(email_templates)} email template(s)")
            for name, tmpl_cfg in email_templates.items():
                if not self._import_email_template(name, tmpl_cfg, token, base_url):
                    error_count += 1

        # -- 3. SAML2 entities ------------------------------------------------
        saml2_entities: Dict[str, Any] = data.get("saml2Entities", {})
        if saml2_entities:
            info(f"Importing {len(saml2_entities)} SAML2 entity(ies)")
            saml_imp = _saml_importer(self.realm)
            # Share our auth state so build_auth_headers / make_http_request work
            saml_imp.token = token
            for entity_id, entity_entry in saml2_entities.items():
                if not self._import_saml_entity(
                    entity_id, entity_entry, saml_imp, token, base_url
                ):
                    error_count += 1

        # -- 4. Circles of trust ----------------------------------------------
        cots: Dict[str, Any] = data.get("saml2CirclesOfTrust", {})
        if cots:
            info(f"Importing {len(cots)} circle(s) of trust")
            for cot_id, cot_cfg in cots.items():
                if not self._import_circle_of_trust(cot_id, cot_cfg, token, base_url):
                    error_count += 1

        # -- 5. Inner nodes ---------------------------------------------------
        inner_nodes: Dict[str, Any] = data.get("innerNodes", {})
        if inner_nodes:
            info(f"Importing {len(inner_nodes)} inner node(s)")
            for node_id, node_cfg in inner_nodes.items():
                if not self._import_node(node_id, node_cfg, token, base_url):
                    error_count += 1

        # -- 6. Root nodes ----------------------------------------------------
        nodes: Dict[str, Any] = data.get("nodes", {})
        if nodes:
            info(f"Importing {len(nodes)} root node(s)")
            for node_id, node_cfg in nodes.items():
                if not self._import_node(node_id, node_cfg, token, base_url):
                    error_count += 1

        # -- 7. Themes --------------------------------------------------------
        themes: Dict[str, Any] = data.get("themes", {})
        if themes:
            info(f"Importing {len(themes)} theme(s)")
            if not self._import_themes(themes, token, base_url):
                error_count += 1

        # -- 8. Journeys (trees) ----------------------------------------------
        trees: Dict[str, Any] = data.get("trees", {})
        if selected_tree_ids:
            trees = {k: v for k, v in trees.items() if k in selected_tree_ids}

        if trees:
            info(f"Importing {len(trees)} journey(s)")
            for tree_id, tree_cfg in trees.items():
                if not self.update_item(tree_cfg, token, base_url):
                    error_count += 1
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

        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "resource=1.0",
        }
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
        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=1.0,resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, json.dumps(payload_data))
            self.logger.debug(f"Imported script: {script_name} ({script_id})")
            return True
        except Exception as exc:
            # If script doesn't exist try creating it
            if "404" in str(exc):
                try:
                    create_url = self._construct_api_url(
                        base_url,
                        f"/am/json/realms/root/realms/{self.realm}"
                        "/scripts?_action=create",
                    )
                    self.make_http_request(
                        create_url, "POST", headers, json.dumps(payload_data)
                    )
                    self.logger.debug(f"Created script: {script_name} ({script_id})")
                    return True
                except Exception as create_exc:
                    error(f"Failed to create script '{script_name}': {create_exc}")
                    return False
            error(f"Failed to import script '{script_name}': {exc}")
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

        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=2.1,resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}

        try:
            self.make_http_request(url, "PUT", headers, json.dumps(payload_data))
            self.logger.debug(f"Imported node: {node_id} [{node_type}]")
            return True
        except Exception as exc:
            error(f"Failed to import node '{node_id}' [{node_type}]: {exc}")
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
                if not saml_imp._post_metadata(
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
        payload_data = {k: v for k, v in cot_cfg.items() if k != "_rev"}
        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=2.1,resource=1.0",
        }
        headers = {**headers, **self.build_auth_headers(token)}
        try:
            self.make_http_request(url, "PUT", headers, json.dumps(payload_data))
            self.logger.debug(f"Imported circle of trust: {cot_id}")
            return True
        except Exception as exc:
            error(f"Failed to import circle of trust '{cot_id}': {exc}")
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


def _scripts_needed_by_trees(data: Dict[str, Any], selected_tree_ids: List[str]) -> set:
    """
    Return the set of script IDs that are directly referenced by nodes
    belonging to the selected trees.

    This is a best-effort scan: it looks at node.script,
    node.transformationScript, node.validationScript, node.filterScript.
    """
    # Build set of node IDs belonging to selected trees
    selected_node_ids: set = set()
    trees = data.get("trees", {})
    for tid in selected_tree_ids:
        tree = trees.get(tid, {})
        selected_node_ids.update(tree.get("nodes", {}).keys())

    script_fields = (
        "script",
        "transformationScript",
        "validationScript",
        "filterScript",
    )
    needed: set = set()

    all_nodes: Dict[str, Any] = {}
    all_nodes.update(data.get("nodes", {}))
    all_nodes.update(data.get("innerNodes", {}))

    for nid, node in all_nodes.items():
        if nid not in selected_node_ids:
            continue
        for field in script_fields:
            sid = node.get(field)
            if sid and isinstance(sid, str):
                needed.add(sid)

    return needed


# ---------------------------------------------------------------------------
# CLI command factory
# ---------------------------------------------------------------------------


def create_journey_import_command():
    """Create the journey import command function."""

    def import_journeys(
        file: str = typer.Option(
            None,
            "--file",
            help="Path to JSON file containing journeys data (local mode only)",
        ),
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Target realm name (default: {DEFAULT_REALM})",
        ),
        cherry_pick: str = typer.Option(
            None,
            "--cherry-pick",
            "-c",
            help=(
                "Import only specific journeys with these IDs (_id) "
                "(comma-separated for multiple IDs)"
            ),
        ),
        force_import: bool = typer.Option(
            False,
            "--force-import",
            "-f",
            help="Skip hash validation and force import",
        ),
        diff: bool = typer.Option(
            False, "--diff", help="Show differences before import"
        ),
        branch: str = typer.Option(
            None, "--branch", help="Git branch to import from (Git mode only)"
        ),
        jwk_path: str = typer.Option(
            None, "--jwk-path", help="Path to JWK private key file"
        ),
        sa_id: str = typer.Option(None, "--sa-id", help="Service Account ID"),
        base_url: str = typer.Option(
            None,
            "--base-url",
            help="Base URL for PingOne Advanced Identity Cloud instance",
        ),
        project_name: str = typer.Option(
            None,
            "--project-name",
            help="Project name for argument mode (optional)",
        ),
        auth_mode: str = typer.Option(
            None,
            "--auth-mode",
            help="Auth mode override: service-account|onprem",
        ),
        onprem_username: str = typer.Option(
            None, "--onprem-username", help="On-Prem username"
        ),
        onprem_password: str = typer.Option(
            None, "--onprem-password", help="On-Prem password", hide_input=True
        ),
        onprem_realm: str = typer.Option(
            "root", "--onprem-realm", help="On-Prem realm"
        ),
        am_base_url: str = typer.Option(
            None, "--am-base-url", help="On-Prem AM base URL"
        ),
        idm_base_url: str = typer.Option(
            None, "--idm-base-url", help="On-Prem IDM base URL"
        ),
        idm_username: str = typer.Option(
            None, "--idm-username", help="On-Prem IDM username"
        ),
        idm_password: str = typer.Option(
            None, "--idm-password", help="On-Prem IDM password", hide_input=True
        ),
    ):
        """Import journeys from a JSON file (enriched or legacy format) or Git repository."""
        importer = JourneyImporter(realm=realm)
        importer.import_from_file(
            file_path=file,
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
            force_import=force_import,
            branch=branch,
            cherry_pick=cherry_pick,
            diff=diff,
        )

    return import_journeys
