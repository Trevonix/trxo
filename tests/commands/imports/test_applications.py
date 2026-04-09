import json
from unittest.mock import MagicMock

import pytest
import typer

from trxo.commands.imports.applications import (
    ApplicationsImporter,
    create_applications_import_command,
)


class ConcreteApplicationsImporter(ApplicationsImporter):
    """Concrete implementation of ApplicationsImporter for testing."""

    def update_item(self, item_data, token, base_url):
        """Mock implementation for testing that calls make_http_request."""
        if not item_data.get("_id"):
            return False

        try:
            # Mimic what a real update_item would do
            headers = self.build_auth_headers(token)
            self.make_http_request(
                self.get_api_endpoint(item_data["_id"], base_url),
                "PUT",
                headers,
                json=item_data,
            )
            return True
        except Exception:
            return False


def test_applications_importer_required_fields():
    importer = ConcreteApplicationsImporter()
    assert importer.get_required_fields() == ["_id"]


def test_applications_importer_item_type():
    importer = ConcreteApplicationsImporter()
    assert importer.get_item_type() == "Applications"


def test_applications_importer_api_endpoint():
    importer = ConcreteApplicationsImporter(realm="alpha")
    url = importer.get_api_endpoint("app1", "http://base")
    assert url == "http://base/openidm/managed/alpha_application/app1"


def test_applications_importer_update_item_missing_id(mocker):
    importer = ConcreteApplicationsImporter()
    mocker.patch("trxo.commands.imports.applications.error")

    result = importer.update_item({}, "t", "b")

    assert result is False


def test_applications_importer_update_item_success(mocker):
    importer = ConcreteApplicationsImporter(realm="alpha")

    mocker.patch.object(
        importer, "build_auth_headers", return_value={"Authorization": "Bearer t"}
    )
    mocker.patch.object(importer, "make_http_request")
    mocker.patch("trxo.commands.imports.applications.info")

    result = importer.update_item({"_id": "app1", "k": "v"}, "t", "http://base")

    assert result is True
    importer.make_http_request.assert_called_once()


def test_applications_importer_update_item_failure(mocker):
    importer = ConcreteApplicationsImporter(realm="alpha")

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

    importer = ConcreteApplicationsImporter()
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

    importer = ConcreteApplicationsImporter()
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
