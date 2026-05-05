from trxo.utils.export.view_config import (
    get_default_columns,
    get_column_description,
    get_available_columns_help,
    suggest_columns,
)

def test_get_default_columns():
    # Valid command
    cols = get_default_columns("realms")
    assert isinstance(cols, list)
    assert "_id" in cols
    
    # Invalid command
    assert get_default_columns("non_existent") is None

def test_get_column_description():
    # Known command and column
    desc = get_column_description("realms", "name")
    assert desc == "Realm name"
    
    # Known command, unknown column
    desc2 = get_column_description("realms", "unknown")
    assert desc2 == "Column: unknown"
    
    # Unknown command
    desc3 = get_column_description("unknown_cmd", "any")
    assert desc3 == "Column: any"

def test_get_available_columns_help():
    # Command with defaults and descriptions
    help_text = get_available_columns_help("realms")
    assert "Default columns for realms:" in help_text
    assert "name: Realm name" in help_text
    
    # Command with defaults but NO descriptions
    # 'esv_variables' has defaults but no entry in COLUMN_DESCRIPTIONS
    help_text2 = get_available_columns_help("esv_variables")
    assert "Default columns for esv_variables:" in help_text2
    assert "valueBase64" in help_text2
    
    # Command without defaults
    help_text3 = get_available_columns_help("non_existent")
    assert help_text3 == "Use --view to see available columns"

def test_suggest_columns():
    # Columns already provided
    assert suggest_columns("realms", "id,name") == "id,name"
    
    # No columns provided, command has defaults
    defaults = suggest_columns("realms", None)
    assert "_id,name,active,parentPath" in defaults
    
    # No columns provided, command has NO defaults
    assert suggest_columns("non_existent", None) is None
