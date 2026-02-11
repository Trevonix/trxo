import json
import pytest
from trxo.commands.imports.privileges import PrivilegesImporter, create_privileges_import_command


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
    monkeypatch.setattr("trxo.commands.imports.privileges.info", lambda *a, **k: None)

    data = {"_id": "p1", "a": 1}

    ok = imp.update_item(data, "t", "http://x")

    assert ok is True
    assert called["url"] == "http://x/openidm/config/p1"
    assert called["method"] == "PUT"
    assert json.loads(called["payload"]) == data


def test_update_item_missing_id(monkeypatch):
    imp = PrivilegesImporter()
    monkeypatch.setattr("trxo.commands.imports.privileges.error", lambda *a, **k: None)
    ok = imp.update_item({}, "t", "http://x")
    assert ok is False


def test_update_item_exception(monkeypatch):
    imp = PrivilegesImporter()

    def boom(*a, **k):
        raise Exception("x")

    monkeypatch.setattr(imp, "make_http_request", boom)
    monkeypatch.setattr("trxo.commands.imports.privileges.error", lambda *a, **k: None)

    ok = imp.update_item({"_id": "p1"}, "t", "http://x")
    assert ok is False


def test_create_privileges_import_command(monkeypatch, tmp_path):
    f = tmp_path / "p.json"
    f.write_text(json.dumps([{"_id": "p1"}]))

    imp = PrivilegesImporter()
    monkeypatch.setattr(
        "trxo.commands.imports.privileges.PrivilegesImporter",
        lambda: imp,
    )

    called = {}

    def fake_import(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(imp, "import_from_file", fake_import)

    cmd = create_privileges_import_command()
    cmd(file=str(f), base_url="http://x")

    assert called["file_path"] == str(f)
    assert called["base_url"] == "http://x"
    assert called["realm"] is None
