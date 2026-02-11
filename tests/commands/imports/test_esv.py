import json
import pytest
import typer

from trxo.commands.imports.esv import (
    EsvVariablesImporter,
    EsvSecretsImporter,
    create_esv_commands,
    create_esv_callback,
)


def test_esv_variables_update_success(mocker):
    imp = EsvVariablesImporter()
    imp.make_http_request = mocker.Mock()
    mocker.patch("trxo.commands.imports.esv.info")

    data = {
        "_id": "v1",
        "valueBase64": "dGVzdA==",
    }

    assert imp.update_item(data, "t", "http://x") is True
    imp.make_http_request.assert_called_once()


def test_esv_variables_missing_id(mocker):
    imp = EsvVariablesImporter()
    mocker.patch("trxo.commands.imports.esv.error")

    assert imp.update_item({}, "t", "http://x") is False


def test_esv_variables_missing_value(mocker):
    imp = EsvVariablesImporter()
    mocker.patch("trxo.commands.imports.esv.warning")

    data = {"_id": "v1"}
    assert imp.update_item(data, "t", "http://x") is False


def test_esv_variables_invalid_base64(mocker):
    imp = EsvVariablesImporter()
    mocker.patch("trxo.commands.imports.esv.error")

    data = {"_id": "v1", "valueBase64": "!!!"}

    assert imp.update_item(data, "t", "http://x") is False


def test_esv_secrets_create_on_404_success(mocker):
    imp = EsvSecretsImporter()

    get_resp = mocker.Mock()
    get_resp.status_code = 404

    imp.make_http_request = mocker.Mock(side_effect=[get_resp, None])
    mocker.patch("trxo.commands.imports.esv.info")

    data = {
        "_id": "s1",
        "valueBase64": "dGVzdA==",
        "encoding": "generic",
    }

    assert imp.update_item(data, "t", "http://x") is True


def test_esv_secrets_404_missing_value(mocker):
    imp = EsvSecretsImporter()

    get_resp = mocker.Mock()
    get_resp.status_code = 404

    imp.make_http_request = mocker.Mock(return_value=get_resp)
    mocker.patch("trxo.commands.imports.esv.warning")

    data = {"_id": "s1"}

    assert imp.update_item(data, "t", "http://x") is False


def test_esv_secrets_404_invalid_encoding(mocker):
    imp = EsvSecretsImporter()

    get_resp = mocker.Mock()
    get_resp.status_code = 404

    imp.make_http_request = mocker.Mock(return_value=get_resp)
    mocker.patch("trxo.commands.imports.esv.warning")

    data = {
        "_id": "s1",
        "valueBase64": "dGVzdA==",
        "encoding": "invalid",
    }

    assert imp.update_item(data, "t", "http://x") is False


def test_esv_secrets_404_invalid_base64(mocker):
    imp = EsvSecretsImporter()

    get_resp = mocker.Mock()
    get_resp.status_code = 404

    imp.make_http_request = mocker.Mock(return_value=get_resp)
    mocker.patch("trxo.commands.imports.esv.warning")

    data = {
        "_id": "s1",
        "valueBase64": "!!!",
        "encoding": "generic",
    }

    assert imp.update_item(data, "t", "http://x") is False


def test_esv_secrets_update_existing_with_value(mocker):
    imp = EsvSecretsImporter()

    get_resp = mocker.Mock()
    get_resp.status_code = 200

    imp.make_http_request = mocker.Mock(side_effect=[get_resp, None])
    mocker.patch("trxo.commands.imports.esv.info")

    data = {
        "_id": "s1",
        "valueBase64": "dGVzdA==",
    }

    assert imp.update_item(data, "t", "http://x") is True


def test_esv_secrets_update_description_only(mocker):
    imp = EsvSecretsImporter()

    get_resp = mocker.Mock()
    get_resp.status_code = 200

    imp.make_http_request = mocker.Mock(side_effect=[get_resp, None])
    mocker.patch("trxo.commands.imports.esv.info")

    data = {
        "_id": "s1",
        "description": "hello",
    }

    assert imp.update_item(data, "t", "http://x") is True


def test_esv_secrets_update_nothing_to_do(mocker):
    imp = EsvSecretsImporter()

    get_resp = mocker.Mock()
    get_resp.status_code = 200

    imp.make_http_request = mocker.Mock(return_value=get_resp)
    mocker.patch("trxo.commands.imports.esv.warning")

    data = {"_id": "s1"}

    assert imp.update_item(data, "t", "http://x") is False


def test_esv_secrets_unexpected_status(mocker):
    imp = EsvSecretsImporter()

    get_resp = mocker.Mock()
    get_resp.status_code = 500
    get_resp.text = "boom"

    imp.make_http_request = mocker.Mock(return_value=get_resp)
    mocker.patch("trxo.commands.imports.esv.error")

    data = {"_id": "s1"}

    assert imp.update_item(data, "t", "http://x") is False


def test_esv_secrets_exception(mocker):
    imp = EsvSecretsImporter()

    imp.make_http_request = mocker.Mock(side_effect=Exception("boom"))
    mocker.patch("trxo.commands.imports.esv.error")

    data = {"_id": "s1"}

    assert imp.update_item(data, "t", "http://x") is False


def test_create_esv_commands_wires_importers(mocker, tmp_path):
    f = tmp_path / "esv.json"
    f.write_text(json.dumps({"data": []}))

    var_imp = mocker.Mock()
    sec_imp = mocker.Mock()

    mocker.patch(
        "trxo.commands.imports.esv.EsvVariablesImporter",
        return_value=var_imp,
    )
    mocker.patch(
        "trxo.commands.imports.esv.EsvSecretsImporter",
        return_value=sec_imp,
    )

    import_vars, import_secrets = create_esv_commands()

    import_vars(file=str(f))
    import_secrets(file=str(f))

    var_imp.import_from_file.assert_called_once()
    sec_imp.import_from_file.assert_called_once()


def test_create_esv_callback_no_subcommand(mocker):
    ctx = mocker.Mock()
    ctx.invoked_subcommand = None

    mocker.patch("trxo.commands.imports.esv.console")
    mocker.patch("trxo.commands.imports.esv.warning")
    mocker.patch("trxo.commands.imports.esv.info")

    cb = create_esv_callback()

    with pytest.raises(typer.Exit):
        cb(ctx)
