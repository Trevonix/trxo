"""
Proxy module to prevent breaking out-of-scope imports.
ConfigStore logic now lives in trxo_lib.config.store.
"""

from trxo_lib.config.store import SERVICE_NAME, ConfigStore

__all__ = ["ConfigStore", "SERVICE_NAME"]
