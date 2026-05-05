import logging
import pytest
from unittest.mock import MagicMock, patch
from rich.console import Console
from trxo.utils.imports.import_progress_handler import ImportProgressHandler

@pytest.fixture
def mock_console():
    return MagicMock(spec=Console)

@pytest.fixture
def handler(mock_console, mocker):
    # Mock Live and Progress to prevent real UI startup
    mocker.patch("trxo.utils.imports.import_progress_handler.Live")
    mocker.patch("trxo.utils.imports.import_progress_handler.Progress")
    return ImportProgressHandler("test_cmd", console=mock_console)

def test_handler_init(handler):
    assert handler.command_name == "test_cmd"
    assert handler.success_count == 0
    assert handler.failure_count == 0

def test_handler_attach_detach(handler, mocker):
    mock_logger = MagicMock()
    mock_logger.level = logging.INFO
    mocker.patch("logging.getLogger", return_value=mock_logger)
    
    # Mock existing handlers
    h1 = logging.StreamHandler()
    mock_logger.handlers = [h1]
    
    handler.attach()
    assert handler in mock_logger.addHandler.call_args_list[0][0]
    assert h1 in handler._silenced_handlers
    handler._live.start.assert_called_once()
    
    handler.detach()
    assert h1 in mock_logger.addHandler.call_args_list[1][0]
    handler._live.stop.assert_called_once()

def test_process_record_count_hint(handler):
    handler._process_record(logging.INFO, "Processing 12 scripts...")
    assert handler.total_hint == 12
    handler._progress.update.assert_called_with(handler._task_id, total=12)

def test_process_record_suppression(handler):
    handler._process_record(logging.INFO, "Cloning repository...")
    # Should not print anything
    assert handler.console.print.call_count == 0

def test_process_record_success(handler):
    handler._process_record(logging.INFO, "Successfully imported script1")
    assert handler.success_count == 1
    assert handler.console.print.call_count == 1
    handler._progress.update.assert_called_with(handler._task_id, advance=1)

def test_process_record_failure(handler):
    handler._process_record(logging.ERROR, "Failed to import script2")
    assert handler.failure_count == 1
    assert handler.console.print.call_count == 1
    handler._progress.update.assert_called_with(handler._task_id, advance=1)

def test_process_record_warning(handler):
    handler._process_record(logging.WARNING, "skipping script3")
    assert handler.warning_count == 1
    assert handler.console.print.call_count == 1

def test_process_record_stage(handler):
    handler._process_record(logging.INFO, "Analyzing dependencies")
    assert handler.console.print.call_count == 1
    # Verify it used the stage format (dim)
    args = handler.console.print.call_args[0][0]
    assert "dim" in args.style

def test_print_summary_all_success(handler):
    handler.success_count = 5
    handler.print_summary()
    assert handler.console.print.call_count >= 2
    panel = handler.console.print.call_args_list[1][0][0]
    assert "Import Complete" in panel.title

def test_print_summary_all_failure(handler):
    handler.failure_count = 5
    handler.print_summary()
    panel = handler.console.print.call_args_list[1][0][0]
    assert "Import Failed" in panel.title

def test_print_summary_partial(handler):
    handler.success_count = 2
    handler.failure_count = 3
    handler.print_summary()
    panel = handler.console.print.call_args_list[1][0][0]
    assert "Import Partial" in panel.title

def test_print_summary_empty(handler):
    handler.print_summary()
    assert handler.console.print.call_count == 0
