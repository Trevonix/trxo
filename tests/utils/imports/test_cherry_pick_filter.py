import pytest

from trxo.utils.imports.cherry_pick_filter import CherryPickFilter


def test_apply_filter_happy_path_id_match(mocker):
    mocker.patch("trxo.utils.imports.cherry_pick_filter.info")
    mocker.patch("trxo.utils.imports.cherry_pick_filter.error")

    items = [{"_id": "1"}, {"_id": "2"}]

    result = CherryPickFilter.apply_filter(items, "1")

    assert result == [{"_id": "1"}]


def test_apply_filter_multiple_ids(mocker):
    mocker.patch("trxo.utils.imports.cherry_pick_filter.info")
    mocker.patch("trxo.utils.imports.cherry_pick_filter.error")

    items = [{"_id": "1"}, {"_id": "2"}, {"_id": "3"}]

    result = CherryPickFilter.apply_filter(items, "1,3")

    assert result == [{"_id": "1"}, {"_id": "3"}]


def test_apply_filter_strips_spaces(mocker):
    mocker.patch("trxo.utils.imports.cherry_pick_filter.info")
    mocker.patch("trxo.utils.imports.cherry_pick_filter.error")

    items = [{"_id": "1"}, {"_id": "2"}]

    result = CherryPickFilter.apply_filter(items, " 1 ,  2 ")

    assert result == [{"_id": "1"}, {"_id": "2"}]


def test_apply_filter_fallback_id_field(mocker):
    mocker.patch("trxo.utils.imports.cherry_pick_filter.info")
    mocker.patch("trxo.utils.imports.cherry_pick_filter.error")

    items = [{"id": "x"}, {"id": "y"}]

    result = CherryPickFilter.apply_filter(items, "y")

    assert result == [{"id": "y"}]


def test_apply_filter_fallback_name_field(mocker):
    mocker.patch("trxo.utils.imports.cherry_pick_filter.info")
    mocker.patch("trxo.utils.imports.cherry_pick_filter.error")

    items = [{"name": "alpha"}, {"name": "beta"}]

    result = CherryPickFilter.apply_filter(items, "beta")

    assert result == [{"name": "beta"}]


def test_apply_filter_nested_type_id(mocker):
    mocker.patch("trxo.utils.imports.cherry_pick_filter.info")
    mocker.patch("trxo.utils.imports.cherry_pick_filter.error")

    items = [
        {"_id": "", "_type": {"_id": "nested-1"}},
        {"_id": "x"},
    ]

    result = CherryPickFilter.apply_filter(items, "nested-1")

    assert result == [{"_id": "", "_type": {"_id": "nested-1"}}]


def test_apply_filter_missing_id_logs_error(mocker):
    error_mock = mocker.patch("trxo.utils.imports.cherry_pick_filter.error")
    mocker.patch("trxo.utils.imports.cherry_pick_filter.info")

    items = [{"_id": "1"}]

    result = CherryPickFilter.apply_filter(items, "999")

    assert result == []
    error_mock.assert_called_once()


def test_apply_filter_partial_missing_ids(mocker):
    error_mock = mocker.patch("trxo.utils.imports.cherry_pick_filter.error")
    mocker.patch("trxo.utils.imports.cherry_pick_filter.info")

    items = [{"_id": "1"}, {"_id": "2"}]

    result = CherryPickFilter.apply_filter(items, "1,999")

    assert result == [{"_id": "1"}]
    error_mock.assert_called_once()


def test_apply_filter_no_valid_ids(mocker):
    error_mock = mocker.patch("trxo.utils.imports.cherry_pick_filter.error")
    mocker.patch("trxo.utils.imports.cherry_pick_filter.info")

    items = [{"_id": "1"}]

    result = CherryPickFilter.apply_filter(items, " , , ")

    assert result == []
    error_mock.assert_called_once()


def test_apply_filter_empty_items(mocker):
    mocker.patch("trxo.utils.imports.cherry_pick_filter.info")
    error_mock = mocker.patch("trxo.utils.imports.cherry_pick_filter.error")

    result = CherryPickFilter.apply_filter([], "1")

    assert result == []
    error_mock.assert_called_once()


def test_apply_filter_duplicate_ids(mocker):
    mocker.patch("trxo.utils.imports.cherry_pick_filter.info")
    mocker.patch("trxo.utils.imports.cherry_pick_filter.error")

    items = [{"_id": "1"}, {"_id": "2"}]

    result = CherryPickFilter.apply_filter(items, "1,1")

    assert result == [{"_id": "1"}, {"_id": "1"}]


def test_validate_cherry_pick_argument_valid():
    assert CherryPickFilter.validate_cherry_pick_argument("id1,id2") is True


def test_validate_cherry_pick_argument_json_file():
    assert CherryPickFilter.validate_cherry_pick_argument("data.json") is False


def test_validate_cherry_pick_argument_option():
    assert CherryPickFilter.validate_cherry_pick_argument("--file") is False


def test_validate_cherry_pick_argument_reserved_realm_alpha():
    assert CherryPickFilter.validate_cherry_pick_argument("alpha") is False


def test_validate_cherry_pick_argument_reserved_realm_bravo():
    assert CherryPickFilter.validate_cherry_pick_argument("bravo") is False


def test_validate_cherry_pick_argument_reserved_realm_charlie():
    assert CherryPickFilter.validate_cherry_pick_argument("charlie") is False
