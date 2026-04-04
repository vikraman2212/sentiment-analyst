"""Provider and queue resolver factories.

Environment-driven factories that inspect ``AgentSDKConfig`` and return
the correct concrete implementation.  Agents use these so they never
instantiate providers or queues directly::

    from agent_sdk.config import AgentSDKConfig
    from agent_sdk.dependencies.factories import get_llm_provider, get_queue

    config = AgentSDKConfig()
    llm = get_llm_provider(config)
    queue = get_queue(config)

Both factories accept an optional ``config`` argument.  When omitted a
fresh ``AgentSDKConfig()`` is constructed from the environment — suitable
for standalone agent processes that own their configuration lifecycle.

Note: These factories create new instances on every call.  If you need
a singleton (e.g. a shared InMemoryQueue between publisher and consumer)
maintain the instance at the agent process level, not here.
"""

from __future__ import annotations

import structlog

from agent_sdk.config import AgentSDKConfig
from agent_sdk.core.llm_provider import LLMProvider
from agent_sdk.core.message_queue import MessageQueue

logger = structlog.get_logger(__name__)


def get_llm_provider(config: AgentSDKConfig | None = None) -> LLMProvider:
    """Resolve and return an LLMProvider based on config.

    Args:
        config: SDK configuration instance. When ``None`` a new
            ``AgentSDKConfig()`` is constructed from the environment.

    Returns:
        Concrete ``LLMProvider`` implementation.

    Raises:
        ValueError: If ``LLM_PROVIDER`` resolves to an unsupported value.
    """
    cfg = config or AgentSDKConfig()

    if cfg.LLM_PROVIDER == "ollama":
        from agent_sdk.providers.llm.ollama import OllamaProvider

        return OllamaProvider(
            base_url=cfg.OLLAMA_BASE_URL,
            timeout_seconds=cfg.OLLAMA_TIMEOUT_SECONDS,
            max_retries=cfg.OLLAMA_MAX_RETRIES,
            backoff_factor=cfg.OLLAMA_BACKOFF_FACTOR,
            capture_prompts=cfg.OTEL_LLM_CAPTURE_PROMPTS,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER: {cfg.LLM_PROVIDER!r}. "
        "Supported values: 'ollama'."
    )


def get_queue(config: AgentSDKConfig | None = None) -> MessageQueue:
    """Resolve and return a MessageQueue based on config.

    Args:
        config: SDK configuration instance. When ``None`` a new
            ``AgentSDKConfig()`` is constructed from the environment.

    Returns:
        Concrete ``MessageQueue`` implementation.

    Raises:
        ValueError: If ``QUEUE_BACKEND`` resolves to an unsupported value.
    """
    cfg = config or AgentSDKConfig()
    backend = cfg.QUEUE_BACKEND.lower()
    logger.info("queue_factory_init", backend=backend)

    if backend == "inmemory":
        from agent_sdk.providers.queue.inmemory import InMemoryQueue

        return InMemoryQueue()

    if backend == "redis":
        from agent_sdk.providers.queue.redis import RedisStreamQueue

        return RedisStreamQueue(redis_url=cfg.REDIS_URL)

    raise ValueError(
        f"Unsupported QUEUE_BACKEND: {cfg.QUEUE_BACKEND!r}. "
        "Supported values: 'inmemory', 'redis'."
    )
