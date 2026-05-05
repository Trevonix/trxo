import sys
import pytest
from unittest.mock import MagicMock, patch
from trxo.utils.imports.cli_handler import CLIImportHandler
from trxo_lib.exceptions import TrxoAbort, TrxoError
from trxo_lib.state.diff.diff_engine import DiffResult

@pytest.fixture
def handler():
    return CLIImportHandler()

def test_handle_import_calls_diff(handler, mocker):
    spy_diff = mocker.spy(handler, "_handle_diff")
    mock_svc = MagicMock()
    handler.handle_import("test", mock_svc, {"diff": True})
    assert spy_diff.called

def test_handle_import_calls_progress(handler, mocker):
    spy_progress = mocker.spy(handler, "_handle_import_with_progress")
    mock_svc = MagicMock()
    handler.handle_import("test", mock_svc, {"diff": False})
    assert spy_progress.called

def test_handle_diff_success(handler, mocker):
    mocker.patch.object(handler.diff_presenter, "display_diff_summary")
    mocker.patch.object(handler.diff_presenter, "generate_html_report")
    mocker.patch("trxo.utils.imports.cli_handler.warning")
    mocker.patch("trxo.utils.imports.cli_handler.info")
    
    dr = DiffResult(
        command_name="test",
        realm="alpha",
        added_items=[1],
        modified_items=[],
        removed_items=[],
        unchanged_items=[],
        total_items_current=0,
        total_items_new=1,
        raw_diff={},
        key_insights=[]
    )
    dr.current_data = {"x": 1}
    dr.new_data = {"x": 2}
    
    mock_svc = MagicMock(return_value=dr)
    res = handler._handle_diff("test", mock_svc, {})
    
    assert res == dr
    handler.diff_presenter.display_diff_summary.assert_called_once_with(dr)
    handler.diff_presenter.generate_html_report.assert_called_once()

def test_handle_diff_failure_exit(handler, mocker):
    mock_svc = MagicMock(return_value=None)
    mocker.patch("trxo.utils.imports.cli_handler.error")
    
    with pytest.raises(SystemExit) as excinfo:
        handler._handle_diff("test", mock_svc, {})
    assert excinfo.value.code == 1

def test_handle_diff_trxo_error(handler, mocker):
    mock_svc = MagicMock(side_effect=TrxoError("fail", code=42))
    mock_present = mocker.patch("trxo.utils.imports.cli_handler.present_error")
    
    with pytest.raises(SystemExit) as excinfo:
        handler._handle_diff("test", mock_svc, {})
    assert excinfo.value.code == 42
    mock_present.assert_called_once()

def test_handle_import_with_progress_success(handler, mocker):
    mock_progress_handler = mocker.patch("trxo.utils.imports.cli_handler.ImportProgressHandler").return_value
    mock_svc = MagicMock(return_value="done")
    
    res = handler._handle_import_with_progress("test", mock_svc, {})
    
    assert res == "done"
    mock_progress_handler.attach.assert_called_once()
    mock_progress_handler.detach.assert_called()
    mock_progress_handler.print_summary.assert_called_once()

def test_handle_import_with_progress_generic_error(handler, mocker):
    mock_progress_handler = mocker.patch("trxo.utils.imports.cli_handler.ImportProgressHandler").return_value
    mock_svc = MagicMock(side_effect=Exception("boom"))
    mock_present = mocker.patch("trxo.utils.imports.cli_handler.present_generic_error")
    
    with pytest.raises(SystemExit) as excinfo:
        handler._handle_import_with_progress("test", mock_svc, {})
    assert excinfo.value.code == 1
    mock_progress_handler.detach.assert_called()
    mock_present.assert_called_once()
