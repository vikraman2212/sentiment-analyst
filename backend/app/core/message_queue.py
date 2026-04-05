"""Message queue abstraction — re-exported from agent_sdk.

``GenerationMessage`` now carries a ``schema_version`` field (default
``"1.0"``) for forward compatibility with the agent queue contract.
All existing callers that omit the field receive the default automatically.

All backend code that imports from this module continues to work without
changes.  The canonical definitions live in ``agent_sdk.core.message_queue``.
"""

from agent_sdk.core.message_queue import GenerationMessage, MessageQueue  # noqa: F401

__all__ = ["GenerationMessage", "MessageQueue"]
