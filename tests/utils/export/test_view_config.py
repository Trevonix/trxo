import pytest
from trxo.utils.export.view_config import (
    get_default_columns,
    get_column_description,
    get_available_columns_help,
    suggest_columns,
    DEFAULT_VIEW_COLUMNS,
    COLUMN_DESCRIPTIONS,
)


def test_get_default_columns_known_command():
    cols = get_default_columns("scripts")
    assert cols == DEFAULT_VIEW_COLUMNS["scripts"]


def test_get_default_columns_unknown_command():
    assert get_default_columns("unknown") is None


def test_get_column_description_known_column():
    desc = get_column_description("scripts", "name")
    assert "Script name" in desc


def test_get_column_description_unknown_column_known_command():
    desc = get_column_description("scripts", "unknown_field")
    assert desc == "Column: unknown_field"


def test_get_column_description_unknown_command():
    desc = get_column_description("unknown", "field")
    assert desc == "Column: field"


def test_get_available_columns_help_known_command():
    help_text = get_available_columns_help("scripts")
    assert "Default columns for scripts:" in help_text
    assert "• _id" in help_text
    assert "• name" in help_text


def test_get_available_columns_help_unknown_command():
    help_text = get_available_columns_help("unknown")
    assert help_text == "Use --view to see available columns"


def test_get_available_columns_help_with_descriptions_and_without():
    help_text = get_available_columns_help("scripts")
    assert "• _id" in help_text
    assert "• name:" in help_text
    assert "Script name" in help_text


def test_suggest_columns_when_view_columns_provided():
    result = suggest_columns("scripts", "a,b,c")
    assert result == "a,b,c"


def test_suggest_columns_when_no_view_columns_and_defaults_exist():
    result = suggest_columns("scripts", None)
    assert result == ",".join(DEFAULT_VIEW_COLUMNS["scripts"])


def test_suggest_columns_when_no_defaults():
    result = suggest_columns("unknown", None)
    assert result is None
