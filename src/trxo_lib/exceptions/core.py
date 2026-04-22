"""
Custom exceptions for the trxo_lib core library.

These exceptions replace typer.Exit() calls in core code, allowing
the CLI layer to catch them and handle appropriately.
"""


class TrxoError(Exception):
    """Base exception for all trxo_lib errors."""

    def __init__(self, message: str = "", hint: str = "", code: int = 1):
        self.message = message
        self.hint = hint
        self.exit_code = code
        super().__init__(self.message)


class TrxoAuthError(TrxoError):
    """Authentication and authorization errors."""


class TrxoConfigError(TrxoError):
    """Configuration, project setup, and environment errors."""


class TrxoValidationError(TrxoError):
    """Data validation errors (bad format, missing fields, schema violations)."""


class TrxoGitError(TrxoError):
    """Git repository, credentials, and version control errors."""


class TrxoIOError(TrxoError):
    """File I/O, JSON parsing, and local filesystem errors."""


class TrxoNetworkError(TrxoError):
    """HTTP, network communication, and API connectivity errors."""


class TrxoAbort(TrxoError):
    """Signals that the operation should be aborted.

    Replaces typer.Exit() in core code. The CLI layer catches this
    and converts it to a clean exit.
    """
