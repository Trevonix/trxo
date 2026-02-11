import pytest
import typer

from trxo.commands.imports.applications import (
    ApplicationsImporter,
    create_applications_import_command,
)


def test_applications_importer_required_fields():
    importer = ApplicationsImporter()
    assert importer.get_required_fields() == ["_id"]


def test_applications_importer_item_type():
    importer = ApplicationsImporter()
    assert importer.get_item_type() == "Applications"


def test_applications_importer_api_endpoint():
    importer = ApplicationsImporter(realm="alpha")
    url = importer.get_api_endpoint("app1", "http://base")
    assert url == "http://base/openidm/managed/alpha_application/app1"


def test_applications_importer_update_item_missing_id(mocker):
    importer = ApplicationsImporter()
    mocker.patch("trxo.commands.imports.applications.error")

    result = importer.update_item({}, "t", "b")

    assert result is False


def test_applications_importer_update_item_success(mocker):
    importer = ApplicationsImporter(realm="alpha")

    mocker.patch.object(importer, "build_auth_headers", return_value={"Authorization": "Bearer t"})
    mocker.patch.object(importer, "make_http_request")
    mocker.patch("trxo.commands.imports.applications.info")

    result = importer.update_item({"_id": "app1", "k": "v"}, "t", "http://base")

    assert result is True
    importer.make_http_request.assert_called_once()


def test_applications_importer_update_item_failure(mocker):
    importer = ApplicationsImporter(realm="alpha")

    mocker.patch.object(importer, "build_auth_headers", return_value={"Authorization": "Bearer t"})
    mocker.patch.object(importer, "make_http_request", side_effect=Exception("boom"))
    mocker.patch("trxo.commands.imports.applications.error")

    result = importer.update_item({"_id": "app1"}, "t", "http://base")

    assert result is False


def test_import_applications_defaults(mocker):
    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.applications.ApplicationsImporter",
        return_value=importer,
    )

    import_applications = create_applications_import_command()
    import_applications()

    importer.import_from_file.assert_called_once()
    kwargs = importer.import_from_file.call_args.kwargs

    assert "file_path" in kwargs
    assert "realm" in kwargs
    assert "jwk_path" in kwargs
    assert "client_id" in kwargs
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
    assert "rollback" in kwargs


def test_import_applications_custom_args(mocker):
    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.applications.ApplicationsImporter",
        return_value=importer,
    )

    import_applications = create_applications_import_command()
    import_applications(
        file="f",
        realm="alpha",
        force_import=True,
        diff=True,
        rollback=True,
        branch="b",
        jwk_path="k",
        client_id="c",
        sa_id="s",
        base_url="u",
        project_name="p",
        auth_mode="onprem",
        onprem_username="ou",
        onprem_password="op",
        onprem_realm="or",
    )

    importer.import_from_file.assert_called_once()
    kwargs = importer.import_from_file.call_args.kwargs

    assert kwargs["file_path"] == "f"
    assert kwargs["realm"] == "alpha"
    assert kwargs["force_import"] is True
    assert kwargs["diff"] is True
    assert kwargs["rollback"] is True
    assert kwargs["branch"] == "b"
    assert kwargs["jwk_path"] == "k"
    assert kwargs["client_id"] == "c"
    assert kwargs["sa_id"] == "s"
    assert kwargs["base_url"] == "u"
    assert kwargs["project_name"] == "p"
    assert kwargs["auth_mode"] == "onprem"
    assert kwargs["onprem_username"] == "ou"
    assert kwargs["onprem_password"] == "op"
    assert kwargs["onprem_realm"] == "or"
