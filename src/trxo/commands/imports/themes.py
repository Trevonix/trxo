"""
Themes import command.

Safe import for Ping AIC ui/themerealm configuration.

Fix summary:
- Uses PUT (full document replacement) instead of field-level PATCH ops
- Merges incoming themes by _id into the current server state
- Handles both "create" (new theme _id) and "update" (existing theme _id) cases
- Adds missing If-Match header with current _rev to avoid 409 conflicts
- Correctly handles the realm->array-of-theme-objects structure
- Removes unreliable deep JSON-PATCH field traversal
"""

import json
from typing import Any, Dict, List, Optional

from trxo.commands.shared.options import (
    AmBaseUrlOpt,
    AuthModeOpt,
    BaseUrlOpt,
    BranchOpt,
    CherryPickOpt,
    DiffOpt,
    ForceImportOpt,
    IdmBaseUrlOpt,
    IdmPasswordOpt,
    IdmUsernameOpt,
    InputFileOpt,
    JwkPathOpt,
    OnPremPasswordOpt,
    OnPremRealmOpt,
    OnPremUsernameOpt,
    ProjectNameOpt,
    RealmOpt,
    RollbackOpt,
    SaIdOpt,
    SyncOpt,
)
from trxo.config.api_headers import get_headers
from trxo.constants import DEFAULT_REALM
from trxo.utils.console import error, info

from .base_importer import BaseImporter


