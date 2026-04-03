import json
import pytest
from trxo.commands.imports.privileges import create_privileges_import_command
from trxo_lib.operations.imports.privileges import PrivilegesImporter


def test_privileges_get_required_fields():
    imp = PrivilegesImporter()
    assert imp.get_required_fields() == ["_id"]


def test_privileges_get_item_type():
    imp = PrivilegesImporter()
    assert imp.get_item_type() == "Privileges"


def test_privileges_get_api_endpoint():
    imp = PrivilegesImporter()
    assert imp.get_api_endpoint("x", "http://b") == "http://b/openidm/config/x"


def test_update_item_success(monkeypatch):
    imp = PrivilegesImporter()

    called = {}

    def fake_http(url, method, headers, payload):
        called["url"] = url
        called["method"] = method
        called["headers"] = headers
        called["payload"] = payload

    monkeypatch.setattr(imp, "make_http_request", fake_http)
    monkeypatch.setattr(
        "trxo_lib.operations.imports.privileges.info", lambda *a, **k: None
    )

    data = {"_id": "p1", "a": 1}

    ok = imp.update_item(data, "t", "http://x")

    assert ok is True
    assert called["url"] == "http://x/openidm/config/p1"
    assert called["method"] == "PUT"
    assert json.loads(called["payload"]) == data


def test_update_item_missing_id(monkeypatch):
    imp = PrivilegesImporter()
    monkeypatch.setattr(
        "trxo_lib.operations.imports.privileges.error", lambda *a, **k: None
    )
    ok = imp.update_item({}, "t", "http://x")
    assert ok is False


def test_update_item_exception(monkeypatch):
    imp = PrivilegesImporter()

    def boom(*a, **k):
        raise Exception("x")

    monkeypatch.setattr(imp, "make_http_request", boom)
    monkeypatch.setattr(
        "trxo_lib.operations.imports.privileges.error", lambda *a, **k: None
    )

    ok = imp.update_item({"_id": "p1"}, "t", "http://x")
    assert ok is False


def test_create_privileges_import_command_wires_service(mocker):
    mock_service = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.privileges.ImportService", return_value=mock_service
    )

    cmd = create_privileges_import_command()
    cmd(file="f.json")

    mock_service.import_privileges.assert_called_once()
