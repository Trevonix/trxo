import pytest
from unittest.mock import MagicMock
from trxo_lib.exceptions import TrxoError
from trxo.utils.error_presenter import present_error, present_generic_error

class MockTrxoError(TrxoError):
    def __init__(self, message, hint=None):
        super().__init__(message)
        self.hint = hint

def test_present_error_with_hint(mocker):
    # Mock the global console in error_presenter
    mock_console = mocker.patch("trxo.utils.error_presenter._console")
    
    error = MockTrxoError("Connection failed", hint="Check your VPN")
    present_error(error)
    
    # Verify console.print was called (Rich components are complex to assert exactly, 
    # but we can verify it was called multiple times)
    assert mock_console.print.call_count >= 2
    
    # Verify the panel content (approximate check)
    args, kwargs = mock_console.print.call_args_list[1]
    panel = args[0]
    from rich.panel import Panel
    assert isinstance(panel, Panel)
    assert "Connection failed" in str(panel.renderable)
    assert "Check your VPN" in str(panel.renderable)

def test_present_error_without_hint(mocker):
    mock_console = mocker.patch("trxo.utils.error_presenter._console")
    
    error = MockTrxoError("Simple error")
    present_error(error)
    
    assert mock_console.print.call_count >= 2
    args, kwargs = mock_console.print.call_args_list[1]
    panel = args[0]
    assert "Simple error" in str(panel.renderable)
    assert "Hint" not in str(panel.renderable)

def test_present_generic_error_with_command(mocker):
    mock_console = mocker.patch("trxo.utils.error_presenter._console")
    
    exc = Exception("System crash")
    present_generic_error(exc, command_name="export saml")
    
    assert mock_console.print.call_count >= 3
    args, kwargs = mock_console.print.call_args_list[1]
    panel = args[0]
    assert "System crash" in str(panel.renderable)
    assert "Error in export saml" in str(panel.title)

def test_present_generic_error_no_command(mocker):
    mock_console = mocker.patch("trxo.utils.error_presenter._console")
    
    exc = Exception("Generic fail")
    present_generic_error(exc)
    
    assert mock_console.print.call_count >= 3
    args, kwargs = mock_console.print.call_args_list[1]
    panel = args[0]
    assert "Generic fail" in str(panel.renderable)
    assert "Unexpected Error" in str(panel.title)
