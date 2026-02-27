import pytest
from trxo.auth.on_premise import OnPremAuth
from unittest.mock import MagicMock


@pytest.fixture
def auth_client():
    return OnPremAuth(base_url="http://localhost:8080", realm="alpha")


def _mock_httpx_client(mocker, mock_response):
    """
    Helper to mock httpx.Client() context manager correctly.
    """
    mock_client = mocker.Mock()
    mock_client.post.return_value = mock_response

    mock_cm = MagicMock()  # 👈 MagicMock supports __enter__/__exit__
    mock_cm.__enter__.return_value = mock_client
    mock_cm.__exit__.return_value = None

    mocker.patch("httpx.Client", return_value=mock_cm)


def test_auth_url_constructed_correctly(mocker, auth_client):
    mock_construct = mocker.patch(
        "trxo.utils.url.construct_api_url",
        return_value="http://localhost:8080/am/json/realms/alpha/authenticate",
    )

    url = auth_client.auth_url

    mock_construct.assert_called_once_with(
        "http://localhost:8080",
        "/am/json/realms/alpha/authenticate",
    )
    assert url == "http://localhost:8080/am/json/realms/alpha/authenticate"


def test_authenticate_success(mocker, auth_client):
    mocker.patch(
        "trxo.utils.url.construct_api_url",
        return_value="http://localhost:8080/auth",
    )

    mock_response = mocker.Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "tokenId": "abc123",
        "successUrl": "/home",
        "realm": "/alpha",
    }

    _mock_httpx_client(mocker, mock_response)

    result = auth_client.authenticate("admin", "password")

    assert result["tokenId"] == "abc123"
    assert result["successUrl"] == "/home"
    assert result["realm"] == "/alpha"


def test_authenticate_token_missing(mocker, auth_client):
    mocker.patch(
        "trxo.utils.url.construct_api_url",
        return_value="http://localhost:8080/auth",
    )

    mock_response = mocker.Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {}

    _mock_httpx_client(mocker, mock_response)

    with pytest.raises(Exception) as exc:
        auth_client.authenticate("admin", "password")

    assert "No tokenId returned" in str(exc.value)


def test_authenticate_http_error(mocker, auth_client):
    mocker.patch(
        "trxo.utils.url.construct_api_url",
        return_value="http://localhost:8080/auth",
    )

    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")

    _mock_httpx_client(mocker, mock_response)

    with pytest.raises(Exception) as exc:
        auth_client.authenticate("admin", "wrong_password")

    assert "OnPrem authentication failed" in str(exc.value)
