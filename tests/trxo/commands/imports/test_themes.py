import json
import pytest
from trxo.commands.imports.themes import create_themes_import_command
from trxo_lib.imports.domains.themes import ThemesImporter


def test_get_item_type():
    importer = ThemesImporter()
    assert importer.get_item_type() == "themes"


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


def test_merge_themes_add_realm():
    importer = ThemesImporter()

    current = {"realm": {}}
    incoming = {"realm": {"alpha": [{"_id": "1", "name": "theme1"}]}}

    merged = importer._merge_themes(current, incoming)

    assert merged == {"realm": {"alpha": [{"_id": "1", "name": "theme1"}]}}


def test_merge_themes_replace_theme():
    importer = ThemesImporter()

    current = {"realm": {"alpha": [{"_id": "1", "name": "old_theme"}]}}
    incoming = {"realm": {"alpha": [{"_id": "1", "name": "new_theme"}]}}

    merged = importer._merge_themes(current, incoming)

    assert merged == {"realm": {"alpha": [{"_id": "1", "name": "new_theme"}]}}


def test_merge_themes_add_new_theme_to_existing_realm():
    importer = ThemesImporter()

    current = {"realm": {"alpha": [{"_id": "1", "name": "theme1"}]}}
    incoming = {"realm": {"alpha": [{"_id": "2", "name": "theme2"}]}}

    merged = importer._merge_themes(current, incoming)

    assert merged == {
        "realm": {
            "alpha": [{"_id": "1", "name": "theme1"}, {"_id": "2", "name": "theme2"}]
        }
    }


def test_apply_cherry_pick_filter():
    importer = ThemesImporter()

    # Mock the cherry_pick_filter validator which is called inside _apply_cherry_pick_filter
    importer.cherry_pick_filter.validate_cherry_pick_argument = lambda x: True

    items = [
        {
            "realm": {
                "alpha": [
                    {"_id": "1", "name": "theme1"},
                    {"_id": "2", "name": "theme2"},
                ],
                "bravo": [{"_id": "3", "name": "theme3"}],
            }
        }
    ]

    filtered = importer._apply_cherry_pick_filter(items, "theme1, 3")

    assert len(filtered) == 1
    assert "alpha" in filtered[0]["realm"]
    assert len(filtered[0]["realm"]["alpha"]) == 1
    assert filtered[0]["realm"]["alpha"][0]["_id"] == "1"

    assert "bravo" in filtered[0]["realm"]
    assert len(filtered[0]["realm"]["bravo"]) == 1
    assert filtered[0]["realm"]["bravo"][0]["_id"] == "3"


def test_update_item_put_success(mocker):
    importer = ThemesImporter()

    importer._fetch_current = mocker.Mock(
        return_value={"_rev": "some-rev", "realm": {}}
    )
    importer.make_http_request = mocker.Mock()
    mocker.patch("trxo_lib.imports.domains.themes.info")

    incoming = {"realm": {"alpha": [{"_id": "1", "name": "theme1"}]}}

    result = importer.update_item(incoming, "t", "http://x")

    assert result is True
    importer.make_http_request.assert_called_once()

    # ensure it was called with PUT and If-Match
    args, kwargs = importer.make_http_request.call_args
    assert args[1] == "PUT"
    assert args[2].get("If-Match") == "some-rev"


def test_update_item_put_failure(mocker):
    importer = ThemesImporter()

    importer._fetch_current = mocker.Mock(return_value={"realm": {}})
    importer.make_http_request = mocker.Mock(side_effect=Exception("boom"))
    mocker.patch("trxo_lib.imports.domains.themes.error")

    incoming = {"realm": {"alpha": [{"_id": "1", "name": "theme1"}]}}

    result = importer.update_item(incoming, "t", "http://x")

    assert result is False


def test_create_themes_import_command_wires_service(mocker, tmp_path):
    f = tmp_path / "themes.json"
    f.write_text(json.dumps({"realm": {"alpha": [{"a": 1}]}}))

    mock_service = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.themes.ImportService", return_value=mock_service
    )

    cmd = create_themes_import_command()
    cmd(file=str(f))

    mock_service.import_themes.assert_called_once()
