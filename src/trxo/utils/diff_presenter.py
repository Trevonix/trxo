"""
CLI Diff & Sync Presenter.

Unified CLI-side presentation for diff, sync, and delete operations.
Delegates to the library for data; handles all Rich console output,
user confirmation prompts, and HTML report linking.
"""

import html as _html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from trxo.utils.console import error, info, warning, success
from trxo_lib.state.diff.diff_engine import ChangeType, DiffItem, DiffResult


class DiffPresenter:
    """Presents diff results in a rich, modern CLI format."""

    def __init__(self):
        self.console = Console()

    # ------------------------------------------------------------------ #
    #  Diff display
    # ------------------------------------------------------------------ #

    def display_diff_summary(self, diff_result: DiffResult) -> None:
        """
        Display a clean table-based summary of differences.

        Args:
            diff_result: The diff result to display
        """
        try:
            # Display header (professional, minimal)
            title = f"Diff Summary: {diff_result.command_name.title()}"
            if diff_result.realm:
                title += f" (Realm: {diff_result.realm})"

            total_current = diff_result.total_items_current
            total_new = diff_result.total_items_new
            added = len(diff_result.added_items)
            modified = len(diff_result.modified_items)
            removed = len(diff_result.removed_items)

            summary_lines = []
            summary_lines.append(f"Total on server: {total_current}")
            summary_lines.append(f"Total in import : {total_new}")
            summary_lines.append("")
            summary_lines.append(
                f"Changes: Added {added}  •  Modified {modified}  •  Removed {removed}"
            )

            panel_text = "\n".join(summary_lines)
            self.console.print()
            self.console.print(Panel(panel_text, title=title, style="bold blue"))

            # Display key insights if available
            if diff_result.key_insights:
                self._display_key_insights(diff_result.key_insights, diff_result)

            # Show per-item table
            if added or modified or removed:
                self._display_changes_table(diff_result)
            else:
                self.console.print("No differences detected. No action required.")

            self.console.print()

        except Exception as e:
            error(f"Failed to display summary: {str(e)}")

    def _display_key_insights(
        self, key_insights: List[str], diff_result: DiffResult
    ) -> None:
        """Display key insights in a formatted panel."""
        if not key_insights:
            return

        cmd = (diff_result.command_name or "").lower()
        if cmd != "oauth":
            insights_text = "\n".join(key_insights)
            self.console.print()
            self.console.print(
                Panel(insights_text, title="🔍 Key Insights", style="bold green")
            )
            return

        # OAuth specific rendering
        field_map = {}
        for line in key_insights:
            m = re.search(r"(?P<field>[A-Za-z0-9_]+).*?:\s*(?P<ids>.+)$", line)
            if not m:
                continue
            field = m.group("field").strip()
            ids_part = m.group("ids").strip()
            ids = [
                re.sub(r"^['\"]|['\"]$", "", s.strip())
                for s in ids_part.split(",")
                if s.strip()
            ]
            if ids:
                field_map.setdefault(field, set()).update(ids)

        total_modified = len(diff_result.modified_items)
        parts = []
        for f in ["grantTypes", "redirectionUris", "scopes", "claims"]:
            cnt = len(field_map.get(f, []))
            if cnt:
                parts.append(f"{f} updated for {cnt}")

        summary = f"This import will modify {total_modified} OAuth client(s)."
        if parts:
            summary += " " + ", ".join(parts) + "."

        lines = [summary, ""]
        field_order = ["grantTypes", "redirectionUris", "scopes", "claims"]
        for field in field_order:
            ids = sorted(field_map.get(field, []))
            if not ids:
                continue
            ids_formatted = ", ".join(f"[green]'{i}'[/green]" for i in ids[:15])
            if len(ids) > 15:
                ids_formatted += f", [dim]... and {len(ids) - 15} more[/dim]"

            lines.append(
                f"✓ [bold cyan]{field}[/bold cyan] updated for {len(ids)} client(s): {ids_formatted}"
            )

        self.console.print()
        self.console.print(
            Panel("\n".join(lines), title="🔍 Key Insights (OAuth)", style="bold green")
        )

    def _display_changes_table(self, diff_result: DiffResult) -> None:
        """Print a concise per-item changes table to the console."""
        table = Table(
            title="Changed Items",
            show_header=True,
            header_style="bold blue",
            show_lines=False,
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("ID", overflow="fold")
        table.add_column("Name", overflow="fold")
        table.add_column("Change", width=10)
        table.add_column("Summary", overflow="fold")

        colour_map = {"added": "green", "modified": "yellow", "removed": "red"}

        combined = (
            [(item, "added") for item in diff_result.added_items]
            + [(item, "modified") for item in diff_result.modified_items]
            + [(item, "removed") for item in diff_result.removed_items]
        )

        for idx, (item, change_type) in enumerate(combined, 1):
            colour = colour_map.get(change_type, "white")
            table.add_row(
                str(idx),
                Text(item.item_id, style=colour),
                item.item_name or "—",
                Text(change_type.upper(), style=f"bold {colour}"),
                item.summary,
            )

        self.console.print(table)

    # ------------------------------------------------------------------ #
    #  HTML Report Generation
    # ------------------------------------------------------------------ #

    def generate_html_report(
        self,
        diff_result: DiffResult,
        current_data: Optional[Dict[str, Any]] = None,
        new_data: Optional[Dict[str, Any]] = None,
        output_dir: Optional[str] = None,
    ) -> Optional[str]:
        """Generate an HTML diff report and print a clickable link."""
        try:
            # Determine output path
            if not output_dir:
                output_dir = Path.cwd() / "diff_reports"
            else:
                output_dir = Path(output_dir)

            output_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{diff_result.command_name}_diff_{timestamp}.html"
            html_path = output_dir / filename

            # Generate HTML content
            html_content = self._generate_html_content(diff_result)

            # Write HTML file
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            html_uri = html_path.absolute().as_uri()
            info(f"Open HTML report: [link={html_uri}]{html_uri}[/link]")
            return str(html_path)

        except Exception as e:
            error(f"Failed to generate HTML report: {str(e)}")
            return None

    def _generate_html_content(self, diff_result: DiffResult) -> str:
        """Generate HTML content for diff report."""
        per_item_html = ""
        if diff_result.modified_items:
            per_item_blocks = []
            for item in diff_result.modified_items:
                unified_diff = item.get_unified_diff()
                if unified_diff:
                    html_lines = []
                    for line in unified_diff.splitlines():
                        esc = _html.escape(line)
                        if line.startswith("+++") or line.startswith("---"):
                            html_lines.append(f'<span class="file-header">{esc}</span>')
                        elif line.startswith("@@"):
                            html_lines.append(f'<span class="hunk-header">{esc}</span>')
                        elif line.startswith("+") and not line.startswith("+++"):
                            html_lines.append(f'<span class="added">{esc}</span>')
                        elif line.startswith("-") and not line.startswith("---"):
                            html_lines.append(f'<span class="removed">{esc}</span>')
                        else:
                            html_lines.append(f'<span class="context">{esc}</span>')

                    block = f"""
            <div class="section">
                <h3>Item: {_html.escape(item.item_name or item.item_id)}</h3>
                <div class="unified-diff">{'<br>'.join(html_lines)}</div>
            </div>
            """
                    per_item_blocks.append(block)
                else:
                    per_item_blocks.append(
                        f"<div class='section'><h3>"
                        f"{_html.escape(item.item_name or item.item_id)}"
                        f"</h3><p>{_html.escape(item.summary)}</p></div>"
                    )

            per_item_html = "\n".join(per_item_blocks)

        # Generate summary statistics
        stats_html = self._generate_stats_html(diff_result)
        # Generate changes table
        changes_html = self._generate_changes_html(diff_result)
        # Generate key insights HTML
        insights_html = self._generate_insights_html(diff_result)

        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        title = f"{diff_result.command_name.title()}"
        realm_suffix = f" - Realm: {diff_result.realm}" if diff_result.realm else ""

        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Diff Report: {title}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 2.5em; }}
        .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
        .content {{ padding: 30px; }}
        .section {{ margin-bottom: 40px; }}
        .section h2 {{ color: #333; border-bottom: 2px solid #667eea; padding-bottom: 10px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; border-left: 4px solid #667eea; }}
        .stat-number {{ font-size: 2em; font-weight: bold; color: #667eea; }}
        .stat-label {{ color: #666; margin-top: 5px; }}
        .changes-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        .unified-diff {{ background: #f7f7f7; padding: 12px; border-radius: 4px; overflow: auto; font-family: 'Courier New', monospace; font-size: 13px; }}
        .unified-diff .added {{ display: block; background: #e6ffed; color: #044; }}
        .unified-diff .removed {{ display: block; background: #ffeef0; color: #600; }}
        .unified-diff .hunk-header {{ display: block; color: #0366d6; font-weight: 600; }}
        .unified-diff .file-header {{ display: block; color: #333; font-weight: 700; }}
        .unified-diff .context {{ display: block; color: #444; }}
        .changes-table th, .changes-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        .changes-table th {{ background: #f8f9fa; font-weight: bold; }}
        .change-added {{ color: #28a745; }}
        .change-modified {{ color: #ffc107; }}
        .change-removed {{ color: #dc3545; }}
        .timestamp {{ color: #666; font-size: 0.9em; }}
        .insights-box {{ background: linear-gradient(135deg, #f0f9ff 0%, #e0f7ff 100%); border-left: 4px solid #0284c7; padding: 16px; border-radius: 6px; margin-top: 12px; }}
        .insight-text {{ color: #0f172a; font-weight: 600; margin: 8px 0 4px 0; font-size: 0.95em; }}
        .insight-bullet {{ color: #0c4a6e; margin: 4px 0 2px 0; padding-left: 12px; font-size: 0.9em; line-height: 1.4; }}
        .insight-sub-bullet {{ color: #0f766e; margin: 2px 0; padding-left: 28px; font-size: 0.9em; }}
        .insight-indent {{ color: #334155; margin: 1px 0; padding-left: 20px; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Diff Report</h1>
            <p>{title}{realm_suffix}</p>
            <p class="timestamp">Generated: {generated_at}</p>
        </div>
        <div class="content">
            <div class="section">
                <h2>Summary</h2>
                {stats_html}
            </div>
            {insights_html}
            {changes_html}
            {per_item_html}
        </div>
    </div>
</body>
</html>
        """
        return html_template.strip()

    def _generate_stats_html(self, diff_result: DiffResult) -> str:
        """Generate HTML for statistics section."""
        return f"""
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{diff_result.total_items_current}</div>
                <div class="stat-label">Current Items</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{diff_result.total_items_new}</div>
                <div class="stat-label">New Items</div>
            </div>
            <div class="stat-card">
                <div class="stat-number change-added">{len(diff_result.added_items)}</div>
                <div class="stat-label">Added</div>
            </div>
            <div class="stat-card">
                <div class="stat-number change-modified">{len(diff_result.modified_items)}</div>
                <div class="stat-label">Modified</div>
            </div>
            <div class="stat-card">
                <div class="stat-number change-removed">{len(diff_result.removed_items)}</div>
                <div class="stat-label">Removed</div>
            </div>
        </div>
        """

    def _generate_changes_html(self, diff_result: DiffResult) -> str:
        """Generate HTML for changes table."""
        if not (
            diff_result.added_items
            or diff_result.modified_items
            or diff_result.removed_items
        ):
            return '<div class="section"><h2>✅ No Changes</h2><p>All items are identical.</p></div>'

        combined = (
            [(item, "added") for item in diff_result.added_items]
            + [(item, "modified") for item in diff_result.modified_items]
            + [(item, "removed") for item in diff_result.removed_items]
        )

        rows_html = ""
        for idx, (item, change_type) in enumerate(combined, 1):
            class_name = f"change-{change_type}"
            rows_html += f"""
            <tr>
                <td>{idx}</td>
                <td class="{class_name}">{item.item_id}</td>
                <td>{item.item_name or 'N/A'}</td>
                <td class="{class_name}">{change_type.upper()}</td>
                <td>{item.summary}</td>
            </tr>
            """

        return f"""
        <div class="section">
            <h2>🔍 Detailed Changes</h2>
            <table class="changes-table">
                <thead>
                    <tr><th>#</th><th>ID</th><th>Name</th><th>Type</th><th>Summary</th></tr>
                </thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
        """

    def _generate_insights_html(self, diff_result: DiffResult) -> str:
        """Generate HTML for key insights section."""
        key_insights = diff_result.key_insights
        if not key_insights:
            return ""

        cmd = (diff_result.command_name or "").lower()
        if cmd != "oauth":
            insights_html = ""
            for insight in key_insights:
                for line in insight.split("\n"):
                    esc = _html.escape(line)
                    if line.startswith("  •"):
                        insights_html += f'<div class="insight-bullet">{esc}</div>'
                    elif line.startswith("    -"):
                        insights_html += f'<div class="insight-sub-bullet">{esc}</div>'
                    elif line.startswith("    "):
                        insights_html += f'<div class="insight-indent">{esc}</div>'
                    else:
                        insights_html += f'<div class="insight-text">{esc}</div>'
            return f'<div class="section"><h2>🎯 Key Insights</h2><div class="insights-box">{insights_html}</div></div>'

        # OAuth specific HTML
        field_map = {}
        for line in key_insights:
            m = re.search(r"(?P<field>[A-Za-z0-9_]+).*?:\s*(?P<ids>.+)$", line)
            if not m:
                continue
            field = m.group("field").strip()
            ids_part = m.group("ids").strip()
            ids = [
                re.sub(r"^['\"]|['\"]$", "", s.strip())
                for s in ids_part.split(",")
                if s.strip()
            ]
            if ids:
                field_map.setdefault(field, set()).update(ids)

        total_modified = len(diff_result.modified_items)
        parts = [
            f"{f} updated for {len(field_map[f])}"
            for f in ["grantTypes", "redirectionUris", "scopes", "claims"]
            if f in field_map
        ]
        summary = f"This import will modify {total_modified} OAuth client(s). {' '.join(parts)}."

        items_html = [f'<div class="insight-text">{_html.escape(summary)}</div>']
        field_order = ["grantTypes", "redirectionUris", "scopes", "claims"]
        for field in field_order:
            ids = sorted(field_map.get(field, []))
            if not ids:
                continue
            ids_formatted = ", ".join(f"'{i}'" for i in ids[:15])
            if len(ids) > 15:
                ids_formatted += f", ... and {len(ids) - 15} more"
            items_html.append(
                f'<div class="insight-bullet"><strong style="color:#0284c7">✓ {field}</strong> updated in: '
                f'<span style="color:#0f766e">{_html.escape(ids_formatted)}</span></div>'
            )

        return f'<div class="section"><h2>🎯 Key Insights</h2><div class="insights-box">{"".join(items_html)}</div></div>'


class SyncPresenter:
    """Presents sync/deletion operations in a rich, modern CLI format."""

    @staticmethod
    def display_deletion_preview(
        items_to_delete: List[DiffItem], item_type: str
    ) -> None:
        """Show a Rich-formatted preview of items that will be deleted."""
        if not items_to_delete:
            info("No items to delete")
            return

        warning(f"{'=' * 60}")
        warning(f"SYNC MODE: {len(items_to_delete)} {item_type} will be DELETED")
        warning(f"{'=' * 60}")

        for item in items_to_delete:
            warning(f"  ❌ {item.item_name or item.item_id}")

        warning(f"{'=' * 60}\n")

    @staticmethod
    def confirm_deletions(
        items_to_delete: List[DiffItem], item_type: str, force: bool = False
    ) -> bool:
        """Display deletion preview and prompt for user confirmation."""
        if not items_to_delete:
            info("No items to delete")
            return True

        SyncPresenter.display_deletion_preview(items_to_delete, item_type)

        if force:
            return True

        return typer.confirm(
            "⚠️  Are you sure you want to DELETE these items?", default=False
        )

    @staticmethod
    def display_deletion_summary(summary: Dict[str, Any]) -> None:
        """Display a Rich-formatted deletion summary."""
        if summary["deleted_count"] > 0:
            success(f"Successfully deleted {summary['deleted_count']} item(s)")

        if summary["failed_count"] > 0:
            error(f"Failed to delete {summary['failed_count']} item(s)")
            for failed in summary["failed_deletions"]:
                error(f"  • {failed['id']}: {failed['error']}")
