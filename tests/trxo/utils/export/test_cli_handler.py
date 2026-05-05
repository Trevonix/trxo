import pytest
from unittest.mock import MagicMock, patch
from trxo.utils.export.cli_handler import CLIExportHandler
from trxo_lib.exceptions import TrxoAbort, TrxoError

@pytest.fixture
def mock_console(mocker):
    return {
        "info": mocker.patch("trxo.utils.export.cli_handler.info"),
        "success": mocker.patch("trxo.utils.export.cli_handler.success"),
        "error": mocker.patch("trxo.utils.export.cli_handler.error"),
        "warning": mocker.patch("trxo.utils.export.cli_handler.warning"),
    }

@pytest.fixture
def cli_handler():
    with patch("trxo.utils.export.cli_handler.ConfigStore"):
        with patch("trxo.utils.export.cli_handler.HashManager"):
            handler = CLIExportHandler()
            return handler

def test_get_storage_mode_local(cli_handler):
    cli_handler.config_store.get_current_project.return_value = "proj"
    cli_handler.config_store.get_project_config.return_value = {"storage_mode": "local"}
    assert cli_handler._get_storage_mode() == "local"

def test_get_storage_mode_git(cli_handler):
    cli_handler.config_store.get_current_project.return_value = "proj"
    cli_handler.config_store.get_project_config.return_value = {"storage_mode": "git"}
    assert cli_handler._get_storage_mode() == "git"

def test_get_storage_mode_fallback(cli_handler):
    cli_handler.config_store.get_current_project.side_effect = OSError("boom")
    assert cli_handler._get_storage_mode() == "local"

def test_handle_export_invalid_view_columns(cli_handler, mock_console):
    service_func = MagicMock()
    with pytest.raises(TrxoAbort):
        cli_handler.handle_export("test", service_func, {"view_columns": "id", "view": False})
    mock_console["warning"].assert_called_once()

def test_handle_export_view_mode(cli_handler, mock_console):
    from types import SimpleNamespace
    service_func = MagicMock(return_value=SimpleNamespace(status_code=200, data={"id": "1"}, metadata={}))
    with patch("trxo.utils.export.cli_handler.ViewRenderer") as mock_renderer:
        cli_handler.handle_export("test", service_func, {"view": True})
        mock_renderer.display_table_view.assert_called_once()
        mock_console["info"].assert_any_call("Displaying test data in view mode")

def test_handle_export_local_save(cli_handler, mock_console):
    from types import SimpleNamespace
    service_func = MagicMock(return_value=SimpleNamespace(status_code=200, data={"id": "1"}, metadata={}))
    cli_handler.config_store.get_project_config.return_value = {"storage_mode": "local"}
    
    with patch("trxo.utils.export.cli_handler.FileSaver") as mock_saver:
        mock_saver.save_to_local.return_value = "/path/to/file"
        cli_handler.handle_export("test", service_func, {})
        
        mock_saver.save_to_local.assert_called_once()
        cli_handler.hash_manager.create_hash.assert_called_once()
        mock_console["success"].assert_called_once()

def test_handle_export_git_save(cli_handler, mock_console):
    from types import SimpleNamespace
    service_func = MagicMock(return_value=SimpleNamespace(status_code=200, data={"id": "1"}, metadata={}))
    cli_handler.config_store.get_current_project.return_value = "proj"
    cli_handler.config_store.get_project_config.return_value = {"storage_mode": "git"}
    
    with patch("trxo.utils.export.cli_handler.GitExportHandler") as mock_git_class:
        mock_git_handler = mock_git_class.return_value
        mock_git_handler.save_to_git.return_value = "/path/to/git/file"
        
        cli_handler.handle_export("test", service_func, {})
        
        mock_git_handler.save_to_git.assert_called_once()
        mock_console["success"].assert_called_once()

def test_handle_export_service_error(cli_handler):
    service_func = MagicMock(side_effect=TrxoError("API Error"))
    with patch("trxo.utils.export.cli_handler.present_error") as mock_present:
        with pytest.raises(TrxoAbort):
            cli_handler.handle_export("test", service_func, {})
        mock_present.assert_called_once()

