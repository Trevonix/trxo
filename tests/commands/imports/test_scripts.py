import json
import base64
import pytest
from click.exceptions import Exit
from trxo.commands.imports.scripts import (
    ScriptImporter,
    create_script_import_command,
    is_base64_encoded,
)
from trxo.constants import DEFAULT_REALM, IGNORED_SCRIPT_IDS, IGNORED_SCRIPT_NAMES


def test_is_base64_encoded_true():
    text = "hello"
    encoded = base64.b64encode(text.encode()).decode()
    assert is_base64_encoded(encoded) is True


def test_is_base64_encoded_false():
    assert is_base64_encoded("hello world") is False


def test_update_item_skips_ignored_script_id(mocker):
    importer = ScriptImporter(realm=DEFAULT_REALM)

    script_id = list(IGNORED_SCRIPT_IDS)[0]
    data = {"_id": script_id, "name": "x"}

    mocker.patch("trxo.commands.imports.scripts.info")

    result = importer.update_item(data, "token", "https://base")

    assert result is True


def test_update_item_skips_ignored_script_name(mocker):
    importer = ScriptImporter(realm=DEFAULT_REALM)

    script_name = list(IGNORED_SCRIPT_NAMES)[0]
    data = {"_id": "id1", "name": script_name}

    mocker.patch("trxo.commands.imports.scripts.info")

    result = importer.update_item(data, "token", "https://base")

    assert result is True


def test_update_item_missing_id_returns_false(mocker):
    importer = ScriptImporter(realm=DEFAULT_REALM)

    mocker.patch("trxo.commands.imports.scripts.error")

    result = importer.update_item({"name": "test"}, "token", "https://base")

    assert result is False


def test_update_item_encodes_script_list(mocker):
    importer = ScriptImporter(realm=DEFAULT_REALM)

    mocker.patch.object(importer, "make_http_request")
    mocker.patch.object(importer, "build_auth_headers", return_value={})

    data = {
        "_id": "s1",
        "name": "script",
        "script": ["line1", "line2"],
    }

    result = importer.update_item(data, "token", "https://base")

    assert result is True


def test_update_item_encodes_script_string(mocker):
    importer = ScriptImporter(realm=DEFAULT_REALM)

    mocker.patch.object(importer, "make_http_request")
    mocker.patch.object(importer, "build_auth_headers", return_value={})

    data = {
        "_id": "s1",
        "name": "script",
        "script": "print('hi')",
    }

    result = importer.update_item(data, "token", "https://base")

    assert result is True


def test_update_item_invalid_script_type_returns_false(mocker):
    importer = ScriptImporter(realm=DEFAULT_REALM)

    mocker.patch("trxo.commands.imports.scripts.error")

    data = {
        "_id": "s1",
        "name": "script",
        "script": 123,
    }

    result = importer.update_item(data, "token", "https://base")

    assert result is False


def test_update_item_http_failure_returns_false(mocker):
    importer = ScriptImporter(realm=DEFAULT_REALM)

    mocker.patch.object(importer, "make_http_request", side_effect=Exception("boom"))
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    mocker.patch("trxo.commands.imports.scripts.error")

    data = {
        "_id": "s1",
        "name": "script",
        "script": "hello",
    }

    result = importer.update_item(data, "token", "https://base")

    assert result is False


def test_delete_item_happy_path(mocker):
    importer = ScriptImporter(realm=DEFAULT_REALM)

    mocker.patch.object(importer, "make_http_request")
    mocker.patch.object(importer, "build_auth_headers", return_value={})

    result = importer.delete_item("s1", "token", "https://base")

    assert result is True


def test_delete_item_failure_returns_false(mocker):
    importer = ScriptImporter(realm=DEFAULT_REALM)

    mocker.patch.object(importer, "make_http_request", side_effect=Exception("boom"))
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    mocker.patch("trxo.commands.imports.scripts.error")

    result = importer.delete_item("s1", "token", "https://base")

    assert result is False


def test_create_script_import_command_calls_import_from_file(mocker):
    import_scripts = create_script_import_command()

    mock_importer = mocker.Mock(spec=ScriptImporter)
    mocker.patch(
        "trxo.commands.imports.scripts.ScriptImporter",
        return_value=mock_importer,
    )

    import_scripts(file="data.json")

    mock_importer.import_from_file.assert_called_once()
