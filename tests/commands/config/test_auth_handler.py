import pytest
import typer
from trxo.commands.config.auth_handler import (
    normalize_base_url,
    setup_service_account_auth,
    setup_onprem_auth,
)


def test_normalize_base_url_service_account_strips_am():
    url = normalize_base_url("https://example.com/am/", "service-account")
    assert url == "https://example.com"


def test_normalize_base_url_service_account_keeps_root():
    url = normalize_base_url("https://example.com", "service-account")
    assert url == "https://example.com"


def test_normalize_base_url_onprem_adds_am():
    url = normalize_base_url("https://example.com", "onprem")
    assert url == "https://example.com/am"


def test_normalize_base_url_onprem_keeps_context():
    url = normalize_base_url("https://example.com/custom", "onprem")
    assert url == "https://example.com/custom"


def test_normalize_base_url_empty():
    assert normalize_base_url("", "service-account") == ""


@pytest.fixture
def base_setup_mocks(mocker):
    mocker.patch(
        "trxo.commands.config.auth_handler.get_credential_value",
        side_effect=lambda v, *_args, **_kwargs: v,
    )
    mocker.patch(
        "trxo.commands.config.auth_handler.process_regions_value",
        return_value=["us"],
    )
    mocker.patch(
        "trxo.commands.config.auth_handler.validate_jwk_file",
        return_value=("jwk-raw", "fp", True),
    )
    mocker.patch(
        "trxo.commands.config.auth_handler.store_jwk_in_keyring",
        return_value=True,
    )
    mocker.patch(
        "trxo.commands.config.auth_handler.validate_authentication",
        return_value=True,
    )
    return mocker


def test_setup_service_account_auth_success(mocker, base_setup_mocks):
    mocker.patch("trxo.commands.config.auth_handler.ServiceAccountAuth")

    config = setup_service_account_auth(
        existing_config={},
        jwk_path="~/.keys/jwk.json",
        client_id="cid",
        sa_id="sid",
        base_url="https://example.com",
        regions="us",
        storage_mode="local",
        git_username=None,
        git_repo=None,
        git_token=None,
        current_project="proj",
    )

    assert config["auth_mode"] == "service-account"
    assert config["client_id"] == "cid"
    assert config["sa_id"] == "sid"
    assert config["token_url"] == "https://example.com/am/oauth2/access_token"
    assert config["jwk_keyring"] is True
    assert config["regions"] == ["us"]


def test_setup_service_account_auth_git_mode(mocker, base_setup_mocks):
    mocker.patch("trxo.commands.config.auth_handler.ServiceAccountAuth")
    mocker.patch("trxo.commands.config.auth_handler.validate_git_setup")

    config = setup_service_account_auth(
        existing_config={},
        jwk_path="~/.keys/jwk.json",
        client_id="cid",
        sa_id="sid",
        base_url="https://example.com",
        regions="us",
        storage_mode="git",
        git_username="gituser",
        git_repo="https://github.com/x/y.git",
        git_token="token",
        current_project="proj",
    )

    assert config["storage_mode"] == "git"
    assert config["git_username"] == "gituser"
    assert config["git_repo"].endswith(".git")


def test_setup_service_account_auth_keyring_unavailable(mocker):
    mocker.patch(
        "trxo.commands.config.auth_handler.get_credential_value",
        side_effect=lambda v, *_args, **_kwargs: v,
    )
    mocker.patch(
        "trxo.commands.config.auth_handler.process_regions_value",
        return_value=["us"],
    )
    mocker.patch(
        "trxo.commands.config.auth_handler.validate_jwk_file",
        return_value=("jwk-raw", "fp", False),
    )
    mocker.patch("trxo.commands.config.auth_handler.ServiceAccountAuth")
    mocker.patch("trxo.commands.config.auth_handler.validate_authentication", return_value=True)

    config = setup_service_account_auth(
        existing_config={},
        jwk_path="~/.keys/jwk.json",
        client_id="cid",
        sa_id="sid",
        base_url="https://example.com",
        regions="us",
        storage_mode="local",
        git_username=None,
        git_repo=None,
        git_token=None,
        current_project="proj",
    )

    assert config["jwk_keyring"] is False


