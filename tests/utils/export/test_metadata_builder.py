import pytest
from trxo.utils.export.metadata_builder import MetadataBuilder


def test_detect_realm_from_am_endpoint():
    api = "/am/json/realms/root/realms/alpha/users"
    realm = MetadataBuilder.detect_realm(api, "users")
    assert realm == "alpha"


def test_detect_realm_from_fields_param():
    api = "/openidm/config?_fields=realm/beta&something=x"
    realm = MetadataBuilder.detect_realm(api, "themes")
    assert realm == "beta"


def test_detect_realm_from_command_name_fallback():
    api = "/some/endpoint/without/realm"
    realm = MetadataBuilder.detect_realm(api, "services_realm_gamma")
    assert realm == "gamma"


def test_detect_realm_no_match_returns_none():
    api = "/am/json/realms/root/users"
    realm = MetadataBuilder.detect_realm(api, "users")
    assert realm is None


def test_detect_realm_handles_exception():
    realm = MetadataBuilder.detect_realm(None, None)
    assert realm is None


def test_count_items_from_result_list():
    data = {"result": [1, 2, 3]}
    assert MetadataBuilder.count_items(data) == 3


def test_count_items_from_list():
    data = [1, 2]
    assert MetadataBuilder.count_items(data) == 2


def test_count_items_from_dict_without_result():
    data = {"x": 1}
    assert MetadataBuilder.count_items(data) == 1


def test_count_items_from_other_type():
    assert MetadataBuilder.count_items("hello") == 0
    assert MetadataBuilder.count_items(123) == 0
    assert MetadataBuilder.count_items(None) == 0


def test_build_metadata_basic():
    data = {"result": [1, 2]}
    meta = MetadataBuilder.build_metadata(
        command_name="scripts",
        api_endpoint="/am/json/realms/root/realms/alpha/scripts",
        data=data,
        version="v1",
    )

    assert meta["export_type"] == "scripts"
    assert meta["realm"] == "alpha"
    assert meta["version"] == "v1"
    assert meta["total_items"] == 2
    assert "timestamp" in meta


def test_build_metadata_services_realm_normalization():
    data = {"result": [1]}
    meta = MetadataBuilder.build_metadata(
        command_name="services_realm_alpha",
        api_endpoint="/am/json/realms/root/realms/alpha/services",
        data=data,
    )

    assert meta["export_type"] == "servicesalpha"
    assert meta["realm"] == "alpha"
    assert meta["total_items"] == 1


def test_build_metadata_services_global_normalization():
    data = {"x": 1}
    meta = MetadataBuilder.build_metadata(
        command_name="services_global",
        api_endpoint="/am/json/realms/root/services",
        data=data,
    )

    assert meta["export_type"] == "services"
    assert meta["total_items"] == 1


def test_build_metadata_no_realm_detected():
    data = []
    meta = MetadataBuilder.build_metadata(
        command_name="users",
        api_endpoint="/am/json/users",
        data=data,
    )

    assert meta["realm"] is None
    assert meta["total_items"] == 0


def test_build_metadata_version_none():
    data = {"result": []}
    meta = MetadataBuilder.build_metadata(
        command_name="scripts",
        api_endpoint="/am/json/realms/root/realms/alpha/scripts",
        data=data,
    )

    assert meta["version"] is None
