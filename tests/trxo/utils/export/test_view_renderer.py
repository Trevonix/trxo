import pytest
from unittest.mock import MagicMock
from trxo.utils.export.view_renderer import ViewRenderer

@pytest.fixture
def mock_console(mocker):
    return mocker.patch("trxo.utils.export.view_renderer.console")

@pytest.fixture
def mock_info(mocker):
    return mocker.patch("trxo.utils.export.view_renderer.info")

@pytest.fixture
def mock_error(mocker):
    return mocker.patch("trxo.utils.export.view_renderer.error")

def test_is_single_config_object():
    # True: has _id and _rev
    assert ViewRenderer.is_single_config_object({"_id": "1", "_rev": "a"}) is True
    
    # True: has config fields
    assert ViewRenderer.is_single_config_object({"trees": {}}) is True
    
    # False: has nested arrays (indicates multi-item)
    assert ViewRenderer.is_single_config_object({"_id": "1", "data": {"list": [1, 2]}}) is False
    
    # False: missing identifiers
    assert ViewRenderer.is_single_config_object({"name": "just a dict"}) is False

def test_create_table_success(mock_console, mock_info):
    items = [{"id": "1", "name": "A"}, {"id": "2", "name": "B"}]
    ViewRenderer.create_table(items, "Test Table", selected_columns=["id", "name"])
    
    mock_console.print.assert_called_once()
    table = mock_console.print.call_args[0][0]
    assert table.title == "Test Table"
    assert len(table.columns) == 3 # #, id, and name

def test_create_table_no_data(mock_info):
    ViewRenderer.create_table([], "Title", None)
    mock_info.assert_called_with("No tabular data to display")

def test_create_table_invalid_columns(mock_error, mock_info):
    items = [{"a": 1, "b": 2}]
    ViewRenderer.create_table(items, "Title", selected_columns=["non_existent"])
    mock_error.assert_called()

def test_display_single_object(mock_console):
    data = {"prop1": "val1", "prop2": {"nested": "val2"}}
    ViewRenderer.display_single_object(data, "Single Obj", None)
    mock_console.print.assert_called_once()

def test_display_nested_structure(mock_console, mocker):
    # This should call create_table internally
    spy = mocker.spy(ViewRenderer, "create_table")
    data = {
        "realm1": {
            "sub": [{"id": 1}]
        }
    }
    ViewRenderer.display_nested_structure(data, "nested", None)
    assert spy.call_count == 1

def test_display_table_view_result_list(mocker):
    spy = mocker.spy(ViewRenderer, "create_table")
    result = {"data": {"result": [{"id": 1}]}}
    ViewRenderer.display_table_view(result, "cmd")
    assert spy.call_count == 1

def test_display_table_view_raw_list(mocker):
    spy = mocker.spy(ViewRenderer, "create_table")
    result = {"data": [{"id": 1}]}
    ViewRenderer.display_table_view(result, "cmd")
    assert spy.call_count == 1

def test_display_table_view_single_config(mocker):
    spy = mocker.spy(ViewRenderer, "display_single_object")
    result = {"data": {"_id": "1", "_rev": "a"}}
    ViewRenderer.display_table_view(result, "cmd")
    assert spy.call_count == 1

def test_display_table_view_invalid_format(mock_error):
    ViewRenderer.display_table_view({}, "cmd")
    mock_error.assert_called_with("Invalid format: no 'data' field")

def test_display_table_view_unsupported_type(mock_error):
    ViewRenderer.display_table_view({"data": 123}, "cmd")
    mock_error.assert_called()
