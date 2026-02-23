"""
Diff report generator for import commands.

This module provides clean, table-based summaries and HTML diff reports
for PingOne Advanced Identity Cloud configuration differences.
"""

import json
import html as _html
import re
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime, timezone
import difflib
from rich.panel import Panel
from trxo.utils.console import console, success, info, error
from trxo.utils.diff.diff_engine import DiffResult


class DiffReporter:
    """Generator for diff reports and summaries"""

    def __init__(self):
        self.console = console

    def display_summary(self, diff_result: DiffResult) -> None:
        """
        Display a clean table-based summary of differences

        Args:
            diff_result: The diff result to display
        """
        try:
            # Display header (professional, minimal)
            title = f"Diff Summary: {diff_result.command_name.title()}"
            if diff_result.realm:
                title += f" (Realm: {diff_result.realm})"

            # Build a compact, easy-to-read summary for non-technical users
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
                # pass the full diff_result so we can render
                # command-specific summaries (e.g., oauth)
                self._display_key_insights(diff_result.key_insights, diff_result)

            # After the friendly summary, show full per-item table so power users can inspect
            if self._has_changes(diff_result):
                self._display_changes_table(diff_result)
            else:
                self.console.print("No differences detected. No action required.")

            self.console.print()

        except Exception as e:
            error(f"Failed to display summary: {str(e)}")

    def _display_key_insights(
        self, key_insights: List[str], diff_result: DiffResult
    ) -> None:
        """Display key insights in a formatted panel.

        For `oauth` command we parse the supplied key_insights lines and render a
        short template summary sentence followed by elaborated field details with
        colored field names and comprehensive id lists.
        """
        if not key_insights:
            return

        # Only apply the enhanced template for oauth command; otherwise fall back
        cmd = (diff_result.command_name or "").lower()
        if cmd != "oauth":
            insights_text = "\n".join(key_insights)
            self.console.print()
            self.console.print(
                Panel(insights_text, title="🔍 Key Insights", style="bold green")
            )
            return

        # Parse field -> set(ids) from key_insights lines
        field_map = {}
        for line in key_insights:
            # try to extract "field: id1, id2" style lines
            m = re.search(r"(?P<field>[A-Za-z0-9_]+).*?:\s*(?P<ids>.+)$", line)
            if not m:
                continue
            field = m.group("field").strip()
            ids_part = m.group("ids").strip()
            # split ids by comma, remove quotes/spaces
            ids = [
                re.sub(r"^[\'\"]|[\'\"]$", "", s.strip())
                for s in ids_part.split(",")
                if s.strip()
            ]
            if ids:
                field_map.setdefault(field, set()).update(ids)

        total_modified = len(diff_result.modified_items)

        # Build summary sentence
        parts = []
        for f in ["grantTypes", "redirectionUris", "scopes", "claims"]:
            cnt = len(field_map.get(f, []))
            if cnt:
                parts.append(f"{f} updated for {cnt}")

        summary = f"""\nHere’s a quick summary of the changes detected in your OAuth client "
        "configurations.These updates may affect how applications log in, "
        "redirect users or receive user information."
        "This import will modify {total_modified} OAuth client(s)."""
        if parts:
            summary += " " + ", ".join(parts) + "."

        # Build detailed lines (old style but with enhanced colors/highlighting)
        lines = [summary, ""]

        # Field order for display
        field_order = ["grantTypes", "redirectionUris", "scopes", "claims"]
        for field in field_order:
            if field not in field_map:
                continue
            ids_list = sorted(field_map[field])
            count = len(ids_list)

            # Format the field name with color and the ids list
            # E.g., "✓ grantTypes updated in: 'id1', 'id2', ..., 'idn'"
            ids_formatted = ", ".join(f"[green]'{i}'[/green]" for i in ids_list[:15])
            if count > 15:
                ids_formatted += f", [dim]... and {count - 15} more[/dim]"

            line = f"\n✓ [bold cyan]{field}[/bold cyan] updated for {count} "
            f"client(s): {ids_formatted}"
            lines.append(line)

        panel_text = "\n".join(lines)
        self.console.print()
        # Use Panel with markup so colors/styles render
        self.console.print(
            Panel(panel_text, title="🔍 Key Insights (OAuth)", style="bold green")
        )

    def _has_changes(self, diff_result: DiffResult) -> bool:
        """Check if there are any changes"""
        return bool(
            diff_result.added_items
            or diff_result.modified_items
            or diff_result.removed_items
        )

    def generate_html_diff(
        self,
        diff_result: DiffResult,
        current_data: Dict[str, Any],
        new_data: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate HTML diff report with line-by-line comparison

        Args:
            diff_result: The diff result
            current_data: Current server data
            new_data: New data to be imported
            output_dir: Output directory for HTML file

        Returns:
            Path to generated HTML file or None if failed
        """
        try:
            info("Generating HTML diff report...")

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
            html_content = self._generate_html_content(
                diff_result, current_data, new_data
            )

            # Write HTML file
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            success(f"HTML diff report saved: {html_path}")
            return str(html_path)

        except Exception as e:
            error(f"Failed to generate HTML diff: {str(e)}")
            return None

    def _generate_html_content(
        self,
        diff_result: DiffResult,
        current_data: Dict[str, Any],
        new_data: Dict[str, Any],
    ) -> str:
        """Generate HTML content for diff report"""

        # Pretty print JSON data
        current_json = json.dumps(current_data, indent=2, ensure_ascii=False)
        new_json = json.dumps(new_data, indent=2, ensure_ascii=False)

        # Generate a colored unified diff (git-style) for quick visual review
        unified_lines = list(
            difflib.unified_diff(
                current_json.splitlines(),
                new_json.splitlines(),
                fromfile="Current",
                tofile="New",
                lineterm="",
            )
        )

        if unified_lines:
            unified_html_lines = []
            for ln in unified_lines:
                esc = _html.escape(ln)
                if ln.startswith("+++") or ln.startswith("---"):
                    unified_html_lines.append(f'<span class="file-header">{esc}</span>')
                elif ln.startswith("@@"):
                    unified_html_lines.append(f'<span class="hunk-header">{esc}</span>')
                elif ln.startswith("+"):
                    unified_html_lines.append(f'<span class="added">{esc}</span>')
                elif ln.startswith("-"):
                    unified_html_lines.append(f'<span class="removed">{esc}</span>')
                else:
                    unified_html_lines.append(f'<span class="context">{esc}</span>')

            unified_diff_html = (
                '<pre class="unified-diff">' + "\n".join(unified_html_lines) + "</pre>"
            )
        else:
            unified_diff_html = (
                '<pre class="unified-diff">No textual differences.</pre>'
            )

        # --- Side-by-side HTML diff (git-style) using reduced per-item payloads when available ---
        try:
            hd = difflib.HtmlDiff(tabsize=2, wrapcolumn=80)
            # If we have modified items with reduced payloads, render an item-wise side-by-side diff
            if diff_result.modified_items:
                item_tables = []
                for item in diff_result.modified_items:
                    dc = item.detailed_changes or {}
                    # Prefer reduced payloads created by the diff engine; fall back to full items
                    reduced_curr = (
                        dc.get("reduced_current") or dc.get("current_item") or {}
                    )
                    reduced_new = dc.get("reduced_new") or dc.get("new_item") or {}

                    # Serialize to stable text
                    curr_text = (
                        json.dumps(reduced_curr, indent=2, ensure_ascii=False)
                        if isinstance(reduced_curr, (dict, list))
                        else str(reduced_curr)
                    )
                    new_text = (
                        json.dumps(reduced_new, indent=2, ensure_ascii=False)
                        if isinstance(reduced_new, (dict, list))
                        else str(reduced_new)
                    )

                    table_html = hd.make_table(
                        curr_text.splitlines(),
                        new_text.splitlines(),
                        fromdesc="Server",
                        todesc="Import",
                        context=True,
                        numlines=3,
                    )
                    safe_title = _html.escape(item.item_name or item.item_id)
                    item_tables.append(
                        f"<div class='item-diff'><h3>Item: {safe_title}</h3>{table_html}</div>"
                    )

                side_by_side_html = "\n".join(item_tables)

            else:
                # Fallback: show overall JSON side-by-side
                side_table = hd.make_table(
                    current_json.splitlines(),
                    new_json.splitlines(),
                    fromdesc="Current",
                    todesc="New",
                    context=True,
                    numlines=3,
                )
                side_by_side_html = f'<div class="side-by-side-diff">{side_table}</div>'
        except Exception:
            side_by_side_html = (
                '<pre class="unified-diff">Failed to generate side-by-side diff.</pre>'
            )

        # --- Per-item focused diffs (show only changed fields for each modified item) ---
        per_item_html = ""
        if diff_result.modified_items:
            per_item_blocks = []
            for item in diff_result.modified_items:
                dc = item.detailed_changes or {}
                curr_item = dc.get("current_item")
                new_item = dc.get("new_item")
                # Create a focused unified diff for the item if payloads are available
                if isinstance(curr_item, dict) and isinstance(new_item, dict):
                    # Optionally reduce payloads to changed keys only —
                    # for now use full item for context
                    curr_text = json.dumps(curr_item, indent=2, ensure_ascii=False)
                    new_text = json.dumps(new_item, indent=2, ensure_ascii=False)
                    item_lines = list(
                        difflib.unified_diff(
                            curr_text.splitlines(),
                            new_text.splitlines(),
                            fromfile="Server",
                            tofile="Import",
                            lineterm="",
                            n=3,
                        )
                    )

                    if item_lines:
                        item_html_lines = []
                        for ln in item_lines:
                            esc = _html.escape(ln)
                            if ln.startswith("+++") or ln.startswith("---"):
                                item_html_lines.append(
                                    f'<span class="file-header">{esc}</span>'
                                )
                            elif ln.startswith("@@"):
                                item_html_lines.append(
                                    f'<span class="hunk-header">{esc}</span>'
                                )
                            elif ln.startswith("+") and not ln.startswith("+++"):
                                item_html_lines.append(
                                    f'<span class="added">{esc}</span>'
                                )
                            elif ln.startswith("-") and not ln.startswith("---"):
                                item_html_lines.append(
                                    f'<span class="removed">{esc}</span>'
                                )
                            else:
                                item_html_lines.append(
                                    f'<span class="context">{esc}</span>'
                                )

                        block = f"""
            <div class="section">
                <h3>Item: {_html.escape(item.item_name or item.item_id)}</h3>
                <div class="unified-diff">{'<br>'.join(item_html_lines)}</div>
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

        # Generate key insights HTML (pass diff_result for command-specific summary)
        insights_html = self._generate_insights_html(
            diff_result.key_insights, diff_result
        )

        title = (diff_result.command_name or "Unknown").title()
        realm_suffix = f" - Realm: {diff_result.realm}" if diff_result.realm else ""
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Create HTML template
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Diff Report: {diff_result.command_name.title()}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
        }}
        .content {{
            padding: 30px;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section h2 {{
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        .diff-container {{
            display: flex;
            gap: 20px;
            margin-top: 20px;
        }}
        .diff-panel {{
            flex: 1;
            border: 1px solid #ddd;
            border-radius: 4px;
            overflow: hidden;
        }}
        .diff-header {{
            background: #f8f9fa;
            padding: 10px 15px;
            font-weight: bold;
            border-bottom: 1px solid #ddd;
        }}
        .diff-content {{
            max-height: 600px;
            overflow: auto;
            background: #fff;
        }}
        pre {{
            margin: 0;
            padding: 15px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            line-height: 1.4;
            white-space: pre-wrap;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border-left: 4px solid #667eea;
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            color: #666;
            margin-top: 5px;
        }}
        .changes-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}

        /* unified diff styles */
        .unified-diff {{ background: #f7f7f7; padding: 12px; border-radius: 4px; overflow: auto; }}
        .unified-diff .added {{ display: block; background: #e6ffed; color: #044; }}
        .unified-diff .removed {{ display: block; background: #ffeef0; color: #600; }}
        .unified-diff .hunk-header {{ display: block; color: #0366d6; font-weight: 600; }}
        .unified-diff .file-header {{ display: block; color: #333; font-weight: 700; }}
        .unified-diff .context {{ display: block; color: #444; }}
        /* HtmlDiff (side-by-side) styling */
        .side-by-side-diff {{
            overflow: auto;
            max-height: 700px;
            border: 1px solid #dfe6ef;
            border-radius: 6px;
            padding: 8px;
            background: #ffffff;
        }}
        table.diff {{
            width: 100%;
            border-collapse: collapse;
            font-family: 'Courier New', monospace;
            font-size: 13px;
        }}
        table.diff th {{
            background: #eef2ff;
            padding: 6px 10px;
            text-align: left;
            border-bottom: 1px solid #dfe6ef;
            color: #0f172a;
            font-weight: 700;
        }}
        table.diff td {{
            vertical-align: top;
            padding: 6px 10px;
            white-space: pre-wrap;
            border-bottom: 1px solid #f3f6fb;
        }}
        /* removed (left) */
        td.diff_sub {{ background: #ffecec; color: #6a1b1b; }}
        /* add a visible marker */
        td.diff_sub::before {{ content: '-'; color: #991b1b; font-weight: 800; margin-right: 8px; }}
        /* added (right) */
        td.diff_add {{ background: #ecfff1; color: #0b5d2e; }}
        td.diff_add::before {{ content: '+'; color: #0b5d2e; font-weight: 800; margin-right: 8px; }}
        /* changed (both) */
        td.diff_chg {{ background: #fff8e6; color: #6b4b00; }}
        td.diff_chg::before {{ content: '~'; color: #6b4b00; font-weight: 800; margin-right: 8px; }}
        td.diff_next {{ background: #f8fafc; color: #444; }}
        td.diff_header {{ background: #f0f6ff; font-weight: 700; color: #06222a; }}

        /* Legend */
       .diff-legend {{
            display: flex;
            gap: 12px;
            align-items: center;
            margin-bottom: 8px;
            flex-wrap: wrap;
        }}
        .legend-item {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 10px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.95em;
        }}

        .legend-item.added {{ background: #ecfff1; color: #0b5d2e; border: 1px solid #d6f6df; }}
        .legend-item.removed {{ background: #ffecec; color: #6a1b1b; border: 1px solid #ffd6d6; }}
        .legend-item.changed {{ background: #fff8e6; color: #6b4b00; border: 1px solid #ffefc6; }}
        .legend-bullet {{
            font-weight: 900;
            padding: 2px 6px;
            border-radius: 4px;
            background: rgba(0, 0, 0, 0.04);
        }}

        .changes-table th,
        .changes-table td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        .changes-table th {{
            background: #f8f9fa;
            font-weight: bold;
        }}
        .change-added {{ color: #28a745; }}
        .change-modified {{ color: #ffc107; }}
        .change-removed {{ color: #dc3545; }}
        .timestamp {{
            color: #666;
            font-size: 0.9em;
        }}
        /* Insights styling */
        .insights-box {{
            background: linear-gradient(135deg, #f0f9ff 0%, #e0f7ff 100%);
            border-left: 4px solid #0284c7;
            padding: 16px;
            border-radius: 6px;
            margin-top: 12px;
        }}
        .insight-text {{
            color: #0f172a;
            font-weight: 600;
            margin: 8px 0 4px 0;
            font-size: 0.95em;
        }}
        .insight-bullet {{
            color: #0c4a6e;
            margin: 4px 0 2px 0;
            padding-left: 12px;
            font-size: 0.9em;
            line-height: 1.4;
        }}
        .insight-sub-bullet {{
            color: #0f766e;
            margin: 2px 0;
            padding-left: 28px;
            font-size: 0.9em;
        }}
        .insight-indent {{
            color: #334155;
            margin: 1px 0;
            padding-left: 20px;
            font-size: 0.9em;
        }}
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

            <!-- Textual Diff section removed -->
            <!-- <div class="section">
                <h2>Side-by-side JSON</h2>
                <div class="diff-container">
                    <div class="diff-panel">
                        <div class="diff-header">Current Data</div>
                        <div class="diff-content">
                            <pre>{_html.escape(current_json)}</pre>
                        </div>
                    </div>
                    <div class="diff-panel">
                        <div class="diff-header">New Data</div>
                        <div class="diff-content">
                            <pre>{_html.escape(new_json)}</pre>
                        </div>
                    </div>
                </div>
            </div> -->

        </div>
    </div>
</body>
</html>
        """

        return html_template.strip()

    def _generate_stats_html(self, diff_result: DiffResult) -> str:
        """Generate HTML for statistics section"""
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
            <div class="stat-card">
                <div class="stat-number">{len(diff_result.unchanged_items)}</div>
                <div class="stat-label">Unchanged</div>
            </div>
        </div>
        """

    def _generate_changes_html(self, diff_result: DiffResult) -> str:
        """Generate HTML for changes table"""
        if not self._has_changes(diff_result):
            return '<div class="section"><h2>✅ No Changes</h2><p>All items are identical.</p></div>'

        # Collect all changed items
        changed_items = []
        changed_items.extend(diff_result.added_items)
        changed_items.extend(diff_result.modified_items)
        changed_items.extend(diff_result.removed_items)

        rows_html = ""
        for idx, item in enumerate(changed_items, 1):
            change_class = f"change-{item.change_type.value}"
            rows_html += f"""
            <tr>
                <td>{idx}</td>
                <td class="{change_class}">{item.item_id}</td>
                <td>{item.item_name or 'N/A'}</td>
                <td class="{change_class}">{item.change_type.value.upper()}</td>
                <!-- <td>{item.changes_count if item.changes_count > 0 else '-'}</td> -->
                <td>{item.summary}</td>
            </tr>
            """

        return f"""
        <div class="section">
            <h2>🔍 Detailed Changes</h2>
            <table class="changes-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>ID</th>
                        <th>Name</th>
                        <th>Type</th>
                        <!-- <th>Changes</th> -->
                        <th>Summary</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        """

    def _generate_insights_html(
        self, key_insights: List[str], diff_result: DiffResult
    ) -> str:
        """Generate HTML for key insights section.

        For `oauth` we produce a compact summary paragraph and field-specific
        bullet lists. For other commands we fall back to rendering the provided
        key_insights lines with basic styling.
        """
        if not key_insights:
            return ""

        cmd = (diff_result.command_name or "").lower()
        if cmd != "oauth":
            insights_items = []
            for insight in key_insights:
                lines = insight.split("\n")
                formatted_lines = []
                for line in lines:
                    escaped = _html.escape(line)
                    if line.startswith("  •"):
                        formatted_lines.append(
                            f'<div class="insight-bullet">{escaped}</div>'
                        )
                    elif line.startswith("    -"):
                        formatted_lines.append(
                            f'<div class="insight-sub-bullet">{escaped}</div>'
                        )
                    elif line.startswith("    "):
                        formatted_lines.append(
                            f'<div class="insight-indent">{escaped}</div>'
                        )
                    else:
                        formatted_lines.append(
                            f'<div class="insight-text">{escaped}</div>'
                        )
                insights_items.append("\n".join(formatted_lines))
            insights_html = "\n".join(insights_items)
            return f"""
        <div class="section">
            <h2>🎯 Key Insights</h2>
            <div class="insights-box">
                {insights_html}
            </div>
        </div>
        """

        # --- OAuth specific rendering ---
        # Parse field -> ids from lines
        field_map = {}
        for line in key_insights:
            m = re.search(r"(?P<field>[A-Za-z0-9_]+).*?:\s*(?P<ids>.+)$", line)
            if not m:
                continue
            field = m.group("field").strip()
            ids_part = m.group("ids").strip()
            ids = [
                re.sub(r"^[\'\"]|[\'\"]$", "", s.strip())
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

        # Build HTML with elaborated field details (old style with colors)
        items_html = [f'<div class="insight-text">{_html.escape(summary)}</div>']

        field_order = ["grantTypes", "redirectionUris", "scopes", "claims"]
        for field in field_order:
            ids = sorted(field_map.get(field, []))
            if not ids:
                continue
            count = len(ids)
            # Format: "✓ fieldName updated in: 'id1', 'id2', ..., 'idn'"
            ids_formatted = ", ".join(f"'{i}'" for i in ids[:15])
            if count > 15:
                ids_formatted += f", ... and {count - 15} more"

        line_html = (
            '<div class="insight-bullet">'
            '<strong style="color:#0284c7">✓ '
            f'{_html.escape(field)}'
            '</strong> updated in: '
            '<span style="color:#0f766e">'
            f'{_html.escape(ids_formatted)}'
            '</span>'
            '</div>'
            )

        items_html.append(line_html)

        insights_html = "\n".join(items_html)
        return f"""
        <div class="section">
            <h2>🎯 Key Insights</h2>
            <div class="insights-box">
                {insights_html}
            </div>
        </div>
        """
