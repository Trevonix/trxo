import pytest
from trxo.commands.config.settings import (
    get_credential_value,
    display_config,
    process_regions_value,
)


@pytest.mark.unit
def test_get_credential_value_uses_arg_value():
    result = get_credential_value(
        arg_value="value",
        config_key="key",
        existing_config={},
        prompt_text="prompt",
    )
    assert result == "value"


def test_get_credential_value_uses_existing_config():
    result = get_credential_value(
        arg_value=None,
        config_key="key",
        existing_config={"key": "stored"},
        prompt_text="prompt",
    )
    assert result == "stored"


def test_get_credential_value_prompts_when_required(mocker):
    prompt_mock = mocker.patch(
        "trxo.commands.config.settings.Prompt.ask",
        return_value="prompted",
    )

    result = get_credential_value(
        arg_value=None,
        config_key="key",
        existing_config={},
        prompt_text="prompt",
    )

    assert result == "prompted"
    prompt_mock.assert_called_once()


def test_get_credential_value_prompts_when_not_required(mocker):
    prompt_mock = mocker.patch(
        "trxo.commands.config.settings.Prompt.ask",
        return_value="",
    )

    result = get_credential_value(
        arg_value=None,
        config_key="key",
        existing_config={},
        prompt_text="prompt",
        required=False,
    )

    assert result == ""
    prompt_mock.assert_called_once()


def test_display_config_no_config_warns(mocker):
    warning_mock = mocker.patch("trxo.commands.config.settings.warning")

    display_config("proj", None)

    warning_mock.assert_called_once()


def test_display_config_masks_jwk_path_and_jwk_kid(mocker, tmp_path):
    display_panel_mock = mocker.patch("trxo.commands.config.settings.display_panel")

    config = {
        "jwk_path": str(tmp_path / "secret.json"),
        "jwk_keyring": 1,
        "jwk_kid": "abcdef123456789",
        "foo": "bar",
    }

    display_config("proj", config)

    args, _ = display_panel_mock.call_args
    panel_text = args[0]

    assert "secret.json" in panel_text
    assert "abcdef" not in panel_text
    assert "foo: bar" in panel_text


def test_process_regions_value_none():
    assert process_regions_value(None) == []


def test_process_regions_value_list():
    assert process_regions_value(["us", "eu"]) == ["us", "eu"]


def test_process_regions_value_string():
    assert process_regions_value("us, eu, asia") == ["us", "eu", "asia"]
