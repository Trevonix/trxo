import pytest
from click.exceptions import Exit

from trxo.commands.imports.services import (
    ServicesImporter,
    create_services_import_command,
)


def test_services_importer_get_api_endpoint_global():
    importer = ServicesImporter(scope="global", realm="alpha")
    url = importer.get_api_endpoint("svc1", "http://x")
    assert url.endswith("/am/json/global-config/services/svc1")


def test_services_importer_get_api_endpoint_realm():
    importer = ServicesImporter(scope="realm", realm="alpha")
    url = importer.get_api_endpoint("svc1", "http://x")
    assert url.endswith("/am/json/realms/root/realms/alpha/realm-config/services/svc1")


def test_prepare_service_payload_removes_dynamic_fields():
    importer = ServicesImporter()

    data = {
        "_id": "svc1",
        "_rev": "r1",
        "_type": {"_id": "svc1"},
        "_lastModified": "x",
        "_lastModifiedBy": "y",
        "enabled": True,
        "config": {"a": 1},
    }

    payload = importer._prepare_service_payload(data)
    assert '"enabled": true' in payload
    assert '"config"' in payload
    assert "_id" not in payload
    assert "_rev" not in payload
    assert "_type" not in payload


def test_update_item_missing_id(mocker):
    importer = ServicesImporter()
    mocker.patch("trxo.commands.imports.services.error")

    result = importer.update_item({}, "t", "http://x")

    assert result is False


def test_update_item_global_success(mocker):
    importer = ServicesImporter(scope="global")

    importer.make_http_request = mocker.Mock()
    mocker.patch("trxo.commands.imports.services.info")

    data = {"_type": {"_id": "svc1"}, "enabled": True}

    assert importer.update_item(data, "t", "http://x") is True
    importer.make_http_request.assert_called_once()


def test_update_item_realm_success(mocker):
    importer = ServicesImporter(scope="realm", realm="alpha")

    importer.make_http_request = mocker.Mock()
    mocker.patch("trxo.commands.imports.services.info")

    data = {"_type": {"_id": "svc1"}, "enabled": True}

    assert importer.update_item(data, "t", "http://x") is True
    importer.make_http_request.assert_called_once()


def test_update_item_http_error(mocker):
    importer = ServicesImporter(scope="realm", realm="alpha")

    importer.make_http_request = mocker.Mock(side_effect=Exception("boom"))
    mocker.patch("trxo.commands.imports.services.error")

    data = {"_type": {"_id": "svc1"}, "enabled": True}

    assert importer.update_item(data, "t", "http://x") is False


def test_create_services_import_command_invalid_scope(mocker):
    mocker.patch("trxo.commands.imports.services.error")

    cmd = create_services_import_command()

    with pytest.raises(Exit):
        cmd(scope="invalid")
