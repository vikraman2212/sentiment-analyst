"""Audit logger protocol and OpenSearch-backed implementation.

All logging is fire-and-forget — ``log()`` swallows exceptions so
that audit failures never interrupt the primary agent pipeline.

Usage::

    import asyncio
    from agent_sdk.audit.logger import OpenSearchAuditLogger
    from agent_sdk.audit.models import make_audit_event

    audit = OpenSearchAuditLogger(opensearch_url="http://localhost:9200")
    event = make_audit_event(pipeline="generation", ...)
    asyncio.create_task(audit.log(event))
"""

from __future__ import annotations

import dataclasses
from typing import Protocol, runtime_checkable

import structlog

from agent_sdk.audit.models import LLMAuditEvent

logger = structlog.get_logger(__name__)

_LLM_AUDITS_INDEX = "llm-audits"


@runtime_checkable
class AbstractAuditLogger(Protocol):
    """Protocol every audit logger must satisfy.

    Implementations must be fire-and-forget safe — ``log()`` must never
    propagate an exception to callers.
    """

    async def log(self, event: LLMAuditEvent) -> None:
        """Persist or emit a single audit event.

        Args:
            event: Fully populated ``LLMAuditEvent`` instance.
        """
        ...


class OpenSearchAuditLogger:
    """Writes ``LLMAuditEvent`` documents to an OpenSearch index.

    All exceptions from the OpenSearch client are caught and emitted
    as structlog warnings — ``log()`` will never propagate.

    Args:
        opensearch_url: Base URL of the OpenSearch cluster
            (e.g. ``"http://localhost:9200"``).
        index: Target index name. Defaults to ``"llm-audits"``.
    """

    def __init__(
        self,
        opensearch_url: str = "http://localhost:9200",
        index: str = _LLM_AUDITS_INDEX,
    ) -> None:
        self._opensearch_url = opensearch_url
        self._index = index

    async def log(self, event: LLMAuditEvent) -> None:
        """Index a single audit event in OpenSearch.

        Args:
            event: Fully populated ``LLMAuditEvent`` instance.
        """
        try:
            from opensearchpy import AsyncOpenSearch

            client = AsyncOpenSearch(
                hosts=[self._opensearch_url],
                use_ssl=False,
                verify_certs=False,
            )
            async with client:
                await client.index(
                    index=self._index,
                    body=dataclasses.asdict(event),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "llm_audit_failed",
                pipeline=event.pipeline,
                client_id=event.client_id,
                index=self._index,
                error=str(exc),
            )
