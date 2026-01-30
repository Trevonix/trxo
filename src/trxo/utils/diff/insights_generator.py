"""
Insights generator for diff analysis.

This module generates intelligent, command-specific summaries
of SPECIFIC FIELD CHANGES in human-readable English.
Only highlights important fields that changed, avoiding redundancy with the detailed table.
"""

from typing import Dict, Any, List, Optional
import re
from trxo.utils.diff.diff_engine import DiffItem


class InsightsGenerator:
    """Generate human-readable insights from diff items (field-specific only)"""

    def __init__(self):
        # Map command names to their important field monitoring rules
        # Each command has a list of "important fields" to track
        self.important_fields = {
            "oauth": ["grantTypes", "redirectionUris", "claims", "scopes"],
            "journeys": ["nodes", "stages", "outcomes"],
            "managed": ["schema.properties"],
        }

        # Map command names to their insight generation rules
        self.command_rules = {
            "oauth": self._generate_oauth_insights,
            "journeys": self._generate_journeys_insights,
            "managed": self._generate_managed_insights,
        }

    def generate_key_insights(
        self,
        command_name: str,
        added_items: List[DiffItem],
        modified_items: List[DiffItem],
        removed_items: List[DiffItem],
    ) -> List[str]:
        """
        Generate key insights for SPECIFIC field changes only.
        Avoids redundancy with the detailed table by focusing on important fields.

        Args:
            command_name: Name of the command (e.g., 'oauth', 'scripts')
            added_items: List of added items
            modified_items: List of modified items
            removed_items: List of removed items

        Returns:
            List of human-readable insight strings for important field changes only
        """
        insights = []

        # Only focus on modified items with specific field changes
        if not modified_items:
            return insights

        # Use command-specific rule if available
        if command_name in self.command_rules:
            specific = self.command_rules[command_name](modified_items)
            insights.extend(specific)

        return insights

    def _extract_changed_fields(
        self, diff_dict: Dict[str, Any], important_fields: List[str]
    ) -> Dict[str, Any]:
        """
        Extract only changes to important fields from a diff.

        Returns a dict with changed_fields and details.
        """
        changed_fields = {}

        # Check values_changed
        if "values_changed" in diff_dict:
            for path, change_info in diff_dict["values_changed"].items():
                # Check if any important field is in this path
                for field in important_fields:
                    if (
                        f"['{field}']" in path
                        or f'["{field}"]' in path
                        or f".{field}" in path
                    ):
                        changed_fields[field] = {
                            "type": "value_changed",
                            "old": change_info.get("old_value"),
                            "new": change_info.get("new_value"),
                        }
                        break

        # Check iterable_item_added/removed for array fields
        if "iterable_item_added" in diff_dict:
            for path in diff_dict["iterable_item_added"]:
                for field in important_fields:
                    if f"['{field}']" in path or f'["{field}"]' in path:
                        if field not in changed_fields:
                            changed_fields[field] = {"type": "items_added"}
                        break

        if "iterable_item_removed" in diff_dict:
            for path in diff_dict["iterable_item_removed"]:
                for field in important_fields:
                    if f"['{field}']" in path or f'["{field}"]' in path:
                        if field not in changed_fields:
                            changed_fields[field] = {"type": "items_removed"}
                        break

        return changed_fields

    def _generate_general_summary(
        self,
        command_name: str,
        added_items: List[DiffItem],
        modified_items: List[DiffItem],
        removed_items: List[DiffItem],
    ) -> Optional[str]:
        """
        Generate a general summary line for all commands.
        Example: "3 OAuth clients updated: 1 added, 2 modified"
        """
        total_changes = len(added_items) + len(modified_items) + len(removed_items)

        if total_changes == 0:
            return None

        # Pluralize command name nicely
        command_label = command_name.title()
        if command_name == "oauth":
            command_label = "OAuth Clients"
        elif command_name == "journeys":
            command_label = "Journeys"
        elif command_name == "managed":
            command_label = "Managed Objects"

        # Build the statement
        parts = []
        if len(added_items) > 0:
            parts.append(f"{len(added_items)} added")
        if len(modified_items) > 0:
            parts.append(f"{len(modified_items)} modified")
        if len(removed_items) > 0:
            parts.append(f"{len(removed_items)} removed")

        changes_desc = ", ".join(parts)
        return f"➜ {command_label}: {total_changes} total changes — {changes_desc}"

    def _generate_oauth_insights(self, modified_items: List[DiffItem]) -> List[str]:
        """
        Generate OAuth-specific insights.
        Only report if important fields like grantTypes changed.
        Format: "grantTypes updated: [ClientID1, ClientID2] – added: X, removed: Y"
        """
        insights = []
        important_fields = self.important_fields.get("oauth", [])

        # Collect items with important field changes
        grant_types_items = []
        redirect_uri_items = []
        scopes_items = []
        claims_items = []

        for item in modified_items:
            dc = item.detailed_changes or {}
            diff_dict = dc.get("diff", {})

            changed_fields = self._extract_changed_fields(diff_dict, important_fields)

            if not changed_fields:
                continue

            # Track grantTypes changes
            if "grantTypes" in changed_fields:
                old_grants = changed_fields["grantTypes"].get("old", [])
                new_grants = changed_fields["grantTypes"].get("new", [])

                if isinstance(old_grants, list) and isinstance(new_grants, list):
                    old_set = set(old_grants)
                    new_set = set(new_grants)
                    added = new_set - old_set
                    removed = old_set - new_set

                    grant_types_items.append(
                        {
                            "id": item.item_id,
                            "name": item.item_name,
                            "added": sorted(added),
                            "removed": sorted(removed),
                        }
                    )

            # Track redirectionUris changes
            if "redirectionUris" in changed_fields:
                redirect_uri_items.append(item.item_id or item.item_name)

            # Track clientSecret changes
            if "scopes" in changed_fields:
                scopes_items.append(item.item_id or item.item_name)

            # Track claims changes
            if "claims" in changed_fields:
                claims_items.append(item.item_id or item.item_name)

        # Format insights
        if grant_types_items:
            ids_str = ", ".join([f"'{item['id']}'" for item in grant_types_items])
            # print("grant_types_items: ", len(grant_types_items))
            # Count total added/removed
            total_added = sum(len(item["added"]) for item in grant_types_items)
            total_removed = sum(len(item["removed"]) for item in grant_types_items)

            insight = f"grantTypes updated for the following clients: {ids_str}"

            if total_added > 0 or total_removed > 0:
                details = []
                if total_added > 0:
                    details.append(f"added: {total_added} type(s)")
                if total_removed > 0:
                    details.append(f"removed: {total_removed} type(s)")
                insight += f" — {', '.join(details)}"

            insights.append(f"\n  ✓ {insight}")

        if redirect_uri_items:
            ids_str = ", ".join([f"'{id}'" for id in redirect_uri_items])
            insights.append(f"\n  ✓ redirectionUris updated in: {ids_str}")

        if scopes_items:
            ids_str = ", ".join([f"'{id}'" for id in scopes_items])
            insights.append(f"\n  ⚠ scopes changed in: {ids_str}")

        if claims_items:
            ids_str = ", ".join([f"'{id}'" for id in claims_items])
            insights.append(f"\n  ⚠ claims changed in: {ids_str}")
        return insights

    def _generate_journeys_insights(self, modified_items: List[DiffItem]) -> List[str]:
        """
        Generate Journeys-specific insights.
        Only report if nodes or stages changed.
        """
        insights = []
        important_fields = self.important_fields.get("journeys", [])

        flow_changed_items = []

        for item in modified_items:
            dc = item.detailed_changes or {}
            diff_dict = dc.get("diff", {})

            changed_fields = self._extract_changed_fields(diff_dict, important_fields)

            if not changed_fields:
                continue

            if "nodes" in changed_fields or "stages" in changed_fields:
                flow_changed_items.append(item.item_id or item.item_name)

        # Format insights
        if flow_changed_items:
            ids_str = ", ".join([f"'{id}'" for id in flow_changed_items])
            insights.append(f"  ✓ Authentication flow updated in: {ids_str}")

        return insights

    def _generate_managed_insights(self, modified_items: List["DiffItem"]) -> List[str]:
        """
        Produce high-level, natural-language summaries for Managed Object schema diffs.
        Only lists property names (added, removed, modified); does NOT show values.
        Output is grouped per object and phrased professionally, AI-style.
        """
        insights = []
        prop_root_regex = re.compile(
            r"root\['schema'\]\['properties'\]\['(?P<prop>[^']+)'\]"
        )

        for item in modified_items:
            dc = item.detailed_changes or {}
            diff_dict = dc.get("diff", {})
            if not diff_dict:
                continue

            added = set()
            removed = set()
            modified = set()

            # TYPE CHANGES = Modified
            for path in diff_dict.get("type_changes", {}):
                m = prop_root_regex.search(path)
                if m:
                    modified.add(m.group("prop"))

            # VALUE CHANGES = Modified
            for path in diff_dict.get("values_changed", {}):
                m = prop_root_regex.search(path)
                if m:
                    modified.add(m.group("prop"))

            # ADDED
            for path in diff_dict.get("dictionary_item_added", {}):
                m = prop_root_regex.search(path)
                if m:
                    added.add(m.group("prop"))
            for path in diff_dict.get("iterable_item_added", {}):
                m = prop_root_regex.search(path)
                if m:
                    added.add(m.group("prop"))

            # REMOVED
            for path in diff_dict.get("dictionary_item_removed", {}):
                m = prop_root_regex.search(path)
                if m:
                    removed.add(m.group("prop"))
            for path in diff_dict.get("iterable_item_removed", {}):
                m = prop_root_regex.search(path)
                if m:
                    removed.add(m.group("prop"))

            # ---------- Natural Language Construction ----------
            obj_name = item.item_id or item.item_name or "<unknown>"
            parts = []

            if modified:
                props = ", ".join(sorted(modified))
                parts.append(f"schema updates across properties ({props})")

            if added:
                props = ", ".join(sorted(added))
                parts.append(f"an addition of new properties ({props})")

            if removed:
                props = ", ".join(sorted(removed))
                parts.append(f"the removal of properties ({props})")

            if not parts:
                insights.append(
                    f"• '{obj_name}' shows structural changes, "
                    "but no property-level differences were identified."
                )
                continue

            # Combine all parts into an elegant, natural-language sentence
            if len(parts) == 1:
                summary = f"\n• '{obj_name}' has {parts[0]}."
            else:
                # Join everything in a natural flow: A, B, and C.
                human = ", ".join(parts[:-1]) + f", and {parts[-1]}"
                summary = f"\n• '{obj_name}' includes {human}."

            insights.append(summary)

        return insights
