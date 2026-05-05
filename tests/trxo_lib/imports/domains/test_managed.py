import json
import pytest
from unittest.mock import MagicMock, patch
from trxo_lib.imports.domains.managed import ManagedObjectsImporter

@pytest.fixture
def importer():
    return ManagedObjectsImporter()

def test_get_item_id(importer):
    assert importer.get_item_id({"name": "user"}) == "user"

def test_generate_patch_operations(importer):
    existing = {"name": "user", "schema": {"type": "object"}}
    new = {"name": "user", "schema": {"type": "string"}, "extra": "v"}
    ops = importer._generate_patch_operations(existing, new)
    assert len(ops) == 2
    # One for schema/type replace, one for extra add
    assert any(o["operation"] == "replace" and o["field"] == "/schema/type" for o in ops)
    assert any(o["operation"] == "add" and o["field"] == "/extra" for o in ops)

def test_delete_item_success(importer, mocker):
    mocker.patch.object(importer, "_get_current_managed_config", return_value={"objects": [{"name": "o1"}, {"name": "o2"}]})
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    mocker.patch.object(importer, "make_http_request")
    
    res = importer.delete_item("o1", "token", "url")
    assert res is True
    # Verify PUT payload has only o2
    args = importer.make_http_request.call_args[0]
    payload = json.loads(args[3])
    assert len(payload["objects"]) == 1
    assert payload["objects"][0]["name"] == "o2"

def test_update_item_patch_existing(importer, mocker):
    mocker.patch.object(importer, "_get_current_managed_config", return_value={"objects": [{"name": "o1", "v": 1}]})
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    mocker.patch.object(importer, "make_http_request")
    mocker.patch.object(importer, "_update_relationship_properties")
    mocker.patch.object(importer, "_delete_orphaned_properties")
    
    obj = {"name": "o1", "v": 2}
    res = importer.update_item(obj, "token", "url")
    assert res is True
    assert importer.make_http_request.call_args[0][1] == "PATCH"

def test_update_relationship_properties_reverse(importer, mocker):
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    mocker.patch.object(importer, "make_http_request", return_value=MagicMock(status_code=200))
    mocker.patch("time.sleep") # avoid 15s wait
    
    data = {
        "schema": {
            "properties": {
                "p1": {
                    "type": "relationship",
                    "reverseRelationship": True,
                    "reversePropertyName": "rev1",
                    "resourceCollection": [{"path": "managed/user"}]
                }
            }
        }
    }
    importer._update_relationship_properties("o1", data, "token", "url")
    # Should call GET for existing prop, then PUT
    assert importer.make_http_request.call_count >= 1

def test_load_data_from_file_formats(importer, tmp_path):
    # Test wrapped format
    f1 = tmp_path / "f1.json"
    f1.write_text(json.dumps({"data": {"objects": [{"name": "o1"}]}}))
    res = importer.load_data_from_file(str(f1))
    assert len(res) == 1
    assert res[0]["name"] == "o1"
    
    # Test raw list format
    f2 = tmp_path / "f2.json"
    f2.write_text(json.dumps([{"name": "o2"}]))
    res = importer.load_data_from_file(str(f2))
    assert len(res) == 1
    assert res[0]["name"] == "o2"
