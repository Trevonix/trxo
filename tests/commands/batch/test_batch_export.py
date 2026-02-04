import pytest
from types import SimpleNamespace
from pathlib import Path
import typer


from trxo.commands.batch.batch_export import create_batch_export_command


class DummyParam:
    """Mock parameter for testing."""

    def __init__(self, name):
        """Initialize with a name."""
        self.name = name


class DummyCommand:
    """Mock command for testing."""

    def __init__(self, name, params=None, should_fail=False):
        """
        Initialize the dummy command.

        Args:
            name: Command name
            params: List of parameter names
            should_fail: Whether the command should simulate a failure
        """
        self.name = name
        self.params = [DummyParam(p) for p in (params or [])]
        self.called_with = None
        self.should_fail = should_fail

    def callback(self, **kwargs):
        """Store arguments and optionally raise error."""
        self.called_with = kwargs
        if self.should_fail:
            raise RuntimeError(f"boom: {self.name}")


class DummyTyperApp:
    """Mock Typer app to hold commands."""

    def __init__(self, commands):
        self.commands = commands


@pytest.fixture
def mock_console(monkeypatch):
    """Mock console logging functions."""
    calls = {"info": [], "success": [], "error": [], "warning": []}

    monkeypatch.setattr(
        "trxo.commands.batch.batch_export.info",
        lambda msg: calls["info"].append(msg),
    )
    monkeypatch.setattr(
        "trxo.commands.batch.batch_export.success",
        lambda msg: calls["success"].append(msg),
    )
    monkeypatch.setattr(
        "trxo.commands.batch.batch_export.error",
        lambda msg: calls["error"].append(msg),
    )
    monkeypatch.setattr(
        "trxo.commands.batch.batch_export.warning",
        lambda msg: calls["warning"].append(msg),
    )

    return calls


@pytest.fixture
def mock_export_app(monkeypatch):
    """Mock export application commands structure."""
    realms_cmd = DummyCommand("realms", params=["realm"])
    services_cmd = DummyCommand("services", params=["scope"])
    esv_secrets_cmd = DummyCommand("secrets")
    esv_vars_cmd = DummyCommand("variables")
    agent_java_cmd = DummyCommand("java")
    agent_gateway_cmd = DummyCommand("gateway")

    esv_group = SimpleNamespace(
        commands={
            "secrets": esv_secrets_cmd,
            "variables": esv_vars_cmd,
        }
    )

    agent_group = SimpleNamespace(
        commands={
            "java": agent_java_cmd,
            "gateway": agent_gateway_cmd,
        }
    )

    root_commands = {
        "realms": realms_cmd,
        "services": services_cmd,
        "esv": esv_group,
        "agent": agent_group,
    }

    app = DummyTyperApp(root_commands)

    monkeypatch.setattr("typer.main.get_command", lambda _: app)

    return {
        "realms": realms_cmd,
        "services": services_cmd,
        "esv.secrets": esv_secrets_cmd,
        "esv.variables": esv_vars_cmd,
        "agent.java": agent_java_cmd,
        "agent.gateway": agent_gateway_cmd,
    }


def test_no_commands_errors(mock_console, mock_export_app, tmp_path):
    """Test error when no commands are specified."""
    batch_export = create_batch_export_command()

    with pytest.raises(typer.Exit):
        batch_export(commands=None, output_dir=str(tmp_path), all=False)

    assert any("No commands specified" in msg for msg in mock_console["error"])


def test_invalid_command_errors(mock_console, mock_export_app, tmp_path):
    """Test error when invalid commands are specified."""
    batch_export = create_batch_export_command()

    with pytest.raises(typer.Exit):
        batch_export(commands=["nope"], output_dir=str(tmp_path), all=False)

    assert any("Invalid commands" in msg for msg in mock_console["error"])
    assert any("Available commands" in msg for msg in mock_console["info"])


def test_all_expands_commands(mock_console, mock_export_app, tmp_path):
    """Test that 'all=True' expands to all available commands."""
    batch_export = create_batch_export_command()

    batch_export(commands=None, output_dir=str(tmp_path), all=True)

    assert mock_export_app["realms"].called_with is not None
    assert mock_export_app["services"].called_with is not None
    assert mock_export_app["esv.secrets"].called_with is not None
    assert mock_export_app["agent.java"].called_with is not None


def test_scope_and_realm_passed_conditionally(mock_console, mock_export_app, tmp_path):
    """Test that scope and realm arguments are passed only to relevant commands."""
    batch_export = create_batch_export_command()

    batch_export(
        commands=["realms", "services"],
        output_dir=str(tmp_path),
        realm="myrealm",
        scope="global",
    )

    assert mock_export_app["realms"].called_with["realm"] == "myrealm"
    assert mock_export_app["services"].called_with["scope"] == "global"
    assert "realm" not in mock_export_app["services"].called_with


def test_continue_on_error_true(mock_console, mock_export_app, tmp_path):
    """Test that execution continues after error when continue_on_error=True."""
    mock_export_app["esv.secrets"].should_fail = True

    batch_export = create_batch_export_command()
    batch_export(
        commands=["esv.secrets", "realms"],
        output_dir=str(tmp_path),
        continue_on_error=True,
    )

    assert mock_export_app["realms"].called_with is not None
    assert any("Failed to export esv.secrets" in msg for msg in mock_console["error"])
    assert any("Partial success" in msg for msg in mock_console["warning"])


def test_continue_on_error_false_stops(mock_console, mock_export_app, tmp_path):
    """Test that execution stops on error when continue_on_error=False."""
    mock_export_app["esv.secrets"].should_fail = True

    batch_export = create_batch_export_command()

    with pytest.raises(typer.Exit):
        batch_export(
            commands=["esv.secrets", "realms"],
            output_dir=str(tmp_path),
            continue_on_error=False,
        )

    assert any(
        "Stopping batch export due to error" in msg for msg in mock_console["error"]
    )


def test_output_dir_created(mock_console, mock_export_app, tmp_path):
    """Test that the output directory is created if it doesn't exist."""
    out = tmp_path / "batch"

    batch_export = create_batch_export_command()
    batch_export(commands=["realms"], output_dir=str(out))

    assert out.exists()
    assert out.is_dir()


def test_all_fail_raises_exit(mock_console, mock_export_app, tmp_path):
    """Test that Exit is raised if all exports fail."""
    mock_export_app["realms"].should_fail = True

    batch_export = create_batch_export_command()

    with pytest.raises(typer.Exit):
        batch_export(commands=["realms"], output_dir=str(tmp_path))

    assert any("All exports failed" in msg for msg in mock_console["error"])
