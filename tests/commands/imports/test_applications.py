import json

import pytest
import typer

from trxo.commands.imports.applications import (
    ApplicationsImporter,
    create_applications_import_command,
)
from trxo.commands.imports.base_importer import BaseImporter


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

    mocker.patch.object(
        importer, "build_auth_headers", return_value={"Authorization": "Bearer t"}
    )
    mocker.patch.object(importer, "make_http_request")
    mocker.patch("trxo.commands.imports.applications.info")

    result = importer.update_item({"_id": "app1", "k": "v"}, "t", "http://base")

    assert result is True
    importer.make_http_request.assert_called_once()


def test_applications_importer_update_item_failure(mocker):
    importer = ApplicationsImporter(realm="alpha")

    mocker.patch.object(
        importer, "build_auth_headers", return_value={"Authorization": "Bearer t"}
    )
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

    assert kwargs["file_path"] == "f"
    assert kwargs["realm"] == "alpha"
    assert kwargs["force_import"] is True
    assert kwargs["diff"] is True
    assert kwargs["rollback"] is True
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


def test_import_applications_passes_continue_on_error(mocker):
    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.applications.ApplicationsImporter",
        return_value=importer,
    )

    import_applications = create_applications_import_command()
    import_applications(continue_on_error=True)

    kwargs = importer.import_from_file.call_args.kwargs
    assert kwargs.get("continue_on_error") is True


def test_applications_process_items_provider_failure_stops_by_default(mocker):
    importer = ApplicationsImporter(realm="alpha")
    importer.include_am_dependencies = True
    importer._pending_providers = [{"_id": "prov1"}]
    importer._pending_scripts = []
    importer._pending_clients = []
    importer.auth_mode = "service-account"

    mock_oauth_inst = mocker.Mock()
    mock_oauth_inst.update_provider = mocker.Mock(side_effect=RuntimeError("fail"))
    mocker.patch(
        "trxo.commands.imports.applications.OAuthImporter",
        return_value=mock_oauth_inst,
    )
    mocker.patch("trxo.commands.imports.applications.info")
    mocker.patch.object(BaseImporter, "process_items", return_value=None)

    with pytest.raises(typer.Exit):
        importer.process_items(
            [{"_id": "app1"}],
            "token",
            "https://idm",
            continue_on_error=False,
        )

    BaseImporter.process_items.assert_not_called()


def test_applications_process_items_provider_failure_continues_when_enabled(mocker):
    importer = ApplicationsImporter(realm="alpha")
    importer.include_am_dependencies = True
    importer._pending_providers = [{"_id": "prov1"}]
    importer._pending_scripts = []
    importer._pending_clients = []
    importer.auth_mode = "service-account"

    mock_oauth_inst = mocker.Mock()
    mock_oauth_inst.update_provider = mocker.Mock(side_effect=RuntimeError("fail"))
    mocker.patch(
        "trxo.commands.imports.applications.OAuthImporter",
        return_value=mock_oauth_inst,
    )
    mocker.patch("trxo.commands.imports.applications.info")
    base_process = mocker.patch.object(BaseImporter, "process_items", return_value=None)

    importer.process_items(
        [{"_id": "app1"}],
        "token",
        "https://idm",
        continue_on_error=True,
    )

    base_process.assert_called_once()
    call_kw = base_process.call_args.kwargs
    assert call_kw.get("continue_on_error") is True


def test_applications_importer_load_data_with_deps(tmp_path):
    path = tmp_path / "apps.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {},
                "data": {
                    "result": [{"_id": "app-1", "name": "App"}],
                    "clients": [{"_id": "oauth-1"}],
                    "scripts": [{"_id": "scr-1", "name": "Script"}],
                },
            }
        ),
        encoding="utf-8",
    )

    importer = ApplicationsImporter()
    importer.include_am_dependencies = True
    items = importer.load_data_from_file(str(path))

    assert len(items) == 1
    assert items[0]["_id"] == "app-1"
    assert len(importer._pending_clients) == 1
    assert importer._pending_clients[0]["_id"] == "oauth-1"
    assert len(importer._pending_scripts) == 1
    assert importer._pending_scripts[0]["_id"] == "scr-1"


def test_applications_importer_load_data_without_deps_skips_pending(tmp_path):
    path = tmp_path / "apps.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {},
                "data": {
                    "result": [{"_id": "app-1", "name": "App"}],
                    "clients": [{"_id": "oauth-1"}],
                },
            }
        ),
        encoding="utf-8",
    )

    importer = ApplicationsImporter()
    importer.include_am_dependencies = False
    importer.load_data_from_file(str(path))

    assert importer._pending_clients == []
    assert importer._pending_scripts == []


def test_import_applications_sets_include_am_dependencies(mocker):
    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.applications.ApplicationsImporter",
        return_value=importer,
    )

    import_applications = create_applications_import_command()
    import_applications(with_deps=True)

    assert importer.include_am_dependencies is True
    importer.import_from_file.assert_called_once()
