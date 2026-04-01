"""
IDM Connectors export command.

This module provides export functionality for PingOne Advanced Identity
Cloud IDM connectors.
Filters /openidm/config?_queryFilter=true to only include items with
_id starting with "provisioner".
"""


from trxo_lib.config.api_headers import get_headers

from trxo_lib.operations.export.base_exporter import BaseExporter

