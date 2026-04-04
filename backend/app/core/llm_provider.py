"""LLM provider abstraction — re-exported from agent_sdk.

All backend modules that import ``LLMResult`` or ``LLMProvider`` from this
file continue to work without changes.  The canonical definitions live in
``agent_sdk.core.llm_provider``.
"""

from agent_sdk.core.llm_provider import LLMProvider, LLMResult  # noqa: F401

__all__ = ["LLMProvider", "LLMResult"]

# ---------------------------------------------------------------------------
# Backward-compatibility note
# ---------------------------------------------------------------------------
# The previous in-module definitions are removed.  Code that imports
# ``from app.core.llm_provider import LLMProvider, LLMResult`` continues
# to work because the names are re-exported here.
