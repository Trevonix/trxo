"""
Rollback module for import operations.

Re-exports RollbackManager for backward-compatible imports:

    from trxo_lib.state.rollback import RollbackManager
"""

from trxo_lib.state.rollback.manager import RollbackManager  # noqa: F401

__all__ = ["RollbackManager"]
