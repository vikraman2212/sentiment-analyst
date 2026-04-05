"""Email generation — re-export shim.

The canonical implementation lives in ``agent_sdk.agents.generation.service``.
Import ``GenerationAgent`` directly from there for new code.

``GenerationService`` is kept as a backward-compatible alias so existing
callers compile without change.
"""

from agent_sdk.agents.generation.service import GenerationAgent as GenerationService  # noqa: F401

__all__ = ["GenerationService"]