def test_handle_export_generic_exception(cli_handler):
    service_func = MagicMock(side_effect=RuntimeError("unexpected"))
    with patch("trxo.utils.export.cli_handler.present_generic_error") as mock_present:
        with pytest.raises(TrxoAbort):
            cli_handler.handle_export("test", service_func, {})
        mock_present.assert_called_once()

def test_handle_export_empty_result(cli_handler, mock_console):
    service_func = MagicMock(return_value=None)
    cli_handler.handle_export("test", service_func, {})
    # Should return early without error if result is None (handled upstream)
    mock_console["error"].assert_not_called()

def test_handle_export_failure_status(cli_handler, mock_console):
    from types import SimpleNamespace
    service_func = MagicMock(return_value=SimpleNamespace(status_code=404, data={}, metadata={}))
    
    with pytest.raises(TrxoAbort):
        cli_handler.handle_export("test", service_func, {})
    mock_console["error"].assert_called_once()

def test_handle_export_save_failure(cli_handler, mock_console):
    from types import SimpleNamespace
    service_func = MagicMock(return_value=SimpleNamespace(status_code=200, data={"id": "1"}, metadata={}))
    cli_handler.config_store.get_project_config.return_value = {"storage_mode": "local"}
    
    with patch("trxo.utils.export.cli_handler.FileSaver") as mock_saver:
        mock_saver.save_to_local.return_value = None
        with pytest.raises(TrxoAbort):
            cli_handler.handle_export("test", service_func, {})
        mock_console["error"].assert_called_once()

def test_get_storage_mode_no_project(cli_handler):
    cli_handler.config_store.get_current_project.return_value = None
    assert cli_handler._get_storage_mode() == "local"

def test_handle_export_mock_result(cli_handler):
    service_func = MagicMock(return_value=MagicMock())
    # Should hit the type name check and return early
    assert cli_handler.handle_export("test", service_func, {}) is None

def test_handle_export_save_trxo_abort(cli_handler):
    from types import SimpleNamespace
    service_func = MagicMock(return_value=SimpleNamespace(status_code=200, data={"id": "1"}, metadata={}))
    cli_handler.config_store.get_project_config.return_value = {"storage_mode": "local"}
    
    with patch("trxo.utils.export.cli_handler.FileSaver") as mock_saver:
        mock_saver.save_to_local.side_effect = TrxoAbort(code=5)
        with patch("sys.exit", side_effect=SystemExit) as mock_exit:
            with pytest.raises(SystemExit):
                cli_handler.handle_export("test", service_func, {})
            mock_exit.assert_called_once_with(5)

def test_handle_export_save_trxo_error(cli_handler):
    from types import SimpleNamespace
    service_func = MagicMock(return_value=SimpleNamespace(status_code=200, data={"id": "1"}, metadata={}))
    cli_handler.config_store.get_project_config.return_value = {"storage_mode": "local"}
    
    with patch("trxo.utils.export.cli_handler.FileSaver") as mock_saver:
        mock_saver.save_to_local.side_effect = TrxoError("disk full", code=2)
        with patch("sys.exit", side_effect=SystemExit) as mock_exit:
            with patch("trxo.utils.export.cli_handler.present_error"):
                with pytest.raises(SystemExit):
                    cli_handler.handle_export("test", service_func, {})
                mock_exit.assert_called_once_with(2)

def test_handle_export_save_generic_exception(cli_handler):
    from types import SimpleNamespace
    service_func = MagicMock(return_value=SimpleNamespace(status_code=200, data={"id": "1"}, metadata={}))
    cli_handler.config_store.get_project_config.return_value = {"storage_mode": "local"}
    
    with patch("trxo.utils.export.cli_handler.FileSaver") as mock_saver:
        mock_saver.save_to_local.side_effect = Exception("save failed")
        with patch("sys.exit", side_effect=SystemExit) as mock_exit:
            with patch("trxo.utils.export.cli_handler.present_generic_error"):
                with pytest.raises(SystemExit):
                    cli_handler.handle_export("test", service_func, {})
                mock_exit.assert_called_once_with(1)
