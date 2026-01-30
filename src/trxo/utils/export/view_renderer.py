"""
View renderer for displaying export data in tables.

Handles table rendering for different data structures.
"""

import json
from typing import Dict, Any, List, Optional
from rich.table import Table
from trxo.utils.console import console, info, error


class ViewRenderer:
    """Renders export data in various view formats"""

    @staticmethod
    def is_single_config_object(data: Dict[str, Any]) -> bool:
        """
        Determine if this is a single configuration object.

        Args:
            data: Data to check

        Returns:
            True if single config object
        """
        has_id_rev = "_id" in data and "_rev" in data
        has_config_fields = any(key in data for key in ["security", "core", "general", "trees"])

        has_nested_arrays = any(
            isinstance(value, dict) and any(isinstance(v, list) for v in value.values())
            for value in data.values()
        )

        return (has_id_rev or has_config_fields) and not has_nested_arrays

    @staticmethod
    def create_table(
        items: List[Dict[str, Any]],
        title: str,
        selected_columns: Optional[List[str]]
    ):
        """
        Create and display a table from list of dictionaries.

        Args:
            items: List of items to display
            title: Table title
            selected_columns: Optional list of columns to show
        """
        if not items or not isinstance(items[0], dict):
            info("No tabular data to display")
            return

        # Get all available columns
        all_columns = list(items[0].keys())

        info(f"Available Fields: {all_columns}\n"
             f"To select specific fields, use --view-columns {all_columns[0]},{all_columns[1]}")
        print()

        # Use selected or all columns
        columns_to_show = selected_columns if selected_columns else all_columns
        valid_columns = [col for col in columns_to_show if col in all_columns]

        if not valid_columns:
            error(f"None of the specified columns exist. Available: {', '.join(all_columns)}")
            return

        # Create table
        table = Table(title=title, show_header=True, header_style="bold magenta")
        table.add_column("#", style="bold yellow", no_wrap=True, width=4)

        for col in valid_columns:
            table.add_column(col, style="cyan", no_wrap=False)

        # Add rows
        for index, item in enumerate(items, start=1):
            row_values = [str(index)]
            for col in valid_columns:
                value = item.get(col, "")
                if isinstance(value, (dict, list)):
                    str_val = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                    row_values.append(str_val)
                else:
                    str_value = "" if value is None else str(value)
                    if len(str_value) > 50:
                        str_value = str_value[:50] + "..."
                    row_values.append(str_value)

            table.add_row(*row_values)

        console.print(table)
        info(f"Displayed {len(items)} items with {len(valid_columns)} columns")

    @staticmethod
    def display_single_object(
        data: Dict[str, Any],
        title: str,
        selected_columns: Optional[List[str]]
    ):
        """
        Display a single configuration object as key-value pairs.

        Args:
            data: Data to display
            title: Table title
            selected_columns: Optional properties to show
        """
        table = Table(title=title, show_header=True, header_style="bold magenta")
        table.add_column("Property", style="cyan", no_wrap=False)
        table.add_column("Value", style="green", no_wrap=False)

        properties_to_show = selected_columns if selected_columns else data.keys()

        for prop in properties_to_show:
            if prop in data:
                value = data[prop]
                if isinstance(value, (dict, list)):
                    display_value = json.dumps(value, indent=2)
                    if len(str(value)) > 200:
                        display_value = display_value[:200] + "..."
                else:
                    display_value = str(value) if value is not None else ""
                table.add_row(prop, display_value)

        console.print(table)

    @staticmethod
    def display_nested_structure(
        data: Dict[str, Any],
        command_name: str,
        selected_columns: Optional[List[str]]
    ):
        """
        Handle nested structures like themes.

        Args:
            data: Nested data structure
            command_name: Command name for title
            selected_columns: Optional columns to show
        """
        displayed_tables = 0

        for key, value in data.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, list) and sub_value and isinstance(sub_value[0], dict):
                        ViewRenderer.create_table(
                            sub_value,
                            f"{command_name.title()} - {key}.{sub_key}",
                            selected_columns
                        )
                        displayed_tables += 1
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                ViewRenderer.create_table(
                    value,
                    f"{command_name.title()} - {key}",
                    selected_columns
                )
                displayed_tables += 1

        if displayed_tables == 0:
            ViewRenderer.display_single_object(
                data,
                f"{command_name.title()} Configuration",
                selected_columns
            )

    @staticmethod
    def display_table_view(
        result: Dict[str, Any],
        command_name: str,
        view_columns: Optional[str] = None
    ):
        """
        Display data in tabular format.

        Args:
            result: Result data with 'data' field
            command_name: Command name
            view_columns: Comma-separated column names
        """
        if "data" not in result:
            error("Invalid format: no 'data' field")
            return

        data = result["data"]

        # Parse column filter
        selected_columns = None
        if view_columns:
            selected_columns = [col.strip() for col in view_columns.split(",")]

        # Handle different data structures
        if isinstance(data, dict) and "result" in data:
            items = data["result"]
            if isinstance(items, list) and items:
                ViewRenderer.create_table(items, f"{command_name.title()} Data", selected_columns)
            else:
                info("No items found in result array")

        elif isinstance(data, list):
            if data:
                ViewRenderer.create_table(data, f"{command_name.title()} Data", selected_columns)
            else:
                info("No items found")

        elif isinstance(data, dict):
            if ViewRenderer.is_single_config_object(data):
                ViewRenderer.display_single_object(
                    data,
                    f"{command_name.title()} Configuration",
                    selected_columns
                )
            else:
                ViewRenderer.display_nested_structure(data, command_name, selected_columns)
        else:
            error(f"Unsupported data format: {type(data)}")
