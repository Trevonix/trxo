import pytest

from trxo.commands.imports.authn import (
    AuthnImporter,
    create_authn_import_command,
)


def test_authn_importer_required_fields():
    importer = AuthnImporter()
    assert importer.get_required_fields() == []


def test_authn_importer_item_type():
    importer = AuthnImporter()
    assert importer.get_item_type() == "authentication settings"


def test_authn_importer_api_endpoint(mocker):
    importer = AuthnImporter(realm="alpha")
    mocker.patch.object(importer, "_construct_api_url", return_value="URL")

    url = importer.get_api_endpoint("", "BASE")

    importer._construct_api_url.assert_called_once()
    assert url == "URL"


def test_authn_importer_update_item_success(mocker):
    importer = AuthnImporter(realm="alpha")

    mocker.patch.object(
        importer, "build_auth_headers", return_value={"Authorization": "Bearer t"}
    )
    mocker.patch.object(importer, "make_http_request")
    mocker.patch("trxo.commands.imports.authn.info")

    result = importer.update_item({"a": 1, "_rev": "x"}, "t", "http://base")

    assert result is True
    importer.make_http_request.assert_called_once()


def test_authn_importer_update_item_failure(mocker):
    importer = AuthnImporter(realm="alpha")

    mocker.patch.object(
        importer, "build_auth_headers", return_value={"Authorization": "Bearer t"}
    )
    mocker.patch.object(importer, "make_http_request", side_effect=Exception("boom"))
    mocker.patch("trxo.commands.imports.authn.error")

    result = importer.update_item({"a": 1}, "t", "http://base")

    assert result is False


def test_import_authn_defaults(mocker):
    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.authn.AuthnImporter",
        return_value=importer,
    )

    import_authn = create_authn_import_command()
    import_authn(file="f")

    importer.import_from_file.assert_called_once()
    kwargs = importer.import_from_file.call_args.kwargs

    assert "file_path" in kwargs
    assert "realm" in kwargs
    assert "jwk_path" in kwargs
    assert "sa_id" in kwargs
    assert "base_url" in kwargs
    assert "project_name" in kwargs
    assert "auth_mode" in kwargs
    assert "onprem_username" in kwargs
    assert "onprem_password" in kwargs
    assert "onprem_realm" in kwargs
    assert "force_import" in kwargs
    assert "branch" in kwargs
    assert "diff" in kwargs


def test_import_authn_custom_args(mocker):
    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.authn.AuthnImporter",
        return_value=importer,
    )

    import_authn = create_authn_import_command()
    import_authn(
        realm="alpha",
        diff=True,
        file="f",
        force_import=True,
        branch="b",
        jwk_path="k",
        sa_id="s",
        base_url="u",
        project_name="p",
        auth_mode="onprem",
        onprem_username="ou",
        onprem_password="op",
        onprem_realm="or",
        am_base_url="am",
    )

    importer.import_from_file.assert_called_once()
    kwargs = importer.import_from_file.call_args.kwargs

    assert kwargs["realm"] == "alpha"
    assert kwargs["diff"] is True
    assert kwargs["file_path"] == "f"
    assert kwargs["force_import"] is True
    assert kwargs["branch"] == "b"
    assert kwargs["jwk_path"] == "k"
    assert kwargs["sa_id"] == "s"
    assert kwargs["base_url"] == "u"
    assert kwargs["project_name"] == "p"
    assert kwargs["auth_mode"] == "onprem"
    assert kwargs["onprem_username"] == "ou"
    assert kwargs["onprem_password"] == "op"
    assert kwargs["onprem_realm"] == "or"
    assert kwargs["am_base_url"] == "am"
