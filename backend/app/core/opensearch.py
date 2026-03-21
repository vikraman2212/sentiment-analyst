"""Async OpenSearch client singleton and index bootstrap utilities.

Provides a lazy-initialised ``AsyncOpenSearch`` client and a best-effort
startup helper that creates the ``llm-audits`` index with explicit mappings.
All failures are caught and logged as warnings — nothing here should crash
the application.
"""

from __future__ import annotations

import structlog
from opensearchpy import AsyncOpenSearch

from app.core.config import settings

logger = structlog.get_logger(__name__)

_client: AsyncOpenSearch | None = None

_LLM_AUDITS_INDEX = "llm-audits"

_LLM_AUDITS_MAPPING: dict = {
    "mappings": {
        "properties": {
            "timestamp": {"type": "date"},
            "pipeline": {"type": "keyword"},
            "client_id": {"type": "keyword"},
            "model": {"type": "keyword"},
            "status": {"type": "keyword"},
            "latency_ms": {"type": "float"},
            "prompt_tokens": {"type": "integer"},
            "completion_tokens": {"type": "integer"},
            "prompt": {"type": "text"},
            "response": {"type": "text"},
            "error": {"type": "text"},
        }
    }
}


def get_opensearch_client() -> AsyncOpenSearch:
    """Return the module-level AsyncOpenSearch singleton, creating it if needed.

    Uses ``settings.OPENSEARCH_URL`` with SSL disabled for local development.
    """
    global _client
    if _client is None:
        _client = AsyncOpenSearch(
            hosts=[settings.OPENSEARCH_URL],
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False,
        )
    return _client


async def ensure_llm_audits_index() -> None:
    """Create the ``llm-audits`` index with explicit mappings if it does not exist.

    This is a best-effort startup check. Any exception is caught, logged as a
    warning, and swallowed so that the application continues to start regardless
    of OpenSearch availability.
    """
    try:
        client = get_opensearch_client()
        exists = await client.indices.exists(index=_LLM_AUDITS_INDEX)
        if not exists:
            await client.indices.create(
                index=_LLM_AUDITS_INDEX,
                body=_LLM_AUDITS_MAPPING,
            )
            logger.info("llm_audits_index_created", index=_LLM_AUDITS_INDEX)
        else:
            logger.info("llm_audits_index_ready", index=_LLM_AUDITS_INDEX)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "llm_audits_index_unavailable",
            error=str(exc),
            index=_LLM_AUDITS_INDEX,
        )
