"""InMemoryQueue — re-exported from agent_sdk.

All backend modules that import ``InMemoryQueue`` from this file continue
to work without changes.  The canonical definition lives in
``agent_sdk.providers.queue.inmemory``.
"""

from agent_sdk.providers.queue.inmemory import InMemoryQueue  # noqa: F401

__all__ = ["InMemoryQueue"]
