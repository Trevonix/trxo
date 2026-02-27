import pytest
from unittest.mock import MagicMock

import httpx

from trxo.utils.git.credentials import build_secure_url, validate_credentials


class FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json


class FakeClient:
    def __init__(self, response=None, raise_exc=None):
        self._response = response
        self._raise_exc = raise_exc

    def __enter__(self):
        if self._raise_exc:
            raise self._raise_exc
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url, headers=None, timeout=None):
        if self._raise_exc:
            raise self._raise_exc
        return self._response


def test_build_secure_url_https():
    url = "https://github.com/org/repo.git"
    out = build_secure_url(url, "user", "token123")
    assert out == "https://user:token123@github.com/org/repo.git"


def test_build_secure_url_non_https_unchanged():
    url = "ssh://github.com/org/repo.git"
    out = build_secure_url(url, "user", "token123")
    assert out == url


def test_validate_credentials_unsupported_url():
    with pytest.raises(ValueError):
        validate_credentials("token", "https://gitlab.com/org/repo.git")


def test_validate_credentials_network_error(mocker):
    mocker.patch(
        "trxo.utils.git.credentials.httpx.Client",
        return_value=FakeClient(raise_exc=httpx.RequestError("boom")),
    )

    with pytest.raises(RuntimeError):
        validate_credentials("token", "https://github.com/org/repo.git")


def test_validate_credentials_404(mocker):
    mocker.patch(
        "trxo.utils.git.credentials.httpx.Client",
        return_value=FakeClient(response=FakeResponse(404)),
    )

    with pytest.raises(PermissionError):
        validate_credentials("token", "https://github.com/org/repo.git")


def test_validate_credentials_401(mocker):
    mocker.patch(
        "trxo.utils.git.credentials.httpx.Client",
        return_value=FakeClient(response=FakeResponse(401)),
    )

    with pytest.raises(PermissionError):
        validate_credentials("token", "https://github.com/org/repo.git")


def test_validate_credentials_unexpected_status(mocker):
    mocker.patch(
        "trxo.utils.git.credentials.httpx.Client",
        return_value=FakeClient(response=FakeResponse(500)),
    )

    with pytest.raises(RuntimeError):
        validate_credentials("token", "https://github.com/org/repo.git")


def test_validate_credentials_no_push_permission(mocker):
    mocker.patch(
        "trxo.utils.git.credentials.httpx.Client",
        return_value=FakeClient(
            response=FakeResponse(200, json_data={"permissions": {"push": False}})
        ),
    )

    with pytest.raises(PermissionError):
        validate_credentials("token", "https://github.com/org/repo.git")


def test_validate_credentials_success(mocker):
    fake_repo = {
        "name": "repo",
        "permissions": {"push": True, "pull": True},
    }

    mocker.patch(
        "trxo.utils.git.credentials.httpx.Client",
        return_value=FakeClient(response=FakeResponse(200, json_data=fake_repo)),
    )

    result = validate_credentials("token", "https://github.com/org/repo.git")
    assert result == fake_repo
