"""
Journeys export commands.

This module provides export functionality for PingOne Advanced Identity
Cloud journeys, including full dependency collection:
  - nodes and inner nodes
  - scripts
  - email templates
  - themes
  - SAML2 entities and circles of trust
  - social identity providers
"""

import base64
import json
from typing import Any, Dict, Optional, Set
from urllib.parse import quote

import typer

from trxo.commands.shared.options import (
    AmBaseUrlOpt,
    AuthModeOpt,
    BaseUrlOpt,
    BranchOpt,
    CommitMessageOpt,
    IdmBaseUrlOpt,
    IdmPasswordOpt,
    IdmUsernameOpt,
    JwkPathOpt,
    NoVersionOpt,
    OnPremPasswordOpt,
    OnPremRealmOpt,
    OnPremUsernameOpt,
    OutputDirOpt,
    OutputFileOpt,
    ProjectNameOpt,
    RealmOpt,
    SaIdOpt,
    VersionOpt,
    ViewColumnsOpt,
    ViewOpt,
)
from trxo.constants import DEFAULT_REALM
from trxo.utils.console import error, info, warning

from .base_exporter import BaseExporter

# ---------------------------------------------------------------------------
# Node-type constants
# ---------------------------------------------------------------------------

_SOCIAL_HANDLER_NODE_TYPES = {
    "SocialProviderHandlerNode",
    "LegacySocialProviderHandlerNode",
}
_SELECT_IDP_NODE_TYPE = "SelectIdPNode"
_INNER_TREE_NODE_TYPE = "InnerTreeEvaluatorNode"

# Keys inside a SAML provider config that carry script UUIDs
_SAML_SCRIPT_KEYS = {
    "attributeMapperScript",
    "authnContextMapperScript",
    "idpAdapterScript",
    "spAdapterScript",
    "idpAttributeMapperScript",
    "spAttributeMapperScript",
    "idpAuthncontextMapperScript",
    "spAuthncontextMapperScript",
    "script",
}

# Script-reference fields that may appear on any AM node
_NODE_SCRIPT_FIELDS = (
    "script",
    "transformationScript",
    "validationScript",
    "filterScript",
)


