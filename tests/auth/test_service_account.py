import json
import pytest
from unittest.mock import MagicMock

from trxo.auth.service_account import ServiceAccountAuth


@pytest.fixture
def jwk_dict():
    return {
        "kty": "RSA",
        "n": "sXchp6b7n0nW0B7x6zZ0y5n7t2H7Z0Zx2m9Z9b9pX0n6p5n8",
        "e": "AQAB",
        "d": "ZsZ4n7X0d1X3kz4n5X9n0dZ3x5Y8",
    }


def test_get_private_key_from_file(tmp_path, mocker, jwk_dict):
    jwk_file = tmp_path / "key.json"
    jwk_file.write_text(json.dumps(jwk_dict))

    key_mock = MagicMock()
    key_mock.export_to_pem.return_value = b"pem"

    mocker.patch("jwcrypto.jwk.JWK", return_value=key_mock)

    auth = ServiceAccountAuth(
        jwk_path=str(jwk_file),
        jwk_content=None,
        client_id="cid",
        sa_id="sid",
        token_url="https://token",
    )

    result = auth.get_private_key()

    assert result == b"pem"


def test_get_private_key_from_content(mocker, jwk_dict):
    key_mock = MagicMock()
    key_mock.export_to_pem.return_value = b"pem"

    mocker.patch("jwcrypto.jwk.JWK", return_value=key_mock)

    auth = ServiceAccountAuth(
        jwk_path="unused",
        jwk_content=json.dumps(jwk_dict),
        client_id="cid",
        sa_id="sid",
        token_url="https://token",
    )

    result = auth.get_private_key()

    assert result == b"pem"


def test_create_jwt_calls_encode(mocker):
    mocker.patch("trxo.auth.service_account.time.time", return_value=1000)
    mocker.patch("trxo.auth.service_account.uuid.uuid4", return_value="uuid")
    mocker.patch(
        "trxo.auth.service_account.ServiceAccountAuth.get_private_key",
        return_value=b"pem",
    )
    jwt_encode = mocker.patch("jwt.encode", return_value="signed-jwt")

    auth = ServiceAccountAuth(
        jwk_path="x",
        client_id="cid",
        sa_id="sid",
        token_url="https://token",
    )

    token = auth.create_jwt()

    jwt_encode.assert_called_once()
    assert token == "signed-jwt"


def test_get_access_token_success(mocker):
    mocker.patch(
        "trxo.auth.service_account.ServiceAccountAuth.create_jwt",
        return_value="signed",
    )

    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"access_token": "abc"}

    client = MagicMock()
    client.post.return_value = response

    httpx_client = MagicMock()
    httpx_client.__enter__.return_value = client
    httpx_client.__exit__.return_value = None

    mocker.patch("httpx.Client", return_value=httpx_client)
    mocker.patch("trxo.auth.service_account.get_logger")

    auth = ServiceAccountAuth(
        jwk_path="x",
        client_id="cid",
        sa_id="sid",
        token_url="https://token",
    )

    result = auth.get_access_token()

    assert result == {"access_token": "abc"}
    client.post.assert_called_once()


def test_get_access_token_http_error(mocker):
    mocker.patch(
        "trxo.auth.service_account.ServiceAccountAuth.create_jwt",
        return_value="signed",
    )

    response = MagicMock()
    response.raise_for_status.side_effect = Exception("boom")

    client = MagicMock()
    client.post.return_value = response

    httpx_client = MagicMock()
    httpx_client.__enter__.return_value = client
    httpx_client.__exit__.return_value = None

    mocker.patch("httpx.Client", return_value=httpx_client)

    logger = MagicMock()
    mocker.patch("trxo.auth.service_account.get_logger", return_value=logger)

    auth = ServiceAccountAuth(
        jwk_path="x",
        client_id="cid",
        sa_id="sid",
        token_url="https://token",
    )

    with pytest.raises(Exception) as exc:
        auth.get_access_token()

    assert "Failed to get access token" in str(exc.value)
    logger.error.assert_called_once()
