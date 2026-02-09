import pytest
from trxo.utils.export.pagination_handler import PaginationHandler
from trxo.constants import DEFAULT_PAGE_SIZE


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class DummyRequester:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def make_http_request(self, url, method, headers):
        self.calls.append((url, method, headers))
        return DummyResponse(self.responses.pop(0))


def test_is_paginated_true_with_remaining():
    data = {"result": [], "remainingPagedResults": 1}
    assert PaginationHandler.is_paginated(data) is True


def test_is_paginated_true_with_result_count():
    data = {"result": [], "resultCount": 1}
    assert PaginationHandler.is_paginated(data) is True


def test_is_paginated_false_when_not_dict():
    assert PaginationHandler.is_paginated([]) is False
    assert PaginationHandler.is_paginated("x") is False


def test_is_paginated_false_when_no_result_list():
    data = {"remainingPagedResults": 1}
    assert PaginationHandler.is_paginated(data) is False


def test_build_endpoint_with_existing_params_and_override():
    endpoint = "/am/json/users?_pageSize=10&_foo=bar"
    result = PaginationHandler.build_endpoint_with_params(
        endpoint, {"_pageSize": 25, "_pagedResultsOffset": 50}
    )

    assert "_pageSize=25" in result
    assert "_pagedResultsOffset=50" in result
    assert "_foo=bar" in result


def test_build_endpoint_without_scheme():
    endpoint = "/am/json/users"
    result = PaginationHandler.build_endpoint_with_params(endpoint, {"a": 1})
    assert result == "/am/json/users?a=1"


def test_build_endpoint_drops_none_params():
    endpoint = "/am/json/users?x=1"
    result = PaginationHandler.build_endpoint_with_params(endpoint, {"y": None})
    assert result == "/am/json/users?x=1"


def test_fetch_all_pages_not_paginated_returns_initial():
    initial = {"result": [1, 2], "remainingPagedResults": 0}

    result = PaginationHandler.fetch_all_pages(
        initial, "/users", http_requester=None, headers={}, api_base_url=""
    )

    assert result == initial


def test_fetch_all_pages_single_extra_page():
    initial = {"result": [1], "remainingPagedResults": 1}

    requester = DummyRequester(
        [
            {"result": [2], "remainingPagedResults": 0},
        ]
    )

    result = PaginationHandler.fetch_all_pages(
        initial,
        "/users",
        requester,
        headers={},
        api_base_url="https://api",
    )

    assert result["result"] == [1, 2]
    assert result["remainingPagedResults"] == 0
    assert result["resultCount"] == 2


def test_fetch_all_pages_multiple_pages():
    initial = {"result": [1], "remainingPagedResults": 2}

    requester = DummyRequester(
        [
            {"result": [2], "remainingPagedResults": 1},
            {"result": [3], "remainingPagedResults": 0},
        ]
    )

    result = PaginationHandler.fetch_all_pages(
        initial,
        "/users?_pageSize=1",
        requester,
        headers={},
        api_base_url="https://api",
    )

    assert result["result"] == [1, 2, 3]
    assert result["remainingPagedResults"] == 0
    assert result["resultCount"] == 3


def test_fetch_all_pages_breaks_on_invalid_next_result():
    initial = {"result": [1], "remainingPagedResults": 1}

    requester = DummyRequester(
        [
            {"no_result": True},
        ]
    )

    result = PaginationHandler.fetch_all_pages(
        initial,
        "/users",
        requester,
        headers={},
        api_base_url="https://api",
    )

    assert result["result"] == [1]


def test_fetch_all_pages_breaks_on_empty_next_result():
    initial = {"result": [1], "remainingPagedResults": 1}

    requester = DummyRequester(
        [
            {"result": [], "remainingPagedResults": 0},
        ]
    )

    result = PaginationHandler.fetch_all_pages(
        initial,
        "/users",
        requester,
        headers={},
        api_base_url="https://api",
    )

    assert result["result"] == [1]


def test_fetch_all_pages_uses_default_page_size_on_parse_error():
    initial = {"result": [1], "remainingPagedResults": 1}

    requester = DummyRequester(
        [
            {"result": [2], "remainingPagedResults": 0},
        ]
    )

    result = PaginationHandler.fetch_all_pages(
        initial,
        "/users?_pageSize=notanumber",
        requester,
        headers={},
        api_base_url="https://api",
    )

    assert result["result"] == [1, 2]


def test_fetch_all_pages_handles_non_dict_json_response():
    initial = {"result": [1], "remainingPagedResults": 1}

    class BadResponse:
        def json(self):
            return "bad"

    class BadRequester:
        def make_http_request(self, url, method, headers):
            return BadResponse()

    result = PaginationHandler.fetch_all_pages(
        initial,
        "/users",
        BadRequester(),
        headers={},
        api_base_url="https://api",
    )

    assert result["result"] == [1]
