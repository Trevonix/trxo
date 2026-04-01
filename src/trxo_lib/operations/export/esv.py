"""
ESV (Environment Secrets & Variables) export commands.

This module provides export functionality for PingOne Advanced Identity Cloud Environment
Secrets and Variables.
"""


from trxo_lib.exceptions import TrxoAbort
from trxo_lib.config.api_headers import get_headers
from trxo_lib.utils.console import console, info, warning

from trxo_lib.operations.export.base_exporter import BaseExporter


def create_esv_callback():
    """Create ESV callback function"""

    def esv_callback(ctx=None):
        """Top-level ESV command.

        If run without a subcommand, prints a short guide to help the user.
        """
        if getattr(ctx, "invoked_subcommand", None) is None:
            console.print()
            warning("No ESV subcommand selected.")
            info("ESV has two subcommands:")
            info("  • secrets")
            info("  • variables")
            console.print()
            info("Run one of:")
            info("  trxo export esv secrets --help")
            info("  trxo export esv variables --help")
            console.print()
            info("Tip: use --help on any command to see options.")
            console.print()
            raise TrxoAbort(code=0)

    return esv_callback