def test_setup_service_account_auth_validation_failure(mocker, base_setup_mocks):
    mocker.patch(
        "trxo.commands.config.auth_handler.validate_authentication",
        return_value=False,
    )
    mocker.patch("trxo.commands.config.auth_handler.ServiceAccountAuth")

    with pytest.raises(typer.Exit):
        setup_service_account_auth(
            existing_config={},
            jwk_path="~/.keys/jwk.json",
            client_id="cid",
            sa_id="sid",
            base_url="https://example.com",
            regions="us",
            storage_mode="local",
            git_username=None,
            git_repo=None,
            git_token=None,
            current_project="proj",
        )


def test_setup_service_account_auth_exception(mocker, base_setup_mocks):
    mocker.patch(
        "trxo.commands.config.auth_handler.ServiceAccountAuth",
        side_effect=RuntimeError("boom"),
    )

    with pytest.raises(typer.Exit):
        setup_service_account_auth(
            existing_config={},
            jwk_path="~/.keys/jwk.json",
            client_id="cid",
            sa_id="sid",
            base_url="https://example.com",
            regions="us",
            storage_mode="local",
            git_username=None,
            git_repo=None,
            git_token=None,
            current_project="proj",
        )


def test_setup_onprem_auth_success(mocker):
    mocker.patch(
        "trxo.commands.config.auth_handler.get_credential_value",
        side_effect=lambda v, *_args, **_kwargs: v,
    )
    mocker.patch(
        "trxo.commands.config.auth_handler.validate_onprem_authentication",
        return_value=True,
    )
    mocker.patch("getpass.getpass", return_value="pwd")

    config = setup_onprem_auth(
        existing_config={},
        onprem_username="user",
        onprem_realm="root",
        base_url="https://example.com/am",
        storage_mode="local",
        git_username=None,
        git_repo=None,
        git_token=None,
        current_project="proj",
    )

    assert config["auth_mode"] == "onprem"
    assert config["onprem_username"] == "user"
    assert config["onprem_realm"] == "root"


def test_setup_onprem_auth_default_realm(mocker):
    mocker.patch(
        "trxo.commands.config.auth_handler.get_credential_value",
        side_effect=lambda v, *_args, **_kwargs: v,
    )
    mocker.patch(
        "trxo.commands.config.auth_handler.validate_onprem_authentication",
        return_value=True,
    )
    mocker.patch("getpass.getpass", return_value="pwd")

    config = setup_onprem_auth(
        existing_config={},
        onprem_username="user",
        onprem_realm=None,
        base_url="https://example.com/am",
        storage_mode="local",
        git_username=None,
        git_repo=None,
        git_token=None,
        current_project="proj",
    )

    assert config["onprem_realm"] == "root"


def test_setup_onprem_auth_git_mode(mocker):
    mocker.patch(
        "trxo.commands.config.auth_handler.get_credential_value",
        side_effect=lambda v, *_args, **_kwargs: v,
    )
    mocker.patch(
        "trxo.commands.config.auth_handler.validate_onprem_authentication",
        return_value=True,
    )
    mocker.patch("trxo.commands.config.auth_handler.validate_git_setup")
    mocker.patch("getpass.getpass", return_value="pwd")

    config = setup_onprem_auth(
        existing_config={},
        onprem_username="user",
        onprem_realm="root",
        base_url="https://example.com/am",
        storage_mode="git",
        git_username="gituser",
        git_repo="https://github.com/x/y.git",
        git_token="token",
        current_project="proj",
    )

    assert config["storage_mode"] == "git"
    assert config["git_username"] == "gituser"


def test_setup_onprem_auth_failure(mocker):
    mocker.patch(
        "trxo.commands.config.auth_handler.get_credential_value",
        side_effect=lambda v, *_args, **_kwargs: v,
    )
    mocker.patch(
        "trxo.commands.config.auth_handler.validate_onprem_authentication",
        return_value=False,
    )
    mocker.patch("getpass.getpass", return_value="pwd")

    with pytest.raises(typer.Exit):
        setup_onprem_auth(
            existing_config={},
            onprem_username="user",
            onprem_realm="root",
            base_url="https://example.com/am",
            storage_mode="local",
            git_username=None,
            git_repo=None,
            git_token=None,
            current_project="proj",
        )
