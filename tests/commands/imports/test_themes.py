import json
import pytest

from trxo.commands.imports.themes import (
    ThemesImporter,
    create_themes_import_command,
)


def test_get_item_type():
    importer = ThemesImporter()
    assert importer.get_item_type() == "themes (ui/themerealm)"


def test_get_api_endpoint():
    importer = ThemesImporter()
    url = importer.get_api_endpoint("", "http://x")
    assert url == "http://x/openidm/config/ui/themerealm"


def test_fetch_current_success(mocker):
    importer = ThemesImporter()

    resp = mocker.Mock()
    resp.json.return_value = {"realm": {"alpha": [{"foo": "bar"}]}}

    importer.make_http_request = mocker.Mock(return_value=resp)

    result = importer._fetch_current("t", "http://x")
    assert result == {"realm": {"alpha": [{"foo": "bar"}]}}


def test_fetch_current_json_error(mocker):
    importer = ThemesImporter()

    resp = mocker.Mock()
    resp.json.side_effect = Exception("boom")

    importer.make_http_request = mocker.Mock(return_value=resp)

    result = importer._fetch_current("t", "http://x")
    assert result == {}


def test_build_patch_ops_add_realm():
    importer = ThemesImporter()

    current = {"realm": {}}
    incoming = {"realm": {"alpha": [{"a": 1}]}}

    ops = importer._build_patch_ops(current, incoming)

    assert ops == [
        {
            "operation": "add",
            "field": "/realm/alpha",
            "value": [{"a": 1}],
        }
    ]


def test_build_patch_ops_replace_whole_array():
    importer = ThemesImporter()

    current = {"realm": {"alpha": []}}
    incoming = {"realm": {"alpha": [{"a": 1}]}}

    ops = importer._build_patch_ops(current, incoming)

    assert ops == [
        {
            "operation": "replace",
            "field": "/realm/alpha",
            "value": [{"a": 1}],
        }
    ]


def test_build_patch_ops_add_and_replace_fields():
    importer = ThemesImporter()

    current = {"realm": {"alpha": [{"x": 1}]}}
    incoming = {"realm": {"alpha": [{"x": 2, "y": 3}]}}

    ops = importer._build_patch_ops(current, incoming)

    assert {"operation": "replace", "field": "/realm/alpha/0/x", "value": 2} in ops
    assert {"operation": "add", "field": "/realm/alpha/0/y", "value": 3} in ops
    assert len(ops) == 2


def test_update_item_no_changes(mocker):
    importer = ThemesImporter()

    importer._fetch_current = mocker.Mock(return_value={"realm": {"a": [{"x": 1}]}})
    mocker.patch("trxo.commands.imports.themes.info")

    result = importer.update_item({"realm": {"a": [{"x": 1}]}}, "t", "http://x")

    assert result is True


def test_update_item_patch_success(mocker):
    importer = ThemesImporter()

    importer._fetch_current = mocker.Mock(return_value={"realm": {}})
    importer.make_http_request = mocker.Mock()
    mocker.patch("trxo.commands.imports.themes.info")

    incoming = {"realm": {"alpha": [{"a": 1}]}}

    result = importer.update_item(incoming, "t", "http://x")

    assert result is True
    importer.make_http_request.assert_called_once()


def test_update_item_patch_failure(mocker):
    importer = ThemesImporter()

    importer._fetch_current = mocker.Mock(return_value={"realm": {}})
    importer.make_http_request = mocker.Mock(side_effect=Exception("boom"))
    mocker.patch("trxo.commands.imports.themes.error")

    incoming = {"realm": {"alpha": [{"a": 1}]}}

    result = importer.update_item(incoming, "t", "http://x")

    assert result is False


def test_create_themes_import_command_wires_importer(mocker, tmp_path):
    f = tmp_path / "themes.json"
    f.write_text(json.dumps({"realm": {"alpha": [{"a": 1}]}}))

    importer = mocker.Mock()
    mocker.patch("trxo.commands.imports.themes.ThemesImporter", return_value=importer)

    cmd = create_themes_import_command()
    cmd(file=str(f))

    importer.import_from_file.assert_called_once()