def _is_uuid(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 36 and value.count("-") == 4


def _node_type_id(node: Dict[str, Any]) -> str:
    return (node.get("_type") or {}).get("_id", "")


# ---------------------------------------------------------------------------
# JourneyExporter – thin subclass that exposes export_as_dict for composability
# ---------------------------------------------------------------------------


class JourneyExporter(BaseExporter):
    """Exporter for journeys with full dependency collection."""

    def export_as_dict(
        self,
        realm: str = DEFAULT_REALM,
        jwk_path=None,
        sa_id=None,
        base_url=None,
        project_name=None,
        auth_mode=None,
        onprem_username=None,
        onprem_password=None,
        onprem_realm="root",
        am_base_url=None,
        idm_base_url=None,
        idm_username=None,
        idm_password=None,
    ) -> Dict[str, Any]:
        """Run the enriched export and return the result dict without saving."""
        captured: Dict[str, Any] = {}
        original_save = self.save_response

        def capture(payload, *args, **kwargs):
            captured["data"] = payload
            return None

        self.save_response = capture
        try:
            self.export_data(
                command_name="journeys",
                api_endpoint=(
                    f"/am/json/realms/root/realms/{realm}"
                    "/realm-config/authentication/authenticationtrees"
                    "/trees?_queryFilter=true"
                ),
                headers=_am_headers(),
                view=False,
                jwk_path=jwk_path,
                sa_id=sa_id,
                base_url=base_url,
                project_name=project_name,
                auth_mode=auth_mode,
                onprem_username=onprem_username,
                onprem_password=onprem_password,
                onprem_realm=onprem_realm,
                am_base_url=am_base_url,
                idm_base_url=idm_base_url,
                idm_username=idm_username,
                idm_password=idm_password,
                response_filter=process_journey_response(self, realm),
            )
        finally:
            self.save_response = original_save

        return captured.get("data") or {}


# ---------------------------------------------------------------------------
# Response filter
# ---------------------------------------------------------------------------


def process_journey_response(exporter: BaseExporter, realm: str):
    """
    Build a response-filter function that replaces the raw trees list with a
    fully enriched export dict (trees + all dependencies).

    Follows the same contract as the SAML response filter.
    """

    def _filter(response_data: Any) -> Dict[str, Any]:
        token, api_base_url = exporter.get_current_auth()

        am_hdrs = {**_am_headers(), **exporter.build_auth_headers(token)}
        idm_hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
        idm_hdrs.update(exporter.build_auth_headers(token))

        # Determine IDM base URL (on-prem may differ from AM base URL)
        idm_base = _resolve_idm_base(exporter, api_base_url)

        export: Dict[str, Any] = {
            "trees": {},
            "nodes": {},
            "innerNodes": {},
            "scripts": {},
            "emailTemplates": {},
            "saml2Entities": {},
            "saml2CirclesOfTrust": {},
            "socialIdentityProviders": {},
            "themes": {},
        }

        # ── Step 1: Bulk fetch all nodes ──────────────────────────────────
        node_map = _fetch_all_nodes(exporter, realm, api_base_url, am_hdrs)

        # ── Step 2: Fetch SAML & social lookup tables ─────────────────────
        saml_provider_list = _fetch_saml_provider_list(
            exporter, realm, api_base_url, am_hdrs
        )
        cot_map = _fetch_circles_of_trust(exporter, realm, api_base_url, am_hdrs)
        social_map = _fetch_social_providers(exporter, idm_base, idm_hdrs)

        # ── Step 3: Themes ────────────────────────────────────────────────
        themes_list = _fetch_themes(exporter, realm, idm_base, idm_hdrs)

        # ── Step 4: Extract tree list from response ────────────────────────
        if isinstance(response_data, dict) and "result" in response_data:
            tree_list = response_data["result"]
        elif isinstance(response_data, list):
            tree_list = response_data
        else:
            tree_list = []

        exporter.logger.info(f"Collecting dependencies for {len(tree_list)} journey(s)")

        # ── Step 5: BFS over trees ────────────────────────────────────────
        # Map treeId → config for quick lookup of inner-tree refs
        tree_id_to_config: Dict[str, Any] = {
            t["_id"]: t for t in tree_list if isinstance(t, dict) and "_id" in t
        }

        processed_trees: Set[str] = set()
        pending_trees: Set[str] = {t["_id"] for t in tree_list if "_id" in t}

        while pending_trees:
            tree_id = pending_trees.pop()
            if tree_id in processed_trees:
                continue
            processed_trees.add(tree_id)

            tree = tree_id_to_config.get(tree_id)
            if tree is None:
                # Inner-tree reference not in the initial query — fetch it
                tree = _fetch_single_tree(
                    exporter, realm, api_base_url, am_hdrs, tree_id
                )
                if tree is None:
                    continue

            export["trees"][tree_id] = tree
            exporter.logger.debug(f"Walking journey: {tree_id}")

            inner_refs: Set[str] = set()
            _walk_nodes(
                tree=tree,
                node_map=node_map,
                export=export,
                realm=realm,
                exporter=exporter,
                api_base_url=api_base_url,
                am_hdrs=am_hdrs,
                idm_base=idm_base,
                idm_hdrs=idm_hdrs,
                saml_provider_list=saml_provider_list,
                cot_map=cot_map,
                social_map=social_map,
                inner_refs=inner_refs,
            )

            for ref in inner_refs:
                if ref not in processed_trees:
                    pending_trees.add(ref)

        # ── Step 6: Themes ────────────────────────────────────────────────
        _resolve_themes(export, themes_list)

        info(
            f"Journey export complete — "
            f"{len(export['trees'])} journey(s), "
            f"{len(export['nodes'])} node(s), "
            f"{len(export['innerNodes'])} inner-node(s), "
            f"{len(export['scripts'])} script(s), "
            f"{len(export['emailTemplates'])} email template(s), "
            f"{len(export['saml2Entities'])} SAML entity(ies), "
            f"{len(export['saml2CirclesOfTrust'])} circle(s) of trust, "
            f"{len(export['socialIdentityProviders'])} social provider(s), "
            f"{len(export['themes'])} theme(s)"
        )

        return export

    return _filter


# ---------------------------------------------------------------------------
# Node walker (BFS within a single tree)
# ---------------------------------------------------------------------------


def _walk_nodes(
    *,
    tree: Dict[str, Any],
    node_map: Dict[str, Any],
    export: Dict[str, Any],
    realm: str,
    exporter: BaseExporter,
    api_base_url: str,
    am_hdrs: Dict[str, str],
    idm_base: str,
    idm_hdrs: Dict[str, str],
    saml_provider_list: Dict[str, Any],
    cot_map: Dict[str, Any],
    social_map: Dict[str, Any],
    inner_refs: Set[str],
) -> None:
    """BFS over nodes of a single tree, collecting all dependencies."""
    root_node_ids: Set[str] = set(tree.get("nodes", {}).keys())
    queue = list(root_node_ids)
    processed: Set[str] = set()

    while queue:
        nid = queue.pop(0)
        if nid in processed:
            continue
        processed.add(nid)

        node = node_map.get(nid)
        if node is None:
            exporter.logger.debug(f"Node not found in bulk data: {nid}")
            continue

        # Root vs inner classification
        if nid in root_node_ids:
            export["nodes"][nid] = node
        else:
            export["innerNodes"][nid] = node

        ntype = _node_type_id(node)
        exporter.logger.debug(f"Processing node {nid} [{ntype}]")

        # Recurse into child/page nodes
        children = node.get("nodes")
        if isinstance(children, list):
            for child in children:
                cid = child.get("_id")
                if cid and cid not in processed:
                    queue.append(cid)

        # Collect dependencies
        _collect_scripts(node, export, realm, exporter, api_base_url, am_hdrs)
        _collect_email_template(node, export, exporter, idm_base, idm_hdrs)
        _collect_saml(
            node,
            export,
            realm,
            exporter,
            api_base_url,
            am_hdrs,
            saml_provider_list,
            cot_map,
        )
        _collect_social_providers(node, export, social_map, exporter)
        _collect_inner_journey(node, inner_refs)


# ---------------------------------------------------------------------------
# Dependency collectors
# ---------------------------------------------------------------------------


def _collect_scripts(
    node: Dict[str, Any],
    export: Dict[str, Any],
    realm: str,
    exporter: BaseExporter,
    api_base_url: str,
    am_hdrs: Dict[str, str],
) -> None:
    for field in _NODE_SCRIPT_FIELDS:
        sid = node.get(field)
        if sid and isinstance(sid, str) and sid not in export["scripts"]:
            script = _fetch_script(exporter, realm, api_base_url, am_hdrs, sid)
            if script:
                export["scripts"][sid] = script
                exporter.logger.debug(f"Collected script [{field}]: {sid}")


def _collect_email_template(
    node: Dict[str, Any],
    export: Dict[str, Any],
    exporter: BaseExporter,
    idm_base: str,
    idm_hdrs: Dict[str, str],
) -> None:
    name = node.get("emailTemplateName")
    if name and name not in export["emailTemplates"]:
        tmpl = _fetch_email_template(exporter, idm_base, idm_hdrs, name)
        if tmpl:
            export["emailTemplates"][name] = tmpl
            exporter.logger.debug(f"Collected email template: {name}")


def _collect_saml(
    node: Dict[str, Any],
    export: Dict[str, Any],
    realm: str,
    exporter: BaseExporter,
    api_base_url: str,
    am_hdrs: Dict[str, str],
    saml_provider_list: Dict[str, Any],
    cot_map: Dict[str, Any],
) -> None:
    ntype = _node_type_id(node)
    if "saml" not in ntype.lower():
        return

    entity_id = (
        node.get("entityProvider")
        or node.get("samlEntityProvider")
        or node.get("idpEntityId")
        or node.get("spEntityId")
        or node.get("entityId")
    )
    if entity_id:
        _fetch_saml_entity(
            entity_id,
            saml_provider_list,
            cot_map,
            export,
            realm,
            exporter,
            api_base_url,
            am_hdrs,
        )


def _collect_social_providers(
    node: Dict[str, Any],
    export: Dict[str, Any],
    social_map: Dict[str, Any],
    exporter: BaseExporter,
) -> None:
    ntype = _node_type_id(node)

    if ntype == _SELECT_IDP_NODE_TYPE:
        use_all = node.get("useAllProviders", False)
        providers = node.get("filteredProviders", [])
        targets = list(social_map.keys()) if use_all else providers
        for name in targets:
            if name and name not in export["socialIdentityProviders"]:
                cfg = social_map.get(name)
                if cfg:
                    export["socialIdentityProviders"][name] = cfg
                    exporter.logger.debug(f"Collected social provider: {name}")
                else:
                    exporter.logger.debug(f"Social provider not found in realm: {name}")

    elif ntype in _SOCIAL_HANDLER_NODE_TYPES:
        for field in ("idpHandler", "providerName", "provider"):
            name = node.get(field)
            if name and name not in export["socialIdentityProviders"]:
                cfg = social_map.get(name)
                if cfg:
                    export["socialIdentityProviders"][name] = cfg
                    exporter.logger.debug(
                        f"Collected social provider (handler): {name}"
                    )


def _collect_inner_journey(node: Dict[str, Any], inner_refs: Set[str]) -> None:
    if _node_type_id(node) == _INNER_TREE_NODE_TYPE:
        ref = node.get("tree")
        if ref:
            inner_refs.add(ref)


# ---------------------------------------------------------------------------
# Bulk and on-demand fetch helpers
# ---------------------------------------------------------------------------


def _fetch_all_nodes(
    exporter: BaseExporter,
    realm: str,
    api_base_url: str,
    headers: Dict[str, str],
) -> Dict[str, Any]:
    """Bulk-fetch all node instances via nextdescendents action."""
    exporter.logger.debug("Fetching all nodes via nextdescendents (bulk)")
    url = exporter._construct_api_url(
        api_base_url,
        f"/am/json/realms/root/realms/{realm}"
        "/realm-config/authentication/authenticationtrees/nodes",
    )
    try:
        resp = exporter.make_http_request(
            url + "?_action=nextdescendents", "POST", headers, "{}"
        )
        data = resp.json()
        items = data.get("result", data) if isinstance(data, dict) else data
        node_map = {n["_id"]: n for n in items if isinstance(n, dict) and "_id" in n}
        exporter.logger.debug(f"Fetched {len(node_map)} node(s) from bulk endpoint")
        return node_map
    except Exception as exc:
        warning(f"Could not bulk-fetch nodes: {exc}")
        return {}


def _fetch_single_tree(
    exporter: BaseExporter,
    realm: str,
    api_base_url: str,
    headers: Dict[str, str],
    tree_id: str,
) -> Optional[Dict[str, Any]]:
    url = exporter._construct_api_url(
        api_base_url,
        f"/am/json/realms/root/realms/{realm}"
        f"/realm-config/authentication/authenticationtrees/trees/{quote(tree_id)}",
    )
    try:
        resp = exporter.make_http_request(url, "GET", headers)
        return resp.json()
    except Exception as exc:
        warning(f"Could not fetch journey '{tree_id}': {exc}")
        return None


def _fetch_script(
    exporter: BaseExporter,
    realm: str,
    api_base_url: str,
    headers: Dict[str, str],
    script_id: str,
) -> Optional[Dict[str, Any]]:
    url = exporter._construct_api_url(
        api_base_url,
        f"/am/json/realms/root/realms/{realm}/scripts/{quote(script_id)}",
    )
    try:
        resp = exporter.make_http_request(url, "GET", headers)
        script_data = resp.json()
        # Decode base64 script field to human-readable lines (consistent with scripts exporter)
        if isinstance(script_data, dict) and isinstance(script_data.get("script"), str):
            try:
                decoded = base64.b64decode(script_data["script"], validate=True).decode(
                    "utf-8"
                )
                script_data["script"] = decoded.splitlines()
            except Exception:
                pass  # leave as-is if decode fails
        return script_data
    except Exception as exc:
        warning(f"Could not fetch script '{script_id}': {exc}")
        return None


def _fetch_email_template(
    exporter: BaseExporter,
    idm_base: str,
    headers: Dict[str, str],
    name: str,
) -> Optional[Dict[str, Any]]:
    url = f"{idm_base}/openidm/config/emailTemplate/{quote(name)}"
    try:
        resp = exporter.make_http_request(url, "GET", headers)
        return resp.json()
    except Exception as exc:
        warning(f"Could not fetch email template '{name}': {exc}")
        return None


def _fetch_saml_provider_list(
    exporter: BaseExporter,
    realm: str,
    api_base_url: str,
    headers: Dict[str, str],
) -> Dict[str, Any]:
    """Return entityId -> shallow provider dict for the realm."""
    exporter.logger.debug("Fetching SAML provider list (shallow lookup)")
    url = exporter._construct_api_url(
        api_base_url,
        f"/am/json/realms/root/realms/{realm}/realm-config/saml2?_queryFilter=true",
    )
    try:
        resp = exporter.make_http_request(url, "GET", headers)
        data = resp.json()
        items = data.get("result", []) if isinstance(data, dict) else []
        result = {}
        for p in items:
            eid = p.get("entityId") or p.get("_id")
            if eid:
                result[eid] = p
        exporter.logger.debug(f"Found {len(result)} SAML provider(s)")
        return result
    except Exception as exc:
        warning(f"Could not fetch SAML provider list: {exc}")
        return {}


def _fetch_circles_of_trust(
    exporter: BaseExporter,
    realm: str,
    api_base_url: str,
    headers: Dict[str, str],
) -> Dict[str, Any]:
    exporter.logger.debug("Fetching circles of trust (shallow lookup)")
    url = exporter._construct_api_url(
        api_base_url,
        f"/am/json/realms/root/realms/{realm}"
        "/realm-config/federation/circlesoftrust?_queryFilter=true",
    )
    try:
        resp = exporter.make_http_request(url, "GET", headers)
        data = resp.json()
        items = data.get("result", []) if isinstance(data, dict) else []
        cot_map = {c.get("_id"): c for c in items if c.get("_id")}
        exporter.logger.debug(f"Found {len(cot_map)} circle(s) of trust")
        return cot_map
    except Exception as exc:
        warning(f"Could not fetch circles of trust: {exc}")
        return {}


def _fetch_social_providers(
    exporter: BaseExporter,
    idm_base: str,
    headers: Dict[str, str],
) -> Dict[str, Any]:
    exporter.logger.debug("Fetching social identity providers from IDM")
    url = f"{idm_base}/openidm/config"
    try:
        resp = exporter.make_http_request(
            url + "?_queryFilter=_id+sw+%22identityProvider%22" + "&_fields=_id",
            "GET",
            headers,
        )
        data = resp.json()
        items = data.get("result", []) if isinstance(data, dict) else []
        providers: Dict[str, Any] = {}
        for item in items:
            config_id = item.get("_id", "")
            name = config_id.split("/")[-1]
            try:
                detail_resp = exporter.make_http_request(
                    f"{idm_base}/openidm/config/{config_id}", "GET", headers
                )
                providers[name] = detail_resp.json()
                exporter.logger.debug(f"Collected social provider: {name}")
            except Exception as exc:
                warning(f"Could not fetch social provider '{name}': {exc}")
        return providers
    except Exception as exc:
        warning(f"Could not list social identity providers: {exc}")
        return {}


def _fetch_themes(
    exporter: BaseExporter,
    realm: str,
    idm_base: str,
    headers: Dict[str, str],
) -> list:
    exporter.logger.debug("Fetching theme realm data from IDM")
    url = f"{idm_base}/openidm/config/ui/themerealm"
    try:
        resp = exporter.make_http_request(
            url + f"?_fields=realm%2F{realm}", "GET", headers
        )
        data = resp.json()
        realm_data = data.get("realm", {}).get(realm, [])
        exporter.logger.debug(f"Found {len(realm_data)} theme(s) for realm '{realm}'")
        return realm_data
    except Exception as exc:
        warning(f"Could not fetch themes: {exc}")
        return []


def _fetch_saml_entity(
    entity_id: str,
    saml_provider_list: Dict[str, Any],
    cot_map: Dict[str, Any],
    export: Dict[str, Any],
    realm: str,
    exporter: BaseExporter,
    api_base_url: str,
    am_hdrs: Dict[str, str],
) -> None:
    if entity_id in export["saml2Entities"]:
        return  # already collected

    shallow = saml_provider_list.get(entity_id)
    if not shallow:
        exporter.logger.debug(f"SAML entity '{entity_id}' not in realm provider list")
        return

    location = shallow.get("location")
    provider_id = shallow.get("_id")
    if not location or not provider_id:
        exporter.logger.debug(
            f"SAML entity '{entity_id}' missing location or _id in shallow list"
        )
        return

    # Fetch full provider detail
    detail_url = exporter._construct_api_url(
        api_base_url,
        f"/am/json/realms/root/realms/{realm}"
        f"/realm-config/saml2/{location}/{quote(provider_id, safe='')}",
    )
    try:
        detail_resp = exporter.make_http_request(detail_url, "GET", am_hdrs)
        detail = detail_resp.json()
    except Exception as exc:
        warning(f"Could not fetch SAML provider detail for '{entity_id}': {exc}")
        return

    entity_entry: Dict[str, Any] = {location: detail}

    # Fetch XML metadata via JSP endpoint (non-fatal if unavailable)
    # We reconstruct the host from api_base_url (strip /am suffix if present)
    host = api_base_url.rstrip("/")
    if host.endswith("/am"):
        host = host[:-3]
    meta_url = (
        f"{host}/am/saml2/jsp/exportmetadata.jsp"
        f"?entityid={quote(entity_id, safe='')}"
        f"&realm={quote('/' + realm, safe='')}"
    )
    try:
        meta_resp = exporter.make_http_request(meta_url, "GET", am_hdrs)
        entity_entry["metadata"] = meta_resp.text
        exporter.logger.debug(f"Collected SAML [{location}] entity: {entity_id}")
    except Exception as exc:
        entity_entry["metadata"] = ""
        exporter.logger.debug(
            f"Metadata fetch failed for SAML entity '{entity_id}': {exc}"
        )

    export["saml2Entities"][entity_id] = entity_entry

    # Collect any scripts embedded inside the provider config
    for sid in _extract_saml_script_ids(detail):
        if sid not in export["scripts"]:
            script = _fetch_script(exporter, realm, api_base_url, am_hdrs, sid)
            if script:
                export["scripts"][sid] = script
                exporter.logger.debug(f"Collected SAML provider script: {sid}")

    # Collect CoTs that reference this entity
    for cot_id, cot in cot_map.items():
        trusted = cot.get("trustedProviders", [])
        if any(entity_id in entry for entry in trusted):
            if cot_id not in export["saml2CirclesOfTrust"]:
                export["saml2CirclesOfTrust"][cot_id] = cot
                exporter.logger.debug(f"Collected circle of trust: {cot_id}")


def _extract_saml_script_ids(data: Any, found: Optional[Set[str]] = None) -> Set[str]:
    if found is None:
        found = set()
    if isinstance(data, dict):
        for k, v in data.items():
            if k in _SAML_SCRIPT_KEYS and _is_uuid(v):
                found.add(v)
            else:
                _extract_saml_script_ids(v, found)
    elif isinstance(data, list):
        for item in data:
            _extract_saml_script_ids(item, found)
    return found


def _resolve_themes(export: Dict[str, Any], themes_list: list) -> None:
    """Add themes linked to exported journeys or referenced in node stages."""
    theme_map = {t["_id"]: t for t in themes_list if isinstance(t, dict) and "_id" in t}
    exported_tree_ids = set(export["trees"].keys())

    for theme in themes_list:
        if not isinstance(theme, dict):
            continue
        for tid in theme.get("linkedTrees", []):
            if tid in exported_tree_ids:
                theme_id = theme.get("_id")
                if theme_id and theme_id not in export["themes"]:
                    export["themes"][theme_id] = theme

    all_nodes = list(export["nodes"].values()) + list(export["innerNodes"].values())
    for node in all_nodes:
        stage = node.get("stage")
        if not stage:
            continue
        try:
            stage_obj = json.loads(stage)
            theme_id = stage_obj.get("themeId")
            if theme_id and theme_id in theme_map and theme_id not in export["themes"]:
                export["themes"][theme_id] = theme_map[theme_id]
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _am_headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Accept-API-Version": "protocol=2.1,resource=1.0",
    }


