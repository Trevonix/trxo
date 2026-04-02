"""
Proxy module for backwards compatibility.
All business logic for configuration storage has been moved to trxo_lib.config.store.
"""

from trxo_lib.config.store import SERVICE_NAME, ConfigStore

__all__ = ["ConfigStore", "SERVICE_NAME"]