class ThemesImporter(BaseImporter):
    """
    Importer for Ping AIC ui/themerealm.

    Strategy:
      1. GET the current full themerealm document (including _rev).
      2. For each incoming realm, merge themes by _id:
           - If a theme _id already exists in that realm → replace it entirely.
           - If a theme _id is new → append it.
      3. PUT the fully merged document back, using If-Match: <_rev> so the
         server can detect mid-flight conflicts.

    This avoids the fragile field-level PATCH path approach which is
    unreliable against the AIC openidm/config endpoint.
    """

    def __init__(self):
        super().__init__()
        self.product = "idm"

    def get_required_fields(self) -> List[str]:
        return []

    def get_item_type(self) -> str:
        return "themes"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/openidm/config/ui/themerealm"

    def _fetch_current(self, token: str, base_url: str) -> Dict[str, Any]:
        """
        GET the current ui/themerealm document.
        Returns the full dict (including _rev) or {} on failure.
        """
        url = self.get_api_endpoint("", base_url)
        headers = get_headers("themes")
        headers = {
            **headers,
            **self.build_auth_headers(token),
        }
        try:
            resp = self.make_http_request(url, "GET", headers)
            return resp.json()
        except Exception as e:
            error(f"Failed to GET ui/themerealm: {e}")
            return {}

    def _merge_themes(
        self,
        current: Dict[str, Any],
        incoming: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Merge incoming realm themes into the current document.

        The themerealm document structure is:
          {
            "_id": "ui/themerealm",
            "_rev": "<etag>",
            "realm": {
              "alpha": [
                { "_id": "<uuid>", "name": "...", ... },
                ...
              ],
              "bravo": [ ... ]
            }
          }

        For each realm in `incoming["realm"]`:
          - Iterate over each theme object (which must have an "_id").
          - If that "_id" already exists in the current realm list → replace it.
          - Otherwise → append it (new theme creation).

        Fields at the document root (like "_id", "_rev") are preserved from
        the current server response and never overwritten from the import file.
        """
        # Start from current; we'll mutate a deep copy
        merged = json.loads(json.dumps(current))  # simple deep copy

        current_realms: Dict[str, List] = merged.get("realm", {}) or {}
        incoming_realms: Dict[str, List] = (incoming or {}).get("realm", {}) or {}

        if not incoming_realms:
            info("No realm data found in incoming themes file; nothing to merge.")
            return merged

        for realm_name, incoming_themes in incoming_realms.items():
            if not isinstance(incoming_themes, list):
                error(
                    f"Skipping realm '{realm_name}': expected a list of theme objects, "
                    f"got {type(incoming_themes).__name__}."
                )
                continue

            # Ensure the realm key exists in the merged document
            if realm_name not in current_realms:
                current_realms[realm_name] = []
                info(f"Realm '{realm_name}' is new; it will be created.")

            curr_list: List[Dict] = current_realms[realm_name]

            # Build indices of existing themes for O(1) lookup
            # id_index: _id -> position in curr_list
            # name_index: name -> position in curr_list
            id_index: Dict[str, int] = {}
            name_index: Dict[str, int] = {}
            for idx, t in enumerate(curr_list):
                if not isinstance(t, dict):
                    continue
                tid = t.get("_id")
                tname = t.get("name")
                if tid:
                    id_index[tid] = idx
                if tname:
                    name_index[tname] = idx

            for in_theme in incoming_themes:
                if not isinstance(in_theme, dict):
                    error(
                        f"Skipping non-dict entry in realm '{realm_name}': {in_theme!r}"
                    )
                    continue

                theme_id: Optional[str] = in_theme.get("_id")
                theme_name: Optional[str] = in_theme.get("name")

                match_idx: int = -1

                # 1. Try to match by _id
                if theme_id and theme_id in id_index:
                    match_idx = id_index[theme_id]
                # 2. Try to match by name (fallback if no ID match)
                elif theme_name and theme_name in name_index:
                    match_idx = name_index[theme_name]
                    # If we matched by name but incoming theme has no _id (or different one),
                    # we should ideally keep the server's existing _id to maintain identity.
                    if not theme_id:
                        in_theme["_id"] = curr_list[match_idx].get("_id")
                        theme_id = in_theme["_id"]

                if match_idx >= 0:
                    # Update existing theme (preserving position)
                    curr_list[match_idx] = in_theme
                    match_info = (
                        f"(_id={theme_id})" if theme_id else f"('{theme_name}')"
                    )
                    info(
                        f"Realm '{realm_name}': updating existing theme "
                        f"'{theme_name or theme_id}' {match_info}"
                    )
                else:
                    # New theme — append
                    curr_list.append(in_theme)
                    info(
                        f"Realm '{realm_name}': creating new theme "
                        f"'{theme_name or theme_id}'"
                    )

            current_realms[realm_name] = curr_list

        merged["realm"] = current_realms
        return merged

    def _apply_cherry_pick_filter(
        self, items: List[Dict[str, Any]], cherry_pick: str
    ) -> List[Dict[str, Any]]:
        """Filter the ui/themerealm payload by theme _id or name for cherry-picking."""
        if not self.cherry_pick_filter.validate_cherry_pick_argument(cherry_pick):
            error(f"Invalid cherry-pick argument: '{cherry_pick}'.")
            return []

        target_identifiers = [t.strip() for t in cherry_pick.split(",") if t.strip()]
        if not target_identifiers:
            return []

        filtered_items = []
        for item in items:
            if "realm" not in item:
                filtered_items.append(item)
                continue

            filtered_realm: Dict[str, Any] = {}
            found_identifiers = set()

            for realm_name, themes in item["realm"].items():
                if not isinstance(themes, list):
                    continue

                filtered_themes = []
                for theme in themes:
                    if not isinstance(theme, dict):
                        continue

                    theme_id = theme.get("_id")
                    theme_name = theme.get("name")

                    for target in target_identifiers:
                        if target in (theme_id, theme_name):
                            filtered_themes.append(theme)
                            found_identifiers.add(target)
                            info(
                                f"Cherry-pick: found theme '{theme_name or 'Unknown'}' (_id='{theme_id or 'Unknown'}') in realm '{realm_name}'"
                            )
                            break

                if filtered_themes:
                    filtered_realm[realm_name] = filtered_themes

            for target in target_identifiers:
                if target not in found_identifiers:
                    error(f"Cherry-pick: realm '{target}' not found in export file")

            if filtered_realm:
                filtered_item = item.copy()
                filtered_item["realm"] = filtered_realm
                filtered_items.append(filtered_item)

        return filtered_items

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """
        Merge and PUT the full ui/themerealm document.

        Steps:
          1. GET current document (captures _rev for If-Match).
          2. Merge incoming themes by _id into current document.
          3. PUT merged document back with If-Match header.
        """
        # --- Step 1: GET current state ---
        current = self._fetch_current(token, base_url)
        rev: Optional[str] = current.get("_rev")

        # --- Step 2: Merge ---
        merged = self._merge_themes(current, item_data)

        # Remove _rev from the body before PUT (server manages it)
        body = {k: v for k, v in merged.items() if k != "_rev"}

        # --- Step 3: PUT ---
        url = self.get_api_endpoint("", base_url)
        headers = get_headers("themes")
        headers = {
            **headers,
            **self.build_auth_headers(token),
        }

        # Include If-Match to prevent clobbering concurrent changes.
        # Use "*" if we couldn't read a _rev (e.g. document didn't exist yet).
        if rev:
            headers["If-Match"] = rev
        else:
            # Document may not exist yet; omit If-Match so the PUT acts as
            # an upsert.  Some AIC versions require If-None-Match: * for
            # creation, but ui/themerealm always pre-exists in a tenant.
            info(
                "Could not determine current _rev for ui/themerealm; "
                "proceeding without If-Match (upsert mode)."
            )

        try:
            self.make_http_request(url, "PUT", headers, json.dumps(body))
            # Count how many themes we touched for a useful log line
            n_realms = len((item_data or {}).get("realm", {}))
            info(
                f"Successfully PUT ui/themerealm "
                f"({n_realms} realm(s) updated/created)"
            )
            return True
        except Exception as e:
            error(f"Failed to PUT ui/themerealm: {e}")
            return False

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """
        Delete a single theme by its _id from ui/themerealm.

        Strategy:
          1. GET the current themerealm document.
          2. Scan all realm arrays and remove the theme matching item_id.
          3. PUT the modified document back.
        """
        current = self._fetch_current(token, base_url)
        if not current:
            error(f"Could not fetch current themerealm document to delete theme '{item_id}'")
            return False

        rev: Optional[str] = current.get("_rev")
        realms: Dict[str, List] = current.get("realm", {}) or {}
        found = False

        for realm_name, themes in realms.items():
            if not isinstance(themes, list):
                continue
            original_len = len(themes)
            realms[realm_name] = [
                t for t in themes if isinstance(t, dict) and t.get("_id") != item_id
            ]
            if len(realms[realm_name]) < original_len:
                found = True
                info(f"Removing theme '{item_id}' from realm '{realm_name}'")

        if not found:
            error(f"Theme '{item_id}' not found in any realm of ui/themerealm")
            return False

        current["realm"] = realms
        body = {k: v for k, v in current.items() if k != "_rev"}

        url = self.get_api_endpoint("", base_url)
        headers = get_headers("themes")
        headers = {**headers, **self.build_auth_headers(token)}
        if rev:
            headers["If-Match"] = rev

        try:
            self.make_http_request(url, "PUT", headers, json.dumps(body))
            return True
        except Exception as e:
            error(f"Failed to delete theme '{item_id}': {e}")
            return False


def create_themes_import_command():
    """Create the themes import command function."""

    def import_themes(
        cherry_pick: CherryPickOpt = None,
        file: InputFileOpt = None,
        realm: RealmOpt = DEFAULT_REALM,
        jwk_path: JwkPathOpt = None,
        sa_id: SaIdOpt = None,
        base_url: BaseUrlOpt = None,
        project_name: ProjectNameOpt = None,
        auth_mode: AuthModeOpt = None,
        onprem_username: OnPremUsernameOpt = None,
        onprem_password: OnPremPasswordOpt = None,
        onprem_realm: OnPremRealmOpt = "root",
        am_base_url: AmBaseUrlOpt = None,
        idm_base_url: IdmBaseUrlOpt = None,
        idm_username: IdmUsernameOpt = None,
        idm_password: IdmPasswordOpt = None,
        force_import: ForceImportOpt = False,
        diff: DiffOpt = False,
        branch: BranchOpt = None,
        rollback: RollbackOpt = False,
        sync: SyncOpt = False,
    ):
        """Import themes from JSON file or Git repository."""
        importer = ThemesImporter()
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
            diff=diff,
            rollback=rollback,
            cherry_pick=cherry_pick,
            sync=sync,
        )

    return import_themes
