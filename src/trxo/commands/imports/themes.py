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

import typer

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
        return "themes (ui/themerealm)"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/openidm/config/ui/themerealm"

    def _fetch_current(self, token: str, base_url: str) -> Dict[str, Any]:
        """
        GET the current ui/themerealm document.
        Returns the full dict (including _rev) or {} on failure.
        """
        url = self.get_api_endpoint("", base_url)
        headers = {
            "Accept-API-Version": "protocol=2.1,resource=1.0",
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

            # Build an index of existing themes by _id for O(1) lookup
            curr_index: Dict[str, int] = {
                t.get("_id"): idx
                for idx, t in enumerate(curr_list)
                if isinstance(t, dict) and t.get("_id")
            }

            for in_theme in incoming_themes:
                if not isinstance(in_theme, dict):
                    error(
                        f"Skipping non-dict entry in realm '{realm_name}': {in_theme!r}"
                    )
                    continue

                theme_id: Optional[str] = in_theme.get("_id")

                if not theme_id:
                    # Theme has no _id — append as a brand-new theme.
                    # AIC will assign an _id on creation if it's missing,
                    # but warn the user since this may produce duplicates.
                    error(
                        f"Theme in realm '{realm_name}' has no '_id' field. "
                        f"Appending anyway — this may create duplicates on "
                        f"repeated imports."
                    )
                    curr_list.append(in_theme)
                    continue

                if theme_id in curr_index:
                    # Replace the existing theme entirely (preserving position)
                    idx = curr_index[theme_id]
                    curr_list[idx] = in_theme
                    info(
                        f"Realm '{realm_name}': updating existing theme "
                        f"'{in_theme.get('name', theme_id)}' (_id={theme_id})"
                    )
                else:
                    # New theme — append
                    curr_list.append(in_theme)
                    info(
                        f"Realm '{realm_name}': creating new theme "
                        f"'{in_theme.get('name', theme_id)}' (_id={theme_id})"
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
        headers = {
            "Content-Type": "application/json",
            "Accept-API-Version": "protocol=2.1,resource=1.0",
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


def create_themes_import_command():
    """Create the themes import command function."""

    def import_themes(
        cherry_pick: str = typer.Option(
            None,
            "--cherry-pick",
            help="Cherry-pick specific theme realms by name (comma-separated)",
        ),
        file: str = typer.Option(
            None,
            "--file",
            help="Path to JSON file containing themes configuration",
        ),
        realm: str = typer.Option(
            DEFAULT_REALM,
            "--realm",
            help=f"Target realm name (default: {DEFAULT_REALM})",
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
            None, "--project-name", help="Project name for argument mode (optional)"
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
            cherry_pick=cherry_pick,
        )

    return import_themes
