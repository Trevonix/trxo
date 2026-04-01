"""
Webhooks export command.

Exports AM realm webhooks from /am/json/realms/root/realms/{realm}/realm-config/webhooks?
_queryFilter=true
"""


from trxo_lib.config.api_headers import get_headers
from trxo_lib.constants import DEFAULT_REALM

from trxo_lib.operations.export.base_exporter import BaseExporter

