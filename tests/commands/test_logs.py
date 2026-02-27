import pytest
import typer

from trxo.commands.logs import show_logs, log_info


def test_show_logs_no_log_file(mocker):
    mocker.patch("trxo.commands.logs.setup_logging")
    mocker.patch("trxo.commands.logs.get_logger")

    log_path = mocker.Mock()
    log_path.exists.return_value = False

    mocker.patch("trxo.commands.logs.get_log_file_path", return_value=log_path)
    warning = mocker.patch("trxo.commands.logs.warning")

    show_logs(lines=10, follow=False, level=None)

    warning.assert_called_once()


def test_show_logs_with_lines(mocker, tmp_path):
    mocker.patch("trxo.commands.logs.setup_logging")
    mocker.patch("trxo.commands.logs.get_logger")

    log_file = tmp_path / "trxo.log"
    log_file.write_text("INFO one\nERROR two\nDEBUG three\n", encoding="utf-8")

    mocker.patch("trxo.commands.logs.get_log_file_path", return_value=log_file)
    console = mocker.patch("trxo.commands.logs.console")

    show_logs(lines=2, follow=False, level=None)

    console.print.assert_called_once()


def test_show_logs_with_level_filter(mocker, tmp_path):
    mocker.patch("trxo.commands.logs.setup_logging")
    mocker.patch("trxo.commands.logs.get_logger")

    log_file = tmp_path / "trxo.log"
    log_file.write_text("INFO one\nERROR two\nERROR three\n", encoding="utf-8")

    mocker.patch("trxo.commands.logs.get_log_file_path", return_value=log_file)
    console = mocker.patch("trxo.commands.logs.console")

    show_logs(lines=10, follow=False, level="ERROR")

    console.print.assert_called_once()


def test_show_logs_no_matching_lines(mocker, tmp_path):
    mocker.patch("trxo.commands.logs.setup_logging")
    mocker.patch("trxo.commands.logs.get_logger")

    log_file = tmp_path / "trxo.log"
    log_file.write_text("INFO one\nDEBUG two\n", encoding="utf-8")

    mocker.patch("trxo.commands.logs.get_log_file_path", return_value=log_file)
    info = mocker.patch("trxo.commands.logs.info")

    show_logs(lines=10, follow=False, level="ERROR")

    info.assert_called_once()


def test_show_logs_exception(mocker):
    mocker.patch("trxo.commands.logs.setup_logging")
    logger = mocker.patch("trxo.commands.logs.get_logger")

    mocker.patch(
        "trxo.commands.logs.get_log_file_path",
        side_effect=Exception("boom"),
    )

    error = mocker.patch("trxo.commands.logs.error")

    with pytest.raises(typer.Exit):
        show_logs(lines=10, follow=False, level=None)

    error.assert_called_once()
    logger.return_value.error.assert_called_once()


def test_log_info_success(mocker, tmp_path):
    mocker.patch("trxo.commands.logs.setup_logging")
    logger = mocker.patch("trxo.commands.logs.get_logger")

    config = mocker.Mock()
    config.default_level.value = "INFO"
    config.log_retention_days = 7

    log_dir = tmp_path
    log_file = tmp_path / "trxo.log"
    log_file.write_text("hello", encoding="utf-8")

    mocker.patch("trxo.commands.logs.LogConfig", return_value=config)
    mocker.patch("trxo.commands.logs.get_log_directory", return_value=log_dir)
    mocker.patch("trxo.commands.logs.get_log_file_path", return_value=log_file)

    console = mocker.patch("trxo.commands.logs.console")

    log_info()

    console.print.assert_called_once()
    logger.return_value.info.assert_called_once()


def test_log_info_no_log_file(mocker, tmp_path):
    mocker.patch("trxo.commands.logs.setup_logging")
    logger = mocker.patch("trxo.commands.logs.get_logger")

    config = mocker.Mock()
    config.default_level.value = "INFO"
    config.log_retention_days = 7

    log_dir = tmp_path
    log_file = tmp_path / "trxo.log"

    mocker.patch("trxo.commands.logs.LogConfig", return_value=config)
    mocker.patch("trxo.commands.logs.get_log_directory", return_value=log_dir)
    mocker.patch("trxo.commands.logs.get_log_file_path", return_value=log_file)

    console = mocker.patch("trxo.commands.logs.console")

    log_info()

    console.print.assert_called_once()
    logger.return_value.info.assert_called_once()


def test_log_info_exception(mocker):
    mocker.patch("trxo.commands.logs.setup_logging")
    logger = mocker.patch("trxo.commands.logs.get_logger")

    mocker.patch(
        "trxo.commands.logs.LogConfig",
        side_effect=Exception("boom"),
    )

    error = mocker.patch("trxo.commands.logs.error")

    with pytest.raises(typer.Exit):
        log_info()

    error.assert_called_once()
    logger.return_value.error.assert_called_once()
