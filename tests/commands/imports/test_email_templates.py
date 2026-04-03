import pytest
from trxo.commands.imports.email_templates import create_email_templates_import_command
from trxo_lib.operations.imports.email_templates import EmailTemplatesImporter


def test_email_templates_importer_required_fields():
    importer = EmailTemplatesImporter()
    assert importer.get_required_fields() == ["_id"]


def test_email_templates_importer_item_type():
    importer = EmailTemplatesImporter()
    assert importer.get_item_type() == "Email Templates"


def test_email_templates_importer_api_endpoint():
    importer = EmailTemplatesImporter()
    url = importer.get_api_endpoint("emailTemplate/test", "http://x")
    assert url == "http://x/openidm/config/emailTemplate/test"


def test_update_item_success(mocker):
    importer = EmailTemplatesImporter()

    importer.make_http_request = mocker.Mock()
    mocker.patch("trxo_lib.operations.imports.email_templates.info")

    data = {"_id": "emailTemplate/test", "subject": "Hi"}

    result = importer.update_item(data, "t", "http://x")

    assert result is True
    importer.make_http_request.assert_called_once()


def test_update_item_missing_id(mocker):
    importer = EmailTemplatesImporter()
    mocker.patch("trxo_lib.operations.imports.email_templates.error")

    result = importer.update_item({}, "t", "http://x")

    assert result is False


def test_update_item_http_error(mocker):
    importer = EmailTemplatesImporter()

    importer.make_http_request = mocker.Mock(side_effect=Exception("boom"))
    mocker.patch("trxo_lib.operations.imports.email_templates.error")

    data = {"_id": "emailTemplate/test"}

    result = importer.update_item(data, "t", "http://x")

    assert result is False
    importer.make_http_request.assert_called_once()


def test_delete_item_success(mocker):
    importer = EmailTemplatesImporter()
    importer.make_http_request = mocker.Mock()
    mocker.patch("trxo_lib.operations.imports.email_templates.info")

    result = importer.delete_item("emailTemplate/test", "t", "http://x")

    assert result is True
    importer.make_http_request.assert_called_with(
        "http://x/openidm/config/emailTemplate/test", "DELETE", mocker.ANY
    )


def test_delete_item_failure(mocker):
    importer = EmailTemplatesImporter()
    importer.make_http_request = mocker.Mock(side_effect=Exception("boom"))
    mocker.patch("trxo_lib.operations.imports.email_templates.error")

    result = importer.delete_item("emailTemplate/test", "t", "http://x")

    assert result is False


def test_create_email_templates_import_command_wires_service(mocker):
    mock_service = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.email_templates.ImportService", return_value=mock_service
    )

    import_cmd = create_email_templates_import_command()
    import_cmd(
        cherry_pick="id1,id2",
        file="x.json",
        force_import=True,
        diff=False,
        branch="main",
        sync=True,
    )

    mock_service.import_email_templates.assert_called_once()
    kwargs = mock_service.import_email_templates.call_args.kwargs
    assert kwargs["file"] == "x.json"
    assert kwargs["force_import"] is True
    assert kwargs["cherry_pick"] == "id1,id2"
    assert kwargs["sync"] is True
