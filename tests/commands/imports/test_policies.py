import pytest
from trxo.commands.imports.policies import create_policies_import_command
from trxo_lib.imports.domains.policies import PoliciesImporter


def test_policies_required_fields():
    importer = PoliciesImporter()
    assert importer.get_required_fields() == ["_id"]


def test_policies_item_type_default_realm():
    importer = PoliciesImporter()
    assert "policies" in importer.get_item_type()


def test_policies_item_type_custom_realm():
    importer = PoliciesImporter(realm="beta")
    assert importer.get_item_type() == "policies (beta)"


def test_policies_api_endpoint():
    importer = PoliciesImporter(realm="alpha")
    url = importer.get_api_endpoint("p1", "http://x")
    assert "/am/json/realms/root/realms/alpha/policies/p1" in url


def test_update_item_missing_id(mocker):
    importer = PoliciesImporter()
    mocker.patch("trxo_lib.imports.domains.policies.error")

    result = importer.update_item({}, "t", "http://x")

    assert result is False


def test_update_item_success(mocker):
    importer = PoliciesImporter(realm="alpha")
    importer.make_http_request = mocker.Mock()
    mocker.patch("trxo_lib.imports.domains.policies.info")

    data = {"_id": "p1", "x": 1}
    result = importer.update_item(data, "t", "http://x")

    assert result is True
    importer.make_http_request.assert_called_once()


def test_update_item_failure(mocker):
    importer = PoliciesImporter(realm="alpha")
    importer.make_http_request = mocker.Mock(side_effect=Exception("boom"))
    mocker.patch("trxo_lib.imports.domains.policies.error")

    data = {"_id": "p1"}
    result = importer.update_item(data, "t", "http://x")

    assert result is False


def test_create_policies_import_command_wires_service(mocker):
    mock_service = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.policies.ImportService", return_value=mock_service
    )

    cmd = create_policies_import_command()
    cmd(file="x.json", realm="beta")

    mock_service.import_policies.assert_called_once()


def test_policies_get_item_id():
    importer = PoliciesImporter(realm="alpha")
    assert importer.get_item_id({"_id": "my-policy"}) == "my-policy"
    assert importer.get_item_id({}) is None


def test_delete_item_success(mocker):
    importer = PoliciesImporter(realm="alpha")
    importer.make_http_request = mocker.Mock()
    mocker.patch("trxo_lib.imports.domains.policies.info")

    result = importer.delete_item("p1", "tok", "http://x")

    assert result is True
    importer.make_http_request.assert_called_once_with(
        importer.get_api_endpoint("p1", "http://x"), "DELETE", mocker.ANY
    )


def test_delete_item_failure(mocker):
    importer = PoliciesImporter(realm="alpha")
    importer.make_http_request = mocker.Mock(side_effect=Exception("403 Forbidden"))
    mocker.patch("trxo_lib.imports.domains.policies.error")

    result = importer.delete_item("p1", "tok", "http://x")

    assert result is False
