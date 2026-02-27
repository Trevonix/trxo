import pytest

from trxo.utils.url import construct_api_url


def test_simple_base_and_endpoint():
    assert (
        construct_api_url("https://host", "/json/realms/root")
        == "https://host/json/realms/root"
    )


def test_base_with_trailing_slash():
    assert (
        construct_api_url("https://host/", "/json/realms/root")
        == "https://host/json/realms/root"
    )


def test_endpoint_without_leading_slash():
    assert (
        construct_api_url("https://host", "json/realms/root")
        == "https://host/json/realms/root"
    )


def test_am_endpoint_without_context_in_base():
    assert (
        construct_api_url("https://host", "/am/json/realms/root")
        == "https://host/am/json/realms/root"
    )


def test_am_endpoint_with_am_context_in_base():
    assert (
        construct_api_url("https://host/am", "/am/json/realms/root")
        == "https://host/am/json/realms/root"
    )


def test_am_endpoint_with_custom_context_in_base():
    assert (
        construct_api_url("https://host/custom", "/am/json/realms/root")
        == "https://host/custom/json/realms/root"
    )


def test_base_with_nested_context():
    assert (
        construct_api_url("https://host/custom/path", "/am/json/realms/root")
        == "https://host/custom/path/json/realms/root"
    )


def test_endpoint_empty():
    assert construct_api_url("https://host", "") == "https://host/"


def test_base_with_path_and_simple_endpoint():
    assert (
        construct_api_url("https://host/am", "/json/realms/root")
        == "https://host/am/json/realms/root"
    )


def test_base_without_context_and_simple_endpoint():
    assert (
        construct_api_url("https://host", "/json/realms/root")
        == "https://host/json/realms/root"
    )


def test_double_slash_protection():
    assert construct_api_url("https://host/", "/json") == "https://host/json"


def test_endpoint_only_am():
    assert construct_api_url("https://host/custom", "/am/") == "https://host/custom/"


def test_endpoint_is_root_slash():
    assert construct_api_url("https://host", "/") == "https://host/"


def test_base_has_query_like_path():
    assert construct_api_url("https://host/am", "/am") == "https://host/am/am"


def test_endpoint_none():
    assert construct_api_url("https://host", None) == "https://host/"
