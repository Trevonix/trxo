import json

from trxo.commands.imports.policies import (
    PoliciesImporter,
    create_policies_import_command,
)


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
    mocker.patch("trxo.commands.imports.policies.error")

    result = importer.update_item({}, "t", "http://x")

    assert result is False


def test_update_item_success(mocker):
    importer = PoliciesImporter(realm="alpha")
    importer.make_http_request = mocker.Mock()
    mocker.patch("trxo.commands.imports.policies.info")

    data = {"_id": "p1", "x": 1}
    result = importer.update_item(data, "t", "http://x")

    assert result is True
    importer.make_http_request.assert_called_once()


def test_update_item_failure(mocker):
    importer = PoliciesImporter(realm="alpha")
    importer.make_http_request = mocker.Mock(side_effect=Exception("boom"))
    mocker.patch("trxo.commands.imports.policies.error")

    data = {"_id": "p1"}
    result = importer.update_item(data, "t", "http://x")

    assert result is False


def test_create_policies_import_command(mocker):
    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.policies.PoliciesImporter",
        return_value=importer,
    )

    cmd = create_policies_import_command()
    cmd(file="x.json", realm="beta")

    importer.import_from_file.assert_called_once()
