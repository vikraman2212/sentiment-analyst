"""No-op audit logger for testing and local development.

Use ``NoOpAuditLogger`` when you want agents to run without an
OpenSearch instance::

    from agent_sdk.audit.noop import NoOpAuditLogger

    audit = NoOpAuditLogger()
    await audit.log(event)   # silently ignored
"""

from __future__ import annotations

import structlog

from agent_sdk.audit.models import LLMAuditEvent

logger = structlog.get_logger(__name__)


class NoOpAuditLogger:
    """``AbstractAuditLogger`` implementation that discards all events.

    Useful in unit tests and local dev environments where OpenSearch is
    not available.  Debug-level log line is emitted so callers can
    confirm the logger is active.
    """

    async def log(self, event: LLMAuditEvent) -> None:
        """Discard the audit event silently.

        Args:
            event: Audit event to discard.
        """
        logger.debug(
            "noop_audit_discarded",
            pipeline=event.pipeline,
            client_id=event.client_id,
            status=event.status,
        )
