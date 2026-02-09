import pytest
from trxo.utils.export.view_renderer import ViewRenderer


def test_is_single_config_object_with_id_and_rev():
    data = {"_id": "1", "_rev": "2", "x": 1}
    assert ViewRenderer.is_single_config_object(data) is True


def test_is_single_config_object_with_config_fields():
    data = {"security": {}, "core": {}}
    assert ViewRenderer.is_single_config_object(data) is True


def test_is_single_config_object_false_when_nested_arrays():
    data = {"a": {"b": [1, 2, 3]}}
    assert ViewRenderer.is_single_config_object(data) is False


def test_is_single_config_object_false_case():
    data = {"x": 1}
    assert ViewRenderer.is_single_config_object(data) is False


def test_create_table_no_items(mocker):
    mocker.patch("trxo.utils.export.view_renderer.info")
    ViewRenderer.create_table([], "Title", None)


def test_create_table_invalid_items(mocker):
    mocker.patch("trxo.utils.export.view_renderer.info")
    ViewRenderer.create_table(["not-a-dict"], "Title", None)


def test_create_table_valid(mocker):
    mocker.patch("trxo.utils.export.view_renderer.console.print")
    mocker.patch("trxo.utils.export.view_renderer.info")
    items = [{"a": 1, "b": "x"}]
    ViewRenderer.create_table(items, "Title", None)


def test_create_table_with_selected_columns(mocker):
    mocker.patch("trxo.utils.export.view_renderer.console.print")
    mocker.patch("trxo.utils.export.view_renderer.info")
    items = [{"a": 1, "b": 2}]
    ViewRenderer.create_table(items, "Title", ["a"])


def test_create_table_with_invalid_selected_columns(mocker):
    mocker.patch("trxo.utils.export.view_renderer.error")
    mocker.patch("trxo.utils.export.view_renderer.info")

    items = [{"a": 1, "b": 2}]  # MUST have 2 keys
    ViewRenderer.create_table(items, "Title", ["missing"])


def test_display_single_object_basic(mocker):
    mocker.patch("trxo.utils.export.view_renderer.console.print")
    data = {"a": 1, "b": {"x": 2}}
    ViewRenderer.display_single_object(data, "Title", None)


def test_display_single_object_selected_columns(mocker):
    mocker.patch("trxo.utils.export.view_renderer.console.print")
    data = {"a": 1, "b": 2}
    ViewRenderer.display_single_object(data, "Title", ["a"])


def test_display_nested_structure_nested_tables(mocker):
    mocker.patch("trxo.utils.export.view_renderer.ViewRenderer.create_table")
    data = {"x": {"y": [{"a": 1, "b": 2}]}}
    ViewRenderer.display_nested_structure(data, "scripts", None)


def test_display_nested_structure_fallback_single_object(mocker):
    mocker.patch("trxo.utils.export.view_renderer.ViewRenderer.display_single_object")
    data = {"a": 1}
    ViewRenderer.display_nested_structure(data, "scripts", None)


def test_display_table_view_missing_data_field(mocker):
    mocker.patch("trxo.utils.export.view_renderer.error")
    ViewRenderer.display_table_view({}, "scripts")


def test_display_table_view_result_list(mocker):
    mocker.patch("trxo.utils.export.view_renderer.ViewRenderer.create_table")
    data = {"data": {"result": [{"a": 1, "b": 2}]}}
    ViewRenderer.display_table_view(data, "scripts")


def test_display_table_view_empty_result(mocker):
    mocker.patch("trxo.utils.export.view_renderer.info")
    data = {"data": {"result": []}}
    ViewRenderer.display_table_view(data, "scripts")


def test_display_table_view_list_root(mocker):
    mocker.patch("trxo.utils.export.view_renderer.ViewRenderer.create_table")
    data = {"data": [{"a": 1, "b": 2}]}
    ViewRenderer.display_table_view(data, "scripts")


def test_display_table_view_dict_single_config(mocker):
    mocker.patch("trxo.utils.export.view_renderer.ViewRenderer.display_single_object")
    data = {"data": {"_id": "1", "_rev": "2"}}
    ViewRenderer.display_table_view(data, "scripts")


def test_display_table_view_nested_dict(mocker):
    mocker.patch(
        "trxo.utils.export.view_renderer.ViewRenderer.display_nested_structure"
    )
    data = {"data": {"a": {"b": [{"x": 1, "y": 2}]}}}
    ViewRenderer.display_table_view(data, "scripts")


def test_display_table_view_unsupported_type(mocker):
    mocker.patch("trxo.utils.export.view_renderer.error")
    ViewRenderer.display_table_view({"data": 123}, "scripts")
