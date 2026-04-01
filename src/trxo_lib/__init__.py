"""
trxo_lib - Core library for PingOne Advanced Identity Cloud Configuration Management.

This package provides the core logic for exporting, importing, and managing
PingOne AIC configurations. It can be used as a standalone library or
through the trxo CLI.
"""

__version__ = "1.0.0"

# Core modules
from trxo_lib.exceptions import (
    TrxoAbort,
    TrxoAuthError,
    TrxoConfigError,
    TrxoError,
    TrxoValidationError,
)

__all__ = [
    "__version__",
    "TrxoError",
    "TrxoAuthError",
    "TrxoConfigError",
    "TrxoValidationError",
    "TrxoAbort",
]
