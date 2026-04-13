"""
Custom exceptions for the trxo_lib core library.

These exceptions replace typer.Exit() calls in core code, allowing
the CLI layer to catch them and handle appropriately.
"""


class TrxoError(Exception):
    """Base exception for all trxo_lib errors."""


class TrxoAuthError(TrxoError):
    """Authentication-related errors."""


class TrxoConfigError(TrxoError):
    """Configuration-related errors."""


class TrxoValidationError(TrxoError):
    """Data validation errors."""


class TrxoGitError(TrxoError):
    """Git operation and repository errors."""


class TrxoAbort(TrxoError):
    """Signals that the operation should be aborted.

    Replaces typer.Exit() in core code. The CLI layer catches this
    and converts it to typer.Exit(code).
    """

    def __init__(self, message: str = "", code: int = 1):
        self.exit_code = code
        super().__init__(message)
