import json
import pytest
from unittest.mock import MagicMock, patch
from trxo_lib.imports.domains.mappings import MappingsImporter

@pytest.fixture
def importer():
    return MappingsImporter()

def test_get_item_id(importer):
    assert importer.get_item_id({"name": "sync1"}) == "sync1"

def test_wrap_for_diff(importer):
    data = {"mappings": [{"name": "m1"}]}
    res = importer._wrap_for_diff(data)
    assert res == {"result": [{"name": "m1"}]}

def test_generate_patch_operations(importer):
    existing = {"name": "m1", "properties": ["p1"]}
    new = {"name": "m1", "properties": ["p1", "p2"], "extra": "v"}
    ops = importer._generate_patch_operations(existing, new)
    # 1 for properties (list replace), 1 for extra (add)
    assert len(ops) == 2
    assert any(o["operation"] == "replace" and o["field"] == "/properties" for o in ops)

def test_update_item_patch(importer, mocker):
    mocker.patch.object(importer, "_get_current_sync_config", return_value={"mappings": [{"name": "m1", "v": 1}]})
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    mocker.patch.object(importer, "make_http_request")
    
    res = importer.update_item({"name": "m1", "v": 2}, "token", "url")
    assert res is True
    assert importer.make_http_request.call_args[0][1] == "PATCH"

def test_delete_item_success(importer, mocker):
    mocker.patch.object(importer, "_get_current_sync_config", return_value={"mappings": [{"name": "m1"}, {"name": "m2"}]})
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    mocker.patch.object(importer, "make_http_request")
    
    res = importer.delete_item("m1", "token", "url")
    assert res is True
    args = importer.make_http_request.call_args[0]
    payload = json.loads(args[3])
    assert len(payload["mappings"]) == 1
    assert payload["mappings"][0]["name"] == "m2"

def test_load_data_from_file_unwraps(importer, tmp_path):
    f = tmp_path / "sync.json"
    f.write_text(json.dumps({"mappings": [{"name": "m1"}]}))
    res = importer.load_data_from_file(str(f))
    assert isinstance(res, list)
    assert res[0]["name"] == "m1"
