"""OllamaProvider — re-exported from agent_sdk.

All backend modules that import ``OllamaProvider`` from this file continue
to work without changes.  The canonical definition lives in
``agent_sdk.providers.llm.ollama``.
"""

from agent_sdk.providers.llm.ollama import OllamaProvider  # noqa: F401

__all__ = ["OllamaProvider"]
