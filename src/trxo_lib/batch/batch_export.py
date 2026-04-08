"""
Batch export command for multiple configurations.

Allows exporting multiple configuration types in a single command.
"""

from pathlib import Path
from typing import List


from trxo_lib.config.constants import DEFAULT_REALM
from trxo.utils.console import error, info, success, warning

from ..export.manager import app as export_app

