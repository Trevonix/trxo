"""
Authentication settings export command (authn).

Exports realm authentication settings from realm:
  GET /am/json/realms/root/realms/{realm-name}/realm-config/authentication
"""

from trxo_lib.config.api_headers import get_headers
from trxo_lib.constants import DEFAULT_REALM

from trxo_lib.operations.export.base_exporter import BaseExporter
