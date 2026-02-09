import json
import pytest
import typer

from trxo.commands.config.validation import (
    validate_authentication,
    validate_jwk_file,
    store_jwk_in_keyring,
    validate_git_setup,
    validate_onprem_authentication,
)


def test_validate_authentication_success(mocker):
    auth = mocker.Mock()
    auth.get_access_token.return_value = {"access_token": "token"}
    assert validate_authentication(auth) is True


def test_validate_authentication_failure(mocker):
    auth = mocker.Mock()
    auth.get_access_token.side_effect = Exception("fail")
    assert validate_authentication(auth) is False


def test_validate_jwk_file_success(tmp_path):
    jwk_file = tmp_path / "key.jwk"
    jwk_data = {"kty": "RSA", "kid": "test"}
    jwk_file.write_text(json.dumps(jwk_data), encoding="utf-8")

    raw, fingerprint, keyring_ok = validate_jwk_file(str(jwk_file))

    assert raw == json.dumps(jwk_data)
    assert fingerprint is not None
    assert keyring_ok is True


def test_validate_jwk_file_missing_file(mocker):
    mocker.patch("trxo.commands.config.validation.os.path.exists", return_value=False)
    mocker.patch("trxo.commands.config.validation.error")

    with pytest.raises(typer.Exit):
        validate_jwk_file("missing.jwk")


def test_validate_jwk_file_read_error(mocker):
    mocker.patch("trxo.commands.config.validation.os.path.exists", return_value=True)
    mocker.patch("builtins.open", side_effect=Exception("read fail"))
    mocker.patch("trxo.commands.config.validation.error")

    with pytest.raises(typer.Exit):
        validate_jwk_file("bad.jwk")


def test_store_jwk_in_keyring_success(mocker):
    keyring = mocker.Mock()
    mocker.patch.dict("sys.modules", {"keyring": keyring})
    keyring.set_password.return_value = None

    assert store_jwk_in_keyring("proj", "secret") is True


def test_store_jwk_in_keyring_failure(mocker):
    keyring = mocker.Mock()
    keyring.set_password.side_effect = Exception("fail")
    mocker.patch.dict("sys.modules", {"keyring": keyring})

    assert store_jwk_in_keyring("proj", "secret") is False


def test_validate_git_setup_success(mocker):
    mocker.patch("trxo.commands.config.validation.validate_and_setup_git_repo")
    store = mocker.Mock()
    mocker.patch("trxo.commands.config.validation.ConfigStore", return_value=store)

    validate_git_setup("user", "repo", "token", "proj")

    store.store_git_credentials.assert_called_once_with("proj", "user", "repo", "token")


def test_validate_git_setup_failure(mocker):
    mocker.patch(
        "trxo.commands.config.validation.validate_and_setup_git_repo",
        side_effect=Exception("git fail"),
    )
    mocker.patch("trxo.commands.config.validation.error")

    with pytest.raises(typer.Exit):
        validate_git_setup("user", "repo", "token", "proj")


def test_validate_onprem_authentication_success(mocker):
    mocker.patch("trxo.commands.config.validation.info")
    mocker.patch("trxo.commands.config.validation.success")

    client = mocker.Mock()
    client.authenticate.return_value = {"tokenId": "abc"}
    mocker.patch("trxo.commands.config.validation.OnPremAuth", return_value=client)

    assert validate_onprem_authentication("url", "realm", "user", "pwd") is True


def test_validate_onprem_authentication_failure_no_token(mocker):
    mocker.patch("trxo.commands.config.validation.info")
    mocker.patch("trxo.commands.config.validation.error")

    client = mocker.Mock()
    client.authenticate.return_value = {}
    mocker.patch("trxo.commands.config.validation.OnPremAuth", return_value=client)

    assert validate_onprem_authentication("url", "realm", "user", "pwd") is False


def test_validate_onprem_authentication_exception(mocker):
    mocker.patch("trxo.commands.config.validation.info")
    mocker.patch("trxo.commands.config.validation.error")

    mocker.patch(
        "trxo.commands.config.validation.OnPremAuth",
        side_effect=Exception("boom"),
    )

    assert validate_onprem_authentication("url", "realm", "user", "pwd") is False
