"""
Agents export commands.

This module provides export functionality for PingOne Advanced Identity
Cloud Identity Gateway, java and web agents.
"""


from trxo_lib.exceptions import TrxoAbort
from trxo_lib.config.api_headers import get_headers
from trxo_lib.constants import DEFAULT_REALM
from trxo_lib.utils.console import console, info, warning

from trxo_lib.operations.export.base_exporter import BaseExporter


def create_agents_callback():
    """Create agents callback function"""

    def agents_callback(ctx=None):
        """Top-level agents command.

        If run without a subcommand, prints a short guide to help the user.
        """
        if getattr(ctx, "invoked_subcommand", None) is None:
            console.print()
            warning("No agents subcommand selected.")
            info("Agents has three subcommands:")
            info("  • gateway")
            info("  • java")
            info("  • web")
            console.print()
            info("Run one of:")
            info("  trxo export agent gateway --help")
            info("  trxo export agent java --help")
            info("  trxo export agent web --help")
            console.print()
            info("Tip: use --help on any command to see options.")
            console.print()
            raise TrxoAbort(code=0)

    return agents_callback
