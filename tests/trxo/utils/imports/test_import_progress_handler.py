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


def test_process_record_aggregate_success_line_not_counted(handler):
    handler._process_record(logging.INFO, "✔ 13 Applications")
    assert handler.success_count == 0
    assert handler.failure_count == 0


def test_process_record_aggregate_failure_line_not_counted(handler):
    handler._process_record(logging.ERROR, "✖ 1 Applications")
    assert handler.success_count == 0
    assert handler.failure_count == 0


def test_process_record_http_error_line_not_counted_as_item_failure(handler):
    handler._process_record(logging.ERROR, "HTTP error: 403 - Policy validation failed")
    assert handler.failure_count == 0


def test_regression_mixed_import_log_counts(handler):
    # Mirrors real CLI output where only per-item status lines should count.
    log_lines = [
        (logging.INFO, "Loaded 14 Applications for import"),
        (logging.INFO, "✔ Upserted application: 117e7321-1622-406f-9ab1-4254c73e9cab"),
        (logging.INFO, "✔ Upserted application: 5cc3f680-c0ad-46dd-a9d1-0df50ae754b8"),
        (logging.INFO, "✔ Upserted application: 8396c1be-4d13-4def-a35f-4755f4a92e6d"),
        (logging.INFO, "✔ Upserted application: 4a7cbc23-6b79-4318-aaa8-26fd74bed419"),
        (logging.INFO, "✔ Upserted application: 37a4ceea-70e5-41dc-a834-f829fb20fbe1"),
        (logging.INFO, "✔ Upserted application: 88785a3e-633f-48a3-8b5d-971efe1b79b8"),
        (logging.INFO, "✔ Upserted application: 59b2c2c6-3a71-4f6b-b6fb-734ca07c8a89"),
        (logging.INFO, "✔ Upserted application: c47180e9-ff2c-499d-a370-ca768c1846a4"),
        (logging.INFO, "✔ Upserted application: ee41ae09-3bca-4c27-ac69-bdb714efeea9"),
        (logging.ERROR, "HTTP error: 403 - Policy validation failed"),
        (
            logging.ERROR,
            "Failed to upsert application 'not-3b39d5ad-3b2b-497b-a3a8-95615044c4a0': 403 - Policy validation failed",
        ),
        (logging.INFO, "✔ Upserted application: c0ebf86f-3377-4c4c-9ebc-d3a362bac48a"),
        (logging.INFO, "✔ Upserted application: 73d5c357-4c01-4ea4-b68f-6018475b3472"),
        (logging.INFO, "✔ Upserted application: 36ff8317-d12d-4ced-9521-2cd799ecbf9c"),
        (logging.INFO, "✔ Upserted application: cdc62c09-2269-46c4-937f-7eaf1caca2c0"),
        (logging.INFO, "✔ 13 Applications"),
        (logging.ERROR, "✖ 1 Applications"),
        (
            logging.WARNING,
            "Partial success: 13 succeeded, 1 failed (--continue-on-error).",
        ),
    ]

    for level, line in log_lines:
        handler._process_record(level, line)

    assert handler.success_count == 13
    assert handler.failure_count == 1