def _resolve_idm_base(exporter: BaseExporter, api_base_url: str) -> str:
    """Return the IDM base URL, falling back to the AM base URL."""
    idm = getattr(exporter, "_idm_base_url", None)
    if idm:
        return idm.rstrip("/")
    # Strip /am suffix if present so IDM calls go to the same host
    base = api_base_url.rstrip("/")
    if base.endswith("/am"):
        base = base[:-3]
    return base


# ---------------------------------------------------------------------------
# CLI command factory
# ---------------------------------------------------------------------------


def create_journeys_export_command():
    """Create the journeys export command function."""

    def export_journeys(
        realm: RealmOpt = DEFAULT_REALM,
        view: ViewOpt = None,
        view_columns: ViewColumnsOpt = None,
        version: VersionOpt = None,
        no_version: NoVersionOpt = False,
        branch: BranchOpt = None,
        commit: CommitMessageOpt = None,
        jwk_path: JwkPathOpt = None,
        sa_id: SaIdOpt = None,
        base_url: BaseUrlOpt = None,
        project_name: ProjectNameOpt = None,
        output_dir: OutputDirOpt = None,
        output_file: OutputFileOpt = None,
        auth_mode: AuthModeOpt = None,
        onprem_username: OnPremUsernameOpt = None,
        onprem_password: OnPremPasswordOpt = None,
        onprem_realm: OnPremRealmOpt = "root",
        am_base_url: AmBaseUrlOpt = None,
        idm_base_url: IdmBaseUrlOpt = None,
        idm_username: IdmUsernameOpt = None,
        idm_password: IdmPasswordOpt = None,
    ):
        """Export journeys with their full dependency graph (nodes, scripts, themes, etc.)"""
        exporter = JourneyExporter()

        exporter.export_data(
            command_name="journeys",
            api_endpoint=(
                f"/am/json/realms/root/realms/{realm}"
                "/realm-config/authentication/authenticationtrees"
                "/trees?_queryFilter=true"
            ),
            headers=_am_headers(),
            view=view,
            view_columns=view_columns,
            jwk_path=jwk_path,
            sa_id=sa_id,
            base_url=base_url,
            project_name=project_name,
            output_dir=output_dir,
            output_file=output_file,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            idm_base_url=idm_base_url,
            idm_username=idm_username,
            idm_password=idm_password,
            am_base_url=am_base_url,
            version=version,
            no_version=no_version,
            branch=branch,
            commit_message=commit,
            response_filter=process_journey_response(exporter, realm),
        )

    return export_journeys
