import json
import httpx
import pytest
from trxo.commands.imports.saml import create_saml_import_command
from trxo_lib.imports.domains.saml import SamlImporter


def test_saml_basic_methods():
    s = SamlImporter(realm="alpha")
    assert s.get_required_fields() == []
    assert s.get_item_type() == "saml"
    assert "realm-config/saml2" in s.get_api_endpoint("x", "http://a")


def test_filter_entities_no_cherry_pick():
    s = SamlImporter()
    entities = [{"_id": "1"}, {"_id": "2"}]
    out = s._filter_entities(entities, None)
    assert out == entities


def test_filter_entities_with_cherry_pick():
    s = SamlImporter()
    entities = [{"_id": "1"}, {"entityId": "e2"}]
    out = s._filter_entities(entities, ["1"])
    assert out == [{"_id": "1"}]


def test_import_single_script_missing_id(mocker):
    s = SamlImporter()
    mocker.patch("trxo_lib.imports.domains.saml.error")
    result = s._import_single_script({"name": "a"}, "t", "http://x")
    assert result is False


def test_import_single_script_success(mocker):
    s = SamlImporter()
    s.make_http_request = mocker.Mock()
    mocker.patch("trxo_lib.imports.domains.saml.info")

    data = {"_id": "s1", "name": "n", "script": ["a", "b"]}
    assert s._import_single_script(data, "t", "http://x") is True


def test_import_single_script_failure(mocker):
    s = SamlImporter()
    s.make_http_request = mocker.Mock(side_effect=Exception("boom"))
    mocker.patch("trxo_lib.imports.domains.saml.error")

    data = {"_id": "s1", "script": "x"}
    assert s._import_single_script(data, "t", "http://x") is False


def test_import_metadata_skip_invalid(mocker):
    s = SamlImporter()
    mocker.patch("trxo_lib.imports.domains.saml.warning")
    assert s._import_metadata([{"x": 1}], [], "t", "http://x", None) is True


def test_import_single_metadata_exists(mocker):
    s = SamlImporter()
    resp = mocker.Mock()
    resp.text = "metadata ok"
    s.make_http_request = mocker.Mock(return_value=resp)
    mocker.patch("trxo_lib.imports.domains.saml.info")

    assert s._import_single_metadata("e1", "<xml/>", "t", "http://x") is None


def test_import_single_metadata_missing_then_post(mocker):
    s = SamlImporter()
    resp = mocker.Mock()
    resp.text = "ERROR No metadata for entity"
    s.make_http_request = mocker.Mock(return_value=resp)
    s._post_metadata = mocker.Mock(return_value=True)
    mocker.patch("trxo_lib.imports.domains.saml.info")

    assert s._import_single_metadata("e1", "<xml/>", "t", "http://x") is True


def test_post_metadata_success(mocker):
    s = SamlImporter()
    s.make_http_request = mocker.Mock()
    mocker.patch("trxo_lib.imports.domains.saml.info")

    assert s._post_metadata("e1", "<xml/>", "t", "http://x") is True


def test_post_metadata_failure(mocker):
    s = SamlImporter()
    s.make_http_request = mocker.Mock(side_effect=Exception("boom"))
    mocker.patch("trxo_lib.imports.domains.saml.error")

    assert s._post_metadata("e1", "<xml/>", "t", "http://x") is False


def test_upsert_entity_missing_id(mocker):
    s = SamlImporter()
    mocker.patch("trxo_lib.imports.domains.saml.error")
    assert s._upsert_entity({}, "remote", "t", "http://x") is False


def test_upsert_remote_entity_success(mocker):
    s = SamlImporter()
    s.make_http_request = mocker.Mock()
    mocker.patch("trxo_lib.imports.domains.saml.info")

    data = {"_id": "r1", "entityId": "e1"}
    assert s._upsert_entity(data, "remote", "t", "http://x") is True


def test_upsert_remote_entity_failure(mocker):
    s = SamlImporter()
    s.make_http_request = mocker.Mock(side_effect=Exception("boom"))
    mocker.patch("trxo_lib.imports.domains.saml.error")

    data = {"_id": "r1", "entityId": "e1"}
    assert s._upsert_entity(data, "remote", "t", "http://x") is False


def test_upsert_hosted_create_on_404(mocker):
    s = SamlImporter()

    resp = mocker.Mock()
    resp.status_code = 404

    client_ctx = mocker.MagicMock()
    client_ctx.__enter__.return_value = client_ctx
    client_ctx.put.return_value = resp

    mocker.patch.object(httpx, "Client", return_value=client_ctx)
    s.make_http_request = mocker.Mock()
    mocker.patch("trxo_lib.imports.domains.saml.info")

    data = {"_id": "h1", "entityId": "e1"}
    assert s._upsert_entity(data, "hosted", "t", "http://x") is True


def test_upsert_hosted_update_success(mocker):
    s = SamlImporter()

    resp = mocker.Mock()
    resp.status_code = 200
    resp.raise_for_status = mocker.Mock()

    client_ctx = mocker.MagicMock()
    client_ctx.__enter__.return_value = client_ctx
    client_ctx.put.return_value = resp

    mocker.patch.object(httpx, "Client", return_value=client_ctx)
    mocker.patch("trxo_lib.imports.domains.saml.info")

    data = {"_id": "h1", "entityId": "e1"}
    assert s._upsert_entity(data, "hosted", "t", "http://x") is True


def test_import_saml_data_empty(mocker):
    s = SamlImporter()
    mocker.patch("trxo_lib.imports.domains.saml.warning")
    assert s.import_saml_data({}, "t", "http://x", None) is True


def test_create_saml_import_command_wires_service(mocker, tmp_path):
    f = tmp_path / "saml.json"
    f.write_text(json.dumps({"data": {}}))

    mock_service = mocker.Mock()
    mocker.patch("trxo.commands.imports.saml.ImportService", return_value=mock_service)

    cmd = create_saml_import_command()
    cmd(file=str(f), diff=False)

    mock_service.import_saml.assert_called_once()
