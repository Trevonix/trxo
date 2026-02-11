from typer.testing import CliRunner
from trxo.commands.batch.manager import app

runner = CliRunner()


def test_batch_app_has_name_and_help():
    """Test that the batch app is configured with correct name and help."""
    assert app.info.name == "batch"
    assert app.info.help == "Batch operations for multiple configurations"


def test_registered_commands():
    """Test that expected subcommands are registered."""
    command_names = {c.name for c in app.registered_commands}
    assert "export" in command_names
    assert "import" in command_names
    assert "generate-config" in command_names


def test_batch_command_help_execution():
    """Test verifying the help command execution."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Batch operations for multiple configurations" in result.stdout
    assert "export" in result.stdout
    assert "import" in result.stdout
    assert "generate-config" in result.stdout
